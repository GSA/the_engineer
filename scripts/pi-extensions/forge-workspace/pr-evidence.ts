import { execFileSync } from "node:child_process";
import { join } from "node:path";

import { ghSubcommandPath, programWords, shellCommands, stripHeredocs } from "./shell.ts";

const isGh = (program: string, rest: string[]): string[] | null => {
	if (/(^|\/)gh(-local\.py)?$/.test(program)) return rest;
	if (/(^|\/)python3?$/.test(program) && /gh-local\.py$/.test(rest[0] ?? "")) return rest.slice(1);
	return null;
};

/** The `gh pr create` arguments in a shell command, or null when it creates no PR. */
export function prCreateArgs(command: string): string[] | null {
	for (const { words } of shellCommands(stripHeredocs(command))) {
		const [program = "", ...rest] = programWords(words);
		const args = isGh(program, rest);
		const sub = args ? ghSubcommandPath(args) : [];
		if (args && sub[0] === "pr" && sub[1] === "create") return args;
	}
	return null;
}

export const createsPr = (command: string): boolean => prCreateArgs(command) !== null;

function prBase(args: string[]): string | null {
	for (let i = 0; i < args.length; i++) {
		if (args[i] === "--base" || args[i] === "-B") return args[i + 1] ?? null;
		if (args[i].startsWith("--base=")) return args[i].slice(7);
	}
	return null;
}

const quote = (value: string) => (/^[\w@%+=:,./-]+$/.test(value) ? value : `'${value.replace(/'/g, "'\\''")}'`);

function run(program: string, args: string[], cwd: string): string {
	return execFileSync(program, args, { cwd, encoding: "utf8", timeout: 15000, stdio: ["ignore", "pipe", "ignore"] });
}

/**
 * After `gh pr create`, tell the agent which evidence the PR needs, but only
 * for Kata tasks that came from Jira (`jira.key`) or carry the `evidence`
 * label. Owner-requested agent work is left alone. Fails open.
 */
export function prEvidenceNote(command: string, output: string, cwd: string): string | null {
	const ref = process.env.KATA_REF?.trim();
	const createArgs = ref ? prCreateArgs(command) : null;
	if (!ref || !createArgs) return null;
	try {
		const shown = JSON.parse(run("kata", ["show", ref, "--json"], cwd));
		const ticket = shown?.issue?.metadata?.["jira.key"];
		const labelled = (shown?.labels ?? []).some((item: any) => item?.label === "evidence");
		if (!ticket && !labelled) return null;
		const root = process.env.ENGINEER_RUNTIME_ROOT || cwd;
		const script = join(root, "scripts", "demo-capture.py");
		const base = prBase(createArgs);
		const classifyArgs = [script, "classify", ...(base ? ["--base", `origin/${base}`] : [])];
		const report = JSON.parse(run("python3", classifyArgs, cwd));
		const tool = `python3 ${quote(script)}`;
		const needed: string[] = report?.evidence ?? [];
		if (!needed.length) return null;
		const pr = output.match(/\/pull\/(\d+)/)?.[1] ?? "<PR>";
		const tag = ticket ? ` --ticket ${ticket}` : "";
		const lines = [`PR evidence (${ticket || "evidence label"}): this PR needs ${needed.join(" and ")} before it is handed off.`];
		if (needed.includes("walkthrough")) {
			lines.push(
				`- UI files changed (${report.changes.ui.join(", ")}): serve the change on loopback with synthetic data, then`,
				`  ${tool} capture --walkthrough --base ${report.base} --task ${ref}${tag} --demonstrates "..." --url http://127.0.0.1:PORT/ --step ...`,
			);
		}
		if (needed.includes("test-evidence")) {
			const changed = [...report.changes.api, ...report.changes.backend];
			lines.push(
				`- API/backend files changed (${changed.join(", ")}): record the synthetic data, command and output (before/after for a bug fix):`,
				`  ${tool} evidence --task ${ref}${tag} --demonstrates "..." --data FILE --command '...' --before ${report.base}`,
			);
		}
		lines.push(`- Post each bundle: ${tool} publish <bundle> --pr ${pr}`);
		return lines.join("\n");
	} catch {
		return null;
	}
}
