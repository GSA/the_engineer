import { statSync } from "node:fs";
import { isAbsolute, resolve } from "node:path";

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
export const GIT_VALUE_FLAGS = new Set(["-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix"]);
export const SHELLS = /(^|\/)(ba|z|da)?sh$/;

// A heredoc body is data for the program that reads it, so it is not scanned as
// shell words; a body a shell executes is spliced back in as commands. The scan
// tracks quoting and comments so `<<` inside quoted text or a comment is not
// taken for a heredoc operator, which would hide the commands after it.
export function stripHeredocs(command: string, depth = 0): string {
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

export function resolveDir(cwd: string, target: string): string | null {
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
export function shellCommands(command: string): SimpleCommand[] {
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

export function programWords(words: string[]): string[] {
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
export function ghSubcommandPath(args: string[]): string[] {
	const path: string[] = [];
	for (let i = 0; i < args.length; i++) {
		const arg = args[i];
		if (!arg.startsWith("-")) path.push(arg);
		else if (GH_VALUE_FLAGS.has(arg)) i++;
	}
	return path;
}

