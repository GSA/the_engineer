import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { isAbsolute, resolve } from "node:path";

import { GIT_VALUE_FLAGS, ghSubcommandPath, programWords, resolveDir, shellCommands, stripHeredocs, SHELLS } from "./shell.ts";

const PROTECTED_BRANCHES = new Set(["main", "master"]);

export function currentBranch(cwd: string): string {
	try {
		return execFileSync("git", ["-C", cwd, "symbolic-ref", "--short", "HEAD"], {
			encoding: "utf8",
			stdio: ["ignore", "pipe", "ignore"],
		}).trim();
	} catch {
		return "";
	}
}

// The repository a directory belongs to, so a checkout through a subdirectory
// and a push from its root share predicted branch state.
function gitIdentity(cwd: string): string {
	try {
		return (
			execFileSync("git", ["-C", cwd, "rev-parse", "--absolute-git-dir"], {
				encoding: "utf8",
				stdio: ["ignore", "pipe", "ignore"],
			}).trim() || cwd
		);
	} catch {
		return cwd;
	}
}

function localBranchExists(cwd: string, name: string): boolean {	try {
		execFileSync("git", ["-C", cwd, "rev-parse", "--verify", "--quiet", `refs/heads/${name}`], {
			encoding: "utf8",
			stdio: ["ignore", "pipe", "ignore"],
		});
		return true;
	} catch {
		return false;
	}
}

// The branch a checkout/switch lands on: a name when it is known, "" when HEAD
// does not move (file or path checkout), null when it cannot be determined.
function checkoutTarget(args: string[], cwd: string): string | null {
	let newBranch = "";
	const positional: string[] = [];
	for (let i = 0; i < args.length; i++) {
		const arg = args[i];
		if (arg === "--") {
			return newBranch || "";
		}
		if (arg === "-b" || arg === "-B" || arg === "-c" || arg === "-C" || arg === "--orphan") {
			newBranch = args[++i] ?? "";
			if (!newBranch || /[$*?~]/.test(newBranch)) return null;
		} else if (arg === "--detach" || arg === "-d") {
			return null;
		} else if (!arg.startsWith("-")) {
			positional.push(arg);
		}
	}
	if (newBranch) return newBranch;
	const target = positional[0];
	if (!target) return "";
	if (/[$*?~]/.test(target)) return null;
	if (localBranchExists(cwd, target)) return target;
	if (resolveDir(cwd, target) || existsSync(isAbsolute(target) ? target : resolve(cwd, target))) return "";
	return null;
}

