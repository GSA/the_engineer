# Current status

## Live environment state

- All four user systemd units are running on loopback:
  - `kenn-kopy-kata.service` (`http://127.0.0.1:17777/kata`, `v0.20.0-37-g14844737`, schema 34, API `0.34.0`)
  - `kenn-kopy-roborev.service` (`http://127.0.0.1:17374/reviews`, API `17373`, `v0.74.0-23-gd53ecfca`)
  - `kenn-kopy-agentsview.service` (`http://127.0.0.1:18080/`, `v0.46.1-84-gc7f77ad0`)
  - `kenn-kopy-forge.service` (`http://127.0.0.1:18091/`, MCP `http://127.0.0.1:18092/mcp`, `v0.5.1-118-gbf025d22-local-kata`)
- Registered Forge repositories and projects (`Engineer`, `Librarian`,
  `Knowitall`, `SPUD`, `falcon-docs`, and `falcon/{backend,frontend,exec-dashboard,mcp}`):
  all 4 primary projects (`Engineer`, `Librarian`, `Knowitall`, `SPUD`) are
  linked to their GitHub `platform_identity` and Kata project mappings
  (`the_engineer`, `the_librarian`, `the_knowitall`, `spud`).
- Active USAi paired coder/reviewer models in `.local/environment/usai.json`,
  `.local/environment/pi/settings.json`, and `.local/environment/roborev/config.toml`:
  coder = `claude-opus-5.5` (with `pi-argon` / `gemini-4-argon` also enabled as a
  first-class Forge workspace agent target), reviewer =
  `gpt-6.1-sol-latest-guardrails-defaultv2` (`https://api.gsa.usai.gov/api/v1`,
  `openai-completions`), with all 25 advertised USAi chat models synced into
  `.local/environment/pi/models.json` (excluding `cohere_english_v3` and
  `text-embedding-005`), `gemini-4-argon` configured for concise PR body
  summarization in `forge-workspace.ts`, and `compat.supportsDeveloperRole = false`
  across all USAi model definitions.

## Recent completed milestones

- **Forge pin `bf025d22` (`v0.5.1-118`)**:
  - `scripts/build-forge-local-kata.mjs` builds with Bun 1.4.4, substitutes
    local Kata Go `v0.20.0` (`976cd155`) and Kata UI `v0.19.0`, and passes an
    empty `POSTHOG_PROJECT_KEY` so the binary carries no telemetry destination;
    the service environment also keeps `TELEMETRY_ENABLED=0`.
  - Upstream fixed the workspace-target MCP output schemas, so the local
    `tools_workspace_targets.go` patch is removed. Config, `serve` flags, the
    MCP listener on `18092`, and the agent-hook/agent-sessions APIs are unchanged.
  - Verified with the build script's Bun tests, 177 script and 52 distribution
    unit tests, `smoke.py --only-forge`, a live MCP `tools/list` and
    `kenn_forge_list_workspace_targets` call, and a clean GitHub sync. Forge's
    hot spares were re-prepared at the rewritten `origin/HEAD` commits.

- **Task-bound business and code evidence consumer (`k4mp`)**:
  - Added `engineer-task-context` (`src/engineer_context/`, CLI
    `engineer-context`, stdio MCP `engineer-context-mcp`), which composes
    `engineer.task-context/v1` packets from the configured Librarian corpus and
    a revision-bound Knowitall generation, reports provenance and readiness, and
    rechecks a sealed packet with `revalidate`. Collection is read-only and
    never writes provider state or mutates a task.
  - Integrated preserved commit `dae66cd` (explicit Librarian binding) as merge
    `b75210c`; branch review job 313 passed it with no findings.
  - Required paged code queries are ready only with the whole page chain;
    malformed requests and refused cursors are caller input (exit 1), while a
    cursor refused during revalidation is reported as changed provider state.
  - Interpreter and server program paths are absolutized lexically, because
    resolving a virtual environment's `bin/python` symlink changed the child's
    prefix and broke the Knowitall bridge.
  - Verified with 58 consumer tests, 10 actual-provider integration tests
    against the Librarian release and pinned Knowitall `81cc9b2` with the
    offline Graphify runtime, 122 local-environment tests, 52 distribution tests
    (4 expected skips), a Pi runtime receipt with `model_requests: 0` and
    `configured_mcp_servers: 0`, plus
    build, compile and whitespace checks. Branch review job 384 passed;
    delivered as https://github.com/GSA/the_engineer/pull/4.
  - Merged current `main` into the branch, keeping main's compacted docs,
    configurable ports (`KENN_KOPY_PORT_OFFSET`) and roborev wrapper removal,
    and re-applying the explicit Librarian binding so `setup` preserves the
    other saved `pi/mcp.json` servers. Branch review job 399 passed.
  - Upstream Librarian `f4c8500` dropped `--reader` from `librarian-mcp` and
    moved the reader to the `tools.context_index` module under `--root`, so the
    consumer binding and `setup --librarian-reader` now treat the reader as an
    optional legacy argument and omit it by default. All 10 actual-provider
    integration tests pass against the current checkout, and the Pi probe now
    supplies the MCP extension an explicit empty configuration and private log
    path, because its default loader reads the operator agent directory rather
    than the session's.
  - Assertions and contributions stay unavailable pending `the_librarian#923h`
    and `the_librarian#rjr5`, so associations remain `unasserted` and `k4mp`
    stays open. Public tests are non-identifying; real corpus/ticket use, model
    traffic and restricted-evidence publication keep separate owner gates.

