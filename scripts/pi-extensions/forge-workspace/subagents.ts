import { join } from "node:path";

const WRITING_SUBAGENTS = new Set(["worker", "delegate"]);

// Writing subagents get managed worktrees so they never share the workspace
// checkout. Explicit worktree/isolation choices, read-only agents, resumes and
// management actions are left as the caller wrote them.
export function isolateWritingSubagents(input: any): void {
	if (!input || typeof input !== "object" || input.action) {
		return;
	}
	const options = input.options && typeof input.options === "object" ? input.options : {};
	if ("worktree" in input || "isolation" in input || "worktree" in options || "isolation" in options) {
		return;
	}
	const tasks = input.workflow === "parallel" && Array.isArray(input.args?.tasks) ? input.args.tasks : [];
	const agents = [input.agent, ...tasks.map((task: any) => task?.agent)];
	if (!agents.some((agent) => WRITING_SUBAGENTS.has(agent))) {
		return;
	}
	input.worktree = true;
	if (!process.env.PI_SUBAGENTS_WORKTREE_DIR?.trim()) {
		const agentDir = process.env.PI_CODING_AGENT_DIR?.trim();
		if (agentDir) {
			process.env.PI_SUBAGENTS_WORKTREE_DIR = join(agentDir, "subagent-worktrees");
		}
	}
}

export function isSubagentProcess(): boolean {
	return Boolean(
		process.env.PI_SUBAGENT_EXTENSION_BINDINGS?.trim() ||
			process.env.PI_SUBAGENT_CHILD?.trim() ||
			process.env.PI_SUBAGENT_RUNNER_PID?.trim(),
	);
}