function pushTargetsProtected(args: string[], heads: () => string[]): boolean {
	const positional: string[] = [];
	let repoGiven = false;
	for (let i = 0; i < args.length; i++) {
		const arg = args[i];
		if (arg === "--all" || arg === "--mirror") {
			return true;
		}
		if (arg === "--repo") {
			repoGiven = true;
			i++;
		} else if (arg.startsWith("--repo=")) {
			repoGiven = true;
		} else if (arg === "-o" || arg === "--push-option") {
			i++;
		} else if (!arg.startsWith("-")) {
			positional.push(arg);
		}
	}
	const refspecs = repoGiven ? positional : positional.slice(1);
	const headProtected = () => heads().some((branch) => PROTECTED_BRANCHES.has(branch));
	if (refspecs.length === 0) {
		return headProtected();
	}
	return refspecs.some((spec) => {
		let dst = spec.replace(/^\+/, "");
		dst = dst.includes(":") ? dst.slice(dst.indexOf(":") + 1) : dst;
		dst = dst.replace(/^refs\/heads\//, "");
		return dst === "HEAD" || dst === "@" ? headProtected() : PROTECTED_BRANCHES.has(dst);
	});
}

// Merging a PR or pushing main is human-controlled on every surface: the agent
// may run it only after the human confirms it in the Pi UI.
export function humanOnlyPublication(command: string, cwd: string, depth = 0): string | null {
	// A workspace push is pre-authorized, so an earlier cd or checkout in the
	// same call is followed rather than assumed to land on main. A checkout adds
	// a branch HEAD may hold without removing the current one, because the
	// checkout can fail and a later `;` still runs the push. A directory move is
	// scoped to its own subshell and dropped in a pipeline stage, and a move a
	// preceding `&&` or `||` can skip leaves the earlier directory a candidate
	// too. HEAD counts as protected while any candidate branch is protected, or
	// while the branch cannot be determined at all.
	const dirsByScope = new Map<string, Set<string>>([["0", new Set([cwd])]]);
	const predicted = new Map<string, Set<string>>();
	let branchUncertain = false;
	// The directories a command in this scope can run in: the innermost
	// enclosing scope that moved, since a subshell inherits its parent.
	const dirsFor = (scope: string): Set<string> => {
		const parts = scope.split("/");
		for (let n = parts.length; n > 0; n--) {
			const found = dirsByScope.get(parts.slice(0, n).join("/"));
			if (found) return found;
		}
		return new Set([cwd]);
	};
	for (const { words, scope, piped, conditional } of shellCommands(stripHeredocs(command))) {
		const pushDirs = [...dirsFor(scope)];
		const pushCwd = pushDirs[0] ?? cwd;
		const [program = "", ...rest] = programWords(words);
		if (SHELLS.test(program) && depth < 3) {
			const script = rest[rest.indexOf("-c") + 1];
			if (rest.includes("-c") && script) {
				for (const dir of pushDirs) {
					const nested = humanOnlyPublication(script, dir, depth + 1);
					if (nested) return nested;
				}
			}
			continue;
		}
		if (program === "cd" || program === "pushd" || program === "popd") {
			const target = rest.find((arg) => !arg.startsWith("-"));
			// `cd` home, `cd -`, an expansion, or a missing directory leaves the
			// next push's branch unknowable here.
			const moved = program === "cd" && target && !/[$*?~]/.test(target) ? resolveDir(pushCwd, target) : null;
			if (!moved) {
				branchUncertain = true;
			} else if (!piped) {
				dirsByScope.set(scope, new Set(conditional ? [...pushDirs, moved] : [moved]));
			}
			continue;
		}
		if (/(^|\/)gh(-local\.py)?$/.test(program) || (/(^|\/)python3?$/.test(program) && /gh-local\.py$/.test(rest[0] ?? ""))) {
			const args = /python3?$/.test(program) ? rest.slice(1) : rest;
			const sub = ghSubcommandPath(args);
			if (sub[0] === "pr" && sub[1] === "merge") {
				return "pr_merge";
			}
			if (sub[0] === "api" && args.some((arg) => /\/pulls\/\d+\/merge$/.test(arg))) {
				return "pr_merge";
			}
			continue;
		}
		if (/(^|\/)git$/.test(program)) {
			let i = 0;
			// `-C` moves the working directory and repeats cumulatively, while an
			// explicit `--git-dir` chooses the repository whose HEAD the push
			// moves, whatever `--work-tree` says.
			const gitCwds = new Set(pushDirs);
			let gitDir: string | null = null;
			let gitDirGiven = false;
			while (i < rest.length && rest[i].startsWith("-")) {
				const flag = rest[i];
				const eq = flag.indexOf("=");
				const name = eq > 0 ? flag.slice(0, eq) : flag;
				if (name === "-C" || name === "--git-dir") {
					const value = eq > 0 ? flag.slice(eq + 1) : rest[i + 1];
					const moved = value ? [...gitCwds].map((dir) => resolveDir(dir, value)).filter(Boolean) : [];
					if (name === "-C") {
						gitCwds.clear();
						for (const dir of moved) gitCwds.add(dir as string);
					} else {
						gitDir = (moved[0] as string) ?? null;
						gitDirGiven = true;
					}
					i += eq > 0 ? 1 : 2;
				} else if (eq < 0 && GIT_VALUE_FLAGS.has(name)) {
					i += 2;
				} else {
					i++;
				}
			}
			const repoDirs = gitDirGiven ? (gitDir ? [gitDir] : []) : [...gitCwds];
			const sub = rest[i];
			if (sub === "checkout" || sub === "switch") {
				if (!repoDirs.length) branchUncertain = true;
				for (const repoDir of repoDirs) {
					const target = checkoutTarget(rest.slice(i + 1), repoDir);
					if (target === null) {
						branchUncertain = true;
					} else if (target) {
						const id = gitIdentity(repoDir);
						predicted.set(id, (predicted.get(id) ?? new Set()).add(target));
					}
				}
			} else if (sub === "worktree") {
				branchUncertain = true;
			} else if (
				sub === "push" &&
				pushTargetsProtected(rest.slice(i + 1), () => {
					if (branchUncertain || !repoDirs.length) return ["main"];
					const candidates: string[] = [];
					for (const repoDir of repoDirs) {
						candidates.push(...(predicted.get(gitIdentity(repoDir)) ?? []));
						const actual = currentBranch(repoDir);
						if (actual) candidates.push(actual);
					}
					return candidates.length ? candidates : ["main"];
				})
			) {
				return "push_main";
			}
		}
	}
	return null;
}

// True when the call really runs `gh pr create` or `gh pr edit`, rather than
// mentioning it in text, so the PR description is reformatted only on a write.
export function writesPrDescription(command: string): boolean {
	return shellCommands(stripHeredocs(command)).some(({ words }) => {
		const [program = "", ...rest] = programWords(words);
		const isGh = /(^|\/)gh(-local\.py)?$/.test(program);
		const viaPython = /(^|\/)python3?$/.test(program) && /gh-local\.py$/.test(rest[0] ?? "");
		if (!isGh && !viaPython) return false;
		const sub = ghSubcommandPath(viaPython ? rest.slice(1) : rest);
		return sub[0] === "pr" && (sub[1] === "create" || sub[1] === "edit");
	});
}

