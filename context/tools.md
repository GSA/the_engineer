# Tools and environment reference

## Service endpoints and systemd units

All four persistent services run under user systemd and bind to `127.0.0.1`:

| Service | Loopback endpoint | Systemd unit | Persistent data under `.local/environment/` |
| --- | --- | --- | --- |
| Kata (`v0.22.0-20-g4853199e`) | `http://127.0.0.1:17777/kata` | `kenn-kopy-kata.service` | `kata/kata.db` |
| roborev (`v0.74.0-161-gcaacbdae`) | `http://127.0.0.1:17374/reviews` (API `17373`) | `kenn-kopy-roborev.service` | `roborev/config.toml`, `roborev/reviews.db` |
| AgentsView (`v0.46.1-283-g49b1c6c84`) | `http://127.0.0.1:18080/` | `kenn-kopy-agentsview.service` | `agentsview/data/sessions.db` |
| Forge (`v0.5.1-331-g3f58f438-local-kata`) | `http://127.0.0.1:18091/` (MCP `http://127.0.0.1:18092/mcp`) | `kenn-kopy-forge.service` | `forge/config.toml`, `forge/forge.db` |

All ports derive from `DEFAULT_PORTS` in `scripts/local_env.py` plus
`KENN_KOPY_PORT_OFFSET` (default `0`). `setup` saves a nonzero offset as
`port_offset` in `environment.json`; every writer (Forge/roborev/Kata configs,
`pi/mcp.json`, `KATA_SERVER`/`KENN_FORGE_API_URL`), unit, probe, `smoke.py`, and
`dist/install.py` uses the shifted ports. A second WSL2 distro shares this
`127.0.0.1`, so it uses offset `1000` (`docs/wsl2-rehearsal.md`, deferred `t592`).

Check live health across all four services with:

```sh
python3 scripts/local_env.py status
```

Verify a whole host read-only with `python3 scripts/local_env.py accept
[--repo PATH ...]` (PASS/FAIL per check, nonzero until every check passes;
needs a login shell for `systemctl --user`).

The coder contract is `scripts/pi-coder-contract.md`; `setup` installs it as
the private `pi/AGENTS.md`. Check which policy coder and roborev review Pi load with `python3
scripts/local_env.py verify-pi-policy [--cwd PATH]` (see
`context/engineering-workflow.md#loaded-policy-by-surface`).

Check a Forge Kata workspace's task, Pi, AgentsView and roborev linkage with
`python3 scripts/local_env.py verify-handoff WORKSPACE_ID [--commit SHA]`.
Linkage is joined by Kata issue UID, worktree path, branch, Pi session ID and
commit SHA; Kata workspaces show reviews only through the roborev hook and
review page (no Forge Reviews tab), reported as `GAP native-review-ui`.

## CLI binaries and wrappers

- `kata` (`~/.local/bin/kata` -> `/home/nkirrish/kenn-kopy/kata/kata`):
  use directly in any repository with a `.kata.toml` binding (`kata list --agent`,
  `kata ready --no-label blocked --no-label deferred --agent`, `kata show <id>`,
  `kata claim <id>`, `kata close <id> --reason "..."`).
- `roborev` (`~/.local/bin/roborev`): `~/.roborev` symlinks to
  `.local/environment/roborev`, so native `roborev status`, `roborev tui`,
  `roborev review`, and `roborev init --no-daemon` talk directly to the
  `127.0.0.1:17373` daemon.
- `python3 scripts/pi-local.py`: runs Pi with `PI_CODING_AGENT_DIR` set to
  `.local/environment/pi`, loading the isolated USAi models, MCP servers
  (`falcon-context`, `kata`, and `kenn-forge` on `127.0.0.1:18092/mcp`),
  Superpowers skills, `pi-subagents`, and `extensions/forge-workspace.ts`
  (which loads `AGENTS.override.md` / Forge `SessionStart` context, overrides
  `finishing-a-development-branch` to push + create PR + register Forge targets,
  and posts live agent activity hooks via `KENN_FORGE_RUNTIME_SESSION_KEY`).
  It exports `KATA_REF` (caller value, else the `Qualified ID` of a Kata-task
  `AGENTS.override.md`) for the native attention-only adapter
  `extensions/kata.js` that `install-pi-extensions` writes with
  `kata agent-hook install pi` (contract removed; AGENTS policy carries it).
  Start sets `work.attention ok`; `/quit` or SIGHUP sets `needs-human`
  "session ended without hand-off" unless the agent already handed off;
  `/reload`, Escape and `pi --session <id>` resume keep or restore `ok`.
- `python3 scripts/gh-local.py`: runs `gh` with `GH_CONFIG_DIR` set to
  `.local/environment/gh` so Forge and operator GitHub checks share isolated
  authentication.
