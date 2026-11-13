import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

import { PR_DESCRIPTION_GUIDANCE } from "./prompts.ts";

const GEMINI_SUMMARY_MODEL = process.env.KENN_FORGE_PR_SUMMARY_MODEL?.trim() || "gemini-4-argon";
const GEMINI_SUMMARY_TIMEOUT_MS = 15000;
const USAI_DEFAULT_BASE_URL = "https://api.gsa.usai.gov/api/v1";

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

// Body-free AgentsView "Direct API" session file: token counts only, never prompts or replies.
function recordDirectApiUsage(name: string, provider: string, model: string, usage: unknown, cwd: string): void {
	try {
		const tokens: any = usage;
		const count = (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? value : 0);
		const cacheRead = count(tokens?.prompt_tokens_details?.cached_tokens);
		const input = Math.max(count(tokens?.prompt_tokens) - cacheRead, 0);
		const output = count(tokens?.completion_tokens);
		const now = new Date();
		const timestamp = now.toISOString();
		const sessionId = randomUUID();
		const infoId = randomUUID().slice(0, 8);
		const lines = [
			{ type: "session", version: 3, id: sessionId, timestamp, cwd },
			{ type: "session_info", id: infoId, parentId: null, timestamp, name },
			{
				type: "message",
				id: randomUUID().slice(0, 8),
				parentId: infoId,
				timestamp,
				message: {
					role: "assistant",
					provider,
					model,
					content: [],
					usage: { input, output, cacheRead, cacheWrite: 0, totalTokens: input + output + cacheRead },
					timestamp: now.getTime(),
				},
			},
		];
		const dir = process.env.AGENTSVIEW_DIRECT_API_DIR?.trim() || join(homedir(), ".agentsview", "direct-api");
		mkdirSync(dir, { recursive: true });
		writeFileSync(join(dir, `${sessionId}.jsonl`), lines.map((line) => `${JSON.stringify(line)}\n`).join(""));
	} catch {
		// Usage logging must never affect the PR description
	}
}

export function extractResultText(result: any): string {
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

export async function summarizePrWithGemini(cwd: string, commandOutput: string): Promise<void> {
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
		recordDirectApiUsage("forge PR description", "usai", GEMINI_SUMMARY_MODEL, payload?.usage, cwd);
		const summary = payload?.choices?.[0]?.message?.content;
		if (typeof summary === "string" && summary.trim()) {
			runGitOrGh("gh", ["pr", "edit", pr.url, "--body-file", "-"], cwd, `${summary.trim()}\n`);
		}
	} catch {
		// Fail open and keep the existing PR description if USAi is unreachable
	}
}
