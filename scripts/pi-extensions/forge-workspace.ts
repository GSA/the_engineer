import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const FORGE_HOOK_SOURCE = "kenn-forge-agent-activity";
const FORGE_HOOK_TIMEOUT_MS = 1500;
const GEMINI_SUMMARY_MODEL = process.env.KENN_FORGE_PR_SUMMARY_MODEL?.trim() || "gemini-4-argon";
const GEMINI_SUMMARY_TIMEOUT_MS = 15000;
const USAI_DEFAULT_BASE_URL = "https://api.gsa.usai.gov/api/v1";

const FORGE_WORKSPACE_SECTION = [
	"Kenn Forge Workspace Completion Policy:",
	"- This session is running inside a Kenn Forge workspace.",
	"- When implementation and verification are complete, do NOT stop to ask whether to merge locally to `main`, keep the branch as-is, or discard work.",
	"- Before opening or updating a pull request, run `roborev review --branch --wait` (and `roborev fix` if any findings are reported).",
	"- Always complete the workspace by pushing the workspace branch (`git push -u origin HEAD`) and creating or updating the GitHub pull request (`gh pr create` / `gh pr edit`).",
	"- Scale PR descriptions proportionally to the size of the change (short 1-sentence + 2-3 bullets for small 1-3 file changes; fuller overview + 4-10 bullets for medium/large multi-module changes; omit raw test transcripts and negative 'what this does not do' disclaimers); `gemini-4-argon` automatically formats the PR summary scaled to the diff when `gh pr create` / `gh pr edit` runs.",
	"- After creating or updating a PR (or working on a GitHub issue or Kata task), register every target with Forge using `mcp__kenn_forge__kenn_forge_add_workspace_target` and `mcp__kenn_forge__kenn_forge_add_workspace_kata_target` (using `mcp__kenn_forge__kenn_forge_list_repos` if needed to look up `platform_repo_id`), then confirm with `mcp__kenn_forge__kenn_forge_list_workspace_targets`.",
].join("\n");

const FINISHING_BRANCH_OVERRIDE = [
	"",
	"## Kenn Forge Workspace Override (Active)",
	"",
	"You are running inside a Kenn Forge workspace. Do **NOT** present Step 4's 4-option menu or ask whether to merge locally to `main`.",
	"",
	"Once Step 1 (tests pass) is verified:",
	"1. Run `roborev review --branch --wait` (and `roborev fix` if needed) so the branch has a clean review.",
	"2. Automatically execute **Option 2 (Push and Create a Pull Request)**: push the workspace branch (`git push -u origin HEAD`) and create or update the pull request (`gh pr create` / `gh pr edit`) with a summary proportional to the diff size (`gemini-4-argon` will automatically scale the PR body to the change size).",
	"3. Register the pull request and any worked GitHub issue or Kata task with Forge using `mcp__kenn_forge__kenn_forge_add_workspace_target` and `mcp__kenn_forge__kenn_forge_add_workspace_kata_target` (using the `Workspace ID` and `Repository` from the Kenn Forge Workspace Context), then verify with `mcp__kenn_forge__kenn_forge_list_workspace_targets`.",
	"4. Do not remove the Forge workspace worktree; Forge manages workspace worktree lifecycle.",
].join("\n");

function isSubagentProcess(): boolean {
	return Boolean(process.env.PI_SUBAGENT_EXTENSION_BINDINGS?.trim());
}

function forgeApiBaseUrl(): string {
	return (process.env.KENN_FORGE_API_URL || "http://127.0.0.1:18091").replace(/\/+$/, "");
}

function readOverrideFile(cwd: string): { path: string; content: string } | null {
	const overridePath = join(cwd, "AGENTS.override.md");
	if (!existsSync(overridePath)) {
		return null;
	}
	try {
		const content = readFileSync(overridePath, "utf8").trim();
		return content ? { path: overridePath, content } : null;
	} catch {
		return null;
	}
}

