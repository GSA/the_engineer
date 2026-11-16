import { basename, dirname } from "node:path";

// Superpowers' Pi extension (superpowers/.pi/extensions/superpowers.ts) tags the
// bootstrap message it injects with this marker. scripts/test_drift.py fails
// when the pinned submodule's marker differs from this copy.
export const BOOTSTRAP_MARKER = "superpowers:using-superpowers bootstrap for pi";

export function containsBootstrap(message: any): boolean {
	const content = message?.content;
	if (typeof content === "string") return content.includes(BOOTSTRAP_MARKER);
	return (
		Array.isArray(content) &&
		content.some((part: any) => part?.type === "text" && typeof part.text === "string" && part.text.includes(BOOTSTRAP_MARKER))
	);
}

// The skill a `read` loaded, or null when the file is not a SKILL.md. The skill
// identity is the `name:` in its frontmatter; a read that skipped the frontmatter
// (offset) falls back to the skill's own directory name, matched exactly.
export function readSkillName(path: string, text: string): string | null {
	const normalized = path.replace(/\\/g, "/");
	if (basename(normalized) !== "SKILL.md") return null;
	const frontmatter = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
	const named = frontmatter?.[1].match(/^name:\s*["']?([^"'\r\n]+?)["']?\s*$/m);
	return named?.[1] ?? basename(dirname(normalized));
}
