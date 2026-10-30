import { writeSync } from "node:fs";

// No-model probe: report the policy Pi assembled for the first provider request,
// then exit before any request is sent. Used by scripts/verify-pi-policy.py.
export default function policyProbe(pi: any): void {
	let report: Record<string, unknown> = {};
	pi.on("context_with_system", async (event: any) => {
		const sections = event.messages.find((m: any) => m?.role === "system")?.sections ?? {};
		report = {
			sections: Object.keys(sections),
			context_files: [...String(sections.project_context ?? "").matchAll(/<project_instructions path="([^"]+)">/g)]
				.map((m) => m[1]),
			skills: [...String(sections.skills ?? "").matchAll(/<name>([^<]+)<\/name>/g)].map((m) => m[1]),
			superpowers_bootstrap: JSON.stringify(event.messages).includes("superpowers:using-superpowers bootstrap"),
		};
	});
	pi.on("before_provider_request", async () => {
		writeSync(1, `\nPI_POLICY_PROBE ${JSON.stringify(report)}\n`);
		process.exit(0);
	});
}