function readUsaiBaseUrl(): string {
	const piDir = process.env.PI_CODING_AGENT_DIR?.trim();
	if (piDir) {
		try {
			const models = JSON.parse(readFileSync(join(piDir, "models.json"), "utf8"));
			const url = models?.providers?.usai?.baseUrl;
			if (typeof url === "string" && url.trim()) {
				return url.trim().replace(/\/+$/, "");
			}
		} catch {
			// Fall back to default USAi endpoint
		}
	}
	return USAI_DEFAULT_BASE_URL;
}

function extractResultText(result: any): string {
	const items = Array.isArray(result?.content) ? result.content : [];
	return items
		.map((item: any) => (typeof item?.text === "string" ? item.text : ""))
		.filter(Boolean)
		.join("\n");
}

function runGitOrGh(cmd: string, args: string[], cwd: string, input?: string): string | null {
	try {
		return execFileSync(cmd, args, {
			cwd,
			input,
			encoding: "utf8",
			stdio: ["pipe", "pipe", "pipe"],
			timeout: 15000,
		}).trim();
	} catch {
		return null;
	}
}

function describeSizeGuidance(shortStat: string): string {
	const filesMatch = shortStat.match(/(\d+)\s+files?\s+changed/);
	const insertionsMatch = shortStat.match(/(\d+)\s+insertions?\(\+\)/);
	const deletionsMatch = shortStat.match(/(\d+)\s+deletions?\(-\)/);
	const files = filesMatch ? Number(filesMatch[1]) : 0;
	const lines =
		(insertionsMatch ? Number(insertionsMatch[1]) : 0) +
		(deletionsMatch ? Number(deletionsMatch[1]) : 0);

	if (files > 0 && files <= 3 && lines <= 80) {
		return "Size tier: SMALL (<=3 files, <=80 lines). Write 1 short sentence followed by 2-3 flat bullet points. Do not use section headings.";
	}
	if (files <= 10 && lines <= 350) {
		return "Size tier: MEDIUM (4-10 files or 81-350 lines). Write a 1-2 sentence overview followed by 4-6 bullet points covering the key behavioral, contract, and module changes. Avoid unnecessary section headings.";
	}
	return "Size tier: LARGE (>10 files or >350 lines). Write a concise 2-3 sentence overview followed by 6-10 structured bullet points (grouped by module or concern if helpful) so all important architectural, contract, and behavioral changes are captured without fluff.";
}

async function summarizePrWithGemini(cwd: string, commandOutput: string): Promise<void> {
	const apiKey = process.env.USAI_API_KEY?.trim();
	if (!apiKey) {
		return;
	}
	const urlMatch = commandOutput.match(/https:\/\/github\.com\/[^\s/]+\/[^\s/]+\/pull\/\d+/);
	const viewArgs = ["pr", "view", "--json", "url,title,body,baseRefName"];
	if (urlMatch) {
		viewArgs.splice(2, 0, urlMatch[0]);
	}
	const prJson = runGitOrGh("gh", viewArgs, cwd);
	if (!prJson) {
		return;
	}
	let pr: { url?: string; title?: string; body?: string; baseRefName?: string };
	try {
		pr = JSON.parse(prJson);
	} catch {
		return;
	}
	if (!pr.url || !pr.title) {
		return;
	}
	const baseRef = pr.baseRefName || "main";
	const shortStat = runGitOrGh("git", ["diff", "--shortstat", `origin/${baseRef}...HEAD`], cwd) || "";
	const diffStat = runGitOrGh("git", ["diff", "--stat", `origin/${baseRef}...HEAD`], cwd) || "";
	const commitLog = runGitOrGh("git", ["log", "--oneline", `origin/${baseRef}...HEAD`], cwd) || "";
	const prompt = [
		"Summarize this GitHub pull request with length and detail strictly proportional to the size of the change.",
		"Rules:",
		`- ${describeSizeGuidance(shortStat)}`,
		"- Focus on what changed and why (contracts, behavior, architecture, and important edge cases).",
		"- Do NOT include raw test command transcripts, environment boilerplate, or negative disclaimers ('what this PR does not do').",
		"- Preserve any Kata or issue reference (for example `Kata: the_engineer#abcd` or `Closes #12`) on a single final line if present.",
		"",
		`PR Title: ${pr.title}`,
		shortStat ? `Short stat: ${shortStat}` : "",
		diffStat ? `\nDiff stat:\n${diffStat}` : "",
		commitLog ? `\nCommits:\n${commitLog}` : "",
		pr.body ? `\nDraft PR body:\n${pr.body}` : "",
	]
		.filter(Boolean)
		.join("\n");

	try {
		const response = await fetch(`${readUsaiBaseUrl()}/chat/completions`, {
			method: "POST",
			headers: {
				Authorization: `Bearer ${apiKey}`,
				"Content-Type": "application/json",
			},
			body: JSON.stringify({
				model: GEMINI_SUMMARY_MODEL,
				messages: [{ role: "user", content: prompt }],
				temperature: 0.2,
			}),
			signal: AbortSignal.timeout(GEMINI_SUMMARY_TIMEOUT_MS),
		});
		if (!response.ok) {
			return;
		}
		const payload: any = await response.json();
		const summary = payload?.choices?.[0]?.message?.content;
		if (typeof summary === "string" && summary.trim()) {
			runGitOrGh("gh", ["pr", "edit", pr.url, "--body-file", "-"], cwd, `${summary.trim()}\n`);
		}
	} catch {
		// Fail open and keep the existing PR description if USAi is unreachable
	}
}

