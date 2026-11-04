import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, statSync } from "node:fs";
import { isAbsolute, join, resolve } from "node:path";

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
const PR_DESCRIPTION_GUIDANCE = [
	"Choose PR description length and structure from the meaningful changes and reviewer needs, not file or line counts.",
	"A focused fix or mechanical change can be a short paragraph, even across many files.",
	"For independent changes, use bullets or sections only when they help explain behavior, rationale, compatibility, or operational impact.",
	"There is no required paragraph, heading, or bullet count; do not pad the description or repeat the overview.",
	"Preserve actionable limitations, migration requirements, and approval gates; omit boilerplate and raw test transcripts.",
].join(" ");

const FORGE_WORKSPACE_SECTION = [
	"Kenn Forge Workspace Execution & Completion Policy:",
	"- This session is running inside an autonomous Kenn Forge workspace.",
	"- Unless a genuine blocking requirement ambiguity cannot be resolved from the repository or Kata/issue description, do NOT stop after `brainstorming` or `writing-plans` to wait for human approval of a classification, design, written spec, implementation plan, or execution method.",
	"- Keep any working spec or implementation plan in ignored `.local/plans/` (never under `docs/superpowers/`), execute the plan directly with TDD, and remove temporary `.local/plans/` files before delivery.",
	"- Apply the coder contract's bounded roborev delivery policy: reuse evidence for unchanged reviewed code; otherwise run `roborev review --branch --wait --min-severity medium` at most once per delivery, followed by at most one focused, verified fix pass. Do not re-review merely to obtain a passing verdict. Record dispositions with `roborev respond <job>` and close a review only when all actionable findings are fixed or confirmed stale/invalid; leave valid out-of-scope findings open and ask the owner. Hand recurring or unresolved confirmed findings to the owner; pause publication and completion for unresolved task-scoped medium/high/critical defects. Low findings do not block delivery. Reloads, resumes, and skill transitions reuse the same review/fix allowance and recorded evidence.",
	"- When implementation and verification are complete, do NOT stop to ask whether to merge locally to `main`, keep the branch as-is, or discard work.",
	"- Always complete the workspace by pushing the workspace branch (`git push -u origin HEAD`) and creating or updating the GitHub pull request (`gh pr create` / `gh pr edit`). This is pre-authorized: do not ask for permission.",
	"- Make every edit and commit inside this workspace worktree on its branch. If the task needs changes in another repository, create a feature branch there (never commit on its `main` checkout), push it, and open a PR there.",
	"- Never commit to, push to, or ask the human whether to push to `main` or the default branch, and never merge a PR; deliver through branches and pull requests.",
	`- ${PR_DESCRIPTION_GUIDANCE} The automatic PR formatter uses the same guidance after \`gh pr create\` / \`gh pr edit\`.`,
	"- Forge links the workspace branch's PR to this workspace automatically. Register PRs in other repositories or extra stacked PRs with `mcp__kenn_forge__kenn_forge_add_workspace_target`, and worked GitHub issues or Kata tasks with it or `mcp__kenn_forge__kenn_forge_add_workspace_kata_target` (using `mcp__kenn_forge__kenn_forge_list_repos` if needed to look up `platform_repo_id`), then confirm with `mcp__kenn_forge__kenn_forge_list_workspace_targets`.",
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
	"- Immediately proceed to implement the plan with TDD in this session (or using `subagent` with `model: \"inherit\"` for independent tasks), remove temporary `.local/plans/` artifacts before delivery, and apply the bounded roborev delivery policy, reusing earlier review/fix evidence without restarting the allowance. When no unresolved task-scoped medium/high/critical defects remain, push the branch, create/update the PR, and register the PR and Kata/issue targets with Forge.",
].join("\n");

const FINISHING_BRANCH_OVERRIDE = [
	"",
	"## Kenn Forge Workspace Override (Active)",
	"",
	"You are running inside a Kenn Forge workspace. Do **NOT** present Step 4's 4-option menu or ask whether to merge locally to `main`.",
	"",
	"Once Step 1 (tests pass) is verified:",
	"1. Apply the bounded roborev delivery policy, reusing earlier review/fix evidence without restarting the allowance, and remove any temporary `.local/plans/` files. Pause publication for unresolved task-scoped medium/high/critical defects and hand them to the owner rather than repeating review/fix passes.",
	`2. Automatically execute **Option 2 (Push and Create a Pull Request)**: push the workspace branch (\`git push -u origin HEAD\`) and create or update the pull request (\`gh pr create\` / \`gh pr edit\`). ${PR_DESCRIPTION_GUIDANCE}`,
	"3. Forge links the workspace branch's PR automatically. Register PRs in other repositories, extra stacked PRs, and any worked GitHub issue or Kata task with Forge using `mcp__kenn_forge__kenn_forge_add_workspace_target` and `mcp__kenn_forge__kenn_forge_add_workspace_kata_target` (using the `Workspace ID` and `Repository` from the Kenn Forge Workspace Context), then verify with `mcp__kenn_forge__kenn_forge_list_workspace_targets`.",
	"4. Do not remove the Forge workspace worktree; Forge manages workspace worktree lifecycle.",
].join("\n");

