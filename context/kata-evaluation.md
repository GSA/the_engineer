# Kata evaluation: 2026-10-12

At 17:42 the owner adopted Kata for Engi Platform's existing backlog only.
See `kata-adoption.md` for the current source-of-truth and migration details.
The trial results and initial recommendation below are historical evidence.

**Kata works without a live repository.** A daemon project can hold tasks
without a Git checkout, `.kata.toml`, provider login or model key. This trial
used `kata projects create`, explicit `--project`, the existing private
SQLite profile and synthetic data only. It did not initialize this repository
or change agent instructions.

## Observed behavior

The installed build is `v0.18.0-62-g281caadd`; its live HTTP API reports
`0.24.0` and storage schema 30. Runtime identity takes precedence over example
versions in upstream documentation.

Project `kata-evaluation-20261012` contains one parent and three dependent
children. All four are now closed, with substantive messages and typed test
evidence. These tasks describe the evaluation itself, not a fictitious
application implementation. The parent was parked with `someday=true` so it
would not compete with its children in the ready queue.

| Check | Observed result | Platform value |
| --- | --- | --- |
| Dependencies and priority | `ready` and `next` selected the prerequisite, not the higher-priority blocked children; each close unblocked the next child. | Small agent work plans with explicit prerequisites. |
| Ownership | Two simultaneous CLI actors claimed one child; exactly one succeeded and the other returned conflict/exit 5. | Reduces accidental duplicate work. |
| Human handoff | `work.attention=needs-human` satisfied `wait`; inbox reads preserved a request until `notify --clear`. | Explicit review/decision handoffs across sessions. |
| Completion discipline | Missing-evidence close returned validation/exit 3; parent close with open children returned conflict/exit 5. Both left state open. | Makes completion claims more auditable than a checkbox alone. |
| Events and retry | Cursor polling returned only later events; replaying the original create idempotency key returned the same UID and kept the total at four issues. | Resumable observation and safer automation retries. |
| Search | Lexical search found the closed ownership task without an embedding provider. | Useful retrieval without new model routing or credentials. |
| Native MCP | Stdio initialization fixed project/actor scope; the discovery loader exposed `kata.show`; a real issue read succeeded before and after restart. | Typed agent access is available without UI scraping. |
| Persistence | Restart changed Kata PID from 12696 to 13497, preserving UIDs, close state, dependency readiness and event history. | Durable work state independent of chat history. |
| Forge reads | The live Forge API discovered `local` as connected at API 0.24.0 and successfully searched/read the synthetic issue. Mapping remained `unmapped`, with no repository targets. | Existing backend task visibility works; worktree creation is a separate milestone. |
| Browser route | `/kata` returned HTML/200 with browser-style `Accept: text/html`. | Human inspection uses the same daemon, not a separate task server. |

Two invocation corrections are part of the evidence, not product defects:
`create --meta` stores strings, so reserved boolean `someday` must instead use
`meta set <ref> someday true --json-value`; and a generic `/kata` request
without an HTML Accept header returned 404. The corrected browser probe passed.
No interactive browser editing or rendered Forge issue-panel test was performed.

## Initial recommendation and limits

**Recommendation: retain Kata as a candidate local execution ledger**, then
use it for one bounded synthetic engineering task before selecting the final
task authority. Its strongest value is shared agent coordination, dependency
ordering, durable handoffs and completion history. For one human/agent with a
short linear backlog, `TODO.md` is simpler and avoids another stateful service.

Kata is not an agent launcher, worktree manager or model router. Forge owns
workspaces/review context; Pi/USAi owns model execution; AgentsView owns usage.
Kata has open/closed issue state plus labels/metadata, not our proposed enforced
design/TDD/review/publication pipeline. Typed evidence validates the completion
record; it does not execute the referenced test or independently prove success.
Local actor strings attribute requests; this trial did not establish an
authenticated multi-user deployment or OS sandbox.

No repo is needed for task/CLI/MCP evaluation. A real configured repository and
mapping are needed to exercise the intended Forge task-to-worktree flow.
Actual Pi/Copilot Kata tool use, attention hooks, policy loading, Jira intake,
provider links, publication gates and backup/restore remain unverified.
Native MCP success alone does not mean those clients are configured for Kata.

Keep Jira as the eventual business-ticket authority and preserve its original
key/URL/criteria when creating local execution tasks. Do not silently maintain
the same operational backlog independently in Jira, Kata, Ouijit and Markdown.
At trial time, `TODO.md` remained authoritative pending the owner's migration
decision; it is now a generated index of the adopted Kata backlog.
No Jira connector or synchronization was validated by this trial.

## Evidence and shutdown

Private records under `.local/environment/runtime/`:
`kata-evaluation-20261012-{ids,before-restart,browser,after-restart,final}.json`
and `kata-evaluation-mcp.log`. The initial incomplete pre-restart record retains
the HTML-probe failure; the browser correction and successful restart phase
are separate records. The bounded assertion client is retained in the session
workspace as `files/kata-evaluation-check.py`, not installed platform tooling.

Both test-owned supervisors and stdio MCP processes have exited. Kata is
stopped again with no port-17777 listener; the synthetic project/data remain
for inspection. AgentsView PID 395, Forge PID 396 and roborev PID 397 stayed
healthy and unchanged. No new hook, agent-profile change, model request,
Helix/Jira connection, Falcon edit, publication or commit occurred.
README documents restart and inspection commands.
