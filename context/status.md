# Current status

## Live environment state

- All four user systemd units are running on loopback:
  - `kenn-kopy-kata.service` (`http://127.0.0.1:17777/kata`)
  - `kenn-kopy-roborev.service` (`http://127.0.0.1:17374/reviews`, API `17373`)
  - `kenn-kopy-agentsview.service` (`http://127.0.0.1:18080/`)
  - `kenn-kopy-forge.service` (`http://127.0.0.1:18091/`)
- Registered Forge repositories: `the_engineer` (`kenn-kopy`), `the_librarian`,
  `the_knowitall`, `falcon-docs`, `aos-spud`, and the four Falcon application
  repositories under `~/falcon/`.
- Active USAi default model in `.local/environment/pi/settings.json`:
  `claude-opus-5` (`https://api.gsa.usai.gov/api/v1`, `openai-completions`).

## Recent completed milestones

- **USAi subagent inheritance and review workflow simplification (`sb77`, `sc6x`, `qc96`)**:
  - Configured `pi-subagents` in `.local/environment/pi/settings.json` and
    `~/.pi/agent/settings.json` to inherit the active `usai/*` session model by
    default and documented `action: "resume"` and `reviewer` vs. `roborev`
    boundaries in `PI_SUBAGENT_DESCRIPTIONS`.
  - Disabled `~/.copilot/hooks/agenthook.json`, cleared global/repo custom hook
    wrappers, installed native `roborev init --no-daemon` hooks across all 8
    workspace repos, and configured `post_commit_batch_size = 5` with concise,
    affirmative `review_guidelines` in `.roborev.toml`.
  - Removed `scripts/roborev-local.py`, `scripts/roborev_hooks.py`, and
    `the_librarian`'s custom `pre-commit` review gate and negative-disclaimer
    context bloat (`the_librarian` commit `876dfcd`, `the_knowitall` commit
    `a6a17b3`).
  - Compacted `kenn-kopy/context/*.md` into concise current-state reference
    documents under 16 KiB each.
- **Selective engineering memory and workspace backup (`5xrm`, `bc20`)**:
  - Documented the selective engineering memory architecture (`context/engineering-memory.md`)
    and added `dist/hindsight.compose.yaml` (`5xrm` awaits owner approval of the
    Phase 1 contract).
  - Verified `scripts/backup_workspace.py` archive generation (`bc20`).

## Active Kata queue (`engi-platform`)

- `2jgk` (`in_progress`): Refactor and simplify `the_engineer` codebase and
  scripts (active in Forge worktree `.local/environment/forge/worktrees/kenn-forge/work-7d57d583`).
- `5xrm` (`open`, `blocked` on owner approval): Design selective engineering
  memory and decision log.
- `eb48` (`open`): Rename runtime identifiers from `kenn-kopy`/`engi-platform`
  to `engineer`.
- Ready unblocked follow-ups (`kata ready --no-label blocked --no-label deferred --agent`):
  `t14m` (reconcile `dist/install.py` with systemd service topology), `k03a`
  (curate Superpowers skills in Pi), `zmzh` (curate installed Pi extensions),
  `025n` (verify Forge terminal click-to-type focus in live browser), and `pcrv`
  (harden USAi provider model discovery).