- **USAi model catalog sync and adversarial coder/reviewer pairing (`zmzh`)**:
  - Refreshed `.local/environment/usai-models.json` from live
    `https://api.gsa.usai.gov/api/v1/models` (27 advertised models) and updated
    `scripts/local_env.py:configure_provider()` to populate all 25 USAi chat
    models into `.local/environment/pi/models.json` while excluding embedding
    models (`cohere_english_v3`, `text-embedding-005`).
  - Added `--review-model` to `configure-provider`, opposite-family (`claude` /
    `openai` / `gemini`) validation in `validate_paired_models()` and
    `validate_roborev_config()`, `roborev/config.toml` `default_model` /
    `review_model` synchronization, `pi_launch()` support for the configured
    `review_model` and `gemini-4-argon`, and `model_routing` reporting in
    `local_env.py status`.
  - Configured live environment with `claude-opus-5.5` on default Forge coders,
    `pi-argon` (`gemini-4-argon`) as an enabled alternate Forge coder target, and
    `gpt-6.1-sol-latest-guardrails-defaultv2` on Roborev reviewers, and simplified
    the over-engineered snapshot acquisition/materialization code in
    `the_knowitall` (`src/knowitall_snapshot/acquire.py` and `materialize.py`,
    commit `a266fa4`).

- **Forge workspace PR completion, MCP targets, and Pi lifecycle hooks (`24g8`)**:
  - Enabled Forge MCP on `http://127.0.0.1:18092/mcp` in
    `.local/environment/forge/config.toml` and `scripts/local_env.py`. Forge
    `bf025d22` declares open MCP output schemas for
    `kenn_forge_add_workspace_target`, `kenn_forge_add_workspace_kata_target`,
    and `kenn_forge_list_workspace_targets`, so their `platform_repo_id` /
    `bitbucket_repository_uuid` fields validate without a local patch.
  - Configured `kenn-forge` and `kata` with `"exposure": "direct"` in
    `.local/environment/pi/mcp.json` and `.pi/mcp.json`, and seeded
    `.local/environment/pi/trust.json` for `kenn-kopy`, `the_librarian`,
    `the_knowitall`, and `aos-spud`.
  - Added `scripts/pi-extensions/forge-workspace.ts` (installed to
    `.local/environment/pi/extensions/forge-workspace.ts`) to load Forge's
    `AGENTS.override.md` and `/api/v1/agent-hooks/claude` `SessionStart`
    context, report live Pi lifecycle events via `KENN_FORGE_RUNTIME_SESSION_KEY`,
    and override `superpowers:finishing-a-development-branch` in Forge
    workspaces so agents automatically push, create/update the PR, and register
    workspace targets instead of asking whether to merge locally to `main`.
  - Linked `Engineer` and `Librarian` project `repo_id`s in `forge.db` and
    registered `GSA/the_knowitall#2` and Kata tasks `knowitall#r9gz`,
    `knowitall#7gv8`, and `knowitall#8jvw` on workspace `577f9f28aea5d6e2`.

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
  - Hardened Forge workspace autonomy and environment (`forge-workspace.ts`,
    `scripts/local_env.py`, `scripts/bootstrap-toolchains.sh`): added
    `KENN_FORGE_RUNTIME_SESSION_KEY` passthrough + workspace API fallback,
    filtered leaked parent `AGENTS.md` from child worktrees, overrode
    `brainstorming` and `writing-plans` interactive stops, capped pre-PR
    `roborev` to 1 branch review + 1 fix pass, removed hardcoded `cwd` from
    `kata` MCP, seeded `.local/environment/home/.gitconfig` + `.config/git/ignore`,
    and provisioned `jq-1.7.1` and shared Python test deps (`.local/tools/pydeps`).
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
- `t592` (`open`): Isolated WSL2 `engineer-mvp` rehearsal. The plan uses a clean
  `wsl --install Ubuntu-24.04 --name` base exported before secrets, treats
  post-`set-key` snapshots as secrets, and runs with `KENN_KOPY_PORT_OFFSET=1000`
  (`8k15`, branch `t592-configurable-ports`) beside the primary stack. Needs a
  real WSL2 run; Knowitall MCP discovery waits on `the_knowitall#vz6q`.
- Ready unblocked follow-ups (`kata ready --no-label blocked --no-label deferred --agent`):
  `t14m` (reconcile `dist/install.py` with systemd service topology), `k03a`
  (curate Superpowers skills in Pi), `zmzh` (curate installed Pi extensions),
  `025n` (verify Forge terminal click-to-type focus in live browser), and `pcrv`
  (harden USAi provider model discovery).

## Knowitall Forge handoff (2026-10-29)

- Forge workspace `577f9f28aea5d6e2`, branch `kenn-forge/work-577f9f28`, rebased
  onto merged provider-contract PR #1 and pushed as PR #2:
  https://github.com/GSA/the_knowitall/pull/2 (open and mergeable).
- Closed `knowitall#r9gz` after fresh execution of all 29 Graphify tests against
  the retained exact lock-built runtime, including real offline Python and
  TypeScript extraction.
- Closed `knowitall#7gv8`; rebased commit `414660e`: added explicit credential-free
  remote clone/fetch intake, origin provenance, executable-mode preservation and
  digest binding, interruption recovery, and immutable-upstream-removal tests.
- Closed `knowitall#8jvw`; rebased commit `08e929d`: added a minimal local NDJSON stdio
  adapter over the revision-bound query service with malformed-line isolation.
- Final post-rebase verification at `08e929d`: 127 pytest tests passed with the pinned
  Graphify runtime, all four contract examples validated, wheel/sdist built and
  contained the new modules, compileall and `git diff --check` passed, and the
  worktree was clean. PR #2 (`GSA/the_knowitall#2`) and Kata tasks
  `knowitall#r9gz`, `knowitall#7gv8`, and `knowitall#8jvw` are registered on
  workspace `577f9f28aea5d6e2`; the host-managed worktree remains for PR
  feedback.
