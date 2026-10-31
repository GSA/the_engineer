import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const RUNTIME_KEY_LOOKUP_COOLDOWN_MS = 5000;
// Forge launches pi-argon as pi-local.py --model gemini-4-argon; the launch
// arguments are the only per-session signal when the env key is missing.
const PI_ARGON_MODEL = "gemini-4-argon";
const FORGE_HOOK_SOURCE = "kenn-forge-agent-activity";
const FORGE_HOOK_TIMEOUT_MS = 1500;
// Pi session_start and session_shutdown reasons in Forge's hook vocabulary.
// A fork ends as "clear": Forge treats "other" as a termination signal.
const SESSION_START_SOURCES: Record<string, string> = { resume: "resume", fork: "fork", new: "clear" };
const SESSION_END_REASONS: Record<string, string> = { new: "clear", resume: "resume", fork: "clear" };
const GEMINI_SUMMARY_MODEL = process.env.KENN_FORGE_PR_SUMMARY_MODEL?.trim() || "gemini-4-argon";
const GEMINI_SUMMARY_TIMEOUT_MS = 15000;
const USAI_DEFAULT_BASE_URL = "https://api.gsa.usai.gov/api/v1";

const FORGE_WORKSPACE_SECTION = [
	"Kenn Forge Workspace Execution & Completion Policy:",
	"- This session is running inside an autonomous Kenn Forge workspace.",
	"- Unless a genuine blocking requirement ambiguity cannot be resolved from the repository or Kata/issue description, do NOT stop after `brainstorming` or `writing-plans` to wait for human approval of a classification, design, written spec, implementation plan, or execution method.",
	"- Keep any working spec or implementation plan in ignored `.local/plans/` (never under `docs/superpowers/`), execute the plan directly with TDD, and remove temporary `.local/plans/` files before delivery.",
	"- Before opening or updating a pull request, run `roborev review --branch --wait` once. If `roborev` reports concrete correctness, security, or contract bugs in your changed code, apply at most one focused fix commit (`roborev fix` or direct fix + test verification) and proceed to delivery; do NOT loop `roborev review --branch --wait` across multiple rounds or add speculative defensive code for hypothetical edge cases.",
	"- When implementation and verification are complete, do NOT stop to ask whether to merge locally to `main`, keep the branch as-is, or discard work.",
	"- Always complete the workspace by pushing the workspace branch (`git push -u origin HEAD`) and creating or updating the GitHub pull request (`gh pr create` / `gh pr edit`).",
	"- Scale PR descriptions proportionally to the size of the change (short 1-sentence + 2-3 bullets for small 1-3 file changes; fuller overview + 4-10 bullets for medium/large multi-module changes; omit raw test transcripts and negative 'what this does not do' disclaimers); `gemini-4-argon` automatically formats the PR summary scaled to the diff when `gh pr create` / `gh pr edit` runs.",
	"- After creating or updating a PR (or working on a GitHub issue or Kata task), register every target with Forge using `mcp__kenn_forge__kenn_forge_add_workspace_target` and `mcp__kenn_forge__kenn_forge_add_workspace_kata_target` (using `mcp__kenn_forge__kenn_forge_list_repos` if needed to look up `platform_repo_id`), then confirm with `mcp__kenn_forge__kenn_forge_list_workspace_targets`.",
].join("\n");

const BRAINSTORMING_OVERRIDE = [
	"",
	"## Kenn Forge Workspace Override (Active)",
	"",
	"You are running inside an autonomous Kenn Forge workspace.",
	"- Unless a genuine blocking requirement ambiguity cannot be resolved from the codebase or Kata/issue specification, `<HARD-GATE>` is satisfied by the workspace launch prompt: do **NOT** stop and wait for human approval of your path classification, in-chat design, or written spec.",
	"- Save any working design/spec to ignored `.local/plans/` (never under `docs/superpowers/specs/` and never commit it to Git).",
	"- Complete the inline spec self-review and immediately proceed to `writing-plans` and TDD implementation in the same turn.",
].join("\n");

const WRITING_PLANS_OVERRIDE = [
	"",
	"## Kenn Forge Workspace Override (Active)",
	"",
	"You are running inside an autonomous Kenn Forge workspace.",
	"- Save any working implementation plan to ignored `.local/plans/` (never under `docs/superpowers/plans/` and never commit it to Git).",
	"- After self-reviewing the plan, do **NOT** stop at `Execution Handoff` to ask the human partner to review the plan or choose between Subagent-driven and Native execution.",
	"- Immediately proceed to implement the plan with TDD in this session (or using `subagent` with `model: \"inherit\"` for independent tasks), remove temporary `.local/plans/` artifacts before delivery, run one `roborev review --branch --wait` pass (with at most one fix pass for concrete bugs in changed code), push the branch, create/update the PR, and register the PR and Kata/issue targets with Forge.",
].join("\n");

