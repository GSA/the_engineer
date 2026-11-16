# Project context

## Purpose

**Engineer** (`engineer`, repository `GSA/the_engineer`, teammate checkout
`~/engineer`) provides the persistent local engineering
environment and operator console for a human-directed, two-product federal
engineering workflow:

1. **Librarian** (`GSA/the_librarian`, `~/the_librarian`): Falcon documentation
   and review-state corpus platform (`falcon-librarian` CLI and MCP server),
   evaluated against the historical `~/falcon-docs` packet and live Falcon
   application repositories under `~/falcon/`.
2. **Engineer** (`GSA/the_engineer`): local orchestration across
   Forge, Pi (`usai`), Superpowers, roborev, Kata, and AgentsView.

Knowitall (`GSA/the_knowitall`) is archived on GitHub and unregistered from
Forge. Engineer owns the stdlib-only cross-repository seam scanner
(`src/engineer_context/seams.py`) for code that crosses repository boundaries.

## Product identity

- Selected product name: **Engineer** (`engineer`), replacing Engi Platform and
  Kenn Kopy in user-facing documentation and UI copy.
- Kata projects match repository names (`the_engineer`, `the_librarian`).
- New installs use `engineer-*.service` units (`unit_prefix` in
  `environment.json`); the owner's original install keeps its legacy unit
  prefix and checkout path until an approved migration.
- Teammates use the `./engineer` front door (`scripts/engineer.py`): install,
  doctor, start/stop/status, key, models, login, add-repo, pi, copilot,
  update, uninstall. Pi and the optional Copilot CLI both use USAi.

## Repository structure

- `scripts/local_env.py`: configures and inspects the persistent `.local/environment/`
  stack (Forge, Kata, roborev, AgentsView, Pi/USAi, and user systemd units).
- `engineer` / `scripts/engineer.py`: teammate front door; `scripts/host_setup.py`
  (Ubuntu packages with consent, Node, Pi, Copilot CLI, `~/.bashrc` block) and
  `scripts/copilot_env.py` (private `COPILOT_HOME` on USAi BYOK).
- `scripts/pi-local.py`, `scripts/gh-local.py`, `scripts/terminal-local.py`,
  `scripts/usai-key.py`: targeted wrappers that isolate Pi, GitHub CLI, and
  tmux terminal sessions under `.local/environment/`.
- `dist/`: lower-level source-build installer (`install.sh` / `install.py`)
  that `./engineer install` runs, plus the fresh-host acceptance container.
- Owner-only Helix mirror/sync and OneDrive backup scripts live in the owner's
  private `engineer-owner-tools` repository, not here.
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
  (`post-commit`, `post-rewrite`, `pre-push`) with `post_commit_batch_size = 5`,
  `review_min_severity = "medium"`, `refine_min_severity = "medium"`,
  `fix_min_severity = "medium"`, and affirmative `review_guidelines` in
  `.roborev.toml`. Superpowers `reviewer` subagents handle per-task
  implementation checks inside subagent workflows, while `roborev` handles
  batched commit reviews. Delivery reuses unchanged-code evidence or allows
  one medium-threshold branch review plus one verified fix pass, with owner
  handoff instead of repeated reviews; see `context/engineering-workflow.md`.
- **Network and credentials**: All local services bind to `127.0.0.1`. Keep keys,
  tokens, and corpus/user state inside ignored `.local/` paths.
