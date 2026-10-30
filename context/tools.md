# Tools and environment reference

## Service endpoints and systemd units

All four persistent services run under user systemd and bind to `127.0.0.1`:

| Service | Loopback endpoint | Systemd unit | Persistent data under `.local/environment/` |
| --- | --- | --- | --- |
| Kata (`v0.20.0-37-g14844737`) | `http://127.0.0.1:17777/kata` | `kenn-kopy-kata.service` | `kata/kata.db` |
| roborev (`v0.74.0-23-gd53ecfca`) | `http://127.0.0.1:17374/reviews` (API `17373`) | `kenn-kopy-roborev.service` | `roborev/config.toml`, `roborev/reviews.db` |
| AgentsView (`v0.46.1-84-gc7f77ad0`) | `http://127.0.0.1:18080/` | `kenn-kopy-agentsview.service` | `agentsview/data/sessions.db` |
| Forge (`v0.5.1-118-gbf025d22-local-kata`) | `http://127.0.0.1:18091/` (MCP `http://127.0.0.1:18092/mcp`) | `kenn-kopy-forge.service` | `forge/config.toml`, `forge/forge.db` |

All ports derive from `DEFAULT_PORTS` in `scripts/local_env.py` plus
`KENN_KOPY_PORT_OFFSET` (default `0`). `setup` saves a nonzero offset as
`port_offset` in `environment.json`; every writer (Forge/roborev/Kata configs,
`pi/mcp.json`, `KATA_SERVER`/`KENN_FORGE_API_URL`), unit, probe, `smoke.py`, and
`dist/install.py` uses the shifted ports. A second WSL2 distro shares this
`127.0.0.1`, so it uses offset `1000` (README "Isolated WSL2 instance").

Check live health across all four services with:

```sh
python3 scripts/local_env.py status
```

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
- `python3 scripts/gh-local.py`: runs `gh` with `GH_CONFIG_DIR` set to
  `.local/environment/gh` so Forge and operator GitHub checks share isolated
  authentication.
- `scripts/jira-intake.py`: manual one-ticket Jira XML export to approved Kata
  tasks (`init`, `check`, `record --apply`); contract in `context/jira-intake.md`.
- `python3 scripts/terminal-local.py`: manages persistent local `pi` and
  `copilot` tmux sessions via `.local/environment/runtime/terminal/tmux.sock`.

## Pi and subagent configuration

`scripts/local_env.py` writes `default_pi_subagents_settings()` into
`.local/environment/pi/settings.json` (and mirrors it in `~/.pi/agent/settings.json`
for standalone `pi` invocations), populates all 25 advertised USAi chat models
into `.local/environment/pi/models.json` (excluding embedding models
`cohere_english_v3` and `text-embedding-005`), and supports opposite-family
adversarial pairing via `--review-model`:

- `defaultProvider`: `"usai"`
- Coder default (`usai.json.model` / `pi/settings.json.defaultModel`): `"claude-opus-5.5"`
- Alternate Forge coder launch target (`forge/config.toml` `key = "pi-argon"`): `"gemini-4-argon"` (`Pi (Gemini 4 Argon)`)
- Reviewer default (`usai.json.review_model` / `roborev/config.toml`): `"gpt-6.1-sol-latest-guardrails-defaultv2"`
- Subagent `defaultModel`: `"inherit"`
- `modelScope.allow`: `["inherit", "usai/*"]`
- Built-in profiles (`delegate`, `oracle`, `reviewer`, `scout`, `worker`):
  `model: "inherit"`
- Tool overrides (`PI_SUBAGENT_DESCRIPTIONS`): instruct agents to omit `model`
  or pass `"inherit"`, omit `model` on `action: "resume"`, and keep Superpowers
  `reviewer` subagents separate from native `roborev` CLI reviews.

## roborev configuration and hooks

- Global config (`.local/environment/roborev/config.toml` via `~/.roborev`):
  `server_addr = "127.0.0.1:17373"`, `default_agent = "pi"`,
  `pi_cmd = "/home/nkirrish/kenn-kopy/scripts/pi-local.py"`,
  `default_model = "gpt-6.1-sol-latest-guardrails-defaultv2"`,
  `review_model = "gpt-6.1-sol-latest-guardrails-defaultv2"`.
  `scripts/local_env.py:pi_launch()` accepts `--model` only when it matches the
  configured `usai.json` coder `model` or `review_model` and validates opposite
  Claude/OpenAI model families in `validate_roborev_config()`.
- Per-repository `.roborev.toml` (installed in `kenn-kopy`, `the_librarian`,
  `the_knowitall`, `falcon-docs`, and `falcon/{backend,frontend,exec-dashboard,mcp}`):
  - `agent = "pi"`, `review_reasoning = "fast"`, `fix_reasoning = "standard"`
  - `post_commit_batch_size = 5`
  - Concise, affirmative `review_guidelines`
- Hooks: native `roborev init --no-daemon` hooks (`post-commit`, `post-rewrite`,
  `pre-push`) in each repo's `.git/hooks/`. Global `core.hooksPath` and Copilot
  CLI's `~/.copilot/hooks/agenthook.json` remain unset/removed to prevent
  recursive review loops.
