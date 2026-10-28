# Engineer: local engineering environment

A persistent Linux environment for local engineering workflows and a
human-directed three-product engineering demo. It combines Forge, Pi,
Superpowers, roborev, Kata, and AgentsView with the Falcon Context MCP server
and USAi LiteLLM as the required model provider.

The selected product name is **Engineer** (`engineer`), formerly Engi Platform
and Kenn Kopy. Checkout paths (`~/kenn-kopy`), the `engi-platform` Kata
project, and `kenn-kopy-*` systemd unit names remain in use until the planned
identity migration (`eb48`).

- Current service state and active priorities: [context/status.md](context/status.md)
- Project objectives and product boundaries: [context/project.md](context/project.md)
- Tooling, builds, and runtime configuration: [context/tools.md](context/tools.md)
- Workflow and prompt boundaries: [context/engineering-workflow.md](context/engineering-workflow.md)
- Cross-product system architecture: [context/system-architecture.md](context/system-architecture.md)
- Selective engineering memory design: [context/engineering-memory.md](context/engineering-memory.md)
- Simplification and refactoring slices: [context/refactoring.md](context/refactoring.md)

## Standalone agent terminals

Use existing Zed or any WSL terminal with `scripts/terminal-local.py` (backed by
an isolated tmux socket under `.local/environment/runtime/terminal/tmux.sock`):

```sh
python3 scripts/terminal-local.py open pi
python3 scripts/terminal-local.py open copilot
python3 scripts/terminal-local.py list
python3 scripts/terminal-local.py stop pi
```

Inside the `pi` session, run `python3 scripts/pi-local.py` to launch the
isolated Pi/USAi profile with its Falcon and Kata MCP configuration. Inside the
`copilot` session, run `copilot` with its native authentication and session
store. Keep sensitive USAi model work in `pi-local.py`.

## Start and access the environment

On this WSL host, Forge, Kata, roborev, and AgentsView run as independent user
systemd services bound to loopback:

| Application | Local browser address | Unit |
| --- | --- | --- |
| Forge: repository/workspace console | http://127.0.0.1:18091/ | `kenn-kopy-forge.service` |
| roborev: reviews | http://127.0.0.1:17374/reviews (API `17373`) | `kenn-kopy-roborev.service` |
| Kata: tasks | http://127.0.0.1:17777/kata | `kenn-kopy-kata.service` |
| AgentsView: sessions and usage | http://127.0.0.1:18080/ | `kenn-kopy-agentsview.service` |

Check live service health and registered projects:

```sh
python3 scripts/local_env.py status
```

Manage the user services with `systemctl --user`:

```sh
systemctl --user start kenn-kopy-kata.service kenn-kopy-roborev.service \
  kenn-kopy-agentsview.service kenn-kopy-forge.service
systemctl --user status kenn-kopy-forge.service --no-pager
```

On hosts without user systemd units enabled, `python3 scripts/local_env.py run`
starts any unmanaged services in the foreground, and
`python3 scripts/local_env.py stop` stops only the foreground supervisor.

## Kata tasks for Engineer

Kata project `engi-platform` is the task authority for this repository
(`.kata.toml` binds the checkout; data lives in `.local/environment/kata/kata.db`).

```sh
kata list --agent
kata ready --no-label blocked --no-label deferred --agent
kata show 5xrm
```

`dist/install.py` provisions `~/.local/bin/kata` and points `~/.kata/config.toml`
at `http://127.0.0.1:17777`. Neighboring repositories bind to their own Kata
projects (`librarian` in `~/the_librarian`, `knowitall` in `~/the_knowitall`,
`falcon-docs` in `~/falcon-docs`, `spud` in `~/aos-spud`, and the four Falcon
application projects under `~/falcon/`).

### From a Kata to a Forge agent

1. Claim ready work in Kata (`kata claim <id>`).
2. Ensure the project is mapped in **Forge Settings > Kata mappings** (`local`
   maps `engi-platform` to `GSA/the_engineer`, `librarian` to
   `GSA/the_librarian`, `knowitall` to `GSA/the_knowitall`, and `spud` to
   `GSA/aos-spud`).
3. In **Forge > Workspaces > New workspace**, select the task and launch **Pi
   (USAi)**.
4. Record verification evidence and close the issue in native Kata when done.

