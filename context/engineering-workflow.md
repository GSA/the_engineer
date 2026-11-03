# Engineering workflow and prompt boundaries

## Core workflow loop

1. **Discover and claim in Kata**: inspect ready issues (`kata ready --no-label blocked --no-label deferred --agent`), read the issue (`kata show <id>`), and claim it (`kata claim <id>`) before editing code.
2. **Execute in an isolated worktree or checkout**: launch a Forge workspace (`Pi (USAi)`) or work in the bound repository checkout using `scripts/pi-local.py` or Copilot CLI.
3. **Validate incrementally**: run targeted unit/integration tests for each change and commit coherent slices locally.
4. **Review with a bounded delivery pass**: native `post-commit` hooks batch every 5 commits (`post_commit_batch_size = 5`) into background `roborev` jobs and `pre-push` flushes unreviewed commits. Apply the review and disposition rules below before delivery.
5. **Complete the Forge workspace PR and register targets**: in a Kenn Forge workspace (`AGENTS.override.md` present or `KENN_FORGE_RUNTIME_SESSION_KEY` set), always finish verified work by pushing the workspace branch (`git push -u origin HEAD`), creating or updating the GitHub PR (`gh pr create` / `gh pr edit`) without stopping on `finishing-a-development-branch`'s local-merge menu, and registering the PR and worked Kata/GitHub items via `kenn_forge_add_workspace_target` and `kenn_forge_add_workspace_kata_target` (confirming with `kenn_forge_list_workspace_targets`).
6. **Close in Kata with evidence**: record test, commit, and PR evidence in Kata (`kata close <id> --reason "..."`) and update `context/status.md` when a milestone completes.

## Subagents vs. `roborev`

- **Pi `subagent` tool (`pi-subagents`)**:
  - Uses `defaultProvider: "usai"`, `defaultModel: "inherit"`, and `toolActivation: "eager"` across
    `delegate`, `oracle`, `scout`, and `worker`, with `reviewer` routed to `usai/<review_model>` when a paired `review_model` is configured (and external-CLI/web builtin agents disabled).
  - Background subagent runner processes (`PI_SUBAGENT_CHILD=1` / `PI_SUBAGENT_RUNNER_PID`) are isolated by `forge-workspace.ts` so they do not inherit `forge_workspace` delivery prompts, fire Forge session hooks, or receive the full Superpowers bootstrap.
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
    `roborev show <job_id>`, `roborev review --branch --wait --min-severity medium`)
    with `review_min_severity = "medium"`, `refine_min_severity = "medium"`, and
    `fix_min_severity = "medium"`.
  - Let native hooks enqueue reviews during development; consume the results
    rather than launching manual dirty-review loops before every commit.

### Bounded delivery review and dispositions

Inspect existing reviews first (`roborev list`, `roborev show <job>`). Reuse
evidence that covers unchanged reviewed code. Otherwise run
`roborev review --branch --wait --min-severity medium` at most once per delivery,
followed by at most one focused fix pass for confirmed task-scoped
medium/high/critical defects. Make additive fix commits and verify actual
behavior with targeted tests. These allowances retain the previous one-review,
one-fix boundary; severity filtering removes low findings from delivery gates.
The allowance is agent guidance, not a runtime-enforced counter.

Do not launch another review just to get a passing verdict. Record reviewed
revision, job IDs, dispositions, fix commits, verification, and any handoff in
Kata so reloads, resumes, and skill transitions reuse evidence and do not
restart the allowance. Background reviews of fix commits do not authorize
another automatic fix pass. A later delivery with new implementation changes
may need fresh review; a review fix or PR-description edit does not reset this
delivery's allowance.

- Treat findings as claims: confirm presence, reachability, and task scope
  before changing code. Low findings do not require fixes or block delivery.
- Record each disposition with `roborev respond <job>`. Close a review with
  `roborev close <job>` only when all actionable findings are fixed with
  evidence or confirmed stale/invalid. A disposition does not require a new
  passing model verdict.
- Leave valid out-of-scope findings open and ask the owner; they do not
  automatically expand the task or block its publication.
- Hand recurring or unresolved confirmed findings to the owner instead of
  repeating review/fix passes. Pause publication and task completion for
  unresolved task-scoped medium/high/critical defects. A failed or unavailable
  review is not passing evidence; report the gap and ask the owner rather than
  repeatedly enqueueing reviews.

`review_min_severity` changes which findings fail a review, not what the model
reports. `auto_close_passing_reviews` closes passing jobs; it does not resolve
failing jobs or bound review loops.

## Loaded policy by surface

Each Pi surface loads one policy set; check it with
`python3 scripts/local_env.py verify-pi-policy [--cwd PATH]` (no model call).

| Surface | Loaded policy |
|---|---|
| Private Pi (`scripts/pi-local.py` in a checkout) | private `.local/environment/pi/AGENTS.md` (installed coder contract), the repository `AGENTS.md`, Superpowers skills and bootstrap, `pi-subagents` |
| Forge-launched Pi (`pi`, `pi-argon`) | the same coder policy with the Forge-generated `AGENTS.override.md` in place of the root `AGENTS.md`, plus the `forge_workspace` section and skill overrides from `forge-workspace.ts` |
| roborev structured review (`--json-schema`) | Pi's base prompt, the roborev prompt with `.roborev.toml` `review_guidelines`, read-only tools and the pinned schema extension only |