- Forge workspace execution (`scripts/pi-extensions/forge-workspace.ts`):
  - Preserves `KENN_FORGE_RUNTIME_SESSION_KEY` across `scripts/pi-local.py` (with API fallback by workspace ID) so Forge tracks live Pi session activity.
  - Filters parent repo `AGENTS.md` files from child worktrees under `.local/environment/forge/worktrees/`.
  - Overrides `superpowers:brainstorming`, `superpowers:writing-plans`, and `superpowers:finishing-a-development-branch` so workspace agents execute autonomously without mid-task approval stops, run a single `roborev review --branch --wait` + at most one fix pass, scale PR descriptions via `gemini-4-argon`, and register PR/Kata targets with Forge.
  - Seeds `.local/environment/home/.gitconfig` and `.config/git/ignore`, and exposes `jq` (`.local/tools/jq-1.7.1/bin`) and shared Python test dependencies (`.local/tools/pydeps`) on `PATH`/`PYTHONPATH`.

## Task-bound evidence consumer

`engineer-task-context` (`src/engineer_context/`, CLI `engineer-context`, stdio
MCP `engineer-context-mcp`) composes `engineer.task-context/v1` packets from the
Librarian MCP server and the owning Knowitall `knowitall.code-context/v1`
provider. Routing is explicit per `engineer.context-config/v1`; the consumer
never discovers providers, writes provider state, or mutates a task.

Provider facts to respect when extending it: Librarian identity is
`the-librarian` 0.3.0, requires fresh `status` and returns exactly one JSON
`TextContent`; `search` is discovery only. Knowitall is
`knowitall-code-context` 0.1.0 over `PublicationStore`, with `resolve_current`
pinned once per packet and exact selectors for follow-ups. Librarian exposes no
project UID or generation token, so configured business identity stays distinct
from provider-asserted code identity, and associations never exceed
`unasserted`. Assertions and contributions remain unavailable pending
`the_librarian#923h` and `the_librarian#rjr5`; do not invent those contracts.

Interpreter and server program paths in the configuration are absolutized
lexically rather than resolved, because dereferencing a virtual environment's
`bin/python` changes the child's prefix and breaks the Knowitall bridge. Corpus,
store, reader and selection paths are still fully resolved. They are treated as
paths only, so spaces are allowed and no launch goes through a shell. The
Librarian launch sends `--root` and, when selected, `--manifest`; the current
toolkit loads its reader from `tools.context_index` under that root and rejects
`--reader`, so `librarian.reader` and `setup --librarian-reader` stay optional
and exist only for a legacy release that requires that argument. The provider
advertises the same `the-librarian` 0.3.0 identity under both contracts, so an
identity check cannot distinguish them.
`src/engineer_context/bridge.py` is executed by path on the provider
interpreter and imports nothing from `engineer_context`, so Engineer and
Knowitall can live in separate private environments; its fixed `REASONS`
vocabulary diagnoses a missing provider package, unpublished store, rejected
request, invalid response or exceeded budget without echoing provider text.
Because each exchange is a fresh process, the bridge passes the owning
`QueryService` a store-bound `continuation_secret` derived from the resolved
store path; a random per-process key would reject every page token the previous
response issued, and the token only selects an offset inside a binding the
holder can already query. A continuation token is bound to the whole selector
that issued it, so collection and revalidation replay a paged request unchanged
and verify generation identity separately: revalidation uses a pinned probe,
and collection compares the resolved identity with the pinned generation after
the response. Collection otherwise pins the first `current` resolution onto
later `current` queries, skipping every page of a supplied chain, including its
first page: repinning one page would make the provider issue different tokens
and break the chain.

A page is partial evidence by itself, so readiness requires the packet to hold
the whole page chain for that query and generation: every carried token must
match a page in the packet, and every issued token must have its successor
there too. Missing neighbours are reported as absent pages rather than treated
as a complete observation. Pagination therefore no longer blocks an individual
page during revalidation, where the digest comparison already proves the page
is unchanged. When a provider refuses a cursor during revalidation, the held
request was accepted at collection, so this is changed provider state and the
check is reported as stale rather than raised as caller input.

The consumer also checks a code request against the owning request shape
(required fields, selector variant, query kind, enumerations, relationship
lists, repository-relative paths and one-based positions) before any provider
exchange, so an unreachable provider cannot turn caller input into an
availability gap. A contract rejection is likewise caller input: the bridge
translates the owning `invalid_request` status, which also answers a cursor
whose binding changed, into `request-invalid`, which surfaces as
`InvalidCodeRequest` and exits 1 rather than appearing as a scoped provider
gap. The owning validator in the bridge remains authoritative.

Actual-provider verification lives in `tests/integration/` and fails rather
than skips when `ENGINEER_LIBRARIAN_SOURCE`, `ENGINEER_KNOWITALL_SOURCE` or
`KNOWITALL_GRAPHIFY_RUNTIME` is absent. Fixtures are built only through owning
supported APIs: Librarian `package.release_paths` plus `tools/initialize.py`,
and Knowitall `create_snapshot`/`extract_generation`/`PublicationStore`. Use the
pinned offline Graphify runtime (`graphifyy==0.9.96`) and non-identifying
fixtures only; never point tests at the Falcon corpus or a production index.

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
  PYTHONPATH=tests/integration python -m unittest test_context_real_providers
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