export default function forgeWorkspaceExtension(pi: any): void {
	let sessionStartContext: string | null = null;
	let sessionStartResolved = false;
	const pendingPrCommands = new Map<string, string>();

	async function postForgeHook(
		ctx: any,
		payload: Record<string, unknown>,
		options?: { allowWithoutRuntimeKey?: boolean },
	): Promise<any> {
		if (isSubagentProcess()) {
			return null;
		}
		const runtimeKey = process.env.KENN_FORGE_RUNTIME_SESSION_KEY?.trim() || "";
		if (!runtimeKey && !options?.allowWithoutRuntimeKey) {
			return null;
		}
		const headers: Record<string, string> = {
			"Content-Type": "application/json",
			"X-Kenn-Forge-Hook-Source": FORGE_HOOK_SOURCE,
		};
		if (runtimeKey) {
			headers["X-Kenn-Forge-Runtime-Session-Key"] = runtimeKey;
		}
		const sessionId =
			typeof ctx?.sessionManager?.getSessionId === "function"
				? ctx.sessionManager.getSessionId()
				: "pi-session";
		try {
			const response = await fetch(`${forgeApiBaseUrl()}/api/v1/agent-hooks/claude`, {
				method: "POST",
				headers,
				body: JSON.stringify({
					session_id: sessionId,
					cwd: ctx.cwd,
					...payload,
				}),
				signal: AbortSignal.timeout(FORGE_HOOK_TIMEOUT_MS),
			});
			if (!response.ok) {
				return null;
			}
			return await response.json();
		} catch {
			return null;
		}
	}

	async function ensureSessionStart(ctx: any): Promise<void> {
		if (sessionStartResolved || isSubagentProcess()) {
			return;
		}
		sessionStartResolved = true;
		const data = await postForgeHook(
			ctx,
			{ hook_event_name: "SessionStart", source: "startup" },
			{ allowWithoutRuntimeKey: true },
		);
		const additional = data?.hook_output?.hookSpecificOutput?.additionalContext;
		if (typeof additional === "string" && additional.trim()) {
			sessionStartContext = additional.trim();
		}
	}

	function isForgeWorkspace(cwd: string): boolean {
		return Boolean(readOverrideFile(cwd) || sessionStartContext);
	}

	pi.on("session_start", async (_event: any, ctx: any) => {
		await ensureSessionStart(ctx);
	});

	pi.on("before_agent_start", async (event: any, ctx: any) => {
		await ensureSessionStart(ctx);
		void postForgeHook(ctx, { hook_event_name: "UserPromptSubmit" });

		const overrideFile = readOverrideFile(ctx.cwd);
		const contextFiles = event?.systemPromptOptions?.contextFiles;
		if (Array.isArray(contextFiles)) {
			if (overrideFile) {
				const agentsMdPath = join(ctx.cwd, "AGENTS.md");
				const existingOverrideIdx = contextFiles.findIndex((item: any) => item?.path === overrideFile.path);
				const agentsMdIdx = contextFiles.findIndex((item: any) => item?.path === agentsMdPath);
				if (existingOverrideIdx >= 0) {
					contextFiles[existingOverrideIdx] = overrideFile;
				} else if (agentsMdIdx >= 0) {
					contextFiles[agentsMdIdx] = overrideFile;
				} else {
					contextFiles.push(overrideFile);
				}
			} else if (sessionStartContext) {
				const syntheticPath = join(ctx.cwd, "AGENTS.override.md");
				if (!contextFiles.some((item: any) => item?.path === syntheticPath)) {
					contextFiles.unshift({
						path: syntheticPath,
						content: sessionStartContext,
					});
				}
			}
		}

		if (!isSubagentProcess() && (overrideFile || sessionStartContext)) {
			if (event?.systemPromptOptions?.sections && typeof event.systemPromptOptions.sections === "object") {
				event.systemPromptOptions.sections.forge_workspace = FORGE_WORKSPACE_SECTION;
			}
		}
	});

	pi.on("tool_execution_start", async (event: any, ctx: any) => {
		if (
			event?.toolName === "bash" &&
			typeof event?.toolCallId === "string" &&
			typeof event?.args?.command === "string" &&
			/\bgh\s+pr\s+(?:create|edit)\b/.test(event.args.command)
		) {
			pendingPrCommands.set(event.toolCallId, event.args.command);
		}
		void postForgeHook(ctx, {
			hook_event_name: "PreToolUse",
			tool_name: event?.toolName || "",
		});
	});

	pi.on("tool_execution_end", async (event: any, ctx: any) => {
		const hadPrCommand =
			typeof event?.toolCallId === "string" && pendingPrCommands.delete(event.toolCallId);
		void postForgeHook(ctx, {
			hook_event_name: "PostToolUse",
			tool_name: event?.toolName || "",
		});
		if (hadPrCommand && !event?.isError && !isSubagentProcess() && isForgeWorkspace(ctx.cwd)) {
			await summarizePrWithGemini(ctx.cwd, extractResultText(event?.result));
		}
	});

	pi.on("ui_prompt_start", async (event: any, ctx: any) => {
		void postForgeHook(ctx, {
			hook_event_name: "Notification",
			notification_type: "elicitation_dialog",
			message: event?.title || event?.method || "Agent is waiting for user input",
		});
	});

	pi.on("ui_prompt_end", async (_event: any, ctx: any) => {
		void postForgeHook(ctx, {
			hook_event_name: "PostToolUse",
		});
	});

	pi.on("agent_settled", async (_event: any, ctx: any) => {
		void postForgeHook(ctx, {
			hook_event_name: "Stop",
		});
	});

	pi.on("session_shutdown", async (_event: any, ctx: any) => {
		await postForgeHook(ctx, {
			hook_event_name: "SessionEnd",
		});
	});

	pi.on("tool_result", async (event: any, ctx: any) => {
		if (
			isSubagentProcess() ||
			event?.toolName !== "read" ||
			event?.isError ||
			!isForgeWorkspace(ctx.cwd)
		) {
			return undefined;
		}
		const targetPath = String(event?.input?.path ?? "").replace(/\\/g, "/");
		if (!targetPath.endsWith("finishing-a-development-branch/SKILL.md")) {
			return undefined;
		}
		const content = Array.isArray(event.content) ? [...event.content] : [];
		content.push({
			type: "text",
			text: FINISHING_BRANCH_OVERRIDE,
		});
		return {
			content,
			...(event.structuredContent !== undefined
				? { structuredContent: event.structuredContent }
				: {}),
		};
	});
}
