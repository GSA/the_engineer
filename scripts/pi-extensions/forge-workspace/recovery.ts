
const RECOVERY_MARK = "Recovery:";

/**
 * One-line recovery advice for the tool failures that recur in agent session
 * history (context/tool-failures.md). Advice only: nothing is retried or run.
 */
export function recoveryHint(toolName: string, input: any, text: string, cwd: string): string | null {
	if (!text || text.includes(RECOVERY_MARK)) {
		return null;
	}
	const command = typeof input?.command === "string" ? input.command : "";
	const kata = /(^|[\s;&|(])kata\s/.test(command) || /^kata[:\s]/m.test(text) || toolName.startsWith("mcp__kata");
	let advice: string | null = null;
	if (/no \.kata\.toml ancestor|outside the MCP startup scope/.test(text)) {
		advice = `run kata from inside the workspace worktree or a bound repository, or pass --project NAME (kata projects list shows names); this shell is in ${cwd}`;
	} else if (/project \S+ is not registered|kata: alias .* is not registered/.test(text)) {
		advice = "the project name or alias is not known to the daemon: kata projects list shows the registered names; use one with --project, or kata init --project NAME in the repository";
	} else if (/daemon_unavailable|daemon unavailable/.test(text) || (kata && /connection refused/.test(text))) {
		advice = "the Kata daemon is not reachable: python3 scripts/tool-health.py shows what is down; systemctl --user status kenn-kopy-kata.service, then restart it if stopped (do not start a second daemon)";
	} else if (kata && /accepts \d+ arg\(s\), received \d+/.test(text)) {
		const sub = command.match(/\bkata\s+(?:--?\S+\s+\S+\s+)*([a-z][\w-]*)/)?.[1] ?? "COMMAND";
		advice = `wrong number of positional arguments: kata ${sub} --help shows the usage; text goes in -m/--body or --body-file, not as a second argument`;
	} else if (/Author identity unknown|empty ident name/.test(text)) {
		advice = "set the identity for this repository only: git config user.name NAME && git config user.email EMAIL, then retry the commit";
	} else if (/hit the output token limit/.test(text)) {
		advice = "the call was cut off before it ran: re-issue it with smaller arguments, writing large files in separate smaller calls";
	} else if (toolName === "edit" && /must be object|Validation failed/.test(text)) {
		advice = "edits must be an array of objects ({oldText, newText}), not a JSON string, and path is required";
	} else if (toolName === "edit" && /Could not find the exact text|No match found|occurrences/.test(text)) {
		advice = "Re-read the file, then copy oldText exactly from it and include enough surrounding lines to make it unique";
	} else if (toolName === "read" && /Offset \d+ is beyond end of file \((\d+) lines total\)/.test(text)) {
		const total = text.match(/\((\d+) lines total\)/)?.[1];
		advice = `the file has ${total} lines: read from line 1, or pick an offset below ${total}`;
	} else if (/ENOENT|No such file or directory|Path does not exist/.test(text) && ["read", "edit", "write", "ls", "find", "grep", "bash"].includes(toolName)) {
		advice = `the path does not exist relative to ${cwd}: run ls there (or git rev-parse --show-toplevel) to confirm the workspace root before retrying; paths are resolved against the current worktree, not the main checkout`;
	}
	return advice ? `${RECOVERY_MARK} ${advice}` : null;
}
