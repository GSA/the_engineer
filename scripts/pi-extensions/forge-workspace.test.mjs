import { afterEach, beforeEach, expect, test } from "bun:test";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
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
let summaryRequests;
let summaryResponse;
const saved = { ...process.env };
const savedArgv = [...process.argv];

beforeEach(() => {
    hookKeys = [];
    runtimeSessions = [];
    reportedSessions = [];
    hooks = [];
    contextRequests = [];
    summaryRequests = [];
    summaryResponse = { status: 200, text: "" };
    cwd = mkdtempSync(join(tmpdir(), "forge-ext-"));
    writeFileSync(join(cwd, "AGENTS.override.md"), "- Workspace ID: `ws1`\n");
    server = Bun.serve({
        port: 0,
        async fetch(req) {
            const path = new URL(req.url).pathname;
            if (path === "/chat/completions") {
                summaryRequests.push(await req.json());
                return Response.json(
                    { choices: [{ message: { content: summaryResponse.text } }] },
                    { status: summaryResponse.status },
                );
            }
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
    delete process.env.PI_SUBAGENT_CHILD;
    delete process.env.PI_SUBAGENT_RUNNER_PID;
    process.env.KENN_FORGE_API_URL = `http://127.0.0.1:${server.port}`;
});

async function summarizePr({ shortStat, draft, summary, status = 200 }) {
    const url = "https://github.com/example/project/pull/42";
    process.env.USAI_API_KEY = "synthetic-summary-test-key";
    process.env.PI_CODING_AGENT_DIR = cwd;
    process.env.PATH = `${cwd}:${process.env.PATH}`;
    process.env.TEST_PR = JSON.stringify({ url, title: "Update widget behavior", body: draft, baseRefName: "main" });
    process.env.TEST_SHORT_STAT = shortStat;
    process.env.TEST_EDIT_PATH = join(cwd, "edited-body");
    writeFileSync(join(cwd, "models.json"), JSON.stringify({
        providers: { usai: { baseUrl: `http://127.0.0.1:${server.port}` } },
    }));
    writeFileSync(join(cwd, "gh"), `#!${process.execPath}
import { readFileSync, writeFileSync } from "node:fs";
if (process.argv[3] === "view") console.log(process.env.TEST_PR);
else if (process.argv[3] === "edit") writeFileSync(process.env.TEST_EDIT_PATH, readFileSync(0));
else process.exit(1);
`, { mode: 0o700 });
    writeFileSync(join(cwd, "git"), `#!${process.execPath}
if (process.argv.includes("--shortstat")) console.log(process.env.TEST_SHORT_STAT);
else if (process.argv.includes("--stat")) console.log(" widgets.ts | 2 +-");
else if (process.argv.includes("log")) console.log("abc123 Update widget behavior");
else process.exit(1);
`, { mode: 0o700 });
    summaryResponse = { status, text: summary };
    const h = load();
    const ctx = makeCtx({ mode: "print" });
    await h.tool_execution_start({
        toolName: "bash", toolCallId: "pr-write", args: { command: "gh pr create --body-file draft.md" },
    }, ctx);
    await h.tool_execution_end({
        toolName: "bash", toolCallId: "pr-write", result: { content: [{ text: url }] },
    }, ctx);
    return existsSync(process.env.TEST_EDIT_PATH) ? readFileSync(process.env.TEST_EDIT_PATH, "utf8") : null;
}

for (const scenario of [
    {
        name: "tiny fix",
        shortStat: "1 file changed, 1 insertion(+), 1 deletion(-)",
        draft: "Fix the widget label typo.\n\nKata: example#abcd",
        summary: "Fix the widget label typo.\n\nKata: example#abcd",
    },
    {
        name: "large mechanical change",
        shortStat: "40 files changed, 800 insertions(+), 800 deletions(-)",
        draft: "Rename the widget import across callers; behavior is unchanged.\n\nCloses #12",
        summary: "Rename the widget import across callers; behavior is unchanged.\n\nCloses #12",
    },
    {
        name: "multi-concern change",
        shortStat: "6 files changed, 180 insertions(+), 40 deletions(-)",
        draft: "Add widget export and change its storage format. Existing stores require migration.\n\nKata: example#abcd",
        summary: "Add widget export.\n\n## Compatibility\nExisting stores require migration.\n\nKata: example#abcd",
    },
]) {
    test(`PR formatter allows content-led structure for a ${scenario.name}`, async () => {
        expect(await summarizePr(scenario)).toBe(`${scenario.summary}\n`);
        expect(summaryRequests).toHaveLength(1);
        const prompt = summaryRequests[0].messages[0].content;
        expect(prompt).toContain(scenario.draft);
        expect(prompt).toContain(scenario.shortStat);
        expect(prompt).not.toMatch(/Size tier:|followed by|(?:\d+-\d+|\d+)\s+(?:flat |structured )?bullet points/i);
        const event = { systemPromptOptions: { sections: {} } };
        await load().before_agent_start(event, makeCtx({ mode: "print" }));
        expect(event.systemPromptOptions.sections.forge_workspace).not.toMatch(/\d+-\d+ bullets/);
    });
}

test("PR formatter leaves the existing description alone when the model route fails", async () => {
    expect(await summarizePr({
        shortStat: "1 file changed, 1 insertion(+)",
        draft: "Keep this description.",
        summary: "",
        status: 503,
    })).toBeNull();
    expect(summaryRequests).toHaveLength(1);
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

test("loaded workspace policy keeps the review allowance across resume and skill transitions", async () => {
    const h = load();
    const ctx = makeCtx();
    await h.session_start({ reason: "resume" }, ctx);
    const event = { systemPromptOptions: { sections: {} } };
    await h.before_agent_start(event, ctx);
    const policy = event.systemPromptOptions.sections.forge_workspace;
    expect(policy).toContain("at most once per delivery");
    expect(policy).toContain("at most one focused, verified fix pass");
    expect(policy).toContain("leave valid out-of-scope findings open");
    expect(policy).toContain("pause publication and completion");
    expect(policy).toContain("Reloads, resumes, and skill transitions reuse");
    for (const skill of ["writing-plans", "finishing-a-development-branch"]) {
        const result = await h.tool_result({
            toolName: "read",
            input: { path: `/skills/${skill}/SKILL.md` },
            content: [{ type: "text", text: "Original skill content" }],
        }, ctx);
        expect(result.content[0].text).toBe("Original skill content");
        const override = result.content[1].text;
        expect(override).toContain("bounded roborev delivery policy");
        expect(override).toContain("without restarting the allowance");
        expect(override).not.toContain("roborev review --branch");
    }
});

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

test("background subagent runner processes stay isolated from Forge hooks, sections, and Superpowers bootstrap", async () => {
    process.env.KENN_FORGE_RUNTIME_SESSION_KEY = "rk";
    process.env.PI_SUBAGENT_CHILD = "1";
    process.env.PI_SUBAGENT_RUNNER_PID = "99999";
    const h = load();
    const ctx = makeCtx();
    await h.session_start({ reason: "startup" }, ctx);
    const beforeEvent = { systemPromptOptions: { sections: {} } };
    await h.before_agent_start(beforeEvent, ctx);
    expect(beforeEvent.systemPromptOptions.sections.forge_workspace).toBeUndefined();
    expect(contextRequests).toEqual([]);
    expect(hooks).toEqual([]);

    const contextResult = await h.context({
        messages: [
            {
                role: "user",
                content: [{ type: "text", text: "<EXTREMELY_IMPORTANT>\nsuperpowers:using-superpowers bootstrap for pi\n</EXTREMELY_IMPORTANT>" }],
            },
            {
                role: "user",
                content: [{ type: "text", text: "Subagent task prompt" }],
            },
        ],
    }, ctx);
    expect(contextResult?.messages).toHaveLength(1);
    expect(contextResult?.messages[0].content[0].text).toBe("Subagent task prompt");

    const skillResult = await h.tool_result({
        toolName: "read",
        input: { path: "/skills/writing-plans/SKILL.md" },
        content: [{ type: "text", text: "Original skill content" }],
    }, ctx);
    expect(skillResult).toBeUndefined();
});
