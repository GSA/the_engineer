# Engineering workflow and prompt boundaries

## Core workflow loop

1. **Discover and claim in Kata**: inspect ready issues (`kata ready --no-label blocked --no-label deferred --agent`), read the issue (`kata show <id>`), and claim it (`kata claim <id>`) before editing code.
2. **Execute in an isolated worktree or checkout**: launch a Forge workspace (`Pi (USAi)`) or work in the bound repository checkout using `scripts/pi-local.py` or Copilot CLI.
3. **Validate incrementally**: run targeted unit/integration tests for each change and commit coherent slices locally.
4. **Review asynchronously via native `roborev`**: native `post-commit` hooks batch every 5 commits (`post_commit_batch_size = 5`) into a single background `roborev` job and flush any unreviewed commits on `git push`.
5. **Close in Kata with evidence**: record test and commit evidence in Kata (`kata close <id> --reason "..."`) and update `context/status.md` when a milestone completes.

## Subagents vs. `roborev`

- **Pi `subagent` tool (`pi-subagents`)**:
  - Uses `defaultProvider: "usai"` and `defaultModel: "inherit"` across
    `delegate`, `oracle`, `reviewer`, `scout`, and `worker`.
  - When calling `subagent` with `action: "run"`, `action: "chain"`, or
    `action: "parallel"`, omit `model` or set `model: "inherit"` (or an active
    `usai/*` model ID).
  - When calling `subagent` with `action: "resume"`, always omit `model` (`resume`
    reuses the existing session's model and rejects `model` overrides).
  - Use the `reviewer` subagent profile only when a Superpowers implementation
    skill (`subagent-driven-development` or `executing-plans`) checks a task
    against its task spec before moving to the next task.
- **Native `roborev` CLI and Git hooks**:
  - Handles repository commit and branch code reviews (`roborev status`,
    `roborev show <job_id>`, `roborev review --branch`).
  - Let the native `post-commit` hook (batched every 5 commits) and `pre-push`
    hook enqueue commit reviews automatically instead of running manual
    `roborev review --dirty --wait` loops before every commit.

## Writing context and instructions

- Write `AGENTS.md`, `README.md`, `context/*.md`, and `.roborev.toml`
  `review_guidelines` in **affirmative, current-state language** (state what the
  code and operator should do now).
- Avoid negative-constraint lists (`"X is NOT Y"`, `"do NOT treat X as Y"`) that
  pollute LLM attention with out-of-scope concepts.
- Update `context/project.md`, `context/tools.md`, and `context/status.md` in
  place rather than prepending dated session logs.

<a id="kata-to-forge-current-pickup-boundary-2026-10-26"></a>
## Kata to Forge pickup

- **Kata (`http://127.0.0.1:17777/kata`)** is the authoritative task tracker.
- **Forge (`http://127.0.0.1:18091/`)** maps local repositories to Kata project
  keys via **Settings > Kata mappings** (`local` connection: `engi-platform` ->
  `GSA/the_engineer`, `librarian` -> `GSA/the_librarian`, `knowitall` ->
  `GSA/the_knowitall`, `spud` -> `GSA/aos-spud`).
- Picking up a Kata task in **Forge > Workspaces > New workspace** creates an
  isolated Git worktree and seeds the initial agent prompt with the Kata issue
  ID, title, and description. Status transitions (`claim`, `close`) remain
  explicit in Kata (`kata claim <id>`, `kata close <id>`).

<a id="private-provider-onboarding-2026-10-26-1741-7943"></a>
## Private provider onboarding

- **Pi (`usai`)**: configured in `.local/environment/pi/models.json` and
  `settings.json` via `python3 scripts/local_env.py set-key` and
  `configure-provider`. The API key is stored at
  `.local/environment/secrets/usai-api-key` (`0600`) and read on demand via
  `!python3 /home/nkirrish/kenn-kopy/scripts/usai-key.py`.
- **GitHub CLI (`gh`)**: isolated under `.local/environment/gh/` via
  `./scripts/gh-local.py auth login`.
- **Copilot CLI**: runs in standalone terminals (`scripts/terminal-local.py open copilot`)
  using the user's native GitHub Copilot authentication for non-sensitive work.
