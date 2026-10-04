# Upstream components

Exact source revisions are the parent repository's gitlinks:
`git submodule status`. Do not duplicate version pins in this document.

| Directory | Upstream | Role |
| --- | --- | --- |
| `roborev/` | https://github.com/kenn-io/roborev | Continuous code review |
| `superpowers/` | https://github.com/obra/superpowers | Agent skills and workflow |
| `forge/` | https://github.com/kenn-io/forge | Review and agent workspaces |
| `kata/` | https://github.com/kenn-io/kata | Task-tracking evaluation |
| `agentsview/` | https://github.com/kenn-io/agentsview | Session and token visibility |

Ghosthub was downloaded and then removed at the user's request because it
requires macOS.

# Build and runtime notes

These are observations from the pinned source, not proof of successful startup.

| Component | Build | Isolation and integration |
| --- | --- | --- |
| roborev | Go 1.27+, Bun 1.3.14; `make build` embeds its web UI | Default API is loopback port 7373. Do not run `roborev init` on real repos before configuring review agents: it installs a post-commit hook and starts a daemon. |
| Forge | Go 1.27+, Bun 1.4.0 per package manifest, Node; `make build` | `KENN_FORGE_HOME` isolates config/data. Foreground command is `kenn-forge serve`; default UI port 8091. Workspaces use Git and tmux. |
| Kata | Go 1.27+, Bun 1.3.14; `make build` | `KATA_HOME` isolates SQLite/config; `KATA_SERVER` selects a daemon. Supports CLI, TUI, web UI, task dependencies, MCP, and optional federation/Postgres. |
| AgentsView | Go 1.27+, CGO/C compiler, Node 24.11+; `make build` | `AGENTSVIEW_DATA_DIR` isolates the archive, but session discovery also needs an isolated home/source configuration. `AGENTSVIEW_NO_DAEMON=1` prevents implicit daemon startup. |
| Superpowers | Skill files and a Pi extension; no independent daemon | Package metadata declares `.pi/extensions/superpowers.ts` and `skills/`. Upstream documents `pi -e /path/to/superpowers` for a session-local trial. |

Forge connects to roborev through `[roborev].endpoint`, default
`http://127.0.0.1:7373`. It does not start roborev. Keep
`init_managed_clones` disabled during initial checks.

Forge discovers Kata's daemon catalog through `$KATA_HOME/config.toml`.
Task/workspace integration needs a connected, compatible daemon and repository
mappings; a running Kata process alone does not prove that integration works.

Forge uses Elastic License 2.0, which restricts providing substantial
functionality as a hosted/managed service to third parties. The user's scope
is personal/private deployment. Preserve all upstream license notices.

Pi 0.87.1 is already on this host's PATH. An isolated, offline RPC session
successfully loaded all 15 Superpowers skills. The Pi extension injects the
Superpowers bootstrap at startup and after compaction; the smoke test verifies
skill discovery, not model behavior or compaction execution.

Roborev has a Pi adapter. Structured reviews and classification additionally
require its configured JSON-schema extension, currently defaulting to
`npm:@nqbao/pi-json-schema@0.1.1`. That extension has not been installed or tested
here. AgentsView has a Pi session parser. Pi session ingestion and model-backed
reviews remain unverified.

# Pi and context MCP: not configured yet

As checked on 2026-10-04, the installed Pi is still 0.87.1. Its CLI does not
advertise `pi mcp`, and its versioned settings documentation has no native MCP
configuration. The published Pi 1.0.2 documents native stdio and Streamable HTTP
MCP support. Do not assume current upstream documentation applies to 0.87.1.

Proposed approach, pending confirmation of the server and Pi version:

1. Identify the intended context server, its transport, its launch command or
   endpoint, and how credentials will be injected. MCP tools available in
   Copilot are not automatically inherited by a separately launched Pi.
2. Prefer a pinned Pi release with native MCP over adding a bridge solely to
   retain 0.87.1. Verify Superpowers compatibility before adopting the upgrade;
   no upgrade or bridge installation has been performed.
3. On a compatible Pi, track secret-free project settings in `.pi/mcp.json`.
   Use `pi mcp add --local` with the confirmed stdio command or HTTP URL, and
   reference environment variables for secrets. Project MCP configuration
   requires project trust. Never set blanket global trust to bypass that gate.