const FINISHING_BRANCH_OVERRIDE = [
	"",
	"## Kenn Forge Workspace Override (Active)",
	"",
	"You are running inside a Kenn Forge workspace. Do **NOT** present Step 4's 4-option menu or ask whether to merge locally to `main`.",
	"",
	"Once Step 1 (tests pass) is verified:",
	"1. Run `roborev review --branch --wait` once (and apply at most one focused fix commit if concrete bugs in changed code are reported; do not loop `roborev review --branch --wait` across multiple rounds) and remove any temporary `.local/plans/` files.",
	"2. Automatically execute **Option 2 (Push and Create a Pull Request)**: push the workspace branch (`git push -u origin HEAD`) and create or update the pull request (`gh pr create` / `gh pr edit`) with a summary proportional to the diff size (`gemini-4-argon` will automatically scale the PR body to the change size).",
	"3. Register the pull request and any worked GitHub issue or Kata task with Forge using `mcp__kenn_forge__kenn_forge_add_workspace_target` and `mcp__kenn_forge__kenn_forge_add_workspace_kata_target` (using the `Workspace ID` and `Repository` from the Kenn Forge Workspace Context), then verify with `mcp__kenn_forge__kenn_forge_list_workspace_targets`.",
	"4. Do not remove the Forge workspace worktree; Forge manages workspace worktree lifecycle.",
].join("\n");

function isSubagentProcess(): boolean {
	return Boolean(process.env.PI_SUBAGENT_EXTENSION_BINDINGS?.trim());
}

