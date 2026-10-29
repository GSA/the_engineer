# Tools and environment reference

## Service endpoints and systemd units

All four persistent services run under user systemd and bind to `127.0.0.1`:

| Service | Loopback endpoint | Systemd unit | Persistent data under `.local/environment/` |
| --- | --- | --- | --- |
| Kata (`v0.19.1`) | `http://127.0.0.1:17777/kata` | `kenn-kopy-kata.service` | `kata/kata.db` |
| roborev (`v0.73.0`) | `http://127.0.0.1:17374/reviews` (API `17373`) | `kenn-kopy-roborev.service` | `roborev/config.toml`, `roborev/reviews.db` |
| AgentsView (`v0.26.0`) | `http://127.0.0.1:18080/` | `kenn-kopy-agentsview.service` | `agentsview/data/sessions.db` |
| Forge | `http://127.0.0.1:18091/` (MCP `http://127.0.0.1:18092/mcp`) | `kenn-kopy-forge.service` | `forge/config.toml`, `forge/forge.db` |

Check live health across all four services with:

```sh
python3 scripts/local_env.py status
```

## CLI binaries and wrappers

- `kata` (`~/.local/bin/kata` -> `/home/nkirrish/kenn-kopy/kata/target/release/kata`):
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
- `python3 scripts/terminal-local.py`: manages persistent local `pi` and
  `copilot` tmux sessions via `.local/environment/runtime/terminal/tmux.sock`.

## Pi and subagent configuration

`scripts/local_env.py` writes `default_pi_subagents_settings()` into
`.local/environment/pi/settings.json` (and mirrors it in `~/.pi/agent/settings.json`
for standalone `pi` invocations):

- `defaultProvider`: `"usai"`
- `defaultModel`: `"inherit"`
- `modelScope.allow`: `["inherit", "usai/*"]`
- Built-in profiles (`delegate`, `oracle`, `reviewer`, `scout`, `worker`):
  `model: "inherit"`
- Tool overrides (`PI_SUBAGENT_DESCRIPTIONS`): instruct agents to omit `model`
  or pass `"inherit"`, omit `model` on `action: "resume"`, and keep Superpowers
  `reviewer` subagents separate from native `roborev` CLI reviews.

## roborev configuration and hooks

- Global config (`.local/environment/roborev/config.toml` via `~/.roborev`):
  `server_addr = "127.0.0.1:17373"`, `default_agent = "pi"`,
  `default_model = "usai/claude-opus-4-6"`, `review_Reasoning = "fast"`,
  `ci.synthesis_agent = "pi"`, `ci.synthesis_model = "usai/claude-opus-4-6"`.
- Per-repository `.roborev.toml` (installed in `kenn-kopy`, `the_librarian`,
  `the_knowitall`, `falcon-docs`, and `falcon/{backend,frontend,exec-dashboard,mcp}`):
  - `agent = "pi"`, `review_reasoning = "fast"`, `fix_reasoning = "standard"`
  - `post_commit_batch_size = 5`
  - Concise, affirmative `review_guidelines`
- Hooks: native `roborev init --no-daemon` hooks (`post-commit`, `post-rewrite`,
  `pre-push`) in each repo's `.git/hooks/`. Global `core.hooksPath` and Copilot
  CLI's `~/.copilot/hooks/agenthook.json` remain unset/removed to prevent
  recursive review loops.

## Build and test commands

- Engineer Python scripts and unit tests:
  ```sh
  python3 -m unittest discover -s scripts -p 'test_*.py'
  python3 -m unittest discover -s dist -p 'test_*.py'
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