`pi_launch()` isolates every structured review with `--no-context-files
--no-extensions --no-skills --no-prompt-templates --no-mcp` and loads the
tracked `scripts/pi-extensions/json-schema.ts` extension by path, so reviewers stay
independent and read-only and never inherit coder commit, fix, push or planning
duties. Coder responsibilities (clarifying, checkpoint commits, additive review
fixes, evaluating task-scoped roborev findings, removing temporary plans) live
once in the tracked coder contract `scripts/pi-coder-contract.md`; `setup`
installs it as the private `pi/AGENTS.md` and `verify-pi-policy` fails when the
installed copy drifts. Forge delivery (push, PR, target registration) lives in
the `forge_workspace` section of `forge-workspace.ts`; Superpowers supplies
TDD, design, planning and verification discipline.

### Source guidance dispositions

| Source | Adopted in the coder contract | Left out |
|---|---|---|
| [Clanker Constitution v2026.08.11](https://github.com/kenn-io/constitution) (CC BY 4.0) | request as contract, ask only on consequential gaps, never amend, preserve others' work, verify with fresh evidence, human merge | `CLAUDE.md` and memory rules (Pi loads `AGENTS.md`); the full text stays in the inactive `context/prompt-drafts/` example |
| [Kent Beck, Augmented Coding (2025)](https://newsletter.kentbeck.com/p/augmented-coding-beyond-the-vibes) | small red/green/refactor steps, separate structural and behavioral commits, keep tests meaningful | the `plan.md`/"go" protocol (Kata holds tasks), Rust preferences, full-suite runs after every edit |
| [Wes McKinney, agentic engineering (2026)](https://wesmckinney.com/blog/agentic-engineering-aug-2026/) | human-owned intent, design and publication; agents execute | role pipelines (Forge workspaces and Superpowers cover execution) |
| [Richard Gill, Pi setup](https://github.com/richardgill/pi-extensions/blob/main/PI_SETUP.md) | automatic project trust (already seeded in `pi/trust.json`) | his extensions and tmux orchestration (Forge owns workspaces and sessions) |

## Task-bound evidence before acting

Before acting on a task that depends on business requirements and code, collect
one `engineer.task-context/v1` packet with `engineer-context collect` and read
its report. Treat the packet as an observation, not authorization: a ready
packet records that required evidence was present at observation time, not that
an assertion, review or approval exists.

Recheck with `engineer-context revalidate` immediately before acting, and stop
when it reports blocked. A corrected source passage or a newer published code
generation must block, because a historical packet is never rewritten to follow
current provider state. Required missing or partial scope, including
pagination, blocks readiness; optional gaps are reported but do not.

Packets and revalidation receipts can carry restricted source text and exact
code locations. Keep them in private paths such as ignored `.local/`, never in
Git, chat, logs or command arguments. Publishing restricted evidence, using a
real corpus or ticket, or running model traffic against it needs separate owner
authorization.

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

<a id="prompt-and-publication-gate-verification-mpew"></a>
## Prompt, temporary-plan, and publication gate verification (`mpew`)

- `python3 scripts/workflow-gates.py` verifies prompt isolation, temporary-plan
  hygiene, review-finding dispositions, and publication/merge boundaries without
  live model traffic or external source access:
  - `check-prompts --surface <private_pi|forge_workspace|roborev_review>`:
    exercises `scripts/pi-extensions/forge-workspace.ts` and
    `scripts/local_env.py:validate_paired_models()` to confirm that `private_pi`
    loads repo policy without Forge overrides, `forge_workspace` filters
    ancestor `AGENTS.md` and applies autonomous skill overrides, and
    `roborev_review` launches through `local_env.structured_review_args()` with
    the `REVIEW_ISOLATION_FLAGS` from `k03a`, read-only tools, and distinct
    model families (`claude`, `openai`, `gemini`). The live loaded policy is
    checked separately by `python3 scripts/local_env.py verify-pi-policy`.
  - `check-plans --repo . --base main`: inspects staged changes, branch diffs
    against `main`, and the working tree for temporary planning artifacts under
    `.local/plans/`, `docs/superpowers/plans/`, and `docs/superpowers/specs/`
    while preserving durable documentation (`README.md`, `context/*.md`, and
    `context/prompt-drafts/jira-refinement.example.md`).
  - `check-publication`: enforces read-only `roborev_review`, additive fix
    commits instead of amending reviewed commits, owner approval for pushes/PRs
    outside Forge workspaces, and explicit human control (`--human-operator`)
    for `push_main` and `pr_merge`.
  - `demo [--receipt <private-path>]`: executes an end-to-end synthetic task
    through Red -> Green -> Refactor -> Review -> Plan Cleanup -> Publication
    gates in an isolated temporary Git repository and writes a mode `0600`
    receipt when requested. The publication stage also drives the real
    `forge-workspace.ts` `tool_call` guard, which blocks agent PR merges and
    pushes to `main` unless the human confirms them in the Pi UI.
