# Engi Platform Kata backlog

The owner adopted Kata at 17:42 on 2026-10-12 for **this project only**.
Project `engi-platform` owns live task state. `TODO.md` is its generated
open-task index plus historical completed Markdown records. Keep detailed
decisions, evidence and operating boundaries in `context/`, not duplicate
task lists. Falcon's checkout, instructions and backlog were not changed.

## Operations

The owner's 17:55 request moves Kata to independent boot ownership under
`kenn-kopy-kata.service`, preserving this database/project. Open
`http://127.0.0.1:17777/kata`; choose `engi-platform`, not the earlier synthetic
evaluation project. Use `systemctl --user start kenn-kopy-kata.service` if
intentionally stopped. README owns installation/restart/journal instructions.
Supervisor stop leaves all four boot services running.

`scripts/kata-local.py` selects the private daemon/profile and pins this
workspace and project, independent of the caller's cwd. It strips inherited
credential/actor environment variables; use `--as` when attribution should
name an agent instead of the local user. Scope overrides fail explicitly.
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
Native automatic Pi/Copilot MCP and attention-hook wiring is still task `tvbf`.

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