See [Kata to Forge pickup](context/engineering-workflow.md#kata-to-forge-current-pickup-boundary-2026-10-26)
and [provider onboarding](context/engineering-workflow.md#private-provider-onboarding-2026-10-26-1741-7943).

### Pi and Copilot task access

Both `.pi/mcp.json` and `.github/mcp.json` invoke native `kata mcp serve`
against `http://127.0.0.1:17777`. Use `kata.load_*` section loaders when MCP
tools are needed, or run the `kata` CLI directly.

## AgentsView session tracking

Open **http://127.0.0.1:18080/**. AgentsView archives sessions from
`~/.copilot`, `~/.pi/agent/sessions`, and `.local/environment/pi/sessions` under
the `transcripts` policy (conversation text, session metadata, and token usage
without raw tool payloads). Guarded USAi GPT aliases
(`gpt-5.6-sol-latest-guardrails-defaultv2` and
`gpt-6.1-sol-latest-guardrails-defaultv2`) reuse canonical base-model pricing.

Configure or reinstall the service with:

```sh
python3 scripts/local_env.py configure-tracking \
  --copilot-dir "$HOME/.copilot" \
  --pi-dir "$HOME/.pi/agent/sessions" \
  --pi-dir "$PWD/.local/environment/pi/sessions" \
  --archive-content transcripts
python3 scripts/local_env.py install-agentsview-service
```

## roborev code review

`kenn-kopy-roborev.service` runs native `~/.local/bin/roborev` (`v0.73.0`) on
`127.0.0.1:17373` (UI at `http://127.0.0.1:17374/reviews`). `~/.roborev` links
to `.local/environment/roborev/`, so native `roborev` CLI commands and Git hooks
use the same loopback daemon and SQLite store directly:

```sh
roborev status
roborev tui
roborev review --repo /absolute/path/to/repo --type default --agent pi --panel none --reasoning fast --wait
```

Install the Pi structured-output and subagent extensions in the isolated Pi
profile with:

```sh
python3 scripts/local_env.py install-pi-extensions
```

### Native batched Git hooks

Repositories use native `roborev init --no-daemon` hooks (`post-commit`,
`post-rewrite`, and `pre-push` in `.git/hooks/`) paired with a machine-local
`.roborev.toml` that sets `post_commit_batch_size = 5` and affirmative
`review_guidelines`:

```sh
roborev init --no-daemon --repo /absolute/path/to/repo
```

Commits run without synchronous pre-commit review blocks, batch every 5 commits
for background Pi/USAi review, and flush remaining unreviewed commits on
`git push`. Copilot CLI's global `agenthook.json` stays disabled so review
workers never re-enter active interactive sessions.

## First-time setup and GSA GitHub authentication

Use [`dist/install.sh`](dist/README.md) or run setup directly against an
existing Librarian checkout and built Forge binary:

```sh
python3 scripts/local_env.py setup \
  --corpus "$HOME/falcon-docs" \
  --forge-binary .local/forge-local-kata/kenn-forge
```

Authenticate Forge's isolated GitHub CLI profile (`.local/environment/gh/`) in
your own terminal:

```sh
./scripts/gh-local.py auth login --hostname github.com --web \
  --git-protocol https --insecure-storage
./scripts/gh-local.py api --hostname github.com user --jq .login
systemctl --user restart kenn-kopy-forge.service
```

## Persistence and projects

All local runtime state lives under ignored **`.local/environment/`**:

| Path under `.local/environment/` | Contents |
| --- | --- |
| `environment.json` | Machine-local executable and corpus paths |
| `forge/config.toml`, `forge/forge.db` | Forge settings and project/worktree records |
| `pi/` | Isolated Pi settings, MCP/model configuration, and session files |
| `roborev/`, `kata/`, `agentsview/` | Persistent service configurations and SQLite stores |
| `systemd/`, `*-service.json` | Generated user units and ownership metadata |
| `gh/` | Isolated GitHub CLI configuration used by Forge |
| `secrets/usai-api-key` | Private USAi API key (`0600`) |

Create a verified workspace backup archive with:

```sh
python3 scripts/backup_workspace.py \
  '/mnt/c/Users/NKIRRISH/OneDrive - CGI Federal, Inc/EngiPlatformBackups'
```

Register an additional local Git repository in Forge with:

```sh
python3 scripts/local_env.py register /absolute/path/to/project
```

## Pi, subagents, and Falcon Context MCP

Launch the isolated Pi/USAi agent from any project directory:

```sh
python3 /home/nkirrish/kenn-kopy/scripts/pi-local.py
```

Both `.local/environment/pi/settings.json` and `~/.pi/agent/settings.json`
configure `pi-subagents` with `defaultProvider: "usai"`,
`defaultModel: "inherit"`, `modelScope.allow: ["inherit", "usai/*"]`, and
`model: "inherit"` across `delegate`, `oracle`, `reviewer`, `scout`, and
`worker`.

Verify the Falcon Context MCP connection from this checkout:

```sh
python3 scripts/pi-local.py mcp list
node scripts/check-pi-mcp.mjs
```

## USAi credential and provider setup

Store or rotate the USAi API key interactively (updates `.local/environment/secrets/usai-api-key`
and links existing global `~/.pi/agent` USAi provider entries to `scripts/usai-key.py`):

```sh
python3 scripts/local_env.py set-key
```

Refresh advertised model IDs and configure the active USAi model:

```sh
python3 scripts/local_env.py list-models --base-url 'https://api.gsa.usai.gov/api/v1'
python3 scripts/local_env.py configure-provider \
  --base-url 'https://api.gsa.usai.gov/api/v1' \
  --model 'claude-opus-5' \
  --api 'openai-completions'
```

## Disposable smoke checks

Stop the four user services before running `scripts/smoke.py` (which binds the
same loopback ports in a temporary `.local/smoke-*` directory), then restart
them afterward:

```sh
systemctl --user stop kenn-kopy-kata.service kenn-kopy-roborev.service \
  kenn-kopy-agentsview.service kenn-kopy-forge.service
python3 scripts/smoke.py --forge-binary .local/forge-local-kata/kenn-forge
systemctl --user start kenn-kopy-kata.service kenn-kopy-roborev.service \
  kenn-kopy-agentsview.service kenn-kopy-forge.service
```
