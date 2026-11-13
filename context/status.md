# Current status

## MVP readiness and task completion

The connected MVP is Librarian plus Engineer, using Engineer's cross-repo
seam scanner (`z6jw`) where needed. Knowitall is archived (`wg6t`).
The priority is measurable value through the configured USAi model roles,
with qualified evidence and accountable human decisions:

- **P0:** full-context audit integration (`the_librarian#9e3j` -> `s27j`) and
  baseline/scorecard (`ef0w`). Corpus (`the_librarian#60h6`, `3y40`), progress
  (`the_librarian#rvx5`), daily snapshots (`the_librarian#9qg1`) and capture
  capability (`86ey`) are closed; verify deployment rather than reopening them.
- **P1:** post-compaction retrieval (`8vhd`), using an existing approved run
  for `s27j` acceptance. The connected demo/presentation track (`pyzt`, `hk33`,
  `d8v5`, `97fg`, `j4v3`, `se6n`, `cgsr`, `eszx`) is retired by owner decision.
- **Tester visibility:** GIF/video walkthroughs of UI tickets built on
  `demo-capture.py` (`8ya9`).
- **Transfer and scale:** clean-host acceptance (`p4ke`, closed) then
  second-team bootstrap-to-value (`7ygh`). The agentsview submodule tracks
  upstream; `am2q` removes the remaining mirror text.
- **Post-1.0:** private hosting (`jmga`), recovery checks (`vg0b`) and Librarian
  Drive/Confluence import (`the_librarian#qgr1`).

The operating-model hypothesis is that refined routine work moves into an
agent-executable backlog, while trusted engineers own intent, consequential
technical decisions, exceptions and acceptance. Measure human touch time,
accepted throughput, rework and escalation rates rather than asserting that
most backlog work is already automated. Refinement is not authorization.

One run establishes feasibility. Faster team onboarding, positive ROI and
outperformance need comparable baselines and observed second-team outcomes.
Private run evidence stays outside the public toolkit. The owner-facing
presentation outline is maintained separately from this capability register.

Merged-PR reconciliation closed Librarian `9hqs`/`0nj8` and Engineer
`k03a`/`mpew`/`tvbf`/`avvp` with per-task merge and acceptance evidence.
The owner accepted the external roborev hook/page for `avvp`; no native
Kata-workspace Reviews tab is claimed.

Forge `3f58f438` merges PRs and optionally cleans up workspaces, but its Kata
integration is read-only. Workspace/PR task links do not authorize completion.
Use native `kata close` only after the task's acceptance is met, with PR/commit
evidence; partial-delivery tasks stay open. `430a` records the planned upstream
change for explicitly authorized, evidence-backed closure after a confirmed
merge, including independent closure-failure reporting. No automatic closure
or reconciliation service is installed.

## Live environment state

- All four user systemd units are running on loopback:
  - `kenn-kopy-kata.service` (`http://127.0.0.1:17777/kata`, `v0.23.0-3-g08facefa`, schema 50, API `0.44.0`)
  - `kenn-kopy-roborev.service` (`http://127.0.0.1:17374/reviews`, API `17373`, `v0.75.0-8-g0cb4d19b`)
  - `kenn-kopy-agentsview.service` (`http://127.0.0.1:18080/`, `v0.47.0-19-g83d3756ed`)
  - `kenn-kopy-forge.service` (`http://127.0.0.1:18091/`, MCP `http://127.0.0.1:18092/mcp`, `v0.6.0-49-g31c6ac38-local-kata`)
- Registered Forge repositories: `gsa/the_engineer`, `gsa/the_librarian`,
  `gsa/aos-spud` and `gsa/supply-chain-user-interface`, each mapped to its Kata
  project (`the_engineer`, `the_librarian`, `spud`,
  `supply-chain-user-interface`).
