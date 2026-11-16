// Pull one JSON value out of model output: the whole text, a ```json fence,
// or the first balanced object/array in surrounding prose.
type Json = Record<string, unknown>;

const parse = (text: string): Json | null => {
	try {
		return JSON.parse(text) as Json;
	} catch {
		return null;
	}
};

// End index (exclusive) of the bracketed value starting at `start`, honoring
// string literals and escapes, or -1 when it never closes.
const balancedEnd = (text: string, start: number): number => {
	let depth = 0;
	let inString = false;
	for (let i = start; i < text.length; i += 1) {
		const ch = text[i];
		if (inString) {
			if (ch === "\\") i += 1;
			else if (ch === '"') inString = false;
		} else if (ch === '"') inString = true;
		else if (ch === "{" || ch === "[") depth += 1;
		else if ((ch === "}" || ch === "]") && --depth === 0) return i + 1;
	}
	return -1;
};

export function extractJson(text: string): Json | null {
	const whole = parse(text.trim());
	if (whole) return whole;
	const fenced = text.match(/```json\s*([\s\S]*?)\s*```/);
	const fromFence = fenced ? parse(fenced[1]) : null;
	if (fromFence) return fromFence;
	for (let i = 0; i < text.length; i += 1) {
		if (text[i] !== "{" && text[i] !== "[") continue;
		const end = balancedEnd(text, i);
		const value = end < 0 ? null : parse(text.slice(i, end));
		if (value) return value;
	}
	return null;
}
