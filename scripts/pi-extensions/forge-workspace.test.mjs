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
let hooks;
let contextRequests;
const saved = { ...process.env };
const savedArgv = [...process.argv];

beforeEach(() => {
    hookKeys = [];
    runtimeSessions = [];
    reportedSessions = [];
    hooks = [];
    contextRequests = [];
    cwd = mkdtempSync(join(tmpdir(), "forge-ext-"));
    writeFileSync(join(cwd, "AGENTS.override.md"), "- Workspace ID: `ws1`\n");
    server = Bun.serve({
        port: 0,
        async fetch(req) {
            const path = new URL(req.url).pathname;
            if (path.endsWith("/workspaces/ws1/runtime")) {
                return Response.json({ sessions: runtimeSessions });
            }
            if (path.endsWith("/workspaces/ws1/agent-sessions")) {
                return Response.json({ sessions: reportedSessions });
            }
            if (path.endsWith("/agent-hooks/claude")) {
                const body = await req.json();
                contextRequests.push({ key: req.headers.get("X-Kenn-Forge-Runtime-Session-Key"), body });
                return Response.json({ hook_output: { hookSpecificOutput: { additionalContext: "ctx" } } });
            }
            if (path.endsWith("/agent-hooks/pi")) {
                const body = await req.json();
                hookKeys.push(req.headers.get("X-Kenn-Forge-Runtime-Session-Key"));
                hooks.push(body);
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

function makeCtx({ saved = true, mode = "tui", id = "sess-1" } = {}) {
    const file = join(cwd, `${id}.jsonl`);
    if (saved) writeFileSync(file, "{}\n");
    return {
        cwd,
        mode,
        sessionManager: { getSessionId: () => id, getSessionFile: () => file },
    };
}

function load() {
    const handlers = {};
    forgeWorkspaceExtension({ on: (name, fn) => { handlers[name] = fn; } });
    return handlers;
}

const names = () => hooks.map((h) => h.hook_event_name);

async function fireToolStart() {
    await load().tool_execution_start({ toolName: "read" }, makeCtx());
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

test("reports to the pi hook endpoint so Forge resumes with pi --session", async () => {
    process.env.KENN_FORGE_RUNTIME_SESSION_KEY = "rk";
    const h = load();
    const ctx = makeCtx();
    await h.session_start({ reason: "startup" }, ctx);
    await h.agent_settled({ aborted: false }, ctx);
    await h.session_shutdown({ reason: "quit" }, ctx);
    expect(hooks.every((x) => x.session_id === "sess-1" && x.cwd === cwd)).toBe(true);
    expect(hookKeys.every((k) => k === "rk")).toBe(true);
    // Workspace context comes from the claude endpoint without a runtime key,
    // so it records no activity or conversation.
    expect(contextRequests.map((r) => r.key)).toEqual([null]);
});

test("startup opening a saved session reports a resume", async () => {
    process.env.KENN_FORGE_RUNTIME_SESSION_KEY = "rk";
    const h = load();
    await h.session_start({ reason: "startup" }, makeCtx());
    await h.session_shutdown({ reason: "quit" }, makeCtx());
    expect(hooks).toMatchObject([{ hook_event_name: "SessionStart", source: "resume" }]);
});

test("fresh session holds events until Pi saves the session file", async () => {
    process.env.KENN_FORGE_RUNTIME_SESSION_KEY = "rk";
    const h = load();
    const ctx = makeCtx({ saved: false });
    await h.session_start({ reason: "startup" }, ctx);
    await h.before_agent_start({ prompt: "hi" }, ctx);
    await Bun.sleep(30);
    expect(hooks).toEqual([]);
    writeFileSync(ctx.sessionManager.getSessionFile(), "{}\n");
    await h.context({}, ctx);
    await h.tool_execution_start({ toolName: "read" }, ctx);
    await h.tool_execution_end({ toolName: "read" }, ctx);
    await h.agent_settled({ aborted: false }, ctx);
    await h.session_shutdown({ reason: "quit" }, ctx);
    expect(hooks[0]).toMatchObject({ hook_event_name: "SessionStart", source: "startup" });
    expect(names()).toEqual(["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"]);
});

test("quit and reload keep the session resumable; replacement ends it with a reason", async () => {
    process.env.KENN_FORGE_RUNTIME_SESSION_KEY = "rk";
    for (const reason of ["quit", "reload"]) {
        await load().session_shutdown({ reason }, makeCtx());
    }
    expect(names()).toEqual([]);
    const expected = { new: "clear", resume: "resume", fork: "clear" };
    for (const reason of Object.keys(expected)) {
        hooks = [];
        await load().session_shutdown({ reason }, makeCtx());
        expect(hooks).toMatchObject([{ hook_event_name: "SessionEnd", reason: expected[reason] }]);
    }
});

test("session start maps fork and new sources", async () => {
    process.env.KENN_FORGE_RUNTIME_SESSION_KEY = "rk";
    await load().session_start({ reason: "fork" }, makeCtx({ id: "f" }));
    const fresh = makeCtx({ saved: false, id: "n" });
    const h = load();
    await h.session_start({ reason: "new" }, fresh);
    writeFileSync(fresh.sessionManager.getSessionFile(), "{}\n");
    await h.session_shutdown({ reason: "quit" }, fresh);
    expect(hooks.map((x) => x.source)).toEqual(["fork", "clear"]);
});

test("ui prompts during a turn report input; idle prompts are not a handoff", async () => {
    process.env.KENN_FORGE_RUNTIME_SESSION_KEY = "rk";
    const h = load();
    const ctx = makeCtx();
    await h.ui_prompt_start({ kind: "select" }, ctx);
    await h.ui_prompt_end({ kind: "select" }, ctx);
    await h.before_agent_start({ prompt: "x" }, ctx);
    await h.ui_prompt_start({ kind: "confirm" }, ctx);
    await h.ui_prompt_end({ kind: "confirm" }, ctx);
    await h.agent_settled({ aborted: true }, ctx);
    await h.session_shutdown({ reason: "quit" }, ctx);
    expect(names()).toEqual(["UserPromptSubmit", "Notification", "PostToolUse", "Stop"]);
    expect(hooks[1].notification_type).toBe("elicitation_dialog");
});

test("non-interactive pi processes report nothing", async () => {
    process.env.KENN_FORGE_RUNTIME_SESSION_KEY = "rk";
    const h = load();
    const ctx = makeCtx({ mode: "print" });
    await h.session_start({ reason: "startup" }, ctx);
    await h.agent_settled({ aborted: false }, ctx);
    await h.session_shutdown({ reason: "new" }, ctx);
    expect(hooks).toEqual([]);
});

test("a termination signal ends the session as other so Forge resumes it", async () => {
    process.env.KENN_FORGE_RUNTIME_SESSION_KEY = "rk";
    const piSignalHandler = () => {};
    process.prependListener("SIGHUP", piSignalHandler);
    try {
        const before = process.listenerCount("SIGHUP");
        const h = load();
        const ctx = makeCtx();
        await h.session_start({ reason: "startup" }, ctx);
        process.emit("SIGHUP", "SIGHUP");
        await h.session_shutdown({ reason: "quit" }, ctx);
        expect(hooks.at(-1)).toMatchObject({ hook_event_name: "SessionEnd", reason: "other" });
        expect(process.listenerCount("SIGHUP")).toBe(before);
    } finally {
        process.off("SIGHUP", piSignalHandler);
    }
});