- Active USAi paired coder/reviewer models in `.local/environment/usai.json`,
  `.local/environment/pi/settings.json`, and `.local/environment/roborev/config.toml`:
  coder = `claude-sonnet-5.5` (with `pi-argon` / `gemini-4-argon` also enabled as a
  first-class Forge workspace agent target), reviewer =
  `gpt-6.1-sol-latest-guardrails-defaultv2` (`https://api.gsa.usai.gov/api/v1`,
  `openai-completions`), with all 26 advertised USAi chat models synced into
  `.local/environment/pi/models.json` (excluding `cohere_english_v3`, `cohere-v4`
  and `text-embedding-005`), `gemini-4-argon` configured for concise PR body
  summarization in `forge-workspace.ts`, and `compat.supportsDeveloperRole = false`
  across all USAi model definitions, and `USAI_MODEL_LIMITS` context caps
  (400k Claude/Gemini, 272k GPT Sol, 32k output) so Pi no longer compacts at its 128k default.

## Recent completed milestones

- **Toolchain upgrade harness and latest pins (`x0pe`)**:
  - `scripts/upgrade.py` (tests in `scripts/test_upgrade.py`) snapshots,
    applies, verifies, cuts over and rolls back; see `context/tools.md`.
  - Live on Kata `v0.23.0-3` (schema 50), roborev `v0.75.0-8`, AgentsView
    `v0.47.0-19`; since cut over to upstream `v0.47.0-64`, with guarded-Sol pricing
    set by `custom_model_pricing.price_as` config via upstream
    kenn-io/agentsview#2951 and no carried commit), Forge
    `v0.6.0-49`, Pi `1.5.0` and pi-subagents `0.87.0`; acceptance 13/13 and a
    live rollback drill passed.
  - Upstream Forge PRs from `biggestbinary/forge`: kenn-io/forge#1965 (list
    configured Kata daemon IDs in the unknown-daemon error, #1896) and
    kenn-io/forge#1966 (`kata` source for
    `kenn_forge_spawn_workspace_with_agent`, #1719); roborev passed on both.
  - Forge now requires Kata Go `v0.21.0` and folds the GitHub App setup into
    `kenn-forge github-app`; `build-forge-local-kata.mjs` derives the Kata Go
    tag from Forge's `go.mod` (it must be contained in the Kata pin) and ships
    only `kenn-forge`. `build.sh` uses `GOPROXY=proxy.golang.org|direct`
    because the network proxy blocks the `go.kenn.io/kata` module zip.
  - USAi now advertises `gpt-6-luna-guardrails-high` (added) and the
    embedding model `cohere-v4` (excluded).
  - The first cutover exposed that freshly built binaries in the live paths
    let roborev restart on `v0.75` and migrate its database before cutover.
    The harness now builds and verifies in a separate candidate worktree, so
    live binaries and pins change only after cutover stops the services.

