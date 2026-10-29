import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const FORGE_HOOK_SOURCE = "kenn-forge-agent-activity";
const FORGE_HOOK_TIMEOUT_MS = 1500;

const FORGE_WORKSPACE_SECTION = [
	"Kenn Forge Workspace Completion Policy:",
	"- This session is running inside a Kenn Forge workspace.",
	"- When implementation and verification are complete, do NOT stop to ask whether to merge locally to `main`, keep the branch as-is, or discard work.",
	"- Always complete the workspace by pushing the workspace branch (`git push -u origin HEAD`) and creating or updating the GitHub pull request (`gh pr create` / `gh pr edit`).",
	"- After creating or updating a PR (or working on a GitHub issue or Kata task), register every target with Forge using `mcp__kenn_forge__kenn_forge_add_workspace_target` and `mcp__kenn_forge__kenn_forge_add_workspace_kata_target` (using `mcp__kenn_forge__kenn_forge_list_repos` if needed to look up `platform_repo_id`), then confirm with `mcp__kenn_forge__kenn_forge_list_workspace_targets`.",
].join("\n");

const FINISHING_BRANCH_OVERRIDE = [
	"",
	"## Kenn Forge Workspace Override (Active)",
	"",
	"You are running inside a Kenn Forge workspace. Do **NOT** present Step 4's 4-option menu or ask whether to merge locally to `main`.",
	"",
	"Once Step 1 (tests pass) is verified:",
	"1. Automatically execute **Option 2 (Push and Create a Pull Request)**: push the workspace branch (`git push -u origin HEAD`) and create or update the pull request (`gh pr create` / `gh pr edit`).",
	"2. Register the pull request and any worked GitHub issue or Kata task with Forge using `mcp__kenn_forge__kenn_forge_add_workspace_target` and `mcp__kenn_forge__kenn_forge_add_workspace_kata_target` (using the `Workspace ID` and `Repository` from the Kenn Forge Workspace Context), then verify with `mcp__kenn_forge__kenn_forge_list_workspace_targets`.",
	"3. Do not remove the Forge workspace worktree; Forge manages workspace worktree lifecycle.",
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

export default function forgeWorkspaceExtension(pi: any): void {
	let sessionStartContext: string | null = null;
	let sessionStartResolved = false;

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
		void postForgeHook(ctx, {
			hook_event_name: "PreToolUse",
			tool_name: event?.toolName || "",
		});
	});

	pi.on("tool_execution_end", async (event: any, ctx: any) => {
		void postForgeHook(ctx, {
			hook_event_name: "PostToolUse",
			tool_name: event?.toolName || "",
		});
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
