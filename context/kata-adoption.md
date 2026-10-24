# Engi Platform Kata backlog

The owner adopted Kata at 17:42 on 2026-10-12 for **this project only**.
Project `engi-platform` owns live task state. `TODO.md` is its generated
open-task index plus historical completed Markdown records. Keep detailed
decisions, evidence and operating boundaries in `context/`, not duplicate
task lists. Falcon's checkout, instructions and backlog were not changed.

## Falcon application projects: 2026-10-20

At 16:24 the owner authorized adding all four mirrored repositories to Kata.
Each received its own empty daemon project, separate from the platform backlog:

| Project | Immutable project UID |
| --- | --- |
| supply-chain-user-interface | 01M5DFTHB5SDG3BVCZB1DHWB3A |
| national-item-file-maintenance | 01M5DFTHAQAQSCB9D205R07HZ7 |
| standard-acquisition-interface | 01M5DFTHAYC77THNNSN9GXBC90 |
| infrastructure | 01M5DFTHB22JCE92T43C6RQTCY |

Created with native `projects create` through the isolated launcher, without
binding or editing a checkout. Forge's `kata_projects` settings map each UID
on daemon `local` to its exact `github` / `github.com` / `gsa/<project>` repo.
All four persist and resolve as `mapped` after configuration hot reload.
All four issue lists were empty at registration; no Jira or GitHub task import
was requested by that step.

The existing engi-platform, librarian and evaluation projects are preserved.
Adding projects did not broaden agent authority or install application
instructions/hooks. At 17:14 the owner separately approved the application CLI
selection below; this checkout's MCP adapters remain scoped to engi-platform.
Use Kata's project selector to view the application backlogs. Forge owns the
repository mapping, not canonical tasks. No task-backed workspace or coding
loop was launched; evidence is `runtime/falcon-kata-projects.json` under the
private environment profile.

## Operations

The owner's 17:55 request moves Kata to independent boot ownership under
`kenn-kopy-kata.service`, preserving this database/project. Open
`http://127.0.0.1:17777/kata`; choose `engi-platform`, not the earlier synthetic
evaluation project. Use `systemctl --user start kenn-kopy-kata.service` if
intentionally stopped. README owns installation/restart/journal instructions.
Supervisor stop leaves all four boot services running.

`scripts/kata-local.py` selects the private daemon/profile and pins this
workspace, independent of the caller's cwd. It defaults to engi-platform.
Explicit `--project <name>` or `--project=<name>` may select one of the four
registered application projects above, but requires exactly one explicit
`--as copilot` (or `--as=copilot`). Repeated project/actor selectors, other
application actors, unrelated projects and daemon/workspace overrides fail
explicitly. An explicit engi-platform selector retains platform behavior.
The non-platform project opt-in belongs only to this CLI entrypoint; internal
callers, the TODO generator and both MCP adapters retain platform scope.
The owner subsequently approved `--project librarian` with exactly one explicit
`--as pi` or `--as copilot`. Falcon application actor rules are unchanged;
caller repository `.kata.toml` files do not alter the platform default.

The launcher strips inherited credential/actor environment variables; platform
commands retain their existing `--as` behavior. Actor labels are attribution,
not authentication or OS isolation. This entrypoint decision does not approve
particular application tasks, ticket decomposition, workers or publication.
It uses explicit `KATA_SERVER`, so an unavailable daemon fails instead of
silently starting another one. The native secret-free `.kata.toml` binding was
changed from the historical `smoke` project with `kata init --replace`, without
agent or event-hook installation.

Search before creating work, claim before execution, record progress/blockers
and close only after actual verification with issue-specific prose/evidence.
Do not close a task merely because its text was imported. The CLI pin is a
convenience boundary, not OS isolation or issue-level authorization.

After task changes, run `python3 scripts/kata_todo.py` to refresh the generated
block in `TODO.md`. It reads every open task, oldest first, preserves completed
history/notes, refuses missing/ambiguous markers and concurrent file changes,
and fails without replacing the index when the daemon read fails. Do not
manually edit the generated block or treat its cached checkboxes as live state
while Kata is stopped. Root `AGENTS.md` directs agents to this CLI/index flow.
Project-scoped Pi/Copilot MCP is now wired as the first `tvbf` milestone.
The current `tvbf` scope retains Pi attention/lifecycle and interruption/resume
work; the future Copilot model-driven pilot is no longer in active scope.
Existing adapters/configuration and historical evidence are preserved.
README owns repeatable setup/check commands and client restart requirements.

### Scope cleanup: 2026-10-13, 11:46

The owner approved five current-scope updates with all original task text
preserved as historical provenance. `v3sd` is closed as superseded by `k03a`,
not completed; the surviving task owns its workflow/Constitution guidance.
There are now 31 open tasks. Existing blockers/relationships, task identities,
ownership, labels and metadata are unchanged.

Current scopes precede imported history in `k03a`, `tvbf`, `99gr`, `jqwq` and
`vg0b`. Do not treat old four-role, tracker-selection, Copilot-pilot, ACP or
database-deferral language inside those historical sections as active work.
The inactive refinement example is a completed artifact, not a live intake
agent or completion of the remaining Forge/Pi integration.

### Agent integration: 23:16 request

`install-kata-mcp` generates ignored local `.pi/mcp.json` / `.github/mcp.json`
and uses Pi's native trust store for this checkout in the private profile only.
It preserves other servers, refuses a conflicting Kata entry or explicit
distrust, and does not change global client settings. `kata-mcp.py` accepts
only actor `pi` or `copilot`, pins the native single-project stdio server and
strips inherited credentials. No new service/listener is needed.