- **Tool-call failure diagnosis (`eynt`)**: `context/tool-failures.md` ranks
  failed tool calls from Pi and Copilot history; the Forge extension appends
  `Recovery:` hints and `scripts/tool-health.py` checks Kata, project binding
  and index freshness (PR #30).
- **Knowitall archived; seam scanner retained (`wg6t`)**:
  - Removed the Knowitall code provider (`knowitall.py`, `bridge.py`, code
    queries, paging and associations) from `engineer-task-context` 0.2.0.
    Contracts are now `engineer.task-context/v2` and
    `engineer.context-config/v2` (Librarian only); v1 packets and configs are
    rejected. The stdlib-only seam scanner (`seams.py`) is unchanged.
  - Unregistered `gsa/the_knowitall` and its stale Kata mapping from live
    Forge; `GSA/the_knowitall` stays archived on GitHub.
  - Verified with 42 consumer tests, 2 actual-Librarian integration tests,
    264 script tests and a live `engineer-context seams` scan of `~/falcon`.

- **Bounded roborev delivery policy (`n3qc`)**:
  - Tracked coder and Forge guidance reuse unchanged-code evidence, allow one
    branch review plus one verified fix pass, and hand recurring/unresolved
    findings to the owner. Valid out-of-scope findings stay open; unresolved
    task-scoped medium/high/critical defects pause publication.
  - Setup adds missing medium-severity and passing-review auto-close defaults
    while preserving explicit config overrides. Verified with 152 local-env,
    17 Forge extension, and 18 workflow-gate tests.
  - Activation uses `setup` to refresh the private coder/extension copies,
    then `/reload` in existing Pi sessions. The delivery allowance is agent
    guidance; native background hooks retain their batching behavior.

- **Enforced roborev review loops (`3twq`)**:
  - The Forge workspace extension blocks a second full-branch review,
    `roborev refine` and unscoped `roborev fix` unless the human confirms
    (print/JSON always block). The per-branch count persists in the
    worktree's git directory. Fix-commit reviews (`roborev review <sha>`) stay
    allowed; findings outside or recurring from the first review are flagged
    for the owner and arm a loop self-check prompt (stop, assess, hand off).
  - Coder contract, `AGENTS.md` and `context/engineering-workflow.md` describe
    the enforced behavior. Copilot has no runtime hook (agent-hook not
    installed by owner choice) and keeps the prose policy.
  - Activation uses `setup` to refresh the private copies, then `/reload`.

- **MVP value case (`ef0w`)**:
  - `context/value-case.md` is a one-page template: labeled estimates, mechanism,
    checks and falsifiers. Capacity released is separate from cash savings.
    Private filled copies for `hk33` and `j4v3` are in ignored `.local/value-case/`;
    baseline hours, loaded rate, pricing approval and the pilot threshold await the owner.
- **Private demo capture (`86ey`)**:
  - `scripts/demo-capture.py` captures screenshots and a WebM video of a
    loopback web UI with headless Playwright Chromium (existing
    `playwright-core` cache and `.local/tools/playwright-browsers`), or
    imports a manual capture, into `.local/demos/` with an
    `engineer.demo-capture/v1` manifest. Handoff prints verified local links;
    nothing is uploaded. Contract: `context/demo-capture.md`.

- **Content-led PR descriptions (`8gp7`)**:
  - Forge coder, branch-finishing and automatic formatter guidance share one
    policy based on meaningful changes and reviewer needs. File/line-count
    tiers and mandatory paragraph/bullet counts are removed.
  - PR #20 merged as `f24bf95`; the reviewed formatting delta is deployed to
    the private Pi extension. New sessions load it automatically; existing
    sessions need `/reload`. Existing PR bodies are untouched; the owner will
    assess the next generated PR.

- **Verified Forge task, Pi and roborev handoffs (`avvp`)**:
  - `local_env.py verify-handoff` joins Forge task detail/mapping, worktree,
    Pi session, AgentsView record, resume file, exact-commit roborev job and
    stored disposition. Kata workspaces use the external roborev hook and
    review page; Forge's native Reviews tab is pull-request-only.

- **Verified Pi policy loading by surface (`k03a`)**:
  - roborev structured reviews run isolated (no AGENTS files, Forge extension,
    Superpowers, prompt templates or MCP; schema extension by path), and
    `local_env.py verify-pi-policy` checks private, Forge and review surfaces
    without a model call.
  - The coder contract is tracked once in `scripts/pi-coder-contract.md`
    (checkpoint and additive-fix commits, consuming roborev results, structural
    vs behavioral commits, temporary-plan cleanup, human merge); `setup`
    installs it as private `pi/AGENTS.md` and `verify-pi-policy` fails on drift.
    Constitution/Beck/McKinney/Gill dispositions are in
    `context/engineering-workflow.md#source-guidance-dispositions`.

- **Librarian audit bindings and decision trail (`s27j`)**:
  - `configure-librarian --audit [--copilot-config PATH]` and
    `scripts/verify-audit-binding.mjs` are delivered and verified against a
    synthetic Librarian kit (status/search/get/error hashes match the audit
    log; a read-only log yields a visible error). The installed
    `falcon-librarian` adapter predates 9e3j: reinstall it from
    `~/the_librarian/tools/context-mcp`, run `configure-librarian --audit`, and
    restart clients before real calls are audited. Global bindings stay
    untouched.
  - `scripts/decision-trail.py` reconstructed the closed `the_librarian#9e3j`
    / PR 14 run privately (human merge, roborev jobs 514-527; missing links:
    ticket approval, session, workspace, check outcomes, review dispositions).
    `hk33` supplies the first full trail.

- **Manual Jira-to-Kata intake contract (`99gr`)**:
  - Added `scripts/jira-intake.py` (`init`, `check`, `record [--apply]`) and
    `context/jira-intake.md`. It retains one owner-supplied Jira XML export
    privately under `.local/jira-intake/<KEY>/` with SHA-256 provenance,
    separates approved refinements, assumptions and blocking questions, and
    creates dependency-ordered Kata tasks carrying `jira.*` metadata.
  - `CCSMFSSM-1290` is recorded: the owner-approved single task adopts
    `supply-chain-user-interface#jwn4` and its PR
    (GSA/supply-chain-user-interface#1, client-side AAC lookup, verified by a
    dev smoke test). `record` supports `adopt` for existing tasks. `d8v5`
    (demonstrate the Jira-to-PR workflow) is unblocked.

- **Managed Pi 1.4.0 (`gamy`)**:
  - Launcher and installer pins are `1.4.0`; the private launcher reports
    `1.4.0`. `setup` now migrates a saved older `pi_version` after `verify_pi()`
    passes, so an in-place executable upgrade is repeatable on other hosts
    without manual `environment.json` edits; other differences still abort.
- **Model-selected qualified read in a real Forge Pi session (`6hce`)**:
  - In Forge workspace `08ac211978ff4ac3` (Pi on `usai/claude-opus-5.5`), the
    model chose `mcp__falcon_context` `status` (fresh, 69 documents), discovery
    `search`, then `get` on a verbatim returned locator. The result kept
    source hashes, roles, line ranges, inheritance reasons and outbound-link
    index status; a compound query with no hits was recorded as absent evidence.
  - Body-free evidence lives in the private
    `.local/environment/runtime/6hce-qualified-read-20261030.json`. No corpus,
    index or provider configuration changed. Compaction (`8vhd`) and the shared
    Librarian+Knowitall run (`hk33`) are tracked separately.
- **Forge pin `3f58f438` (`v0.5.1-331`)**:
  - `scripts/build-forge-local-kata.mjs` builds with Bun 1.4.4, substitutes
    local Kata Go `v0.20.0` (`976cd155`) and Kata UI `v0.19.0`, and passes an
    empty `POSTHOG_PROJECT_KEY` so the binary carries no telemetry destination;
    the lock check permits only the local Kata UI package's nested devDependency
    subtree (Kata UI now declares `vite-plus`);
    the service environment also keeps `TELEMETRY_ENABLED=0`.
  - Upstream fixed the workspace-target MCP output schemas, so the local
    `tools_workspace_targets.go` patch is removed. Config, `serve` flags, the
    MCP listener on `18092`, and the agent-hook/agent-sessions APIs are unchanged.
  - Verified with the build script's Bun tests, 177 script and 52 distribution
    unit tests, `smoke.py --only-forge`, a live MCP `tools/list` and
    `kenn_forge_list_workspace_targets` call, and a clean GitHub sync. Forge's
    hot spares were re-prepared at the rewritten `origin/HEAD` commits.

- **Task-bound business and code evidence consumer (`k4mp`)** (code provider
  path since removed by `wg6t`):
  - Added `engineer-task-context` (`src/engineer_context/`, CLI
    `engineer-context`, stdio MCP `engineer-context-mcp`), which composes
    `engineer.task-context/v1` packets from the configured Librarian corpus and
    a revision-bound Knowitall generation, reports provenance and readiness, and
    rechecks a sealed packet with `revalidate`. Collection is read-only and
    never writes provider state or mutates a task.
  - Integrated preserved commit `871a1bc` (explicit Librarian binding) as merge
    `9988f2b`; branch review job 313 passed it with no findings.
  - Required paged code queries are ready only with the whole page chain;
    malformed requests and refused cursors are caller input (exit 1), while a
    cursor refused during revalidation is reported as changed provider state.
  - Interpreter and server program paths are absolutized lexically, because
    resolving a virtual environment's `bin/python` symlink changed the child's
    prefix and broke the Knowitall bridge.
  - Verified with 58 consumer tests, 10 actual-provider integration tests
    against the Librarian release and pinned Knowitall `28d195d` with the
    offline Graphify runtime, 122 local-environment tests, 52 distribution tests
    (4 expected skips), a Pi runtime receipt with `model_requests: 0` and
    `configured_mcp_servers: 0`, plus
    build, compile and whitespace checks. Branch review job 384 passed;
    delivered as https://github.com/GSA/the_engineer/pull/4.
  - Merged current `main` into the branch, keeping main's compacted docs,
    configurable ports (`KENN_KOPY_PORT_OFFSET`) and roborev wrapper removal,
    and re-applying the explicit Librarian binding so `setup` preserves the
    other saved `pi/mcp.json` servers. Branch review job 399 passed.
  - Upstream Librarian `73597aa` dropped `--reader` from `librarian-mcp` and
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
    commit `5efdd85`).

