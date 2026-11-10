import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

export const RUNTIME_KEY_LOOKUP_COOLDOWN_MS = 5000;
// Forge launches pi-argon as pi-local.py --model gemini-4-argon; the launch
// arguments are the only per-session signal when the env key is missing.
const PI_ARGON_MODEL = "gemini-4-argon";
export const FORGE_HOOK_SOURCE = "kenn-forge-agent-activity";
export const FORGE_HOOK_TIMEOUT_MS = 1500;
// Pi session_start and session_shutdown reasons in Forge's hook vocabulary.
// A fork ends as "clear": Forge treats "other" as a termination signal.
export const SESSION_START_SOURCES: Record<string, string> = { resume: "resume", fork: "fork", new: "clear" };
export const SESSION_END_REASONS: Record<string, string> = { new: "clear", resume: "resume", fork: "clear" };

export function ownForgeTargetKey(): string {
	const args = process.argv.slice(2);
	for (let i = 0; i < args.length; i++) {
		const model = args[i] === "--model" ? args[i + 1] : args[i].startsWith("--model=") ? args[i].slice(8) : undefined;
		if (model !== undefined) {
			return model.trim() === PI_ARGON_MODEL ? "pi-argon" : "pi";
		}
	}
	return "pi";
}

export function forgeApiBaseUrl(): string {
	return (process.env.KENN_FORGE_API_URL || "http://127.0.0.1:18091").replace(/\/+$/, "");
}

export function readOverrideFile(cwd: string): { path: string; content: string } | null {
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