4. Use `pi mcp list` to check the handshake and discovered tools. Then confirm
   the intended tool exposure through `/mcp` inside the actual Pi session and
   perform a harmless context search/read with a known expected result.
   Recheck after restart and compaction; a server being configured is not proof
   that Pi can invoke it.
5. Add a dedicated MCP smoke check. The current `smoke.py` deliberately uses a
   temporary working directory, isolated agent home, `--no-extensions`,
   `--no-context-files`, and `--no-tools`; its Superpowers check does not prove
   that a project MCP server is configured or accessible.

The local `context/` directory is just files, not an MCP server. Pi can read
these through its normal file tool following `AGENTS.md`. Which external
context MCP server the user intends remains an open question.

Sources:
[Pi 0.87.1 settings](https://github.com/earendil-works/pi/blob/v0.87.1/packages/coding-agent/docs/settings.md),
[Pi 1.0.2 MCP](https://github.com/earendil-works/pi/blob/v1.0.2/packages/coding-agent/docs/mcp.md).

# Local build and smoke commands

```sh
./scripts/bootstrap-sources.sh
./scripts/bootstrap-toolchains.sh
./scripts/build.sh roborev kata agentsview
./scripts/build.sh forge
python3 scripts/smoke.py
```

The current toolchain bootstrap supports Linux x86_64. It requires curl, tar,
sha256sum, and npm; builds also require make, a C compiler, and Node 24.11+.
Python 3 and an installed Pi are required for the smoke test. The observed host
has Node 26.9.0 and Pi 0.87.1; these host tools are not installed or pinned by
our bootstrap yet. This is not a hermetic build environment.

Go 1.27.1 is installed under `.local/tools/` after checking its official SHA-256.
Bun 1.3.14 and 1.4.0 are installed there as exact-version native npm packages,
with package scripts disabled. Neither bootstrap edits global settings.
`build.sh` uses frozen Bun lockfiles and AgentsView's upstream `npm ci`,
workspace-local caches, and two Go build workers per invocation. Its default
target list includes all four applications and stops at the first failure.
Pass target names to build the unblocked applications independently.

Roborev and Kata need `sqlite3.h` for sqlite-vec. Our build script stages the
header from each project's pinned go-sqlite3 module, following AgentsView's
existing Makefile pattern, rather than requiring a system-wide package change.
Forge's unfrozen frontend dependency prerequisite is skipped only after a
successful explicit frozen install; no upstream manifest or lockfile is edited.

`smoke.py` creates a fresh private `.local/smoke-*` directory on each run. It
clears inherited credentials/configuration through an explicit environment,
disables telemetry, runs daemons in the foreground, and always attempts
shutdown in `finally`. It does not start system services, install hooks, open a
browser, sync private sessions, or submit model requests.

| Service | Smoke address |
| --- | --- |
| roborev API | `http://127.0.0.1:17373/api/status` |
| roborev UI | `http://127.0.0.1:17374/reviews` |
| Kata API | `http://127.0.0.1:17777/api/v1/health` |
| Kata UI | `http://127.0.0.1:17777/kata` |
| AgentsView API/UI | `http://127.0.0.1:18080` |
| Forge API/UI, when built | `http://127.0.0.1:18091` |

An occupied port fails the affected startup rather than replacing its owner.
UI probes send `Accept: text/html` and fetch the embedded JavaScript entry
points. These are HTTP/asset checks, not browser-rendering tests. Kata's test
creates and reads a synthetic task. Pi runs offline RPC with the explicit
Superpowers package while the available daemons are running.

Forge is configured to use the smoke roborev endpoint, but this connection is
not verified while Forge is blocked. Provider sync and AgentsView ingestion are
disabled in the smoke test. The script exits nonzero for any blocked or failed
check, including a missing Forge binary, and writes local `results.json` plus
per-service logs before exiting.

# Source references

- `roborev/Makefile`, `roborev/docs/configuration.md`
- `forge/Makefile`, `forge/docs/configuration.md`, `forge/docs/integrations.md`
- `kata/Makefile`, `kata/docs/reference/configuration.md`
- `agentsview/Makefile`, `agentsview/docs/configuration.md`
- `superpowers/README.md`, `superpowers/package.json`
