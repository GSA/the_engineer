# Project context

## Purpose

**Engineer** (`engineer`, repository `GSA/the_engineer`, local checkout
`/home/nkirrish/kenn-kopy`) provides the persistent local engineering
environment and operator console for a human-directed, three-product federal
engineering workflow:

1. **Librarian** (`GSA/the_librarian`, `~/the_librarian`): Falcon documentation
   and review-state corpus platform (`falcon-context` CLI and MCP server),
   evaluated against the historical `~/falcon-docs` packet and live Falcon
   application repositories under `~/falcon/`.
2. **Engineer** (`GSA/the_engineer`, `~/kenn-kopy`): local orchestration across
   Forge, Pi (`usai`), Superpowers, roborev, Kata, and AgentsView.
3. **Knowitall** (`GSA/the_knowitall`, `~/the_knowitall`): evidence-backed
   multi-source organizational intelligence platform (current implementation
   focus is Phase 1 architecture, terminology, and local stack scaffolding).

## Product identity

- Selected product name: **Engineer** (`engineer`), replacing Engi Platform and
  Kenn Kopy in user-facing documentation and UI copy.
- Checkout directory (`~/kenn-kopy`), Kata project key (`engi-platform`), and
  systemd unit prefix (`kenn-kopy-*`) remain stable until the scheduled
  runtime/identifier migration (`eb48`).

## Repository structure

- `scripts/local_env.py`: configures and inspects the persistent `.local/environment/`
  stack (Forge, Kata, roborev, AgentsView, Pi/USAi, and user systemd units).
- `scripts/pi-local.py`, `scripts/gh-local.py`, `scripts/terminal-local.py`,
  `scripts/usai-key.py`: targeted wrappers that isolate Pi, GitHub CLI, and
  tmux terminal sessions under `.local/environment/`.
- `scripts/backup_workspace.py`: builds and verifies reproducible tar.zst
  backups of workspace repos, SQLite databases, and local environment state.
- `dist/`: self-contained host bundle (`install.sh` / `install.py`) for
  reproducing the 3-product workspace on another Linux/WSL machine.
- `forge/`, `kata/`, `roborev/`, `agentsview/`, `superpowers/`: upstream source
  submodules (pinned commits; keep upstream checkouts clean unless maintaining
  an explicit tracked fork/build).
- `context/`: concise current-state reference documents for agents and
  operators.

## Core operating boundaries

- **Task authority**: Native Kata (`http://127.0.0.1:17777`, `~/.local/bin/kata`)
  is the single source of truth for issues across all workspace repositories via
  per-repo `.kata.toml` bindings.
- **Model provider**: Pi uses the GSA **USAi** LiteLLM endpoint
  (`https://api.gsa.usai.gov/api/v1`) with the private API key helper
  `scripts/usai-key.py` reading `.local/environment/secrets/usai-api-key`.
- **Subagent dispatch**: Both `.local/environment/pi/settings.json` and
  `~/.pi/agent/settings.json` set `pi-subagents` to `defaultProvider: "usai"`
  and `defaultModel: "inherit"` across `delegate`, `oracle`, `reviewer`,
  `scout`, and `worker`. Always omit `model` on `action: "resume"`.
- **Code review**: Repositories use native `roborev init --no-daemon` Git hooks
  (`post-commit`, `post-rewrite`, `pre-push`) with `post_commit_batch_size = 5`
  and affirmative `review_guidelines` in `.roborev.toml`. Superpowers
  `reviewer` subagents handle per-task implementation checks inside subagent
  workflows, while `roborev` handles commit and branch reviews asynchronously.
- **Network and credentials**: All local services bind to `127.0.0.1`. Keep keys,
  tokens, and corpus/user state inside ignored `.local/` paths.