- **Pi Kata lifecycle, attention and resume verification (`tvbf`)**:
  - `forge-workspace.ts` now reports as Forge agent `pi` (resume argv
    `--session <id>`; the former `claude` identity produced Pi's boolean
    `--resume` picker), forwards session start sources, ends sessions only on
    replacement or termination signals, and gates idle dialogs out of attention.
  - Live pilot on Forge workspace `30c7faa073ddba15` (target `pi`, USAi
    `claude-opus-5.5`): read-only `kata show tvbf` turn → `done`; Escape
    interrupt during `sleep 60` → `done` with the turn aborted; `/reload` →
    `idle`, `continued=true`; in-turn `ctx.ui.confirm` → `input`, answered →
    `done`; `/quit` → row forgotten as finished; SIGHUP → end reason `other`,
    row retained (Forge currently resumes it only on daemon restart);
    `pi --session <id>` restored the conversation (recalled codeword). `tvbf`
    stayed open, owned by `nkirrish`, with no added comments throughout.
  - Kata attention: `pi-local.py` derives `KATA_REF` from the workspace
    override and `install-pi-extensions` installs Kata's attention-only Pi
    adapter. Pilot (tmux, USAi `claude-opus-5.5`, private
    `runtime/tvbf-kata-attention-pilot-20261101.json`): start → `ok`;
    `/reload` and Escape keep `ok`; `/quit` and SIGHUP without hand-off →
    `needs-human` "session ended without hand-off"; `pi --session <id>`
    resume → `ok` with the conversation restored; a model-run
    `kata meta set` hand-off survived `/quit`. No claim, close or comment
    was duplicated; `tvbf` stayed open and owned by `nkirrish`.

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
    context, report live Pi lifecycle events (now via `/api/v1/agent-hooks/pi`),
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
  - Forge workspaces launch `worker`/`delegate` subagents in managed
    worktrees under `.local/environment/pi/subagent-worktrees` and land their
    patches with `git apply --3way` (see `context/tools.md`).
  - Disabled `~/.copilot/hooks/agenthook.json`, cleared global/repo custom hook
    wrappers, installed native `roborev init --no-daemon` hooks across all 8
    workspace repos, and configured `post_commit_batch_size = 5` with concise,
    affirmative `review_guidelines` in `.roborev.toml`.
  - Removed `scripts/roborev-local.py`, `scripts/roborev_hooks.py`, and
    `the_librarian`'s custom `pre-commit` review gate and negative-disclaimer
    context bloat (`the_librarian` commit `376d6d4`, `the_knowitall` commit
    `d985920`).
  - Compacted `kenn-kopy/context/*.md` into concise current-state reference
    documents under 16 KiB each.
  - Hardened Forge workspace autonomy and environment (`forge-workspace.ts`,
    `scripts/local_env.py`, `scripts/bootstrap-toolchains.sh`): added
    `KENN_FORGE_RUNTIME_SESSION_KEY` passthrough + workspace `agent-sessions` API fallback (reads `sessions[].runtime_session_key`),
    filtered leaked parent `AGENTS.md` from child worktrees, overrode
    `brainstorming` and `writing-plans` interactive stops, capped pre-PR
    `roborev` to 1 branch review + 1 fix pass, removed hardcoded `cwd` from
    `kata` MCP, seeded `.local/environment/home/.gitconfig` + `.config/git/ignore`,
    and provisioned `jq-1.7.1` and shared Python test deps (`.local/tools/pydeps`).
