#!/usr/bin/env node
// Drives one fresh Pi SDK client process through the falcon-librarian binding in
// AGENT_DIR/mcp.json: status, search, exact get and a failing get. Prints only
// tool names, error flags, character counts and SHA-256 of what Pi received,
// so the output can be compared with the Librarian audit log without bodies.
// With an optional AUDIT_LOG it also requires four NEW records appended by this run
// (label, tool, outcome and returned SHA-256 matching) - the activation/reload check.
// usage: node verify-audit-binding.mjs PI_EXECUTABLE AGENT_DIR QUERY [AUDIT_LOG]
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { compareAudit } from "./audit-compare.mjs";
const auditLines = () => (auditLog && existsSync(auditLog) ? readFileSync(auditLog, "utf8").split("\n").filter(Boolean) : []);
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

if (process.argv.length < 5 || process.argv.length > 7) throw new Error("usage: verify-audit-binding.mjs PI_EXECUTABLE AGENT_DIR QUERY [AUDIT_LOG [LABEL]]");
const auditLog = process.argv[5];
const label = process.argv[6] ?? "pi-forge";
const [piExecutable, agentDir, query] = [resolve(process.argv[2]), resolve(process.argv[3]), process.argv[4]];
process.env.PI_OFFLINE = "1";
process.env.PI_CODING_AGENT_DIR = agentDir;
delete process.env.USAI_API_KEY;

const {
  createAgentSession, createCodemodeExtension, createMcpExtension,
  createToolSearchExtension, DefaultResourceLoader, SessionManager,
} = await import(pathToFileURL(join(dirname(piExecutable), "index.js")).href);
const before = auditLines();
const resourceLoader = new DefaultResourceLoader({
  cwd: agentDir, agentDir, noContextFiles: true, noSkills: true, noPromptTemplates: true,
  extensionFactories: [createCodemodeExtension(), createToolSearchExtension(), createMcpExtension()],
});
await resourceLoader.reload();
const { session } = await createAgentSession({
  cwd: agentDir, agentDir, resourceLoader, sessionManager: SessionManager.inMemory(),
});
try {
  await session.bindExtensions({});
  const deadline = Date.now() + 30_000;
  while (!session.getToolDefinition("mcp__falcon_librarian__status")) {
    assert.ok(Date.now() < deadline, "falcon-librarian tools did not become callable in Pi");
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  async function call(name, args) {
    const result = await session.getToolDefinition(`mcp__falcon_librarian__${name}`)
      .execute(`audit-${name}`, args, AbortSignal.timeout(30_000));
    const complete = result.structuredContent;
    const text = complete.content.filter((block) => block.type === "text").map((b) => b.text).join("\n");
    return { tool: name, error: Boolean(complete.isError), chars: text.length,
      sha256: createHash("sha256").update(text).digest("hex"), text };
  }
  const calls = [await call("status", {}), await call("search", { query })];
  const locator = JSON.parse(calls[1].text).hits?.[0]?.locator;
  assert.ok(locator, "search returned no locator");
  calls.push(await call("get", { locator }));
  calls.push(await call("get", { locator: "documents/does-not-exist.md" }));
  if (auditLog) {
    const added = compareAudit(before, auditLines(), calls, label);
    console.error(`${added} new audit records match client-received payload hashes`);
  }
  console.log(JSON.stringify(calls.map(({ text, ...summary }) => summary), null, 2));
} finally {
  await session.extensionRunner.emit({ type: "session_shutdown", reason: "exit" });
  session.dispose();
}
