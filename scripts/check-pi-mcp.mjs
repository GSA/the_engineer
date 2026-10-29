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
  cwd: root,
  agentDir: join(state, "pi"),
  noContextFiles: true,
  noSkills: true,
  noPromptTemplates: true,
  extensionFactories: [
    createCodemodeExtension(), createToolSearchExtension(), createMcpExtension(),
  ],
});
await resourceLoader.reload();
const { session } = await createAgentSession({
  cwd: root,
  agentDir: join(state, "pi"),
  resourceLoader,
  sessionManager: SessionManager.inMemory(),
});

try {
  await session.bindExtensions({});
  const deadline = Date.now() + 30_000;
  while (
    !session.getToolDefinition("mcp__falcon_context__get") ||
    !session.getToolDefinition("mcp__kata__kata_load_issue_discovery")
  ) {
    assert.ok(Date.now() < deadline, "Falcon and Kata MCP tools did not become callable in Pi");
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  async function call(name, args) {
    const tool = session.getToolDefinition(`mcp__falcon_context__${name}`);
    assert.ok(tool, `${name} tool missing from the Pi session`);
    const result = await tool.execute(`local-check-${name}`, args, AbortSignal.timeout(30_000));
    const complete = result.structuredContent;
    assert.ok(complete && !complete.isError, `${name} returned an MCP error`);
    const text = complete.content.filter((block) => block.type === "text")
      .map((block) => block.text).join("\n");
    const packet = JSON.parse(text);
    assert.ok(packet.audience && packet.notice, `${name} omitted handling qualifications`);
    return packet;
  }
  const status = await call("status", {});
  assert.equal(status.fresh, true, "selected Falcon index is stale");
  const packet = await call("get", {
    locator: "AGENT-CONTEXT/questions-register.md#q44",
    format: "compact",
    max_output_chars: 12_000,
  });
  assert.equal(packet.command, "get");
  console.log(JSON.stringify({
    ok: true,
    fresh: status.fresh,
    tools: session.getCallableToolNames().filter((name) => name.startsWith("mcp__falcon_context__")),
    qualified_read_characters: JSON.stringify(packet).length,
    model_calls: 0,
    corpus_text_logged: false,
  }, null, 2));
} finally {
  await session.extensionRunner.emit({ type: "session_shutdown" });
  session.dispose();
}