function isSubagentProcess(): boolean {
	return Boolean(
		process.env.PI_SUBAGENT_EXTENSION_BINDINGS?.trim() ||
			process.env.PI_SUBAGENT_CHILD?.trim() ||
			process.env.PI_SUBAGENT_RUNNER_PID?.trim(),
	);
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
		"Edit this GitHub pull request description for reviewers. Return only the finished Markdown body.",
		"Rules:",
		`- ${PR_DESCRIPTION_GUIDANCE}`,
		"- Focus on what changed and why (contracts, behavior, architecture, and important edge cases).",
		"- Use the draft and commit messages for substance; diff statistics are context, not a length target. Do not invent changes or verification claims.",
		"- Keep a clear, concise draft's structure when it already fits the change; do not force a paragraph-plus-bullets template.",
		"- Preserve all Kata and issue references and their closing keywords (for example `Kata: the_engineer#abcd` or `Closes #12`).",
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

const PROTECTED_BRANCHES = new Set(["main", "master"]);
// Programs that run another command, with the options that take a separate
// value, so the real program is found rather than one of their arguments. Each
// wrapper differs: `env -i` is valueless while `env -u` takes a name.
const COMMAND_WRAPPERS = new Map<string, { valueFlags: Set<string>; duration?: boolean }>([
	["env", { valueFlags: new Set(["-u", "--unset", "-C", "--chdir", "-S", "--split-string"]) }],
	["sudo", { valueFlags: new Set(["-u", "--user", "-g", "--group", "-p", "--prompt", "-C", "--close-from", "-h", "--host", "-r", "--role", "-t", "--type", "-U", "--other-user", "-D", "--chdir", "-R", "--chroot"]) }],
	["doas", { valueFlags: new Set(["-u", "-C", "-a"]) }],
	["command", { valueFlags: new Set() }],
	["exec", { valueFlags: new Set(["-a"]) }],
	["time", { valueFlags: new Set(["-o", "--output", "-f", "--format"]) }],
	["nohup", { valueFlags: new Set() }],
	["setsid", { valueFlags: new Set() }],
	["unbuffer", { valueFlags: new Set() }],
	["timeout", { valueFlags: new Set(["-k", "--kill-after", "-s", "--signal"]), duration: true }],
	["stdbuf", { valueFlags: new Set(["-i", "--input", "-o", "--output", "-e", "--error"]) }],
	["nice", { valueFlags: new Set(["-n", "--adjustment"]) }],
	["ionice", { valueFlags: new Set(["-n", "--classdata", "-c", "--class", "-p", "--pid"]) }],
	["xargs", { valueFlags: new Set(["-I", "--replace", "-i", "-L", "--max-lines", "-n", "--max-args", "-P", "--max-procs", "-s", "--max-chars", "-E", "-e", "--eof", "-d", "--delimiter", "-a", "--arg-file"]) }],
]);
const DURATION = /^\d+(?:\.\d+)?[smhd]?$/;
// gh flags that take a separate value, so the value is not a subcommand word.
const GH_VALUE_FLAGS = new Set([
	"-R", "--repo", "--hostname", "--jq", "-q", "--template", "-t", "--json",
	"--method", "-X", "--field", "-F", "--raw-field", "-f", "--header", "-H",
	"--input", "--body", "-b", "--body-file", "-B", "--title", "--base",
	"--head", "--search", "--label", "-l", "--limit", "-L", "--state", "-s",
	"--subject", "--match-field", "--cache",
]);
// git global flags whose value is a separate word, so the value is not the
// subcommand.
const GIT_VALUE_FLAGS = new Set(["-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix"]);
const SHELLS = /(^|\/)(ba|z|da)?sh$/;

function currentBranch(cwd: string): string {
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

// A heredoc body is data for the program that reads it, so it is not scanned as
// shell words; a body a shell executes is spliced back in as commands. The scan
// tracks quoting and comments so `<<` inside quoted text or a comment is not
// taken for a heredoc operator, which would hide the commands after it.
function stripHeredocs(command: string, depth = 0): string {
	let out = "";
	let lineStart = 0;
	let quote = "";
	let comment = false;
	let pending: { delimiter: string; quoted: boolean }[] = [];
	let i = 0;
	while (i < command.length) {
		const ch = command[i];
		if (ch === "\n" && !quote && pending.length) {
			const ownerExecutes = runsShellStdin(out.slice(lineStart));
			const bodies: string[] = [];
			i++;
			for (const { delimiter, quoted } of pending) {
				const body: string[] = [];
				while (i < command.length) {
					const end = command.indexOf("\n", i);
					const line = command.slice(i, end === -1 ? command.length : end);
					i = end === -1 ? command.length : end + 1;
					if (line.trim() === delimiter) break;
					body.push(line);
				}
				// A shell runs the body in a child shell, so its directory moves
				// stay there: the body is spliced inside a subshell. An unquoted
				// delimiter expands the body wherever it goes, so the commands in
				// its substitutions run even when the body itself is data.
				if (ownerExecutes && depth < 3) {
					bodies.push(`(\n${stripHeredocs(body.join("\n"), depth + 1)}\n)`);
				} else if (!quoted) {
					bodies.push(...commandSubstitutions(body.join("\n")));
				}
			}
			pending = [];
			comment = false;
			out += bodies.length ? `\n${bodies.join("\n")}\n` : "\n";
			lineStart = out.length;
			continue;
		}
		if (ch === "\n") {
			comment = false;
			out += ch;
			lineStart = out.length;
			i++;
			continue;
		}
		if (comment) {
			out += ch;
			i++;
			continue;
		}
		if (quote) {
			if (ch === "\\" && quote === '"' && i + 1 < command.length) {
				out += ch + command[i + 1];
				i += 2;
				continue;
			}
			if (ch === quote) quote = "";
			out += ch;
			i++;
			continue;
		}
		if (ch === "'" || ch === '"') {
			quote = ch;
			out += ch;
			i++;
			continue;
		}
		if (ch === "\\" && i + 1 < command.length) {
			out += ch + command[i + 1];
			i += 2;
			continue;
		}
		if (ch === "#" && (out.length === lineStart || /[\s;&|(]/.test(out[out.length - 1] ?? " "))) {
			comment = true;
			out += ch;
			i++;
			continue;
		}
		if (ch === "<" && command[i + 1] === "<" && command[i + 2] !== "<") {
			let j = i + 2;
			if (command[j] === "-") j++;
			while (/[ \t]/.test(command[j] ?? "")) j++;
			const wrap = command[j] === "'" || command[j] === '"' ? command[j] : "";
			let escaped = false;
			if (!wrap && command[j] === "\\") {
				escaped = true;
				j++;
			}
			let delimiter = "";
			if (wrap) {
				j++;
				while (j < command.length && command[j] !== wrap) delimiter += command[j++];
				j++;
			} else {
				while (j < command.length && /[A-Za-z0-9_.\-]/.test(command[j] ?? "")) delimiter += command[j++];
			}
			if (delimiter) {
				pending.push({ delimiter, quoted: Boolean(wrap) || escaped });
				i = j;
				continue;
			}
		}
		out += ch;
		i++;
	}
	return out;
}

// The `$(...)` and backtick spans in expanded text, returned as `$(...)` so
// they are read as the subshells the shell really runs them in.
function commandSubstitutions(text: string): string[] {
	const spans: string[] = [];
	for (let i = 0; i < text.length; i++) {
		if (text[i] === "\\") {
			i++;
		} else if (text[i] === "$" && text[i + 1] === "(") {
			let open = 0;
			let j = i;
			for (; j < text.length; j++) {
				if (text[j] === "(") open++;
				else if (text[j] === ")" && --open === 0) break;
			}
			spans.push(text.slice(i, Math.min(j + 1, text.length)));
			i = j;
		} else if (text[i] === "`") {
			const end = text.indexOf("`", i + 1);
			if (end === -1) break;
			spans.push(`$(${text.slice(i + 1, end)})`);
			i = end;
		}
	}
	return spans;
}

// True when the line runs a shell that reads its script from stdin, so the
// heredoc body is executed rather than consumed as data.
function runsShellStdin(line: string): boolean {
	return shellCommands(line).some(({ words }) => {
		const [program = "", ...rest] = programWords(words);
		return SHELLS.test(program) && !rest.includes("-c");
	});
}

function resolveDir(cwd: string, target: string): string | null {
	const path = isAbsolute(target) ? target : resolve(cwd, target);
	try {
		return statSync(path).isDirectory() ? path : null;
	} catch {
		return null;
	}
}

type SimpleCommand = { words: string[]; scope: string; piped: boolean; conditional: boolean };

// Split a shell command into simple commands of words, keeping quoted text as
// data inside one word. Each command records the identity of the shell scope it
// runs in, whether it runs in a pipeline, and whether a preceding `&&` or `||`
// can skip it, because `cd` in a subshell or a pipeline does not move the
// directory the following commands run in, and a skipped `cd` moves nothing.
// Scope identities are unique, so sibling subshells never share state.
function shellCommands(command: string): SimpleCommand[] {
	const commands: SimpleCommand[] = [];
	let words: string[] = [];
	let word = "";
	let inWord = false;
	let quote = "";
	const stack = [0];
	let scopes = 0;
	let inBacktick = false;
	let commandScope = "0";
	let started = false;
	let piped = false;
	let nextPiped = false;
	let conditional = false;
	let nextConditional = false;
	const open = () => {
		scopes++;
		stack.push(scopes);
	};
	const close = () => {
		if (stack.length > 1) stack.pop();
	};
	const note = () => {
		if (!started) {
			commandScope = stack.join("/");
			piped = nextPiped;
			conditional = nextConditional;
			started = true;
		}
	};
	const endWord = () => {
		if (inWord) words.push(word);
		word = "";
		inWord = false;
	};
	const endCommand = () => {
		endWord();
		if (words.length) commands.push({ words, scope: commandScope, piped, conditional });
		words = [];
		started = false;
		piped = false;
		conditional = false;
	};
	for (let i = 0; i < command.length; i++) {
		const ch = command[i];
		if (quote) {
			if (ch === quote) quote = "";
			else if (ch === "\\" && quote === '"' && i + 1 < command.length) word += command[++i];
			else word += ch;
		} else if (ch === "'" || ch === '"') {
			quote = ch;
			inWord = true;
			note();
		} else if (ch === "\\" && i + 1 < command.length) {
			word += command[++i];
			inWord = true;
			note();
		} else if (ch === "|") {
			const or = command[i + 1] === "|";
			endCommand();
			if (!or && commands.length) commands[commands.length - 1].piped = true;
			nextPiped = !or;
			nextConditional = or;
			if (or) i++;
		} else if (ch === "#" && !inWord) {
			// a comment: the rest of the line is not a command
			endCommand();
			nextPiped = false;
			nextConditional = false;
			while (i < command.length && command[i] !== "\n") i++;
		} else if (ch === "(" || (ch === "$" && command[i + 1] === "(")) {
			endCommand();
			nextPiped = false;
			nextConditional = false;
			open();
			if (ch === "$") i++;
		} else if (ch === ")") {
			endCommand();
			nextPiped = false;
			nextConditional = false;
			close();
		} else if (ch === "`") {
			endCommand();
			nextPiped = false;
			nextConditional = false;
			if (inBacktick) close();
			else open();
			inBacktick = !inBacktick;
		} else if (/[;&\n]/.test(ch)) {
			const and = ch === "&" && command[i + 1] === "&";
			endCommand();
			nextPiped = false;
			nextConditional = and;
			if (and) i++;
		} else if (/\s/.test(ch)) {
			endWord();
		} else {
			word += ch;
			inWord = true;
			note();
		}
	}
	endCommand();
	return commands;
}

function programWords(words: string[]): string[] {
	let i = 0;
	while (i < words.length) {
		const word = words[i];
		if (/^[A-Za-z_][A-Za-z0-9_]*=/.test(word) || word === "{") {
			i++;
			continue;
		}
		const name = word.replace(/^.*\//, "");
		const wrapper = COMMAND_WRAPPERS.get(name);
		if (!wrapper) break;
		i++;
		while (i < words.length && words[i].startsWith("-")) {
			const flag = words[i++];
			if (wrapper.valueFlags.has(flag) && i < words.length) i++;
		}
		if (wrapper.duration && i < words.length && DURATION.test(words[i])) i++;
	}
	return words.slice(i);
}

// gh accepts its own flags before and between subcommand words, so the
// subcommand path is the positional words with flag values removed.
function ghSubcommandPath(args: string[]): string[] {
	const path: string[] = [];
	for (let i = 0; i < args.length; i++) {
		const arg = args[i];
		if (!arg.startsWith("-")) path.push(arg);
		else if (GH_VALUE_FLAGS.has(arg)) i++;
	}
	return path;
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
function writesPrDescription(command: string): boolean {
	return shellCommands(stripHeredocs(command)).some(({ words }) => {
		const [program = "", ...rest] = programWords(words);
		const isGh = /(^|\/)gh(-local\.py)?$/.test(program);
		const viaPython = /(^|\/)python3?$/.test(program) && /gh-local\.py$/.test(rest[0] ?? "");
		if (!isGh && !viaPython) return false;
		const sub = ghSubcommandPath(viaPython ? rest.slice(1) : rest);
		return sub[0] === "pr" && (sub[1] === "create" || sub[1] === "edit");
	});
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
				event.systemPromptOptions.sections.forge_workspace = FORGE_WORKSPACE_SECTION;
			}
		}
	});

	pi.on("tool_call", async (event: any, ctx: any) => {
		const command = event?.toolName === "bash" ? event?.input?.command : undefined;
		const action = typeof command === "string" ? humanOnlyPublication(command, ctx.cwd) : null;
		if (!action) {
			return undefined;
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
