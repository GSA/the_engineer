import { afterEach, beforeEach, expect, test } from "bun:test";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import forgeWorkspaceExtension from "./forge-workspace.ts";

let server;
let cwd;
let hookKeys;
let runtimeSessions;
let reportedSessions;
const saved = { ...process.env };
const savedArgv = [...process.argv];

beforeEach(() => {
    hookKeys = [];
    runtimeSessions = [];
    reportedSessions = [];
    cwd = mkdtempSync(join(tmpdir(), "forge-ext-"));
    writeFileSync(join(cwd, "AGENTS.override.md"), "- Workspace ID: `ws1`\n");
    server = Bun.serve({
        port: 0,
        fetch(req) {
            const path = new URL(req.url).pathname;
            if (path.endsWith("/workspaces/ws1/runtime")) {
                return Response.json({ sessions: runtimeSessions });
            }
            if (path.endsWith("/workspaces/ws1/agent-sessions")) {
                return Response.json({ sessions: reportedSessions });
            }
            if (path.endsWith("/agent-hooks/claude")) {
                hookKeys.push(req.headers.get("X-Kenn-Forge-Runtime-Session-Key"));
                return Response.json({});
            }
            return new Response("not found", { status: 404 });
        },
    });
    delete process.env.KENN_FORGE_RUNTIME_SESSION_KEY;
    delete process.env.PI_SUBAGENT_EXTENSION_BINDINGS;
    process.env.KENN_FORGE_API_URL = `http://127.0.0.1:${server.port}`;
});

afterEach(() => {
    server.stop(true);
    rmSync(cwd, { recursive: true, force: true });
    process.env = { ...saved };
    process.argv = [...savedArgv];
});

async function fireToolStart() {
    const handlers = {};
    forgeWorkspaceExtension({ on: (name, fn) => { handlers[name] = fn; } });
    await handlers.tool_execution_start({ toolName: "read" }, { cwd });
    await Bun.sleep(50);
}

test("fresh session without env key or activity reports resolves the key from the live runtime", async () => {
    runtimeSessions = [
        { key: "sh", target_key: "shell", kind: "shell", status: "running" },
        { key: "pi-live", target_key: "pi", kind: "agent", status: "running" },
    ];
    await fireToolStart();
    expect(hookKeys).toEqual(["pi-live"]);
});

test("ambiguous live pi sessions are not guessed", async () => {
    runtimeSessions = [
        { key: "a", target_key: "pi", kind: "agent", status: "running" },
        { key: "b", target_key: "pi", kind: "agent", status: "running" },
    ];
    await fireToolStart();
    expect(hookKeys).toEqual([]);
});

const siblings = [
    { key: "pi-key", target_key: "pi", kind: "agent", status: "running" },
    { key: "argon-key", target_key: "pi-argon", kind: "agent", status: "running" },
];

test("pi-argon alongside pi resolves its own key", async () => {
    process.argv = [...savedArgv.slice(0, 2), "--model", "gemini-4-argon"];
    runtimeSessions = siblings;
    await fireToolStart();
    expect(hookKeys).toEqual(["argon-key"]);
});

test("pi-argon alone resolves its key and pi alongside argon keeps its own", async () => {
    process.argv = [...savedArgv.slice(0, 2), "--model=gemini-4-argon"];
    runtimeSessions = [siblings[1]];
    await fireToolStart();
    expect(hookKeys).toEqual(["argon-key"]);

    hookKeys = [];
    process.argv = [...savedArgv.slice(0, 2)];
    runtimeSessions = siblings;
    await fireToolStart();
    expect(hookKeys).toEqual(["pi-key"]);
});
