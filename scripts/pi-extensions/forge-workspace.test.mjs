import { afterEach, beforeEach, expect, test } from "bun:test";
import { execFileSync } from "node:child_process";
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
let confirms;
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
    confirms = [];
    contextRequests = [];
    summaryRequests = [];
    summaryResponse = { status: 200, text: "" };
    cwd = mkdtempSync(join(tmpdir(), "forge-ext-"));
    writeFileSync(join(cwd, "AGENTS.override.md"), "- Workspace ID: `ws1`\n");
    execFileSync("git", ["init", "-q", "-b", "feature-a", cwd]);
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

function makeCtx({ saved = true, mode = "tui", id = "sess-1", confirm } = {}) {
    const file = join(cwd, `${id}.jsonl`);
    if (saved) writeFileSync(file, "{}\n");
    return {
        cwd,
        mode,
        sessionManager: { getSessionId: () => id, getSessionFile: () => file },
        ...(confirm ? { hasUI: true, ui: { confirm: async (...args) => { confirms.push(args); return confirm(); } } } : {}),
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

// Bounded roborev review loops: the first branch review is allowed, later
// full-branch reviews need the human, and findings on fix commits go to the
// owner instead of another fix pass.
const call = (h, command, ctx = makeCtx({ mode: "print" })) =>
    h.tool_call({ toolName: "bash", toolCallId: "c1", input: { command } }, ctx);
const finding = (n, severity, path, problem) =>
    `### ${n}. ${severity}\n\n**Location:** ${path}:10-12\n\n**Problem:** ${problem}\n\n**Fix:** change it.\n`;
const ORIGINAL = finding(1, "Medium", "src/widget.ts", "The widget cache never invalidates when the store format changes.");
const result = (h, command, text, ctx = makeCtx({ mode: "print" })) =>
    h.tool_result({ toolName: "bash", toolCallId: "c1", input: { command }, content: [{ type: "text", text }] }, ctx);

test("the first branch review is allowed and the second is blocked in non-interactive sessions", async () => {
    const h = load();
    expect(await call(h, "roborev review --branch --wait --min-severity medium")).toBeUndefined();
    const blocked = await call(h, "roborev review --branch --wait --min-severity medium");
    expect(blocked.block).toBe(true);
    expect(blocked.reason).toContain("review budget");
    expect(blocked.reason).toContain("loop");
    expect(blocked.reason).toContain("human");
});

test("a second branch review needs the human and runs only when confirmed", async () => {
    const h = load();
    await call(h, "roborev review --branch");
    const declined = await call(h, "roborev review --branch", makeCtx({ confirm: () => false }));
    expect(declined.block).toBe(true);
    expect(confirms).toHaveLength(1);
    const allowed = await call(h, "roborev review --branch=feature-a", makeCtx({ confirm: () => true }));
    expect(allowed).toBeUndefined();
});

test("the branch review count survives reload, resume and a new session", async () => {
    await call(load(), "cd . && roborev review --branch --wait");
    const reloaded = load();
    await reloaded.session_start({ reason: "resume" }, makeCtx({ id: "sess-2" }));
    const blocked = await call(reloaded, "bash -c 'roborev review --since main'", makeCtx({ mode: "print", id: "sess-2" }));
    expect(blocked.block).toBe(true);
});

test("each branch keeps its own review budget", async () => {
    await call(load(), "roborev review --branch");
    execFileSync("git", ["-C", cwd, "symbolic-ref", "HEAD", "refs/heads/feature-b"]);
    expect(await call(load(), "roborev review --branch")).toBeUndefined();
});

test("a fix-commit review is allowed after the branch review", async () => {
    const h = load();
    await call(h, "roborev review --branch --wait");
    for (const command of ["roborev review abc123 --wait --min-severity medium", "roborev review", "roborev review --dirty"]) {
        expect(await call(h, command)).toBeUndefined();
    }
});

test("refine and unscoped fix loops need the human like a second branch review", async () => {
    const h = load();
    for (const command of ["roborev refine", "roborev fix", "roborev fix --open"]) {
        expect((await call(h, command)).block).toBe(true);
    }
    expect(await call(h, "roborev fix 42")).toBeUndefined();
    expect(await call(h, "roborev show 42")).toBeUndefined();
});

test("new findings on a fix commit are recorded for the owner and trigger the loop self-check", async () => {
    const h = load();
    await call(h, "roborev review --branch --wait");
    await result(h, "roborev review --branch --wait", ORIGINAL);
    const fix = "roborev review abc123 --wait";
    await call(h, fix);
    const out = await result(h, fix, finding(1, "High", "src/other.ts", "The exporter drops trailing rows."));
    const text = out.content.map((part) => part.text).join("\n");
    expect(text).toContain("outside the original findings");
    expect(text).toContain("roborev respond");
    expect(text).toContain("Do not action");
    expect(text).toContain("assess whether you are in a review loop");
    const event = { systemPromptOptions: { sections: {} } };
    await h.before_agent_start(event, makeCtx());
    expect(event.systemPromptOptions.sections.forge_workspace).toContain("Stop and assess whether you are in a review loop");
    // The escalation persists across a reload.
    const reloaded = { systemPromptOptions: { sections: {} } };
    await load().before_agent_start(reloaded, makeCtx());
    expect(reloaded.systemPromptOptions.sections.forge_workspace).toContain("Stop and assess whether you are in a review loop");
});

test("a recurring finding on a fix commit triggers the self-check as recurring", async () => {
    const h = load();
    await call(h, "roborev review --branch --wait");
    await result(h, "roborev review --branch --wait", ORIGINAL);
    const out = await result(h, "roborev review abc123 --wait", finding(1, "Medium", "src/widget.ts", "The widget cache never invalidates when the store format changes again."));
    const text = out.content.map((part) => part.text).join("\n");
    expect(text).toContain("recurring");
    expect(text).toContain("assess whether you are in a review loop");
});

test("a clean or low-only fix-commit review leaves the result and prompt alone", async () => {
    const h = load();
    await call(h, "roborev review --branch --wait");
    await result(h, "roborev review --branch --wait", ORIGINAL);
    expect(await result(h, "roborev review abc123 --wait", "## Summary\n\nNo issues found.")).toBeUndefined();
    expect(await result(h, "roborev review abc123 --wait", finding(1, "Low", "src/x.ts", "Rename a variable."))).toBeUndefined();
    const event = { systemPromptOptions: { sections: {} } };
    await h.before_agent_start(event, makeCtx());
    expect(event.systemPromptOptions.sections.forge_workspace).not.toContain("Stop and assess whether you are in a review loop");
});

test("originals are read from roborev show when the branch review ran in the background", async () => {
    const h = load();
    await call(h, "roborev review --branch");
    await result(h, "roborev show 7", ORIGINAL);
    const out = await result(h, "roborev review abc123 --wait", finding(1, "Medium", "src/widget.ts", "The widget cache never invalidates when the store format changes."));
    expect(out.content.map((part) => part.text).join("\n")).toContain("recurring");
});

test("a blocked second branch review also arms the self-check prompt", async () => {
    const h = load();
    await call(h, "roborev review --branch");
    await call(h, "roborev review --branch");
    const event = { systemPromptOptions: { sections: {} } };
    await h.before_agent_start(event, makeCtx());
    expect(event.systemPromptOptions.sections.forge_workspace).toContain("Stop and assess whether you are in a review loop");
});

test("workspace policy states the enforced review budget and original-finding scope", async () => {
    const event = { systemPromptOptions: { sections: {} } };
    await load().before_agent_start(event, makeCtx());
    const policy = event.systemPromptOptions.sections.forge_workspace;
    expect(policy).toContain("Pi enforces the review budget");
    expect(policy).toContain("only the findings recorded in the first review");
    expect(policy).toContain("`roborev review <sha>`");
});
