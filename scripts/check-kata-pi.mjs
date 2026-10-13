import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const state = join(root, ".local/environment");
const config = JSON.parse(await readFile(join(state, "environment.json"), "utf8"));
process.env.PI_OFFLINE = "1";
process.env.PI_CODING_AGENT_DIR = join(state, "pi");
delete process.env.USAI_API_KEY;
const {
  createAgentSession, createCodemodeExtension, createMcpExtension,
  createToolSearchExtension, DefaultResourceLoader, SessionManager,
} = await import(pathToFileURL(join(dirname(config.pi_executable), "index.js")).href);
const resourceLoader = new DefaultResourceLoader({
  cwd: root, agentDir: join(state, "pi"),
  noContextFiles: true, noSkills: true, noPromptTemplates: true,
  extensionFactories: [
    createCodemodeExtension(), createToolSearchExtension(), createMcpExtension(),
  ],
});
await resourceLoader.reload();
const { session } = await createAgentSession({
  cwd: root, agentDir: join(state, "pi"), resourceLoader,
  sessionManager: SessionManager.inMemory(),
});

try {
  await session.bindExtensions({});
  async function tool(suffix) {
    const deadline = Date.now() + 30_000;
    while (Date.now() < deadline) {
      const name = session.getCallableToolNames()
        .find((value) => value.startsWith("mcp__kata__") && value.endsWith(suffix));
      if (name) return session.getToolDefinition(name);
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error(`Pi did not discover Kata tool: ${suffix}`);
  }
  async function call(suffix, args) {
    const definition = await tool(suffix);
    const result = await definition.execute(`kata-check-${suffix}`, args, AbortSignal.timeout(30_000));
    assert.ok(result.structuredContent, "Pi lost the complete MCP result");
    return result.structuredContent;
  }
  for (const section of ["issue_discovery", "coordination"]) {
    const result = await call(`kata_load_${section}`, {});
    assert.ok(!result.isError, `Kata ${section} loader failed`);
  }
  const shown = await call("kata_show", { ref: "tvbf" });
  assert.ok(!shown.isError, "Kata issue read failed in Pi");
  assert.equal(shown.structuredContent.project.name, "engi-platform");
  const status = await call("kata_status", { ref: "tvbf" });
  assert.equal(status.structuredContent.actor, "pi");
  const outside = await call("kata_show", { ref: "kata-evaluation-20261012#abcd" });
  assert.equal(outside.isError, true, "Pi could read outside the bound Kata project");
  assert.match(JSON.stringify(outside.content), /scope/i, "Pi did not receive a scope refusal");
  console.log(JSON.stringify({
    ok: true, actor: "pi", project: "engi-platform",
    progressive_catalog: true, cross_project_refused: true, model_calls: 0,
    active_tools: session.getActiveToolNames(),
  }, null, 2));
} finally {
  await session.extensionRunner.emit({ type: "session_shutdown", reason: "quit" });
  session.dispose();
}