Both real adapters passed initialize, progressive tools/list refresh (16 to
37 tools), issue read, fixed actor, inbox read and cross-project refusal.
Retry-safe comments on the actual integration task were attributed separately
to Pi and Copilot. Pi's attempt to claim Copilot-owned `tvbf` was refused;
ownership remained Copilot's. Pi SDK execution separately verified dynamic
tool refresh and scope. Cross-project writes also receive explicit scope
refusals before mutation. `copilot mcp list --json` reports `kata` enabled from
the workspace `.github/mcp.json`; it is not a model-driven Copilot test.

The final saved Pi/USAi model pilot selected both loaders, searched the refreshed
catalog, called show/status, and returned exactly
`{"project":"engi-platform","ref":"tvbf","actor":"pi","owner":"copilot"}`.
It used no builtin filesystem tools or Falcon reads and did not mutate the task.
Earlier two pilot invocations restricted the native proxy tools out of the
allowlist and truthfully returned unavailable results, despite CLI exit zero.
They are retained as failed evidence, not counted as successful task reads.
The corrected invocation uses `--no-builtin-tools` without the incomplete
`--tools` allowlist. A known pre-existing schema-extension peer-dependency
warning appeared; no extension upgrade or unrelated fix was attempted.

All 109 focused Python tests pass, including seven new setup/actor/config/
entrypoint regressions. Private JSONL evidence is under `runtime/` in the
environment profile; the saved Pi sessions remain available to AgentsView.
No USD price is inferred from Pi's zero-valued cost fields.
At that milestone, `tvbf` remained open and was explicitly unassigned with a
handoff identifying unproven lifecycle/attention, interruption/resume and a
Copilot model-selected MCP loop. The 2026-10-13 cleanup retains the Pi lifecycle/
resume work but omits the future Copilot pilot without claiming it verified.

## Migration and scope

The source `TODO.md` SHA-256 was
`78502d83fbcd1407260e2929fb99dc9a10540e61b8c7c44b8a8072671cf50539`.
It contained 37 open and 29 completed checklist entries.

- 36 imported open issues preserve all 37 original open descriptions verbatim
  in their bodies, with source-line/hash/section metadata and migration labels.
  Source lines 41 and 72 described the same Helix authentication/repository/
  workspace outcome; both descriptions are retained in task `j54x`.
- The obsolete tracker-selection wording is preserved as provenance in
  `tvbf`, with the owner's adoption decision clarifying that remaining work is
  client integration and a real engineering-task pilot.
- Blocked items retain `blocked` labels. Explicitly deferred CLI/backup/cloud/
  sandbox work retains `deferred` labels; use ready filters in README when
  selecting actionable work. No owners, priorities or completion evidence
  were invented.
- Six blocking links encode explicit prerequisites: prompt demo after prompt
  definition; Helix setup after network access; real Forge retrieval after
  Helix setup; Jira-to-PR flow after Helix setup and Jira intake; workaround
  removal after normal-build verification. No dependency was inferred from
  checkbox order.
- The 29 completed entries stay in Markdown as historical records, not newly
  closed issues claiming fresh evidence. No historical done task was recreated
  and closed.

New task **`5xrm`: Capture the complete environment in a reproducible
redeployment script** is related to fresh-host setup `p4ke` and backup/recovery
`vg0b`. It covers version/build provenance, portable non-secret configuration,
private profiles, loopback services, secure credential handoff, rerunnable
behavior, optional state restoration and a clean-host acceptance check.
No redeployment script/deployment is claimed complete or authorized by recording it.

Database backup remains explicitly deferred to a separate session (`vg0b`).
No database export/copy/backup was made for this migration. The retained TODO
source/receipts are migration provenance, not a database backup.

## Evidence

### Boot-service follow-up: 17:55 request

Task `rw31` records the independent-service implementation and verified close.
The repeatable installer retains the existing config/database and project;
systemd MainPID must match native liveness, database/profile/version checks
and HTML readiness. Unit enablement and the existing lingering manager
configure WSL startup; no WSL reboot was performed.

All 88 focused tests pass. Live service reinstall, restart (PID 24848 to
25008), exact preservation of the then-38 open task records/configuration and
empty-child supervisor start/stop passed. The other service PIDs stayed
395/396/397; Kata inherited no model/provider credential. After closing `rw31`,
the generated index again contains the original 37 open live tasks and the
29 historical completed entries. No experimental supervisor remains.
Private evidence is `runtime/kata-boot-service-verification.json` under the
environment directory. No database backup or agent hook was introduced.

### Original adoption: 17:42 request

Native issue reads verified the 37 live issue UIDs, open state, titles and
exact migrated descriptions. Repeating the full import with stable idempotency
keys created no duplicates. Generated index checks preserve all
29 completed entries. Focused integration coverage includes private CLI
scope/credential handling, snapshot rendering, failure preservation,
concurrent-edit refusal and repeatability.

All 77 focused tests passed. A real stop/start changed Kata PID from 21281 to
23500 while preserving the 37 task identities/bodies and six blocking links.
No new close events were created. The documented ready filters return 26
tasks under the current dependency/label state; this is scheduling state,
not permission to execute every task.

Private provenance is under `.local/environment/runtime/`:
`engi-platform-todo-source-20261012.md` and
`engi-platform-todo-migration-20261012.json`, plus
`engi-platform-kata-adoption-verification.json`. The bounded one-time importer is
retained in the session workspace as `files/migrate-engi-todo.py`; it is not
the promised deployment recipe or an ongoing sync daemon.

At the end of the 17:42 migration, both owned supervisors exited; Kata was stopped with no
17777 listener. AgentsView PID 395, Forge PID 396 and roborev PID 397 remain
healthy and unchanged. An actual offline refresh failure preserved `TODO.md`.
No experimental process, model request, external connection, hook, database
backup, source publication or commit was introduced.