function ownForgeTargetKey(): string {
	const args = process.argv.slice(2);
	for (let i = 0; i < args.length; i++) {
		const model = args[i] === "--model" ? args[i + 1] : args[i].startsWith("--model=") ? args[i].slice(8) : undefined;
		if (model !== undefined) {
			return model.trim() === PI_ARGON_MODEL ? "pi-argon" : "pi";
		}
	}
	return "pi";
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
	let resolvedRuntimeKey: string | null = null;
	let lastRuntimeKeyLookupMs = 0;
	const pendingPrCommands = new Map<string, string>();

	async function resolveRuntimeSessionKey(cwd: string): Promise<string> {
		const envKey = process.env.KENN_FORGE_RUNTIME_SESSION_KEY?.trim() || "";
		if (envKey) {
			return envKey;
		}
		if (resolvedRuntimeKey) {
			return resolvedRuntimeKey;
		}
		if (Date.now() - lastRuntimeKeyLookupMs < RUNTIME_KEY_LOOKUP_COOLDOWN_MS) {
			return "";
		}
		const sourceText = readOverrideFile(cwd)?.content || sessionStartContext || "";
		const match = sourceText.match(/-\s*Workspace ID:\s*`([^`]+)`/);
		if (!match?.[1]) {
			return "";
		}
		lastRuntimeKeyLookupMs = Date.now();
		const workspaceUrl = `${forgeApiBaseUrl()}/api/v1/workspaces/${encodeURIComponent(match[1])}`;
		const fetchJson = async (suffix: string): Promise<any> => {
			try {
				const response = await fetch(`${workspaceUrl}${suffix}`, {
					signal: AbortSignal.timeout(FORGE_HOOK_TIMEOUT_MS),
				});
				return response.ok ? await response.json() : null;
			} catch {
				return null;
			}
		};
		// The live runtime inventory exists before any hook has reported, so a
		// fresh session resolves here; agent-sessions only lists reported ones.
		const runtime = await fetchJson("/runtime");
		const live = (Array.isArray(runtime?.sessions) ? runtime.sessions : []).filter(
			(item: any) =>
				(item?.kind === "agent" || item?.kind === "acp") &&
				(item?.status === "starting" || item?.status === "running") &&
				typeof item?.key === "string" &&
				item.key.trim(),
		);
		const targetKey = ownForgeTargetKey();
		const liveOwn = live.filter((item: any) => item?.target_key === targetKey);
		// Only trust an unambiguous match so a sibling agent's key is never adopted.
		if (liveOwn.length === 1) {
			resolvedRuntimeKey = liveOwn[0].key.trim();
			return resolvedRuntimeKey;
		}
		if (liveOwn.length === 0) {
			const reported = await fetchJson("/agent-sessions");
			const sessions = (Array.isArray(reported?.sessions) ? reported.sessions : []).filter(
				(item: any) => item?.target_key === targetKey && typeof item?.runtime_session_key === "string",
			);
			const active = sessions.find((item: any) => item?.state !== "done") || sessions[0];
			if (active?.runtime_session_key?.trim()) {
				resolvedRuntimeKey = active.runtime_session_key.trim();
				return resolvedRuntimeKey;
			}
		}
		return "";
	}

	function hookHeaders(runtimeKey: string): Record<string, string> {
		const headers: Record<string, string> = {
			"Content-Type": "application/json",
			"X-Kenn-Forge-Hook-Source": FORGE_HOOK_SOURCE,
		};
		if (runtimeKey) {
			headers["X-Kenn-Forge-Runtime-Session-Key"] = runtimeKey;
		}
		return headers;
	}

	async function postJson(path: string, runtimeKey: string, body: Record<string, unknown>): Promise<any> {
		try {
			const response = await fetch(`${forgeApiBaseUrl()}${path}`, {
				method: "POST",
				headers: hookHeaders(runtimeKey),
				body: JSON.stringify(body),
				signal: AbortSignal.timeout(FORGE_HOOK_TIMEOUT_MS),
			});
			return response.ok ? await response.json() : null;
		} catch {
			return null;
		}
	}

	// Lifecycle reports use Forge's native Pi profile so a saved conversation
	// resumes with `pi --session <id>`. Only the interactive session a user can
	// resume reports, and only once Pi has saved its session file; events
	// before that are held (as kit's Pi agenthook extension does).
	const sessionFile = (ctx: any): string =>
		typeof ctx?.sessionManager?.getSessionFile === "function" ? ctx.sessionManager.getSessionFile() || "" : "";
	const reportable = (ctx: any): boolean => !isSubagentProcess() && ctx?.mode === "tui" && Boolean(sessionFile(ctx));
	const saved = (ctx: any): boolean => existsSync(sessionFile(ctx));
	let heldStart: Record<string, unknown> | null = null;
	const heldPrompts: Record<string, unknown>[] = [];
	let hookQueue: Promise<unknown> = Promise.resolve();
	let agentRunning = false;
	let inputPromptOpen = false;
	// Pi handles SIGTERM/SIGHUP by disposing with reason "quit". Forge reads
	// end reason "other" as a termination signal and resumes the conversation
	// instead of forgetting it as finished.
	let terminatedBySignal = false;
	const markSignal = () => {
		terminatedBySignal = true;
	};
	const TERMINATION_SIGNALS = ["SIGTERM", "SIGHUP"] as const;
	let signalsWatched = false;

	async function sendHook(ctx: any, payload: Record<string, unknown>): Promise<void> {
		const runtimeKey = await resolveRuntimeSessionKey(ctx.cwd);
		if (!runtimeKey) {
			return;
		}
		await postJson("/api/v1/agent-hooks/pi", runtimeKey, {
			session_id: ctx.sessionManager.getSessionId(),
			cwd: ctx.cwd,
			transcript_path: sessionFile(ctx),
			...payload,
		});
	}

	// Hooks post in event order so a late PostToolUse never overwrites Stop.
	function reportHook(ctx: any, payload: Record<string, unknown> | null, hold = false): Promise<unknown> {
		if (!reportable(ctx)) {
			return hookQueue;
		}
		hookQueue = hookQueue.then(async () => {
			if (!saved(ctx)) {
				if (hold && payload) {
					heldPrompts.push(payload);
				}
				return;
			}
			if (heldStart) {
				const start = heldStart;
				heldStart = null;
				await sendHook(ctx, start);
			}
			for (const prompt of heldPrompts.splice(0)) {
				await sendHook(ctx, prompt);
			}
			if (payload) {
				await sendHook(ctx, payload);
			}
		});
		return hookQueue;
	}

	// Workspace context comes from Forge's Claude SessionStart renderer. The
	// request carries no runtime key, so Forge records no activity for it.
	async function ensureSessionStart(ctx: any): Promise<void> {
		if (sessionStartResolved || isSubagentProcess()) {
			return;
		}
		sessionStartResolved = true;
		const data = await postJson("/api/v1/agent-hooks/claude", "", {
			session_id: "forge-workspace-context",
			cwd: ctx.cwd,
			hook_event_name: "SessionStart",
			source: "startup",
		});
		const additional = data?.hook_output?.hookSpecificOutput?.additionalContext;
		if (typeof additional === "string" && additional.trim()) {
			sessionStartContext = additional.trim();
		}
	}

	function isForgeWorkspace(cwd: string): boolean {
		return Boolean(readOverrideFile(cwd) || sessionStartContext);
	}

	pi.on("session_start", async (event: any, ctx: any) => {
		await ensureSessionStart(ctx);
		if (!reportable(ctx)) {
			return;
		}
		const reason = String(event?.reason || "startup");
		// Pi reports startup (or reload) even when it opens a saved session.
		const source =
			SESSION_START_SOURCES[reason] || (saved(ctx) ? "resume" : "startup");
		heldStart = { hook_event_name: "SessionStart", source };
		if (!signalsWatched) {
			signalsWatched = true;
			for (const signal of TERMINATION_SIGNALS) process.on(signal, markSignal);
		}
		await reportHook(ctx, null);
	});

	// Pi has appended the turn's user message by the first model call.
	pi.on("context", async (_event: any, ctx: any) => {
		if (heldStart || heldPrompts.length > 0) {
			void reportHook(ctx, null);
		}
	});

	pi.on("before_agent_start", async (event: any, ctx: any) => {
		await ensureSessionStart(ctx);
		agentRunning = true;
		void reportHook(ctx, { hook_event_name: "UserPromptSubmit" }, true);

		const overrideFile = readOverrideFile(ctx.cwd);
		const contextFiles = event?.systemPromptOptions?.contextFiles;
		if (Array.isArray(contextFiles)) {
			if (overrideFile || sessionStartContext || ctx.cwd.includes("/.local/environment/forge/worktrees/")) {
				const piDir = process.env.PI_CODING_AGENT_DIR?.trim() || "";
				for (let idx = contextFiles.length - 1; idx >= 0; idx -= 1) {
					const itemPath = String(contextFiles[idx]?.path ?? "");
					if (
						itemPath.endsWith("/AGENTS.md") &&
						!itemPath.startsWith(`${ctx.cwd}/`) &&
						(!piDir || !itemPath.startsWith(`${piDir}/`))
					) {
						contextFiles.splice(idx, 1);
					}
				}
			}
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
		void reportHook(ctx, {
			hook_event_name: "PreToolUse",
			tool_name: event?.toolName || "",
		});
	});

	pi.on("tool_execution_end", async (event: any, ctx: any) => {
		const hadPrCommand =
			typeof event?.toolCallId === "string" && pendingPrCommands.delete(event.toolCallId);
		void reportHook(ctx, {
			hook_event_name: "PostToolUse",
			tool_name: event?.toolName || "",
		});
		if (hadPrCommand && !event?.isError && !isSubagentProcess() && isForgeWorkspace(ctx.cwd)) {
			await summarizePrWithGemini(ctx.cwd, extractResultText(event?.result));
		}
	});

	// A dialog during a turn is the agent waiting for the user. Dialogs while
	// Pi is idle (commands, pickers) are not an agent handoff.
	pi.on("ui_prompt_start", async (_event: any, ctx: any) => {
		if (!agentRunning) {
			return;
		}
		inputPromptOpen = true;
		void reportHook(ctx, { hook_event_name: "Notification", notification_type: "elicitation_dialog" });
	});

	pi.on("ui_prompt_end", async (_event: any, ctx: any) => {
		if (!inputPromptOpen) {
			return;
		}
		inputPromptOpen = false;
		if (agentRunning) {
			void reportHook(ctx, { hook_event_name: "PostToolUse" });
		}
	});

	// Settling ends the turn, completed or aborted; either way Pi is idle.
	pi.on("agent_settled", async (_event: any, ctx: any) => {
		agentRunning = false;
		inputPromptOpen = false;
		await reportHook(ctx, { hook_event_name: "Stop" });
	});

	// Quit and reload keep the conversation resumable, so only a replacement
	// session or a termination signal ends it. Pending reports drain before
	// Pi exits.
	pi.on("session_shutdown", async (event: any, ctx: any) => {
		// Signal listeners run in one synchronous dispatch; yield so a
		// signal-triggered shutdown is visible here.
		await Promise.resolve();
		if (signalsWatched) {
			signalsWatched = false;
			for (const signal of TERMINATION_SIGNALS) process.off(signal, markSignal);
		}
		const reason =
			event?.reason === "quit" && terminatedBySignal ? "other" : SESSION_END_REASONS[String(event?.reason || "")];
		await reportHook(ctx, reason ? { hook_event_name: "SessionEnd", reason } : null);
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
		let overrideText: string | null = null;
		if (targetPath.endsWith("brainstorming/SKILL.md")) {
			overrideText = BRAINSTORMING_OVERRIDE;
		} else if (targetPath.endsWith("writing-plans/SKILL.md")) {
			overrideText = WRITING_PLANS_OVERRIDE;
		} else if (targetPath.endsWith("finishing-a-development-branch/SKILL.md")) {
			overrideText = FINISHING_BRANCH_OVERRIDE;
		}
		if (!overrideText) {
			return undefined;
		}
		const content = Array.isArray(event.content) ? [...event.content] : [];
		content.push({
			type: "text",
			text: overrideText,
		});
		return {
			content,
			...(event.structuredContent !== undefined
				? { structuredContent: event.structuredContent }
				: {}),
		};
	});
}