- `scripts/jira-intake.py`: manual one-ticket Jira XML export to approved Kata
  tasks (`init`, `check`, `record --apply`); contract in `context/jira-intake.md`.
- `local_env.py configure-librarian --audit [--copilot-config PATH]`: opt-in
  `--audit-log`/`--agent-label` flags (`pi-forge`, `copilot`) after probing
  `librarian-mcp --help`; unmanaged bindings are reported, not edited. Flags
  apply when a client restarts its MCP process; `scripts/verify-audit-binding.mjs`
  checks a fresh Pi client against the audit log.
- `scripts/decision-trail.py`: read-only per-task retrospective into
  `.local/decision-trail/` joining Kata, intake approval, audit log, Forge
  workspace, Pi session, git, roborev and `gh`; absent links print `MISSING`.
- `python3 scripts/demo-capture.py`: private screenshot/video demos of
  loopback web UIs (`capture`, `import`, `handoff`, `cleanup`, `doctor`,
  `smoke`) into ignored `.local/demos/` with a provenance manifest; never
  uploads. Contract in `context/demo-capture.md`.
- `python3 scripts/terminal-local.py`: manages persistent local `pi` and
  `copilot` tmux sessions via `.local/environment/runtime/terminal/tmux.sock`.

## Pi and subagent configuration

Pi is pinned to `PI_VERSION = "1.4.0"` in both `scripts/local_env.py` and
`dist/install.py`; `verify_pi()` rejects any other `--version`. When the saved
`pi_executable` is upgraded in place, rerunning `setup` with the same arguments
rewrites only the stale `pi_version` in `environment.json` after `verify_pi()`
passes; any other saved difference still aborts without mutation.

`scripts/local_env.py` writes `default_pi_subagents_settings()` into
`.local/environment/pi/settings.json` (and mirrors it in `~/.pi/agent/settings.json`
for standalone `pi` invocations), populates all 25 advertised USAi chat models
into `.local/environment/pi/models.json` (excluding embedding models
`cohere_english_v3` and `text-embedding-005`), and supports opposite-family
adversarial pairing via `--review-model`:

- `defaultProvider`: `"usai"`
- Coder default (`usai.json.model` / `pi/settings.json.defaultModel`): `"claude-sonnet-5.5"`
- Alternate Forge coder launch target (`forge/config.toml` `key = "pi-argon"`): `"gemini-4-argon"` (`Pi (Gemini 4 Argon)`)
- Reviewer default (`usai.json.review_model` / `roborev/config.toml`): `"gpt-6.1-sol-latest-guardrails-defaultv2"`
- Subagent `defaultModel`: `"inherit"`
- Subagent `toolActivation`: `"eager"`
- `modelScope.allow`: `["inherit", "usai/*"]`
- Built-in profiles (`delegate`, `oracle`, `scout`, `worker`): `model: "inherit"`;
  `reviewer` routes to `usai/<review_model>` when a paired `review_model` is configured in `usai.json` (otherwise `"inherit"`).
- External-CLI and web-access builtin profiles (`claude-code`, `claude-code-writer`, `codex-exec`, `codex-exec-writer`, `cursor-agent`, `cursor-agent-writer`, `evidence-auditor`, `researcher`): disabled (`disabled: true`, `advertise: false`) in the isolated USAi-only profile.
- Tool overrides (`PI_SUBAGENT_DESCRIPTIONS`): instruct agents to omit `model`
  or pass `"inherit"`, omit `model` on `action: "resume"`, and keep Superpowers
  `reviewer` subagents separate from native `roborev` CLI reviews.

## roborev configuration and hooks

- Global config (`.local/environment/roborev/config.toml` via `~/.roborev`):
  `server_addr = "127.0.0.1:17373"`, `default_agent = "pi"`,
  `pi_cmd = "/home/nkirrish/kenn-kopy/scripts/pi-local.py"`,
  `default_model = "gpt-6.1-sol-latest-guardrails-defaultv2"`,
  `review_model = "gpt-6.1-sol-latest-guardrails-defaultv2"`,
  `review_min_severity = "medium"`, `refine_min_severity = "medium"`,
  `fix_min_severity = "medium"`, `auto_close_passing_reviews = true`.
  `setup` adds missing defaults to existing private configs while preserving
  explicit overrides, model routing, and unrelated settings.
  `scripts/local_env.py:pi_launch()` accepts `--model` only when it matches the
  configured `usai.json` coder `model` or `review_model` and validates opposite
  Claude/OpenAI model families in `validate_roborev_config()`.
- Per-repository `.roborev.toml` (installed in `kenn-kopy`, `the_librarian`,
  `falcon-docs`, and `falcon/{backend,frontend,exec-dashboard,mcp}`):
  - `agent = "pi"`, `review_reasoning = "standard"`
  - `review_min_severity = "medium"`, `refine_min_severity = "medium"`, `fix_min_severity = "medium"`
  - `post_commit_batch_size = 5`
  - Concise, affirmative `review_guidelines`
