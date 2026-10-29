#!/usr/bin/env node
// Explicit, isolated Pi SDK probe. Never prompts a model or loads user settings.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const args = process.argv.slice(2);
if (args.length !== 6) throw new Error('usage: node verify-context-runtime.mjs SDK_ROOT AGENT_DIR MCP_EXECUTABLE CONFIG REQUEST RECEIPT');
const [sdkRoot, agentDir, executable, config, requestPath, receiptPath] = args.map(p => path.resolve(p));
const sdk = await import(pathToFileURL(path.join(sdkRoot, 'dist/index.js')));
const request = JSON.parse(await fs.readFile(requestPath, 'utf8'));
await fs.mkdir(agentDir, { recursive: true, mode: 0o700 });
assert.equal((await fs.lstat(agentDir)).mode & 0o077, 0, 'agent directory must be private');
const cwd = process.cwd();
let calls = 0;
const loader = new sdk.DefaultResourceLoader({ cwd, agentDir, noExtensions: true, noSkills: true,
  noPromptTemplates: true, noThemes: true,
  // The MCP extension's default loader and log path read the operator agent
  // directory (PI_CODING_AGENT_DIR or ~/.pi/agent) rather than the agentDir of
  // this session, so an explicit empty configuration keeps the probe from
  // launching configured servers or letting one shadow the registered provider.
  extensionFactories: [pi => sdk.createCodemodeExtension({ mode: 'on' })(pi),
    pi => sdk.createMcpExtension({ loadConfig: () => ({ servers: [], autoEnableCodemode: true, errors: [] }),
      logPath: path.join(agentDir, 'mcp.log') })(pi), pi => {
    pi.on('before_provider_request', () => { calls++; throw new Error('model traffic forbidden'); });
    pi.registerMcpServer('component-context', { command: executable, args: ['--config', config], cwd,
      exposure: 'codemode', timeout: 30 });
  }],
});
await loader.reload();
const started = new Date().toISOString();
// Nested tool calls are attributed to the assistant turn that issued them, so the
// probe seeds the turn it stands in for; without it Pi answers "No assistant
// message issued this call" instead of running the discovered MCP tools.
const transcript = [
  { type: 'session', version: sdk.CURRENT_SESSION_VERSION, id: '01000000-0000-7000-8000-000000000000',
    timestamp: started, cwd },
  { type: 'message', id: 'isolated-probe-turn', parentId: null, timestamp: started,
    message: { role: 'assistant', content: [{ type: 'text', text: 'isolated probe turn' }],
      api: 'none', provider: 'none', model: 'none', stopReason: 'toolUse', timestamp: Date.parse(started),
      usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } } },
];
const { session } = await sdk.createAgentSession({ cwd, agentDir, resourceLoader: loader,
  settingsManager: sdk.SettingsManager.inMemory({ defaultTools: ['codemode'], cacheWarming: { enabled: false } }),
  sessionManager: sdk.SessionManager.inMemory(cwd, undefined, transcript) });
try {
  await session.bindExtensions({});
  session.setActiveToolsByName(['codemode']);
  // MCP servers connect in the background; Pi waits for them when a model-issued
  // call reaches them, so this direct probe waits for the registration itself.
  const deadline = Date.now() + 30000;
  const registered = () => session.getAllTools().some(t => t.name.startsWith('mcp__component_context__'));
  while (!registered() && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 100));
  assert.ok(registered(), 'component context MCP tools unregistered');
  const foreign = session.getAllTools().map(t => t.name)
    .filter(name => name.startsWith('mcp__') && !name.startsWith('mcp__component_context__'));
  assert.deepEqual(foreign, [], 'only the registered provider may be reachable');
  // The SDK's wrapped codemode AgentTool receives ExtensionToolContext; nested
  // execution uses Pi's validation/hooks and actual MCP discovery, not RPC guesses.
  const tool = session.agent.state.tools.find(t => t.name === 'codemode');
  assert.ok(tool, 'codemode unavailable');
  const script = `
    const names = ALL_TOOLS.map(t => t.name);
    const collect = names.find(n => n.endsWith('__collect') && n.includes('component'));
    const report = names.find(n => n.endsWith('__report') && n.includes('component'));
    if (!collect || !report) throw new Error('consumer tools undiscovered');
    // MCP tools resolve to their CallToolResult, so the text content carries the packet.
    const read = (result) => {
      const text = result.content.filter(c => c.type === 'text').map(c => c.text).join('\\n');
      if (result.isError) throw new Error('consumer tool failed: ' + text);
      return text;
    };
    const packet = JSON.parse(read(await tools[collect]({request: ${JSON.stringify(request)}})));
    if (!packet.business[0].response || !packet.code[0].response?.resolved || !packet.code[0].response.evidence.length)
      throw new Error('actual qualified evidence missing');
    const rendered = read(await tools[report]({packet}));
    text({packet, rendered, tools: names.filter(n => n.includes('component'))});`;
  const result = await tool.execute('isolated-probe', { code: script }, AbortSignal.timeout(60000));
  assert.ok(!result.isError, 'probe tool failed');
  const output = result.content.filter(c => c.type === 'text').map(c => c.text).join('\n');
  assert.ok(output.includes('engineer.task-context/v1') && output.includes('unasserted'), 'qualified packet/report not returned');
  assert.equal(calls, 0);
  const parent = await fs.lstat(path.dirname(receiptPath));
  assert.ok(parent.isDirectory() && !parent.isSymbolicLink() && !(parent.mode & 0o077), 'receipt parent must be private');
  await fs.writeFile(receiptPath, JSON.stringify({ schema: 'engineer.runtime-verification/v1', cwd,
    model_requests: calls, configured_mcp_servers: foreign.length, sdk_root: sdkRoot, output }, null, 2), { mode: 0o600, flag: 'wx' });
  console.log('Actual Pi discovery, qualified collect/report and zero model requests verified.');
} finally {
  await session.extensionRunner.emit({ type: 'session_shutdown', reason: 'exit' });
  session.dispose();
}
