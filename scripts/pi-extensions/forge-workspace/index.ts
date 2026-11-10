import { existsSync } from "node:fs";
import { join } from "node:path";

import {
	FORGE_HOOK_SOURCE,
	FORGE_HOOK_TIMEOUT_MS,
	RUNTIME_KEY_LOOKUP_COOLDOWN_MS,
	SESSION_END_REASONS,
	SESSION_START_SOURCES,
	forgeApiBaseUrl,
	ownForgeTargetKey,
	readOverrideFile,
} from "./forge-api.ts";
import { extractResultText, summarizePrWithGemini } from "./pr-summary.ts";
import { BRAINSTORMING_OVERRIDE, FINISHING_BRANCH_OVERRIDE, FORGE_WORKSPACE_SECTION, WRITING_PLANS_OVERRIDE } from "./prompts.ts";
import { humanOnlyPublication, writesPrDescription } from "./publication-guard.ts";
import { recoveryHint } from "./recovery.ts";
import {
	REVIEW_LOOP_PROMPT,
	actionable,
	createBudgetStore,
	isReviewText,
	parseReviewFindings,
	roborevInvocations,
	sameFinding,
	showJobId,
} from "./roborev-budget.ts";
import { isSubagentProcess, isolateWritingSubagents } from "./subagents.ts";

export { humanOnlyPublication } from "./publication-guard.ts";
export { recoveryHint } from "./recovery.ts";
export { parseReviewFindings, roborevInvocations } from "./roborev-budget.ts";
export { isolateWritingSubagents } from "./subagents.ts";