- **Selective engineering memory and workspace backup (`5xrm`, `bc20`)**:
  - Documented the selective engineering memory architecture (`context/engineering-memory.md`)
    using repo-local `context/*.md`, Kata, and Librarian without sidecar memory containers.
  - Verified `scripts/backup_workspace.py` archive generation (`bc20`).
- **Synthetic prompt, temporary-plan, and publication gate verification (`mpew`)**:
  - Added `scripts/workflow-gates.py` and `scripts/test_workflow_gates.py` (18
    unit tests) to verify prompt and tool isolation across `private_pi`,
    `forge_workspace`, and `roborev_review`, enforce non-model temporary plan
    checks across `.local/plans/` and `docs/superpowers/`, validate additive
    review fixes and human-controlled `main` merge/push gates, and run an
    end-to-end synthetic Red -> Green -> Refactor -> Review -> Publication task
    demonstration with a private `0600` receipt at
    `.local/environment/runtime/mpew-synthetic-gates-20261030.json`.
  - Refinement: `forge-workspace.ts` now enforces the human-only merge/`main`
    push gate at runtime (`tool_call` block unless the human confirms in the
    Pi UI), the demo exercises that guard, the `roborev_review` gate reuses
    `k03a`'s `structured_review_args()` isolation, and the red stage records
    the observed failure. Receipt:
    `.local/environment/runtime/mpew-synthetic-gates-20261101.json`.
  - Refinement (`bxz7`): the runtime guard resolves the directory and branch a
    push actually runs in, so a workspace-branch push after `cd`, `git -C` or a
    new-branch checkout no longer asks the human to approve a `main` push,
    while subshell/pipeline `cd`, unknowable branches, shell-executed heredocs
    and possibly failing checkouts stay gated. The same pass closed the mirror
    bypasses found by scanning our own wrappers: a wrapper program
    (`timeout`, `stdbuf`, `nice`, `setsid`, `env -i`, …), a `gh` flag placed
    before the subcommand (`gh --repo … pr merge`), and an explicit
    `git --git-dir` no longer hide a `main` push or a PR merge from the gate,
    each subshell carries its own directory scope, a conditionally skipped
    `cd` keeps the pre-`cd` branch a candidate, a shell heredoc's `cd` stays
    in its child scope, an unquoted heredoc's command substitutions are still
    scanned, and PR-description reformatting triggers on real `gh pr
    create`/`edit` calls rather than text that mentions them. Residual
    indirection (`gh alias`, `ssh host 'git push origin main'`, variable-
    expanded program words) is tracked in `kt2r`, and the wider
    enumerated-list/regex drift the scan surfaced in `c95c`.

