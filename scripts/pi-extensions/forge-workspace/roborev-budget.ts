import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { currentBranch } from "./publication-guard.ts";
import { programWords, SHELLS, shellCommands } from "./shell.ts";

// ---- Bounded roborev review loops ------------------------------------------
// One full-branch review per workspace branch; fix passes cover only the
// original findings; a repeated or widened review escalates to the human.

const ROBOREV_VALUE_FLAGS = new Set([
	"--agent", "--base", "--model", "--panel", "--provider", "--reasoning", "--repo", "--sha",
	"--since", "--spec", "--plan", "--type", "--min-severity", "--server",
]);
const BUDGET_FILE = "forge-roborev-budget.json";
export const REVIEW_LOOP_PROMPT =
	"Review loop self-check: Pi flagged a possible roborev review loop on this branch. Stop and assess whether you are in a review loop and need a human. Do not run further reviews or fix passes. Summarize the open findings (job IDs, severity, location, disposition) and hand off by PR comment, Forge or Kata, then wait for the human.";

type RoborevKind = "branch" | "loop" | "narrow" | "other";

// Classify each roborev invocation in a shell command. A full-branch review
// (--branch, --since or a commit range), `refine` and an unscoped `fix` widen
// the review; `review <sha>`, `--dirty` and `fix <job>` stay narrow.
export function roborevInvocations(command: string, depth = 0): RoborevKind[] {
	const kinds: RoborevKind[] = [];
	for (const { words } of shellCommands(command)) {
		const [program = "", ...rest] = programWords(words);
		if (SHELLS.test(program) && depth < 3) {
			const script = rest[rest.indexOf("-c") + 1];
			if (rest.includes("-c") && script) kinds.push(...roborevInvocations(script, depth + 1));
			continue;
		}
		if (!/(^|\/)roborev$/.test(program)) continue;
		let i = 0;
		while (i < rest.length && rest[i].startsWith("-")) i += ROBOREV_VALUE_FLAGS.has(rest[i]) ? 2 : 1;
		const sub = rest[i];
		const args = rest.slice(i + 1);
		const positional: string[] = [];
		let branch = false;
		for (let j = 0; j < args.length; j++) {
			const arg = args[j];
			if (arg === "--branch" || arg.startsWith("--branch=") || arg === "--since" || arg.startsWith("--since=")) branch = true;
			// A two- or three-dot ref (positional or --sha) names a range.
			if (arg.startsWith("--sha=") && arg.includes("..")) branch = true;
			if (arg.startsWith("-")) {
				if (ROBOREV_VALUE_FLAGS.has(arg)) {
					j++;
					if (arg === "--sha" && args[j]?.includes("..")) branch = true;
				}
			} else {
				positional.push(arg);
				if (arg.includes("..")) branch = true;
			}
		}
		if (sub === "refine") kinds.push("loop");
		else if (sub === "fix") kinds.push(positional.some((arg) => /^\d+$/.test(arg)) ? "narrow" : "loop");
		else if (sub === "review") kinds.push(branch || positional.length > 1 ? "branch" : "narrow");
		else kinds.push("other");
	}
	return kinds;
}

export type ReviewFinding = { severity: string; path: string; problem: string };
// Job ID shown by `roborev show [--job] <id>`, or 0.
export function showJobId(command: string): number {
	for (const { words } of shellCommands(command)) {
		const [program = "", sub = "", ...rest] = programWords(words);
		if (/(^|\/)roborev$/.test(program) && sub === "show") {
			const id = rest.find((arg) => /^\d+$/.test(arg));
			return id ? Number(id) : 0;
		}
	}
	return 0;
}

type ReviewBudget = {
	branchReviews: number;
	branchJob: number;
	fixJobs: number[];
	originalsRecorded: boolean;
	originals: ReviewFinding[];
	escalation: string;
	ownerFindings: ReviewFinding[];
};

export function parseReviewFindings(text: string): ReviewFinding[] {
	return text
		.split(/^###\s+\d+\.\s+/m)
		.slice(1)
		.map((block) => ({
			severity: (block.match(/^\s*(\w+)/)?.[1] ?? "").toLowerCase(),
			path: block.match(/\*\*Location:\*\*\s*`?([^\s`:,]+)/)?.[1] ?? "",
			problem: (block.match(/\*\*Problem:\*\*\s*([\s\S]*?)(?=\n\s*\*\*\w+:\*\*|$)/)?.[1] ?? "").trim().slice(0, 400),
		}));
}

export const isReviewText = (text: string): boolean => /^###\s+\d+\.\s+\w+/m.test(text) || /\*\*Agent assessment/.test(text) || /^##\s+Summary/m.test(text);
export const actionable = (finding: ReviewFinding): boolean => ["critical", "high", "medium"].includes(finding.severity);

function words(text: string): Set<string> {
	return new Set(text.toLowerCase().match(/[a-z0-9_]{4,}/g) ?? []);
}

export function sameFinding(a: ReviewFinding, b: ReviewFinding): boolean {
	if (!a.path || a.path !== b.path) return false;
	const left = words(a.problem);
	const right = words(b.problem);
	let shared = 0;
	for (const word of left) if (right.has(word)) shared++;
	const union = left.size + right.size - shared;
	return union === 0 || shared / union >= 0.4;
}

function emptyBudget(): ReviewBudget {
	return { branchReviews: 0, branchJob: 0, fixJobs: [], originalsRecorded: false, originals: [], escalation: "", ownerFindings: [] };
}

// Budget state lives in the worktree's git directory, keyed by branch, so it
// survives reloads, resumes, new sessions and skill transitions.
export function createBudgetStore() {
	const memory = new Map<string, ReviewBudget>();
	const location = (cwd: string): { file: string; branch: string } => {
		let gitDir = "";
		try {
			gitDir = execFileSync("git", ["-C", cwd, "rev-parse", "--absolute-git-dir"], {
				encoding: "utf8",
				stdio: ["ignore", "pipe", "ignore"],
			}).trim();
		} catch {
			// Not a git checkout: keep the count in memory.
		}
		return { file: gitDir ? join(gitDir, BUDGET_FILE) : "", branch: currentBranch(cwd) || "(detached)" };
	};
	const readAll = (file: string): Record<string, ReviewBudget> => {
		try {
			return JSON.parse(readFileSync(file, "utf8"));
		} catch {
			return {};
		}
	};
	return {
		read(cwd: string): ReviewBudget {
			const { file, branch } = location(cwd);
			const stored = file ? readAll(file)[branch] : memory.get(`${cwd}\0${branch}`);
			return { ...emptyBudget(), ...(stored ?? {}) };
		},
		write(cwd: string, update: (budget: ReviewBudget) => void): ReviewBudget {
			const { file, branch } = location(cwd);
			const all = file ? readAll(file) : {};
			const budget: ReviewBudget = { ...emptyBudget(), ...((file ? all[branch] : memory.get(`${cwd}\0${branch}`)) ?? {}) };
			update(budget);
			if (file) {
				all[branch] = budget;
				writeFileSync(file, JSON.stringify(all, null, 2), { mode: 0o600 });
			} else {
				memory.set(`${cwd}\0${branch}`, budget);
			}
			return budget;
		},
	};
}