- Hooks: native `roborev init --no-daemon` hooks (`post-commit`, `post-rewrite`,
  `pre-push`) in each repo's `.git/hooks/`. Global `core.hooksPath` and Copilot
  CLI's `~/.copilot/hooks/agenthook.json` remain unset/removed to prevent
  recursive review loops.
- Forge workspace execution (`scripts/pi-extensions/forge-workspace.ts`):
  - Preserves `KENN_FORGE_RUNTIME_SESSION_KEY` across `scripts/pi-local.py` (with API fallback by workspace ID) so Forge tracks live Pi session activity.
  - Reports lifecycle to Forge's native Pi hook profile (`/api/v1/agent-hooks/pi`), so Forge resumes a saved conversation with `pi --session <id>`; workspace context still comes from the Claude `SessionStart` renderer without a runtime key. Only interactive (`tui`) sessions with a saved session file report; earlier events are held until Pi saves the file. Reports post in order.
  - Maps Pi events: `session_start` → `SessionStart` (`resume`/`fork`/`clear`, or `resume` when startup opens a saved file), turns → `UserPromptSubmit`/`PreToolUse`/`PostToolUse`/`Stop` (aborted turns also settle to `Stop`), dialogs during a turn → `Notification elicitation_dialog` (Forge `input`). `session_shutdown` sends `SessionEnd` only for replacement (`new`/`fork` → `clear`, `resume` → `resume`) or SIGTERM/SIGHUP (`other`, so Forge resumes instead of forgetting); `/quit` and `/reload` keep the conversation resumable.
  - Blocks agent `gh pr merge` (including `gh-local.py` and `gh api .../pulls/N/merge`) and `git push` to `main`/`master` (explicit refspec, `--all`/`--mirror`, or bare push from a `main` checkout) on every Pi surface unless the human confirms the call in the Pi UI; print/JSON sessions always block. Workspace-branch pushes and `gh pr create`/`gh pr edit` are unaffected, including after an earlier `cd`, `git -C`, or `git checkout -b`/`switch -c` in the same command: the guard follows literal directory and branch moves and resolves the real HEAD. It still treats HEAD as protected when the branch is genuinely unknowable (`cd` with no argument, `cd -`, an expansion such as `cd "$(...)"`, a missing directory, `pushd`/`popd`, `git worktree`, a detached checkout, or a `cd` whose effect does not reach the push because it ran in a subshell, backticks, or a pipeline stage), and when a checkout that could fail is followed by a push the pre-checkout branch still counts. A wrapper program (`timeout`, `stdbuf`, `nice`, `setsid`, `env`, `sudo`, `xargs`, and friends, by basename, with their own options — valued or valueless per wrapper — and `timeout`'s duration skipped) does not hide the push or merge it runs, `gh` flags such as `--repo` placed before or between subcommand words do not hide `pr merge`, `git -C` composes cumulatively, and an explicit `--git-dir` selects the repository whose HEAD the push moves. Each subshell gets its own directory scope, so a sibling subshell's `cd` does not leak, and a `cd` a preceding `&&`/`||` may skip leaves the pre-`cd` directory a candidate too. A heredoc body a program consumes is data, while a shell-executed body (`bash <<EOF`) runs in a child scope whose directory moves stay there, and an unquoted heredoc delimiter still exposes the command substitutions the shell expands in the body; heredoc syntax inside quotes or a comment never hides the commands after it. PR-description reformatting also triggers structurally, so `gh --repo … pr create`, a wrapped `gh pr edit`, and `gh-local.py pr create` are recognized while a mention of `gh pr create` in `echo` or `grep` text is not.
  - Enforces the roborev review budget on bash `roborev` commands: one `review --branch`/`--since` per workspace branch (count kept in `forge-roborev-budget.json` in the worktree's git directory, so it survives reloads and resumes), then block unless the human confirms in the Pi UI (print/JSON always block); `refine` and unscoped `fix` are treated the same, `review <sha>`/`--dirty` and `fix <job>` are allowed. Medium-or-higher findings on a fix commit outside (or recurring from) the first review's findings are flagged for the owner and arm a loop self-check prompt in the workspace policy. Copilot has no runtime hook and follows the prose policy. See `context/engineering-workflow.md`.
  - Filters parent repo `AGENTS.md` files from child worktrees under `.local/environment/forge/worktrees/`.
  - Overrides `superpowers:brainstorming`, `superpowers:writing-plans`, and `superpowers:finishing-a-development-branch` so workspace agents execute autonomously without mid-task approval stops, share the bounded delivery review policy in `context/engineering-workflow.md`, format PR descriptions via `gemini-4-argon`, and register PR/Kata targets with Forge. The review/fix allowance survives skill transitions, reloads, and resumes; unresolved task-scoped medium/high/critical defects pause publication for owner handoff. Coder, finishing and formatter prompts share content-led guidance: no size tiers or paragraph/bullet quotas, concise prose for focused changes, optional lists/sections for independent concerns, and retained task references and actionable caveats.
  - Seeds `.local/environment/home/.gitconfig` and `.config/git/ignore`, and exposes `jq` (`.local/tools/jq-1.7.1/bin`) and shared Python test dependencies (`.local/tools/pydeps`) on `PATH`/`PYTHONPATH`.

## Task-bound evidence consumer and seam scanner

`engineer-task-context` (`src/engineer_context/`, CLI `engineer-context`, stdio
MCP `engineer-context-mcp`) composes `engineer.task-context/v2` packets from the
Librarian MCP server, routed explicitly per `engineer.context-config/v2`. The
consumer never discovers providers, writes provider state, or mutates a task.
The same package ships the stdlib-only cross-repository seam scanner
(`src/engineer_context/seams.py`, CLI `engineer-seams` / `engineer-context
seams`, MCP tool `seams`) for UI, API Gateway, CDK, Lambda, async and
CloudFormation edges across repositories.

Librarian facts to respect when extending it: identity is `the-librarian`
0.3.0, it requires fresh `status` and returns exactly one JSON `TextContent`;
`search` is discovery only. Librarian exposes no project UID or generation
token, so configured business identity stays distinct from provider-asserted
identity. Assertions and contributions remain unavailable pending
`the_librarian#923h` and `the_librarian#rjr5`; do not invent those contracts.

The server program path in the configuration is absolutized lexically rather
than resolved, because dereferencing a virtual environment's entry point
changes the child's prefix. Corpus, reader and selection paths are fully
resolved. They are treated as paths only, so spaces are allowed and no launch
goes through a shell. The Librarian launch sends `--root` and, when selected,
`--manifest`; the current toolkit loads its reader from `tools.context_index`
under that root and rejects `--reader`, so `librarian.reader` and `setup
--librarian-reader` stay optional and exist only for a legacy release that
requires that argument.

Actual-provider verification lives in `tests/integration/` and fails rather
than skips when `ENGINEER_LIBRARIAN_SOURCE` is absent. Fixtures are built only
through the owning Librarian `package.release_paths` plus `tools/initialize.py`
with non-identifying content; never point tests at the Falcon corpus or a
production index.

`scripts/verify-context-runtime.mjs` proves actual Pi discovery and a qualified
read with zero model requests. Pi SDK facts it depends on: passing `tools: []`
to `createAgentSession` is an empty allowlist that hides `codemode` and all
`mcp__*` tools; nested tool execution needs a last assistant message, which the
probe supplies through `SessionManager.inMemory` preloaded entries; MCP servers
connect in the background, so a direct `tool.execute` must poll
`session.getAllTools()` first; and MCP tools resolve to `CallToolResult`, so
content text must be parsed and `isError` surfaced. The MCP extension's default
configuration loader and log path read `getAgentDir()`
(`PI_CODING_AGENT_DIR` or `~/.pi/agent`) rather than the session's `agentDir`,
so the probe passes an explicit empty `loadConfig` and a private `logPath`;
otherwise operator-configured servers launch and a saved `component-context`
entry would shadow the registered provider. The receipt records
`configured_mcp_servers: 0` alongside `model_requests: 0` as that isolation
evidence.

## Build and test commands

- Toolchain bootstrap and submodule builds (`Go 1.27.3`, `Bun 1.3.14 / 1.4.4`, `gh 2.102.0`, `jq 1.7.1`):
  ```sh
  bash scripts/bootstrap-toolchains.sh
  bash scripts/build.sh agentsview kata
  ```
- Engineer Python scripts and unit tests:
  ```sh
  python3 -m unittest discover -s scripts -p 'test_*.py'
  python3 -m unittest discover -s dist -p 'test_*.py'
  ```
- Task-bound evidence consumer (private venv with `engineer-task-context` installed):
  ```sh
  python -m unittest discover -s tests -p 'test_context_*.py'
  ENGINEER_LIBRARIAN_SOURCE=~/the_librarian PYTHONPATH=tests/integration python -m unittest test_context_real_providers
  ```
- Local Forge binary (`.local/forge-local-kata`, keeps `forge/` submodule clean):
  ```sh
  cd .local/forge-local-kata/web && npm run build
  cd .local/forge-local-kata && go test ./internal/server ./internal/git ./internal/agent/... && go build -o kenn-forge ./cmd/kenn-forge
  ```
- Librarian (`~/the_librarian`):
  ```sh
  cargo test --manifest-path ~/the_librarian/Cargo.toml
  ```
