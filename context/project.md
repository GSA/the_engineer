# Project context

## Purpose

**Engineer** (`engineer`, repository `GSA/the_engineer`, teammate checkout
`~/engineer`) provides the persistent local engineering
environment and operator console for a human-directed, two-product federal
engineering workflow:

1. **Librarian** (`GSA/the_librarian`): documentation and review-state corpus
   platform (`falcon-librarian` CLI and MCP server). It is owner-only and
   optional today; teammate installs have no Librarian or corpus, and no
   Engineer code path requires one. It becomes a remote MCP server with its
   own installer under `the_librarian#a4ra` (hosting in `jmga`).
2. **Engineer** (`GSA/the_engineer`): local orchestration across
   Forge, Pi (`usai`), Superpowers, roborev, Kata, and AgentsView.

Engineer owns the stdlib-only cross-repository seam scanner
(`src/engineer_context/seams.py`) for code that crosses repository boundaries.

## Product identity

- Product name: **Engineer** (`engineer`) in user-facing documentation and UI
  copy.
- Kata projects match repository names (`the_engineer`, `the_librarian`).
- Installs use `engineer-*.service` units (`unit_prefix = "engineer"` in
  `environment.json`).
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
  batched commit reviews. The delivery review budget and dispositions are in
  `context/engineering-workflow.md#bounded-delivery-review-and-dispositions`.
- **Network and credentials**: All local services bind to `127.0.0.1`. Keep keys,
  tokens, and corpus/user state inside ignored `.local/` paths.

## Where knowledge lives

| Store | What belongs here |
| --- | --- |
| `AGENTS.md` + `context/*.md` | Current-state operating agreements, tool commands and the active status summary, updated in place. |
| **Kata** (`http://127.0.0.1:17777`) | Actionable work items, dependencies, claims and closure evidence. |
| **Librarian** (`falcon-librarian`, optional) | Versioned corpus documents and recorded review coverage. |
| **AgentsView** (`http://127.0.0.1:18080`) | Session transcripts and token/cost telemetry. |
