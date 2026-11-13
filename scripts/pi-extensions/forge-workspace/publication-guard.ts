import { SHELLS, ghSubcommandPath, programWords, shellCommands, stripHeredocs } from "./shell.ts";

const isGh = (program: string, rest: string[]): { args: string[] } | null => {
	if (/(^|\/)gh(-local\.py)?$/.test(program)) return { args: rest };
	if (/(^|\/)python3?$/.test(program) && /gh-local\.py$/.test(rest[0] ?? "")) return { args: rest.slice(1) };
	return null;
};

// Merging a PR is human-controlled on every surface: the agent may run it only
// after the human confirms it in the Pi UI. Pushing main is enforced by git
// itself (the `pre-push` hook `local_env.py init-repo` installs), which sees the
// real destination, so no shell-parsing predicts it here.
export function humanOnlyPublication(command: string, depth = 0): "pr_merge" | null {
	for (const { words } of shellCommands(stripHeredocs(command))) {
		const [program = "", ...rest] = programWords(words);
		if (SHELLS.test(program) && depth < 3) {
			const script = rest[rest.indexOf("-c") + 1];
			if (rest.includes("-c") && script && humanOnlyPublication(script, depth + 1)) return "pr_merge";
			continue;
		}
		const gh = isGh(program, rest);
		if (!gh) continue;
		const sub = ghSubcommandPath(gh.args);
		if (sub[0] === "pr" && sub[1] === "merge") return "pr_merge";
		if (sub[0] === "api" && gh.args.some((arg) => /\/pulls\/\d+\/merge$/.test(arg))) return "pr_merge";
	}
	return null;
}

// True when the call really runs `gh pr create` or `gh pr edit`, rather than
// mentioning it in text, so the PR description is reformatted only on a write.
export function writesPrDescription(command: string): boolean {
	return shellCommands(stripHeredocs(command)).some(({ words }) => {
		const [program = "", ...rest] = programWords(words);
		const gh = isGh(program, rest);
		if (!gh) return false;
		const sub = ghSubcommandPath(gh.args);
		return sub[0] === "pr" && (sub[1] === "create" || sub[1] === "edit");
	});
}
