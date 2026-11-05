import { afterEach, beforeEach, expect, test } from "bun:test";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import forgeWorkspaceExtension, { humanOnlyPublication } from "./forge-workspace.ts";

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

async function summarizePr({ shortStat, draft, summary, status = 200, command = "gh pr create --body-file draft.md" }) {
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
        toolName: "bash", toolCallId: "pr-write", args: { command },
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

// The guard must not stop the pre-authorized workspace PR flow: agents routinely
// prefix a workspace push with `cd`, so a tracked `cd` has to resolve the real
// branch instead of assuming `main`.
test("a workspace-branch push stays allowed after cd, checkout -b, and heredoc text", () => {
    const root = mkdtempSync(join(tmpdir(), "guard-allow-"));
    const work = join(root, "work-kenn-forge");
    mkdirSync(join(work, "nested"), { recursive: true });
    execFileSync("git", ["init", "-q", "-b", "kenn-forge/work-5a30c3b8", work]);
    const allowed = [
        "cd " + work + " && git push -u origin HEAD",
        "cd nested && git push -u origin HEAD",
        "git checkout -b follow-up && git push -u origin HEAD",
        "git switch -c follow-up && git push origin HEAD",
        "git checkout -- README.md && git push -u origin HEAD",
        "cat > notes.md <<'DOC'\ncd /tmp/main\ngit push origin main\nDOC\ngit push -u origin HEAD",
        "echo '<<EOF' && git push -u origin HEAD",
        "bash <<'EOF'\ngit push -u origin HEAD\nEOF",
        "# git push origin main\ngit push -u origin HEAD",
        "cd " + work + " && python3 - <<'E'\nprint(1)\nE\ngit push -u origin HEAD",
        "git -C " + work + " push -u origin HEAD",
        "git -C " + join(work, "nested") + " checkout -b follow-up && git -C " + work + " push origin HEAD",
        "git push -u origin HEAD # not git push origin main",
        "(cd nested && git status -sb) && git push -u origin HEAD",
        "timeout 60 git push -u origin HEAD",
        "gh --repo GSA/the_engineer pr create --fill",
        "gh -R GSA/the_engineer pr edit 29 --body-file /tmp/body.md",
        // --work-tree alone does not change the repository the push reads
        "git --work-tree " + root + " push -u origin HEAD",
        // a quoted heredoc a program consumes stays data
        "cat <<'EOF'\n$(git push origin main)\nEOF\ngit push -u origin HEAD",
    ];
    try {
        for (const command of allowed) {
            expect([command, humanOnlyPublication(command, work)]).toEqual([command, null]);
        }
    } finally {
        rmSync(root, { recursive: true, force: true });
    }
});

test("pushing main still needs human approval however the branch is reached", () => {
    const root = mkdtempSync(join(tmpdir(), "guard-block-"));
    const work = join(root, "work-kenn-forge");
    const trunk = join(root, "main-checkout");
    mkdirSync(join(work, "nested"), { recursive: true });
    mkdirSync(trunk, { recursive: true });
    execFileSync("git", ["init", "-q", "-b", "kenn-forge/work-5a30c3b8", work]);
    execFileSync("git", ["init", "-q", "-b", "main", trunk]);
    const blocked = [
        [work, "cd " + trunk + " && git push -u origin HEAD"],
        [work, "cd ../main-checkout && git push"],
        [work, "cd " + trunk + "; git push -u origin HEAD"],
        [work, "git checkout main && git push origin HEAD"],
        [work, "git switch master && git push"],
        [work, 'cd "$(dirname ' + trunk + ')" && git push origin HEAD'],
        [work, "cd && git push origin HEAD"],
        [work, "cd " + join(root, "absent") + " && git push origin HEAD"],
        [work, "git worktree add ../wt main && git push origin HEAD"],
        [work, "git -C " + join(root, "absent") + " push origin HEAD"],
        [work, "git checkout --detach && git push origin HEAD"],
        [work, "cd " + trunk + " && git checkout -- README.md && git push origin HEAD"],
        [work, "git push origin HEAD:refs/heads/main"],
        // a wrapper program must not hide the push it runs
        [trunk, "timeout 60 git push origin HEAD"],
        [trunk, "stdbuf -o0 git push origin main"],
        [trunk, "nice -n 10 git push origin main"],
        [trunk, "setsid git push origin main"],
        [trunk, "/usr/bin/timeout 5m git push origin main"],
        [trunk, "timeout 120 gh pr merge 29 --merge", "pr_merge"],
        // gh takes its own flags before and between subcommand words
        [work, "gh --repo GSA/the_engineer pr merge 29 --merge", "pr_merge"],
        [work, "gh -R GSA/the_engineer pr merge 29", "pr_merge"],
        [work, "gh pr --repo GSA/the_engineer merge 29", "pr_merge"],
        [work, "gh api --method PUT /repos/GSA/the_engineer/pulls/29/merge", "pr_merge"],
        // --git-dir chooses the repository whose HEAD a push moves
        [work, "git --git-dir=" + join(trunk, ".git") + " --work-tree=" + trunk + " push origin HEAD"],
        // a wrapper's own valueless option must not swallow the program
        [work, "env -i /usr/bin/git -C " + trunk + " push origin HEAD"],
        // a cd a preceding && can skip leaves the earlier directory possible
        [trunk, "false && cd " + work + "; git push origin HEAD"],
        // sibling subshells each inherit the outer directory
        [trunk, "(cd " + work + "); (git push origin HEAD)"],
        // a shell heredoc's cd stays inside that shell
        [trunk, "bash <<'EOF'\ncd " + work + "\nEOF\ngit push origin HEAD"],
        // an unquoted heredoc expands, so its substitutions run
        [work, "cat <<EOF\n$(git push origin main)\nEOF"],
        // a checkout in a subdirectory moves the same repository's HEAD
        [work, "git -C " + join(work, "nested") + " checkout main && git push origin HEAD"],
        // a heredoc body a shell executes is still a command
        [work, "bash <<'EOF'\ngit push origin main\nEOF"],
        // quoted heredoc syntax must not swallow the commands that follow
        [work, "echo '<<EOF'\ngit push origin main"],
        // the checkout may fail, leaving HEAD on main, and ; runs the push anyway
        [trunk, "git checkout -b follow-up; git push origin HEAD"],
        // a cd inside a subshell, a backtick, or a pipeline stage does not move
        // the directory the later push runs in
        [trunk, "(cd " + work + " && git status) && git push origin HEAD"],
        [trunk, "`cd " + work + "`; git push origin HEAD"],
        [trunk, "cd " + work + " | cat; git push origin HEAD"],
    ];
    try {
        for (const [dir, command, expected = "push_main"] of blocked) {
            expect([command, humanOnlyPublication(command, dir)]).toEqual([command, expected]);
        }
    } finally {
        rmSync(root, { recursive: true, force: true });
    }
});

test("PR formatter leaves the existing description alone when the model route fails", async () => {
    expect(await summarizePr({
        shortStat: "1 file changed, 1 insertion(+)",
        draft: "Keep this description.",
        summary: "",
        status: 503,
    })).toBeNull();
    expect(summaryRequests).toHaveLength(1);
});

test("PR formatter runs on a flagged or wrapped PR write and not on a mere mention", async () => {
    const base = { shortStat: "1 file changed, 1 insertion(+)", draft: "Keep this.", summary: "Rewritten." };
    for (const command of [
        "gh --repo GSA/the_engineer pr create --fill",
        "timeout 60 gh pr edit 29 --body-file /tmp/body.md",
        "python3 scripts/gh-local.py pr create --fill",
    ]) {
        summaryRequests.length = 0;
        rmSync(join(cwd, "edited-body"), { force: true });
        expect([command, await summarizePr({ ...base, command })]).toEqual([command, "Rewritten.\n"]);
    }
    for (const command of ['echo "gh pr create"', "grep -n 'gh pr edit' README.md"]) {
        summaryRequests.length = 0;
        rmSync(join(cwd, "edited-body"), { force: true });
        expect([command, await summarizePr({ ...base, command })]).toEqual([command, null]);
        expect([command, summaryRequests.length]).toEqual([command, 0]);
    }
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

test("a failing review that exits nonzero is still screened and recorded", async () => {
    const h = load();
    const failing = (command, text) => h.tool_result({
        toolName: "bash", toolCallId: "c1", isError: true, input: { command },
        content: [{ type: "text", text: `Enqueued job 5 for abc\n${text}\n\nCommand exited with code 1` }],
    }, makeCtx({ mode: "print" }));
    await call(h, "roborev review --branch --wait");
    await failing("roborev review --branch --wait", ORIGINAL);
    await call(h, "roborev review abc123 --wait");
    const out = await failing("roborev review abc123 --wait", finding(1, "High", "src/other.ts", "The exporter drops trailing rows."));
    expect(out.content.map((part) => part.text).join("\n")).toContain("outside the original findings");
});

test("single-argument and --sha ranges count as branch reviews", async () => {
    for (const range of ["roborev review main..HEAD", "roborev review --sha main...HEAD", "roborev review --sha=main..HEAD"]) {
        execFileSync("git", ["-C", cwd, "symbolic-ref", "HEAD", `refs/heads/b-${range.length}`]);
        const h = load();
        expect(await call(h, range)).toBeUndefined();
        expect((await call(h, range)).block).toBe(true);
    }
});

test("a fix review enqueued without --wait is screened when its job is shown", async () => {
    const h = load();
    await call(h, "roborev review --branch");
    await result(h, "roborev review --branch", "Enqueued job 10 for abc..def");
    await result(h, "roborev show 10", ORIGINAL);
    await call(h, "roborev review abc123");
    await result(h, "roborev review abc123", "Enqueued job 11 for abc123");
    const out = await result(h, "roborev show --job 11", finding(1, "High", "src/other.ts", "The exporter drops trailing rows."));
    const text = out.content.map((part) => part.text).join("\n");
    expect(text).toContain("outside the original findings");
    const event = { systemPromptOptions: { sections: {} } };
    await h.before_agent_start(event, makeCtx());
    expect(event.systemPromptOptions.sections.forge_workspace).toContain("Stop and assess whether you are in a review loop");
});

test("showing the original branch job again does not replace its recorded findings", async () => {
    const h = load();
    await call(h, "roborev review --branch");
    await result(h, "roborev review --branch", "Enqueued job 10 for abc..def");
    await result(h, "roborev show 10", ORIGINAL);
    await result(h, "roborev show 10", finding(1, "Medium", "src/else.ts", "A different problem entirely."));
    await call(h, "roborev review abc123 --wait");
    const out = await result(h, "roborev review abc123 --wait", finding(1, "Medium", "src/widget.ts", "The widget cache never invalidates when the store format changes."));
    expect(out.content.map((part) => part.text).join("\n")).toContain("recurring");
});