## Active Kata queue (`engi-platform`)

- List current work with `kata ready --no-label blocked --no-label deferred --agent`.
- MVP (`pyzt`) is Librarian plus Engineer plus the cross-repo seam scanner;
  `z6jw`, `k4mp`, `n0vk`, `6hce` and `h28d` are closed.
- Open MVP work: `d8v5` (uninterrupted Jira-to-PR demo on a fresh owner-selected ticket; awaits the export), `gamy` (PR #6 merged; close after
  verification), `p4ke` (fresh-host installer plus read-only
  `local_env.py accept`; container run of `8bfdd6d` passes 12/14 with only
  credentials missing, the former unfetchable `agentsview` pin is gone
  (all pins are now upstream); the installer preflights pin fetchability,
  accepts an optional `--submodule-mirror NAME=URL` (no default mirror), defaults `GOPROXY` to `...|direct` and writes
  `.local/install-receipts/*.json` timing/fix receipts for `ef0w`), `hk33` and `86ey`.
- `t592` (isolated WSL2 rehearsal, `docs/wsl2-rehearsal.md`) is deferred
  post-MVP. `5xrm` (reproducible redeployment script) and `eb48` (legacy
  identity/path migration during planned downtime) remain open.

## Repository history

- On 2026-10-29 the histories of `GSA/the_engineer`, `GSA/the_librarian`,
  `GSA/the_knowitall` and the `GSA/supply-chain-user-interface` PR #1 branch
  were rewritten so author/committer `nader.kirrish@cgifederal.gov` became
  `nader.kirrish@gsa.gov` (linked to GitHub `biggestbinary`), then
  force-pushed. Commit IDs above are post-rewrite; refresh other clones with
  `git fetch` and `git reset --hard origin/<branch>`.
- Knowitall PRs #2 and #5 are merged; Forge hot spares were re-prepared on the
  rewritten history.