export default function forgeWorkspaceExtension(pi: any): void {
	const budgets = createBudgetStore();
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
		if (isSubagentProcess() && Array.isArray(_event?.messages)) {
			const filtered = _event.messages.filter((msg: any) => {
				const content = msg?.content;
				if (typeof content === "string") {
					return !content.includes("superpowers:using-superpowers bootstrap for pi");
				}
				if (Array.isArray(content)) {
					return !content.some(
						(part: any) =>
							part?.type === "text" &&
							typeof part.text === "string" &&
							part.text.includes("superpowers:using-superpowers bootstrap for pi"),
					);
				}
				return true;
			});
			if (filtered.length !== _event.messages.length) {
				return { messages: filtered };
			}
		}
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
				const escalation = budgets.read(ctx.cwd).escalation;
				event.systemPromptOptions.sections.forge_workspace = escalation
					? `${FORGE_WORKSPACE_SECTION}\n- ${REVIEW_LOOP_PROMPT} (${escalation})`
					: FORGE_WORKSPACE_SECTION;
			}
		}
	});

	async function guardReviewBudget(command: string, ctx: any): Promise<{ block: true; reason: string } | undefined> {
		const kinds = roborevInvocations(command);
		const wide = kinds.filter((kind) => kind === "branch").length;
		const loops = kinds.filter((kind) => kind === "loop").length;
		if (wide + loops === 0) {
			return undefined;
		}
		const budget = budgets.read(ctx.cwd);
		if (loops === 0 && budget.branchReviews + wide <= 1) {
			budgets.write(ctx.cwd, (state) => {
				state.branchReviews += wide;
			});
			return undefined;
		}
		const detail = loops
			? "`roborev refine` and unscoped `roborev fix` loop over the whole branch"
			: "the one full-branch review for this branch is spent";
		if (ctx.hasUI && (await ctx.ui.confirm("Another roborev review pass? Possible review loop; human approval required", command))) {
			budgets.write(ctx.cwd, (state) => {
				state.branchReviews += wide;
				state.escalation = "";
			});
			return undefined;
		}
		budgets.write(ctx.cwd, (state) => {
			state.escalation = state.escalation || "A further full-branch review or review loop was blocked.";
		});
		return {
			block: true,
			reason: `roborev review budget: ${detail}. Stop and assess whether you are in a review loop and need a human. Verify fixes against the original findings only (\`roborev respond <job>\` dispositions plus targeted tests, or \`roborev review <sha>\` of the fix commit), summarize open findings, and hand off by PR comment, Forge or Kata. A human can approve another pass in the Pi UI.`,
		};
	}

	// Record the first review's findings; screen fix-commit reviews against them.
	// Output is processed even when bash reports a nonzero exit, because a
	// completed failing review exits 1.
	function screenReviewResult(command: string, text: string, cwd: string): string | null {
		const kinds = roborevInvocations(command);
		const wide = kinds.includes("branch");
		const narrow = kinds.includes("narrow") && !wide;
		const enqueued = Number(text.match(/Enqueued job (\d+)/)?.[1] ?? 0);
		let budget = budgets.read(cwd);
		if (enqueued && budget.branchReviews >= 1) {
			budget = budgets.write(cwd, (state) => {
				if (wide && !state.branchJob) state.branchJob = enqueued;
				else if (narrow && !state.fixJobs.includes(enqueued)) state.fixJobs.push(enqueued);
			});
		}
		if (!isReviewText(text) || budget.branchReviews < 1) {
			return null;
		}
		const shown = showJobId(command);
		const found = parseReviewFindings(text).filter(actionable);
		const isFixReview = narrow || (shown > 0 && budget.fixJobs.includes(shown));
		if (!budget.originalsRecorded && !isFixReview && (wide || shown > 0)) {
			budgets.write(cwd, (state) => {
				state.originalsRecorded = true;
				state.originals = found;
			});
			return null;
		}
		const fixShown = shown > 0 ? budget.fixJobs.includes(shown) : true;
		if (!budget.originalsRecorded || !isFixReview || !fixShown || found.length === 0) {
			return null;
		}
		const recurring = found.filter((item) => budget.originals.some((original) => sameFinding(item, original)));
		const outside = found.filter((item) => !recurring.includes(item));
		const lines = ["", "## Pi review-loop guard"];
		if (outside.length) {
			lines.push(
				`${outside.length} medium-or-higher finding(s) on this fix commit are outside the original findings (${outside.map((item) => item.path || "unknown location").join(", ")}). Do not action them: record them with \`roborev respond <job>\` and hand them to the owner.`,
			);
		}
		if (recurring.length) {
			lines.push(`${recurring.length} finding(s) are recurring from the original review (${recurring.map((item) => item.path).join(", ")}): the fix did not resolve them.`);
		}
		lines.push(REVIEW_LOOP_PROMPT);
		budgets.write(cwd, (state) => {
			state.ownerFindings.push(...outside);
			state.escalation = recurring.length ? "A finding recurred on a fix commit." : "A fix-commit review raised new findings.";
		});
		return lines.join("\n");
	}

	pi.on("tool_call", async (event: any, ctx: any) => {
		if (event?.toolName === "subagent") {
			if (!isSubagentProcess() && isForgeWorkspace(ctx.cwd)) {
				isolateWritingSubagents(event.input);
			}
			return undefined;
		}
		const command = event?.toolName === "bash" ? event?.input?.command : undefined;
		const action = typeof command === "string" ? humanOnlyPublication(command, ctx.cwd) : null;
		if (!action) {
			return typeof command === "string" ? guardReviewBudget(command, ctx) : undefined;
		}
		const label = action === "pr_merge" ? "Merge a pull request" : "Push to main";
		if (ctx.hasUI && (await ctx.ui.confirm(`${label}? Human approval required`, command))) {
			return undefined;
		}
		return {
			block: true,
			reason: `${action} is human-controlled: the human must merge or push main, or approve it in the Pi UI`,
		};
	});

	pi.on("tool_execution_start", async (event: any, ctx: any) => {
		if (
			event?.toolName === "bash" &&
			typeof event?.toolCallId === "string" &&
			typeof event?.args?.command === "string" &&
			writesPrDescription(event.args.command)
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
		if (event?.toolName === "bash" && typeof event?.input?.command === "string") {
			const note = screenReviewResult(event.input.command, extractResultText(event), ctx.cwd);
			if (note) {
				return { content: [...(Array.isArray(event.content) ? event.content : []), { type: "text", text: note }] };
			}
		}
		if (event?.isError) {
			const hint = recoveryHint(String(event?.toolName ?? ""), event?.input, extractResultText(event), ctx.cwd);
			if (hint) {
				return { content: [...(Array.isArray(event.content) ? event.content : []), { type: "text", text: hint }] };
			}
		}
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
