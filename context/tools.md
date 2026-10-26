# Upstream components

## Installer simplification and Kata pickup evidence: 2026-10-26 (rzsc)

Source cleanup is committed as a650c44. One MANAGED_SERVICES tuple replaces
repeated installer inventories; a runtime set mismatch fails before port
checks/builds/configuration. Tests execute the actual CLI help for all four
install commands rather than trusting mocked dispatch alone.

Manual Kata startup pins KATA_DSN and clears KATA_DB. Generated native units
and the supervisor reuse kata_environment; it is not applied to ordinary
client invocations. Removed duplicate kata_command validation. Synthetic
native Kata processes launched from printed commands and generated-unit
settings selected the expected private db_path despite inherited and stored
overrides, left all alternate database paths absent, and preserved config.
Both processes were stopped and temporary fixtures removed.

146 environment/hook/installer tests passed after the final shared runtime
fix. Commit a650c44 also captured late concurrent roborev follow-up hunks in
the shared files; this was disclosed on 9hj3, not rewritten away. Exact review
86 found a roborev replacement-unit rollback issue, not a Kata/installer
finding. Its owner fixed it in 3365355; stored review 87 passed. Do not describe
review 86 itself as a pass. Existing live units were not reapplied by rzsc.

Live Forge GETs found the native `local` Kata daemon connected. Project
mappings resolve only the four earlier Falcon application projects;
engi-platform, librarian and spud are unmapped. Forge creates/reuses a mapped
task workspace after an explicit request; task creation does not dispatch an
agent or claim/close a task. Source references and the supported handoff are
in engineering-workflow.md; existing demo task jgcf records the integration
gap. No provider catalog, repository mapping or remote was changed.

## Native roborev convergence: 2026-10-26 (Kata 9hj3)

Owner's update replaced the former ~/.local/bin/roborev launcher symlink with
native v0.73.0. Its ordinary HOME discovered a new ~/.roborev store and TUI
started PID 38540 on 7373, while managed PID 419 still ran the pinned v0.71.0
binary/private store on 17373. This was two binary/state identities, not a
missing process-killing script.

Waited until both had no queued/running reviews, then paused queues and took
online snapshots. Stopped secondary with native daemon stop and old managed
service through systemd. Preserved the complete secondary directory (one
canceled job) at runtime/roborev-native-9hj3/secondary-profile; ~/.roborev now
symlinks to the established managed store. No SQL merge or history deletion.
Normal CLI discovery and idempotent native daemon start both return the same
managed v0.73.0 PID 44494; 7373 is closed, API/UI stay at 17373/17374.

The unit directly executes ~/.local/bin/roborev with the existing private
environment, working directory and Pi/Node path. Installer --binary persists
that choice in roborev-service.json; reruns preserve it. Compatibility hook
entrypoints and foreground execution share the choice, including child PATH,
so they cannot accidentally select the old source build. Removed the obsolete
install-roborev-cli command that would recreate the updater-vulnerable wrapper
symlink. No new dispatch/update script or upstream source change.

Native v0.73 migration introduces zstd job_content. Verified exact retained
columns for 34 repos, 66 commits, 82 jobs, 75 review documents and 5 responses,
except 19 stale worker IDs cleared by native startup. All 118 nonempty job
payloads match after zstd decompression. Native job-prompt precedence collapses
different review-prompt copies for jobs 44/45/47/48/50; originals remain in
managed-before.sqlite3. Do not claim every old column is byte-identical.
Private integrity-result.json records counts and this distinction; raw content
was not printed. Pi settings/models/MCP hashes are unchanged.

The first generated WorkingDirectory incorrectly reused ExecStart quoting;
systemd-analyze rejected it before reload/start. Corrected the path directive,
then verified the actual unit and repeat installation. 139 focused environment,
hook and installer tests initially passed with the existing pinned Pi on PATH. Existing
review hooks remain intact and use the canonical native binary through their
compatibility entrypoint.

Runtime commit c9ae1c1 and follow-ups 3e31ddf/a650c44 received completed failing
reviews 84/85/86: selecting another binary while active, a late-start race,
then a rejected install leaving the replacement unit armed for next restart.
Added helper-level stopped-state refusal, actual /proc executable identity
verification and previous-unit rollback/reload without killing active work.
The identity changes landed alongside concurrent rzsc changes in a650c44;
history and those independent Kata/installer edits were preserved.
Final rollback commit 3365355 received exact-commit job 87: completed/pass,
no issues. All 116 focused environment/hook tests pass after that fix; the
preceding combined environment/hook/installer suite passed 146 tests.
Same-binary live reinstall retained PID 44494. Final native status and legacy
compatibility status agree; no duplicate warning, queue idle/unpaused, old port
7373 closed. Forge/Kata/AgentsView remained active at 35810/23538/417.

Native update --no-restart avoids detached-daemon ownership and hook/skill
rewrite. Pause/wait for running work, update, systemd restart, then unpause.
This shared default prevents the old update-induced split; explicit alternate
ROBOREV_DATA_DIR profiles can still create independent instances. An already
open TUI targeting 7373 must be closed/reopened, not forcibly killed.

Read-only Git checks: ~/kenn-kopy, ~/the_librarian and ~/falcon-docs have no
remotes; ~/aos-spud has origin github.com/GSA/aos-spud.git with authenticated
pull access. Forge's four visible GSA entries are application mirrors, not
these intended engineering projects. README names the actual entries and the
local-project UI limitation. No new provider repo was added in this task.

## Restored Forge and remote-free Git evidence: 2026-10-26 (Kata 7pq7)

Restored the existing `install-forge-service`/managed-service boundary in
`scripts/local_env.py`, using the same private profile and pinned temporary
binary `v0.3.0-136-gd6b14b9f-local-kata`. The native four-service installer
invocation is supported again; no dependency upgrade/build or provider change.
The foreground supervisor can own Forge when it is not independently managed.
Status distinguishes the managed unit from a foreground probe and checks the
runtime PID/address/data/config identity, health version/revision and HTML.

Installed the unit, repeated installation, then restarted only Forge.
`systemctl --user` reports enabled/active/running; PID 35810 and listener
127.0.0.1:18091. Original AgentsView/roborev/Kata PIDs remain 417/419/23538.
SHA-256 comparisons preserve environment.json, Forge config and all three
Pi settings/MCP/model files. Pre-start private online SQLite snapshot and
metadata are `runtime/forge-restore-before.sqlite3` and
`runtime/forge-restore-before.json`; no credentials or corpus text are committed.

Actual installed API, disposable repository with an initial empty commit and
zero remotes:

- `POST /api/v1/projects` with local_path/default_branch registers without
  platform_identity. Existing primary worktree discovery is separate from the
  provider workspace catalog.
- `POST /api/v1/projects/{id}/worktrees` with branch, path, base_ref and
  create_on_disk=true creates the Git branch and linked worktree.
- Worktree `POST /runtime/sessions` with a synthetic command launches a live
  tmux-backed process. Native runtime listing plus tmux pane_current_path verify
  the process is in the new worktree; DELETE stops only that session.
- Worktree `POST /delete` with remove_from_disk/remove_branch refuses an
  uncommitted file with HTTP 409. Removing only our synthetic file permits
  clean deletion. Fixture project registration and temporary tree are removed.

Saved bounded result: `runtime/forge-local-smoke-result.json`. No model request
or real-project mutation was part of this smoke. Existing project's launch
targets report Pi (USAi) available through pi-local.py; other model targets stay
disabled. Terminal-agent launch is supported by source, not newly demonstrated
model-selected retrieval. Project runtime rejects workspace-only ACP targets.

Source confirms NewWorkspaceDialog reads RepositoryReads/provider identity;
WorkspaceFirstRunPanel offers local intake without gh auth. Thus no-remote Git
is supported by the backend, while registration does not bridge the main UI
catalog. A fake remote, a local bare remote or publication is not the fix.
README now gives first-session UI guidance and a native Git/private-Pi fallback.
No submodule changes or bespoke local-project launcher were introduced.

123 local-environment/installer tests pass with the already-installed pinned
Pi on PATH (`PATH=/home/nkirrish/.nvm/versions/node/v26.9.0/bin:$PATH
PYTHONPATH=scripts python3 -m unittest scripts.test_local_env dist.test_install`).
Initial default-PATH run hit the known global Pi 1.3.0 versus required 1.0.3
fixture mismatch; no dependency installation or global setting change was
needed. Test teardown now restores cwd after the foreground launcher test.
Exact runtime commit bc00164 received roborev job 80: completed/pass, no
actionable issues. Review inference is distinct from the model-free local
project smoke; no real coding session or end-to-end task loop is claimed.

## Cleanup lifecycle reconciliation: 2026-10-26, 17:03

The owner resolved the earlier concurrent-edit blocker: Forge is required for
agent execution, not a dormant optional component. Runtime restoration is now
committed separately in bc00164/18ba217. Read Forge README, commands and runtime
contracts: native `daemon start` owns detached execution; `serve` is foreground.
Keep the existing user-systemd owner running `forge-run`/`serve`, not both.
Read-only checks found the unit enabled/active/running, Restart=on-failure,
WantedBy=default.target, user Linger=yes and a healthy loopback endpoint.
No service was restarted or configuration changed by this reconciliation.

Updated rzsc to retain four services and its independent Kata safeguards;
closed k79n `wontfix` rather than create unnecessary optional packaging. Eight
backlog items remain active. Prior review 78 covers the old design, not the
reconciled service boundary; final review/commit evidence belongs to ycns.
Stored managed design review 82 passed the reconciled six-file diff with no
findings. The default `roborev` CLI now routes to a separate v0.73.0 daemon;
this task's initial review there (job 1) was canceled, not accepted as evidence.
Review 82 used the pinned `roborev/bin/roborev` with explicit
`--server http://127.0.0.1:17373` (managed v0.71.0). Neither daemon was stopped
or reconfigured. Preserve the existing scoped commit hook.

## Cleanup refinement evidence: 2026-10-26 (Kata ycns)

See `refactoring.md` for the nine task references, source-backed deletion
targets, preserved behavior and first bounded design. Parent inspected Engineer;
two read-only scouts inspected Librarian/Falcon and externally owned SPUD.
No neighbor source was edited. A follow-up challenged suggested abstractions:
XLSX helper extraction and typed coverage-loader replacement were rejected
because they add compatibility/freshness complexity rather than remove it.

Native Kata records use repo metadata to distinguish both Librarian checkouts.
Only the producer-to-receiver dependency is added: spud#3sv9 blocks
librarian#55nx. Existing p4ke/5xrm, 51kq and vkye/1dkw remain authoritative for
their broader scope. No shared binding is changed or historical task moved.

Managed roborev is healthy. Stored job 75 for prior architecture commit c1acc84
reports pass/no issues across seven files; that is not a review of this later
refinement or proof of a working environment. Subsequent review evidence belongs
to this task's exact diff/commit. No new product/model trial is enabled.
Stored dirty design review 76 completed with two medium findings: missing
managed Kata storage-override coverage and missing fresh-host native CLI/client
provisioning. Source confirms both. Created 0sfx under p4ke. Review 77 found
that a stored `[storage].dsn` still redirects Kata after environment clearing;
rzsc now requires an authoritative managed KATA_DSN plus checks covering both
inherited variables and conflicting stored configuration. Stored design review
78 passed with no findings on the revised five-file diff. Runtime fixes remain
unimplemented. This review preceded the required-Forge clarification above;
final local commit and commit-review evidence belong to ycns. No broad runtime
suite is needed for this documentation-only work.

## Cross-project architecture evidence: 2026-10-26 (Kata qt7g)

Detailed current evidence and proposals are in `system-architecture.md`;
selective-memory requirements and a bounded pilot are in
`engineering-memory.md`. These supersede the action-ledger emphasis of the
earlier research for this request, not the provenance/handling safeguards.

Inspected all four top-level READMEs, local instructions, relevant roadmap/
decision/operating files and native Kata records. SPUD's local ingestion CLI
calls separate Jira/Confluence exporters and then renders/packages output;
Graphify is a separate repository pipeline. Its graph-index generator emits
nodes, not edges. No Drive connector or code-query MCP was found in inspected
SPUD source/docs/manifest; this is not a claim about other branches/services.

Both Librarian checkouts bind to Kata project `librarian`; no binding or task
was moved. Falcon has broader instance tooling and retained data, not version
parity with the data-empty toolkit. Toolkit policy/store-path/index identity
limitations remain relevant to reproduction. Engineer installer source still
expects legacy qualified-context-mcp and invokes removed install-forge-service
in its user-service branch; these are open p4ke/5xrm integration gaps, not
fixed by the architecture documents.

Public Hindsight/Mem0 docs fetched successfully. Hindsight's standard coding
integration auto-ingests conversations/history and auto-updates; explicit
selected-record retain/recall, not that default installer, fits a first pilot.
MCP authentication is off by default; bank paths/metadata filters do not prove
authorization. No Pi web-provider test, model pilot, product install or private
upload occurred. Existing configured commit-review hooks remain enabled.
Prior conversation-history search did not recover the recent
thread; use the supplied transcript plus existing context as historical basis.

Moved `../the_librarian/tmp_convo.txt` into ignored
`.local/context-inputs/tmp_convo.txt`, mode 0600, preserving 60,317 bytes and
SHA-256 `a6bef1456fc65a3d4c28f8197e3a05e5598e7c7513daa1f2bfe90cee68332671`.
It is a private input, not a distributable document or new memory ingestion.
No neighboring source/store changes beyond the requested untracked-file move.

## Centralized agent memory/event-store research: 2026-10-26 (Kata 8cne)

Public HN Algolia story searches covered agent memory, MCP memory, shared
memory, action ledgers, event stores, named products and recent submissions.
Product capabilities below are checked against current upstream documentation,
not deployment evidence. HN points measure discussion visibility, not adoption
or correctness; several plausible products have only 2-9 points.

The important split is exact events versus derived recall. An agent saying
"deployment succeeded" is not evidence that deployment succeeded. Preserve tool
outcomes and evidence references, explicit failure states, actor/session/project/
task identity, event IDs and timestamps. A memory engine's ADD-only extraction,
immutable nodes or source episodes do not establish a complete, append-only,
tamper-proof execution ledger. MCP is access, not automatic event capture.
Capture through runtime/tool hooks for completeness rather than relying solely
on the model remembering to write. Treat retrieved memories as untrusted data.

Main candidates:

| Candidate | Hosting and MCP evidence | Fit and limitations |
| --- | --- | --- |
| Hindsight (Vectorize) | Self-hosted Docker/Helm with PostgreSQL + pgvector; managed cloud. Built-in HTTP MCP, bank-scoped endpoints, retain/recall/reflect. | First shared-memory pilot candidate: experience/fact memory and evidence-backed observations. MIT. Extraction/model routing, retention and exact-event durability still need evaluation. MCP is unauthenticated by default; API-key tenant extension is documented. |
| Graphiti / Zep | Graphiti is self-managed; Neo4j, FalkorDB or Neptune backends. Reference HTTP/stdio MCP. Zep is a distinct managed/BYOC product, not a hosted drop-in promise for the OSS MCP. | Strong temporal history and source-episode provenance. More graph/service operations. Reference MCP explicitly lacks authentication/authorization and is not for production; tenancy and access control must be supplied. |
| Mem0 | OSS self-hosted server and managed platform; official authenticated remote MCP documents memory CRUD and memory-operation events. | Useful established comparison baseline. Current April 2026 algorithm describes ADD-only extraction and agent-action facts; that still is not a lossless execution log. Managed optimizations differ from OSS. Hosted MCP verified; self-hosted MCP parity needs separate confirmation. Historical openmemory directory is now 404. |
| Cognee | Self-hosted and Cognee Cloud; MCP supports stdio, SSE and Streamable HTTP, local/API/cloud modes. | Good shared company/project brain from docs, code and session lessons. More knowledge processing than action-ledger infrastructure; do not equate rotating tool logs with a durable ledger. |
| LongMemory (CaviraOSS, formerly OpenMemory) | Self-hosted TypeScript service with SQLite; REST plus stdio/authenticated Streamable HTTP MCP. | Particularly relevant immutable-content/provenance and recorded-time/valid-time model, decisions/project-event tools. Single-server SQLite is not proof of HA or distributed-writer scale. Temporal/governance claims require a bounded pilot. Not Mem0's different OpenMemory project. |
| kcap (Kurrent, formerly Capacitor) | Hosted workspace; documented local server is Mac-only/loopback/personal. Local stdio MCP adapters call authenticated workspace APIs; session-read and memory-write tools exist. | Closest action-capture fit: session/tool/result/commit recording into KurrentDB event streams plus recall, handoffs and team memory. Supports Copilot CLI and Pi (Pi uses an extension bridge). Invite-only; self-managed multiuser Linux/AWS deployment is not established by current docs despite homepage self-management language. Broad runtime/task features overlap existing authorities. |

Primary sources and HN discovery:

- Hindsight: https://github.com/vectorize-io/hindsight and
  https://hindsight.vectorize.io/developer/mcp-server ;
  https://news.ycombinator.com/item?id=46294975 (4 points, 2025-12-16).
- Graphiti: https://github.com/getzep/graphiti and
  https://github.com/getzep/graphiti/blob/main/mcp_server/README.md ;
  https://news.ycombinator.com/item?id=41445445 (142 points, 2024-09-04).
- Mem0: https://github.com/mem0ai/mem0 and
  https://docs.mem0.ai/platform/mem0-mcp ;
  https://news.ycombinator.com/item?id=41447317 (201 points, 2024-09-04).
- Cognee: https://github.com/topoteretes/cognee and
  https://github.com/topoteretes/cognee/blob/main/cognee-mcp/README.md ;
  https://news.ycombinator.com/item?id=44169594 (9 points, 2025-06-03).
- LongMemory: https://github.com/CaviraOSS/LongMemory and its docs/mcp.md;
  https://news.ycombinator.com/item?id=46262294 (48 points, 2025-12-14).
  The HN thread refers to its earlier OpenMemory name/version.
- kcap: https://www.kurrent.io/docs/ and its configuration/local-edition/
  and reference/mcp-tools-and-skills/ pages;
  https://news.ycombinator.com/item?id=48734560 (2 points, 2026-06-30).
  HN's Capacitor URL redirects to the current kcap site.

Other relevant findings:

- AWS AgentCore Memory: managed AWS service, not self-hostable software.
  AWS Labs MCP now includes operational memory event/record tools, not only
  documentation search. Raw event retention is at most 365 days, fixed at
  write time; extending the setting cannot extend already-written events.
  Thus it cannot alone be a permanent raw ledger. Region/service approval and
  model-processing authorization in the eventual GSA environment are unknown.
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-create-a-memory-store.html
  https://awslabs.github.io/mcp/servers/amazon-bedrock-agentcore-mcp-server
  HN platform launch: https://news.ycombinator.com/item?id=44583456 (4 points).
- Mnemora: README describes own-account AWS CDK deployment with DynamoDB/S3
  append-only episodic events plus Aurora pgvector semantic memory. No native
  MCP documentation/path found in the inspected repository tree; SDK/REST.
  Early candidate, not selected: handler documents 48-hour hot TTL and an
  archival library, so archival wiring/replay must be proven before trusting
  durability. README labels infra/api BSL 1.1, SDK MIT; actual license terms
  need reconciliation before adoption, not an unqualified OSS assumption.
  https://github.com/mnemora-db/mnemora ;
  https://news.ycombinator.com/item?id=47260077 (4 points, 2026-03-05).
- Supermemory: current remote OAuth MCP supports authorized shared spaces.
  Current downloadable self-hosted server is non-public-source and its feature
  comparison explicitly excludes Supermemory MCP; do not conflate a self-hosted
  adapter calling their cloud with owning the memory backend.
  https://supermemory.ai/docs/self-hosting/overview
  https://supermemory.ai/docs/supermemory-mcp/mcp
  https://news.ycombinator.com/item?id=44218106 (4 points, 2025-06-08).
- MemMachine: Apache-2.0, self-hosted/managed, native HTTP/stdio MCP, episodic
  Neo4j plus SQL profile memory. Another comparison candidate, not a demonstrated
  exact action ledger. https://github.com/MemMachine/MemMachine ;
  https://news.ycombinator.com/item?id=46008220 (4 points).
- Letta has shifted active development to letta-code; the former API server is
  archived. It is an agent harness/platform, less suitable as a neutral drop-in
  memory store. https://github.com/letta-ai/letta ;
  https://news.ycombinator.com/item?id=43294974 (121 points).
- HN's Elasticsearch memory thread (116 points) argues both for a shared team
  service and against needless operational complexity. The linked implementation
  is a demo, not a production-ready ledger; it explicitly omits agent replies
  and some advertised production guards.
  https://news.ycombinator.com/item?id=48583703
  https://www.elastic.co/search-labs/blog/agent-memory-elasticsearch
- Simpler baselines: Memoryfields (191 HN points) is a portable Markdown/
  optional SQLite format, not a multiwriter service; fellowgeek/mcp-memory
  (70 points) is local project files/SQLite, not established hosted infrastructure.
  LedgerSync is append-only local JSONL, not a centralized service.
  OneMemory's new HN submission describes HTTP/MCP shared notes but its own
  README says only the latest note body is retained; metadata change history
  is pruned after 90 days. These are not equivalent to a durable action ledger.

Recommendation is a proposal: compare Hindsight for portable shared recall,
Graphiti for temporal provenance, and kcap for actual action capture (subject to
deployment availability). LongMemory merits a smaller ledger-shaped pilot.
Keep exact raw events as authoritative and semantic memory as a rebuildable,
source-linked projection, potentially in one service/database. Require restart,
retry/idempotency, concurrent-agent isolation, exact evidence retrieval,
read-after-write, backup/restore and export/retention demonstrations before
adoption. Preserve Kata's task authority and Falcon's qualified-source interface;
no selection, new service, cloud account, hook or private-content upload occurred.

## Native Kata usage (2026-10-26; supersedes launcher guidance below)

`~/.local/bin/kata` points directly to `/home/nkirrish/kenn-kopy/kata/kata`.
Native `~/.kata/config.toml` selects named URL target `engi-platform` at
`http://127.0.0.1:17777`. This is a daemon name, not a project restriction.
CLI uses normal `.kata.toml` bindings/flags and native attribution. Shell
startup files were unchanged. Reinstall with a direct binary symlink plus
native active_daemon/daemon URL config; do not recreate a dispatcher.

Deleted kata-local.py, kata-mcp.py, Kata-specific MCP checker/pilot/trust
helpers, kata_todo.py and tests, and the newly added shell wrapper. Removed
custom project/actor guards and kata-run dispatch. Local Pi/Copilot configs
now run the binary with `mcp serve`, repository cwd and explicit loopback
KATA_SERVER; other servers/profile settings are preserved. These configs and
user config are private/ignored, so README documents repeatable native setup.
Existing MCP sessions need reconnect/restart; old in-memory adapters do not
magically reload. No custom trust installer or new attention hook.

The enabled user service executes the binary directly, with explicit managed
KATA_HOME; current PID 23538. Database remains `.local/environment/kata/kata.db`
(schema 30, same binary). Shared installer/health checks remain in local_env.py
so redeployment and dashboard status still work, not as runtime wrappers.
Private online rollback snapshot: runtime/kata-native-cleanup/before.sqlite3.
All 8 project rows and 68 tasks preserved across restart; 67 task rows exact,
only tracking task tvbf changed by explicit Pi claim. All 58 original comments
preserved plus cleanup progress. Native health/CLI and stdio initialize, loader,
rediscovery/task read pass. Pi reports Kata connected (16 initial tools);
Copilot lists native workspace config. These are connectivity, not model pilots.

89 local_env tests pass; combined installer suite passes 115/116 with an
unrelated existing isolated Pi startup check failing. Direct existing-profile
Pi version/MCP list works. TODO generated live block is retired; completed
history remains. No application repository initialization or publication.

# Librarian Kata CLI access (recovered session)

`local_env.py::kata_project_scope` now accepts explicit `--project librarian`
only through the existing CLI opt-in. Exactly one explicit `--as pi` or
`--as copilot` is required; inherited actors, abbreviations, duplicate actors/
projects and daemon/workspace overrides cannot select a different scope.
Caller `.kata.toml` is intentionally not consulted; engi-platform remains the
default. Falcon applications still require Copilot and MCP remains platform-only.

Use `python3 scripts/kata-local.py --project librarian --as pi list --json`.
Live reads resolve nine issues in project ID 26; both explicit actors resolve
correctly. `PYTHONPATH=scripts python3 -m unittest scripts.test_local_env
scripts.test_kata_todo` passes 118 tests. `python3 scripts/check-kata-mcp.py`
passes both actors, platform binding and cross-project read/write refusal
without model calls or pilot comments. No Librarian issue was mutated.

# Single roborev command and duplicate diagnostics: 2026-10-24

Owner approved deleting the unused global installation, not retaining another
profile for history. Removed the old ~/.local/bin/roborev executable and
~/.roborev (three legacy jobs plus config/logs/cache), after confirming no
legacy listener or daemon. The managed database was untouched. Git does not
contain those ignored historical records; deletion was explicitly approved.

`python3 scripts/local_env.py install-roborev-cli` installs a symlink from
~/.local/bin/roborev to this checkout's scripts/roborev-local.py. Existing
conflicts require explicit inspected --replace-existing; reruns are no-ops.
No second wrapper or binary is installed. The entrypoint resolves its real
script directory so Python imports work through the symlink from any cwd.
Use `roborev status`, `roborev ui`, `roborev show --job N` and `roborev review`.
Existing external hooks retain their absolute scoped path; no migration needed.
Keep the thin Python entrypoint: native config alone does not disable automatic
discovery/startup, and a shell replacement would duplicate private environment,
validation and guard logic. Read-only scout source inspection confirms this.

Native daemon and update commands are blocked at the managed entrypoint:
use systemctl --user start|stop|restart kenn-kopy-roborev.service and deliberate
pinned source/build updates. This prevents native lifecycle from escaping
systemd ownership. API address overrides remain blocked.

`roborev status`/`doctor` print read-only warnings on stderr for loopback
listeners at native port 7373 (IPv4/IPv6) and roborev daemon-run processes
outside the managed unit/verified optional supervisor. local_env.py status
returns the same roborev_warnings list. Diagnostic inspection never signals
processes. A temporary real loopback socket verified the warning and was closed.

# roborev model recovery and UI checks: 2026-10-24

The catalog refresh below removed the active private GPT-5.6 entry while
`usai.json` still selected it. Pi 1.0.3 used an unknown/custom-model fallback
that emitted a developer role, which USAi rejected with HTTP 422. The selected
alias is still advertised in the saved USAi catalog. Restored it in private
`pi/models.json` with `compat.supportsDeveloperRole = false`, verified by a
completed structured Pi/USAi review (job 36). Global Pi remains unchanged;
private Pi now lists eight entries, global Pi still seven. The earlier
seven-entry discovery update was not proof of continued launcher compatibility.

`scripts/local_env.py pi_launch` now rejects an active model absent from the
private catalog before loading credentials; it never silently chooses a new
model or accepts Pi custom-model fallback. Keep the selected verified entry
during future discovery refreshes. This guard is covered by a regression test.

Use `python3 scripts/roborev-local.py ui` to open the managed browser UI, or
visit http://127.0.0.1:17374/reviews directly. Browser navigation requires
`Accept: text/html`; bare curl (Accept: */*) returns 404 by design. Check with
`curl -H "Accept: text/html" http://127.0.0.1:17374/reviews`. HTML and embedded
JS/CSS returned 200; this is HTTP evidence, not an interactive browser test.
No extra daemon should be started on native default 7373.

Synthetic recovery fixture and saved job response remain private under
`.local/environment/runtime/roborev-recovery-smoke/`. Job 36 detected the
intentional inverted even predicate; its fail verdict means findings, not an
agent execution failure. No historical failed jobs were resubmitted.

# USAi model-router catalog refresh: 2026-10-24

A fresh authenticated `GET /models` through `local_env.py list-models` returned
24 unique IDs. Compared with the 2026-10-20 discovery catalog, advertised
additions are `claude-sonnet-5.5`, `gpt-6-astra`, `gpt-6-luna`,
`gpt-6-sol-latest-guardrails-defaultv2` and
`gpt-6.1-sol-latest-guardrails-defaultv2`; older Gemini 2.5 aliases disappeared.
The private timestamped catalog is `.local/environment/usai-models.json`.

Normal Pi (`~/.pi/agent/models.json`) and private platform Pi
(`.local/environment/pi/models.json`) now expose the newest advertised
per-family set:

- `claude-opus-5`, `claude-sonnet-5.5`
- `gemini-3.8-flash`
- `gpt-6-astra`, `gpt-6-luna`, `gpt-6.1-sol-latest-guardrails-defaultv2`
- `llama_4_maverick`

Both files remain 0600 and Pi lists the same seven aliases from each profile.
The selected launcher default remains the previously verified
`gpt-5.6-sol-latest-guardrails-defaultv2`; model discovery does not prove chat,
streaming or tool-call compatibility, so the newly advertised aliases were not
made the runtime default or invoked. Endpoint, protocol, credential references,
MCP settings and sessions are unchanged.

# Quiet roborev fail semantics: 2026-10-24

For `roborev review --dirty --wait --quiet`, a completed review with findings
returns exit 1 and deliberately prints nothing. In pinned v0.71.0 this flows
through `review.go` (`waitForJob`, `silenceIfExit`, then deferred `quietExit`);
it is not evidence that the scoped Python wrapper failed before enqueue.
Runtime/configuration failures still carry a cause internally, but quiet mode's
exit sentinel suppresses Cobra output.

For retained synthetic snapshots, query the exact repository rather than using
an unscoped list:

```
python3 scripts/roborev-local.py list --repo /absolute/snapshot/repo \
  --all-branches --limit 10 --json
python3 scripts/roborev-local.py show --job JOB_ID --json
```

The retained Librarian snapshot `f4f3a3abc760f1cbe97a604f9e60e4ab` produced
completed failed jobs 26-29. Job 29 is the latest review. Its findings concern
bounded diagnostic capture, race-safe result-file reading and standard test
discovery. The review gate correctly treats a fail verdict as a commit block.

The repeated-review follow-up (Kata p2v5) supersedes the unique-job diagnostic
restriction described below, not the unique-job approval requirement. The gate
now queries --repo <exact snapshot> --all-branches --limit 10 --json and validates
each done/fail list/show identity independently. Failed execution statuses are
reported separately. History is explicitly not attribution of the command exit.
Findings share a 16,384-character budget across returned rows; missing one show
does not hide other verified results. Verified failing IDs persist separately as
result.json diagnostic_job_ids; approval job_id semantics stay unchanged.
50 synthetic gate tests and 74 standard tests pass in the Librarian venv. Native
read-only history verifies IDs 42,40,29,28,27,26 and infrastructure job 34 without
submitting a review. Scoped delta and output are private runtime artifacts, not
committed corpus data; Librarian pre-existing staged work is preserved.

Historical first fix:
The owner's diagnostics-only follow-up adds exact-snapshot failed-job lookup
and bounded stored output to the Librarian gate's nonzero review path. Findings
are limited to 16,384 characters in the diagnostic; full text remains in the
stored job. Matching list/show identity and explicit integer fail verdict are
required; ambiguity is not resolved by choosing the newest job. Error evidence
is written to the run's `review.log`, while `result.json` stays blocked.
44 gate tests cover output retention/bounds, unavailable queries, mismatched
jobs and unchanged failure gates; 72 standard tests pass in its installed venv.

# One managed roborev daemon and hook migration: 2026-10-23

Official roborev usage centers one daemon/database serving multiple registered
repositories; isolated daemons are an escape hatch, not the normal topology.
This workspace now follows that model for `~/the_librarian` as well as the six
previously managed repositories. The hand-started global daemon on
`127.0.0.1:7373` (PID 7233, data `~/.roborev`) was stopped with its own explicit
server address. Its two historical records remain in that database but were not
migrated. The managed `kenn-kopy-roborev.service` stayed active as PID 401 on
loopback 17373/17374 with one worker, scoped `pi-local.py`, and USAi routing.
The global config retains `default_agent = 'pi'` as defense in depth if an
operator deliberately starts that daemon later.

`~/the_librarian` had a hybrid hook setup: its repository-owned untracked
`.githooks/pre-commit` already used the scoped launcher, while native roborev
post-commit/post-rewrite/pre-push hooks baked in `~/.local/bin/roborev` and
therefore reached the global daemon. The chosen migration uses the established
private staging topology under
`.local/environment/roborev/hooks/34f026ce6c3644e2/hooks`. Its original
`.githooks` bytes are unchanged; the pre-commit gate is copied byte-for-byte,
the three roborev hooks select `scripts/roborev-local.py`, global executable
fallback is removed, and `core.hooksPath` selects staging. The existing local
`roborev.precommitLauncher` remains unchanged. The repository is registered in
the managed database with zero jobs; migration itself queued no review.
Its ignored `.roborev.toml` selects Pi/standard commit reviews and a new
`toolkit` guideline derived from its AGENTS.md: reusable/data-empty defaults,
no seeded demo corpus, no weakened integrity checks, and no claims that planned
automation is installed.

The earlier installer guard rejected every existing `post-rewrite`, even a
native generated roborev hook that native installation safely replaces rather
than chains. `scripts/roborev_hooks.py` now recognizes the stable generated
marker prefix without pinning a version, so current and old native hooks can be
copied and upgraded while a foreign post-rewrite still fails closed. It also
adds explicit `--restage`: a saved-manifest/active-path mismatch remains an
error by default, but after human inspection this option copies the active hooks
into private staging and updates rollback metadata. This repaired the existing
`~/falcon-docs` mismatch without changing its dirty worktree or original
`.githooks`. Use `--restage` only for a deliberate inspected recovery, never as
a routine bypass.

Focused verification: `PYTHONPATH=scripts python3 -m unittest
scripts.test_roborev_hooks` passes 16 tests, including old native rewrite
versions, foreign rewrite refusal, original-hook preservation, scoped routing,
manifest mismatch refusal/recovery, rollback and rerun stability. Both Pi auth
paths were also checked on 2026-10-23: managed roborev `check-agents` completed
a real private Pi/USAi request, and ordinary global Pi completed a minimal
no-session request through the `usai-key.py` command. `scripts/pi-local.py` and
`scripts/usai-key.py` hash-match committed bytes. The 401 still visible in the
all-agent health output is Codex contacting OpenAI with ignored user config,
not a Pi authentication failure. The unrelated pre-existing dirty
`scripts/local_env.py` Forge lifecycle rewrite was preserved and not attributed
to this work.


# Dual-remote sync tool: 2026-10-21

`scripts/sync-helix-gsa.py` maintains one working clone per repository that
carries both remotes, which is what makes continuous pull and later push-back
possible. `scripts/mirror-helix-to-github.sh` remains the one-shot seeding
tool; it is not a sync tool and must not be scheduled (see status.md for the
silent-success defect).

| Remote | URL |
| --- | --- |
| `origin` | `https://github.com/GSA/<repo>.git` (PR remote, unchanged) |
| `helix` | `https://github.helix.gsa.gov/FSS19-Cloud/<repo>.git` |

Commands: `status` compares and changes nothing, `pull` fast-forwards GSA
branches and new tags from Helix, `push --branch X [--pr]` sends one local
branch upstream and optionally opens a PR with `gh` pinned via `GH_HOST` to
the Helix host.

Invariants it will not break: the working tree and checked-out branch are never
touched (sync uses refspecs, not checkouts), nothing is force-pushed, no merge
is created, and no branch is deleted on either remote. A branch that moved on
both sides is reported as `diverged` and skipped, with a non-zero exit. A clone
that has no Helix refs is a failure, not a clean run. One `flock` per `--into`
tree prevents overlapping runs. Helix tags are fetched into `refs/helix-tags/*`
so they cannot shadow existing local tags.

It holds no credentials and relies on the per-host Git credential helpers, with
`GIT_TERMINAL_PROMPT=0` so a missing credential fails instead of hanging. The
reachability probe is bounded by `PREFLIGHT_TIMEOUT`; on this WSL host the
Helix route hangs rather than refusing, so run the tool on the VPN-side host.

Tests: `python3 -m unittest test_sync_helix_gsa` from `scripts/`. They build
local bare repos as stand-in hosts and use `insteadOf` rewrites for the CLI
tests, so real git behavior is exercised with no network and no `gh`.

# Application Kata authoring boundary: 2026-10-20 at 17:10 request

Reproduced `kata-local.py --project supply-chain-user-interface list --json`
failing before native execution. The guard is in `local_env.py::kata_launch`,
not the entrypoint itself, and `kata_mcp_launch` shares it. Removing that guard
without separating CLI selection from MCP pinning would change the established
scope contract. Native `projects list --json` confirms all four registered
application project UIDs still match `kata-adoption.md`; `--as copilot whoami
--json` resolves actor `copilot` from the explicit flag.

At 17:14 the owner approved explicit CLI selection of only
those four application projects with explicit Copilot attribution; retain
engi-platform as default, platform-only MCP, private daemon/profile and
workspace locks. Do not grant access to librarian/evaluation projects or infer
approval to author particular application tasks.

Concurrent commit `7266ac9` appeared during implementation and changed
`kata_launch` plus its tests. It allowed project selection without requiring
explicit `--as copilot`. The initial regression-test patch failed cleanly on
that changed context; implementation paused rather than overwriting it.
At 17:19 the owner authorized tightening that implementation.

The existing allowlist is preserved. Only `kata-local.py` enables application
selection; internal callers and `kata-mcp.py` keep the platform default.
Application requests require exactly one explicit Copilot actor; a non-
abbreviating standard parser removes the actor selector and places the fixed
actor before native arguments. Missing, alternate, duplicate or post-`--`
actor selectors fail explicitly; duplicate projects also fail rather than
silently selecting the last one. Literal arguments after `--` are preserved.
Explicit engi-platform selection retains the existing platform actor behavior.

All 114 local-environment/task-index tests pass. Real CLI reads succeed for all
four projects and report Copilot; negative cases reject absent/wrong actor,
librarian and daemon overrides. The live UI project now has two independently
created tasks; the other three are empty. The first read smoke incorrectly
assumed all were still empty, so it was corrected to check attribution and
report counts, not assert stale backlog state.

A disposable loopback-only native daemon verified real create/show round trips
for all four application names, checking exact project IDs/UIDs, author Copilot
and stdin body preservation. Its first assertion used the MCP response shape;
the corrected run checks native CLI issue fields and passes. Both isolated
daemons were terminated/waited and temporary databases removed, including on
the failed assertion. No live task mutation was used for this verification.
Both real MCP adapters pass initialize, progressive tool loading, fixed actor,
engi-platform binding and cross-project read/write refusal with zero model
calls. README/adoption instructions are updated; the TODO generator retains
its platform-only selection.

The owner's intervening CI question prompted read-only inspection of the UI's
`pr-check.yml`: it references `FSS19-Cloud/github-actions-workflows` (not
FSS19-FALCON) and CodeBuild runner labels. Normal GitHub API reads can access
the private GSA mirror, but the reusable-workflow repo and the mirror's workflow
lookup returned 404; the runner list was empty. This does not establish an
observed PR failure. At 17:16 the owner said to ignore that script. It remains
unchanged; no workflow disablement, runner installation or bypass is authorized.
No live task mutation, configuration/service change or publication by this
session. No experimental process remains; existing services stay running.

# Platform Kata completion audit: 2026-10-20

At 16:50 the owner requested marking already-finished platform Katas complete.
Read all 30 open bodies, full comment histories and dependency links; compare
current acceptance rather than treating historical imported text or working
infrastructure as a completed application workflow. Actor remained nkirrish
through `scripts/kata-local.py`; no force claim or cross-project mutation.

| Kata | Disposition and evidence |
| --- | --- |
| `7dhp` | Closed **done**. The approved GSA WorkSpace/VPN route successfully mirrored four Helix repositories to private GSA GitHub.com repositories; local clones and four provider-backed Forge entries are established. See mirror/clone status, `ff9b4f4` and `189d044`. This does not establish direct WSL Helix access or permit Citrix exports. |
| `djfr` | Closed **done**. The committed Librarian `INBOX/README.md#agent-context-contributions`, referenced by its AGENTS.md, defines explicit finding handoff, provenance/limits, receipt, assessment, canonical updates, refresh and returned disposition. This is the requested path definition, not an implemented automatic queue or a claim that a first contribution was processed. |

Both closes include substantive evidence and revision checks. The independent
Librarian contract was read, not changed. The platform README now points to it;
this checkout's `context/` is not automatically submitted or ingested.

Remaining scopes were individually reviewed and are not complete:

| Open Katas | Remaining acceptance |
| --- | --- |
| `k03a`, `mpew` | Active Forge/private-Pi engineering policy loading and its synthetic behavioral/publication-gate demonstration; the saved refinement example is still inactive. Existing red/green hook repairs do not establish that separate prompt contract. |
| `5ayh` | Deliberate checkout/state/service-name migration; active kenn-kopy paths and units remain. |
| `p4ke`, `ww7g`, `5xrm` | Clean-host end-to-end acceptance, automatic pinned Pi provisioning, and the complete reproducible team redeployment/restoration contract. Initial dist scripts and manual Pi instructions are not those outcomes. |
| `0rc1` | Actual Spokenly microphone/hotkey/text insertion trial; no completed personal GUI trial is recorded. |
| `6bxa`, `93hq` | Explicit Citrix export policy resolution and standard-VDI tooling permissions respectively. The separate approved WorkSpace/mirror route must not be presented as a lifted Citrix restriction. |
| `j54x`, `avvp`, `6hce` | First mapped Forge workspace, task/review integration, and actual Forge-Pi model-selected retrieval. Native live reads still report four repositories and zero workspaces. |
| `8vhd` | Actual model compaction followed by MCP-backed behavior; connectivity is not compaction evidence. |
| `bbm2` | A confirmed approved renewal API/CLI, if supported; current owner-selected manual console/set-key handoff is not automated renewal. |
| `jqwq` | Owner-visible Zed terminal/thread attachment; successful standalone tmux launch is already recorded and is not the missing GUI check. |
| `99gr`, `jgcf`, `d8v5` | Human-approved first-ticket decomposition, actual application coding/review, and explicitly approved Jira-to-PR publication. New code-inspection evidence locates 1290 but leaves NIF/UX/verification questions; all application projects remain empty. |
| `3c2c`, `fjyf` | Retention/approved alias pricing/client coverage and truthful no-session review accounting; unavailable metrics cannot be turned into zero usage. |
| `tvbf` | Native Pi attention/lifecycle, interruption/resume/session-end behavior and bounded engineering pilot; existing scoped MCP discovery/task reads are completed milestones only. |
| `me8k` | Owner retention/retirement decision for historical private profiles; no deletion approval inferred. |
| `vg0b` | Protected cloud-copy retrieval and actual isolated running-application recovery; local archive extraction is already recorded. |
| `vkye`, `1dkw` | Normal frozen Forge build/smoke verification and subsequent retirement of the local-Kata workaround, in that order. |
| `hfbz` | Conditional mirrored-WSL investigation only if needed; working NAT is not a completed mirrored-network investigation. |
| `jmga` | Approved private cloud architecture/deployment planning; WorkSpace access is not that plan. |
| `vd8j` | Deferred agent sandbox boundary/candidate evaluation; read-only review tools and Git worktrees are not OS isolation. |

Renamed `j54x` to identify only its remaining first-workspace milestone and
commented completed authentication/mapping evidence. Added current first-ticket
limitations to `99gr`. Preserved IDs, imported history, all dependencies,
deferred/blocked labels and the other task scopes. No unfinished work was
silently dropped, canceled or marked complete.

The generated TODO index now contains 28 open Katas. Full before/after issue
snapshots are session artifacts `files/engi-kata-audit-{before,after}.json`.
Concurrent spec-readiness commit `e1a3b36` was preserved and incorporated as
evidence, not reimplemented. No service/configuration/corpus changes,
experimental process, manual model request or publication.

# Scoped automatic commit reviews: 2026-10-20

The owner's 16:23 approval covers exactly the four ~/falcon application clones,
this platform checkout and ~/falcon-docs. Inspection found no `core.hooksPath`
override or non-sample hook in any of them. `scripts/roborev_hooks.py` installs
explicit paths with platform/application/corpus review guidance and refuses
differing existing configs rather than overwriting them.

Each gets an ignored/untracked `.roborev.toml`: Pi, standard reasoning,
commit mode, batch size one, runtime/dependency-directory exclusions and no
automatic design review. Native config validation runs before hook activation.
The private daemon retains its original one-worker Pi/USAi config; there is
no model/provider override, backup route, fix worker, agent hook, roborev CI
poller, history backfill or publication. Existing Forge provider sync is a
separate previously authorized feature, not changed by this work.

Private per-repository directories below
`.local/environment/roborev/hooks/<path-hash>/` copy the original hooks and
record the previous local hook setting. `core.hooksPath` points outside Git
metadata, protecting the scoped executable from automatic native repair.
Native `init --no-daemon --binary <absolute roborev-local.py>` registers each
repository and generates the three hooks. The installer removes global-binary
fallback and exposes launcher errors; native enqueue outcomes use `post-commit.log`.
Registration/installation failures restore the prior hooks-path setting.
Existing shell post-commit/pre-push hooks are chained; non-shell managed
hooks and existing post-rewrite hooks require explicit migration because the
native remap command consumes stdin. No unsupported hook is overwritten.

All original sample-hook bytes and the five external worktree diffs are
unchanged, including falcon-docs's dirty files. Concurrent Forge/Kata work
changed this platform's tracked context independently and was preserved.
Repeated installation is byte-stable; native Git-metadata-only repair skips
all six external directories. Thirteen native-hook integration tests cover
shell-hook preservation, stdin/exit status, symlink targets, worktrees,
missing launchers, errors, policy guards and registration rollback. All 99
existing local-environment tests also pass.

Live platform commit `fb7667a` automatically produced job 2, source
`post_commit`, agent Pi, standard reasoning, non-agentic, done/pass in 18s.
Setup commit `50ddfa3` then automatically produced job 3, which correctly
flagged an overly narrow shell-shebang preflight. A new env-bash hook test
failed before removing that duplicate classifier; the installer now relies
on native shell recognition and verifies all hooks before reporting success.
The regression and all other hook tests pass; original hooks stay untouched.
Review job 5 subsequently identified stale copied hooks after a rejected hook
was corrected. Retry now refreshes only inactive, manifest-owned staging from
the original directory. A failure/correction/retry execution test verifies it.
The env-bash case also exercises bash arrays: POSIX sh syntax validation must
not reject a preserved hook written for another native-supported shell.
No manual review command or historical Falcon review was submitted.
The dashboard works at http://127.0.0.1:17374/reviews; URL-only curl's 404 was
a content-negotiation mistake, not a broken browser route. Use
`Accept: text/html`. Private non-secret evidence is
`runtime/review-hook-activation.json`; local configs/hooks are intentionally
not committed. No service restart or experimental background process.

# Falcon Kata projects mapped: 2026-10-20 at 16:27

Owner-authorized native `kata projects create` added one empty project per
Falcon repository through `scripts/kata-local.py --as copilot`. Project names
match repository names; immutable UIDs are recorded in `kata-adoption.md`.
No checkout binding or alias is needed for a daemon project.

Native partial `PUT /api/v1/settings` persisted four exact `kata_projects`
entries using daemon `local`, project UID, provider `github`, host
`github.com` and matching `gsa/<repository>` paths. After native hot reload,
`GET /api/v1/kata/project-mappings` reports all four `mapped` with source
`manual_daemon`; no restart was needed. The immediate pre-reload response
reported `tracked_repo`, so verification checks the resolved repository and
mapped status rather than assuming that provenance label is stable.

All four native issue-list reads return `issues: []`. Existing engi-platform,
librarian and evaluation project UIDs are preserved, as are all service PIDs.
Application checkouts, agent/MCP scope, credentials and existing tasks were
not changed; no worker, hook, model request or publication occurred.
Secret-free evidence: `.local/environment/runtime/falcon-kata-projects.json`.
No temporary process remains. This adds project/mapping metadata only, not
application tasks or a demonstrated task-to-worktree flow.

# Forge mirrors connected: 2026-10-20 at 16:21

The owner authenticated Forge's isolated github.com profile and authorized
adding the four private GSA mirrors. Native `POST /api/v1/repos/bulk` returned
201 and persisted exactly these provider-verified identities:

| Repository | GitHub repository ID |
| --- | --- |
| GSA/supply-chain-user-interface | 1427373391 |
| GSA/national-item-file-maintenance | 1427373711 |
| GSA/standard-acquisition-interface | 1427374148 |
| GSA/infrastructure | 1427374407 |

Forge canonicalizes the stored owner to `gsa`. No glob, hidden entry, unrelated
GSA repository, local-clone registration or Kata repository mapping was added.
The account has ADMIN permissions; this read/integration scope is an operating
boundary, not a technically read-only credential.

`scripts/local_env.py::forge_command` now appends `--disable-sync` only when
native Forge config has no repositories. Selecting repositories opts into
normal provider sync on the next startup, including after reboot; fresh
repository-free profiles stay offline. This uses the existing config rather
than a new marker/setting or upstream patch. Adding the first repositories
to a currently sync-disabled daemon requires a restart.

Only `kenn-kopy-forge.service` was restarted (PID 476 to 42950). All four
catalog entries completed sync by 20:21:11 UTC with empty `LastSyncError`;
the loopback UI/health, saved IDs, 0600 config and enabled boot unit were
verified. AgentsView/roborev/Kata remained PIDs 475/478/477. Pi/USAi is still
the only enabled agent, quick actions/workspaces are empty,
`init_managed_clones=false`, and the existing falcon-docs project is unchanged.

Notifications are built in, not switchable: `NotificationsEnabled` returns
true for a loaded config, including the running pinned revision. The earlier
proposal to disable them was not implemented. Normal sync lists user threads
host-wide, then filters to tracked repositories; no notification mutation was
requested. No application source, prompt, model-route or corpus change, model request,
worker launch or publication occurred.

The new sync-policy test failed against the hardcoded flag, then all 99
`test_local_env` tests passed with the change. Secret-free live evidence:
`.local/environment/runtime/forge-falcon-intake.json`. No experimental
process remains; the four pre-existing boot services remain running.

# Forge repository readiness: 2026-10-20 at 16:14

Normal `gh api` authenticates to github.com as biggestbinary. A bounded GraphQL
read confirms all four GSA mirrors below are private and accessible with ADMIN
permission; their default branches match the recorded clones. This does not
authorize writes or mean Forge can use the normal CLI's credentials.

`python3 scripts/gh-local.py api --hostname github.com graphql ...` exits 4
with the CLI's login-required message. Forge shares this isolated profile, not
the normal CLI profile. Its healthy boot service still starts with
`--disable-sync` (`scripts/local_env.py::forge_command`), and live
`/api/v1/repos` and `/api/v1/workspaces` reads return empty collections.

Use owner-terminal authentication in that profile against **github.com** for
these mirrors, then deliberately configure only the selected repositories and
enable scoped sync. Restart alone does not remove the startup flag. No Helix
route, GitHub App or local-project UI modification is needed for mirror intake.
This assessment changed no credentials, services, provider configuration,
repository content or task state and started no experimental process.

# Helix mirror completed: 2026-10-20

Four FSS19-Cloud repositories are mirrored from `github.helix.gsa.gov` to
private repositories in the github.com `GSA` organization:

| Repo | Branches | Default |
| --- | --- | --- |
| supply-chain-user-interface | 285 | master |
| national-item-file-maintenance | 97 | master |
| standard-acquisition-interface | 108 | main |
| infrastructure | 24 | master |

No repository had tags or submodules, and no blob exceeded 100 MB.
`falcon-end-users` was deliberately excluded as per-environment YAML only.

GHE exposes read-only `refs/pull/*` refs that github.com rejects with
`deny updating a hidden ref`. These hold no branch content, so the rejections
were cosmetic, but the prune step had been written as `for-each-ref
'refs/pull/*'`, which matches nothing because git's glob does not cross `/`.
The pattern is now the prefix form `refs/pull`. Mirrors already pushed are
complete; this only removes the noise from future runs.

`scripts/verify-mirror.sh` is read-only confirmation: it compares every branch
and tag tip between source and destination and diffs any mismatch. Run it from
a host with both logins.

Not done: repository settings other than the default branch (topics, Actions,
branch protection, collaborators) are untouched, and `infrastructure` history
was pushed without a secret scan by the owner's explicit decision.

# Helix-to-GitHub mirror script: 2026-10-20

`scripts/mirror-helix-to-github.sh` mirrors Git repositories from a Helix
GitHub Enterprise host to private repositories in a GitHub.com organization.
It is written for a single host with both routes (VPN-side source and
github.com), which is the owner's WorkSpace, not this WSL environment.

It holds no credentials: it relies on the Git credential helpers already
configured for each host and sets `GIT_TERMINAL_PROMPT=0` plus
`GIT_ASKPASS=/bin/false` so a missing credential fails instead of hanging.

Per repository it clones `--mirror`, deletes GHE's read-only `refs/pull/*`
(github.com rejects those on push), logs branch/tag counts and on-disk size,
fails if any blob in history exceeds `--max-blob-mb` (default 100), lists every
`.gitmodules` URL found on any branch or tag, creates the destination with
`gh repo create --private` when absent, refuses a destination that already has
refs unless `--allow-nonempty`, and then `git push --mirror`.

```
scripts/mirror-helix-to-github.sh --source-org falcon --dest-org GSA \
    --dry-run --keep --repos-file scripts/mirror-repos.txt
```

Repo specs are `name`, `source-org/name`, or `source-org/name=dest-name`.
`--dry-run` clones and audits without creating or pushing anything. A failed
repository does not stop the others; the final summary lists each outcome and
the exit status is non-zero if any failed, with per-repo logs in
`<workdir>/logs/`. Submodule URLs are reported, never rewritten: a mirrored
repo whose submodules point at Helix will not clone usably off-VPN.

Secret scanning is not built in. Full history was mirrored by owner choice, so
anything ever committed to these repositories reaches github.com. Copy
`scripts/mirror-repos.txt.example` to an untracked `scripts/mirror-repos.txt`
for the real names. Verification so far is synthetic local repositories only:
dry run, blob-size failure, submodule detection and bad-spec handling. No
Helix clone, GSA repository creation or push has been performed.

# USAi model-router catalog refresh: 2026-10-20

The owner requested that Pi expose the latest models advertised by the existing
USAi router. A fresh authenticated `GET /models` through the secret-safe
`local_env.py list-models` path returned 22 unique IDs and refreshed the private
metadata catalog at `.local/environment/usai-models.json`. Both Pi profiles initially listed all 20 chat-model candidates under provider
`usai`; at the owner's follow-up direction, the visible catalog was reduced to
the newest model generation per family:

- `claude-opus-5`, `claude-sonnet-5`
- `gemini-3.8-flash`
- `gpt-5.6-luna`, `gpt-5.6-sol-latest-guardrails-defaultv2`, `gpt-5.6-terra`
- `llama_4_maverick`

The resulting seven-model `usai` provider is configured in:

- global CLI: `~/.pi/agent/models.json`
- Forge/private Pi: `.local/environment/pi/models.json`

`cohere_english_v3` and `text-embedding-005` were excluded because they are
embedding models rather than Pi chat models. The existing selected/default
model remains `gpt-5.6-sol-latest-guardrails-defaultv2`; endpoint, API type,
credential-command/environment references, settings, sessions and MCP config
are unchanged. The global model's previously verified explicit metadata was
preserved; newly discovered aliases use Pi's conservative defaults until their
capabilities and limits are verified rather than guessed.

The global profile also had a second `litellm-usai` provider pointing to the
same router. The owner authorized choosing one. Retained the explicit `usai`
provider because Forge/private Pi already uses it and its curated list will not
be repopulated by dynamic discovery. Removed the `pi-provider-litellm` package
and its now-unused global `litellm` settings; no other Pi packages changed.

Both model files and global settings remain mode 0600. Normal and private
`--list-models usai` now show only the same seven IDs, and `pi list` confirms the
LiteLLM extension is absent. The shared-key tests pass, confirming normal and
private credential handoff still works without copying the token. No model
inference, credential rotation, service restart or publication occurred.
Existing interactive sessions should restart to unload the removed extension;
a newly started session reads only `usai`.

For the 2026-10-12 live service/boot snapshot, see `status.md`. For Forge
workflow semantics and draft prompt responsibilities, see
`engineering-workflow.md`. Repository-free Kata runtime findings and remaining
integration boundaries are in `kata-evaluation.md`; current project-scoped
backlog adoption and CLI/index operations are in `kata-adoption.md`.
The project display name is now Engi Platform;
paths and installed service names remain `kenn-kopy` pending migration.

Exact source revisions are the parent repository's gitlinks:
`git submodule status`. Do not duplicate version pins in this document.

| Directory | Upstream | Role |
| --- | --- | --- |
| `roborev/` | https://github.com/kenn-io/roborev | Continuous code review |
| `superpowers/` | https://github.com/obra/superpowers | Agent skills and workflow |
| `forge/` | https://github.com/kenn-io/forge | Review and agent workspaces |
| `kata/` | https://github.com/kenn-io/kata | Engi Platform task ledger |
| `agentsview/` | https://github.com/kenn-io/agentsview | Session and token visibility |

Ghosthub was downloaded and then removed at the user's request because it
requires macOS.

# Librarian MCP connected to project Pi: 2026-10-20 at 17:40

Added the FALCON `falcon-context` server to this workspace's private
`.pi/mcp.json` beside the existing `kata` entry, so the project-scoped Pi
session this repository uses gets qualified read-only corpus retrieval. That
file is git-ignored (`.gitignore:7`); this entry is the committed record of its
contents.

`pi mcp list` reports both servers connected: `kata` with 16 tools and
`falcon-context` with 7 (`status`, `search`, `get`, `get_many`, `coverage`,
`catalog`, `review_events`), both `codemode` exposure, source `project`.

Configuration follows the server README's example host block rather than the
shorter form already in `.local/environment/pi/mcp.json`: explicit
`--event-reader`, `--manifest`, `--db`, `--max-source-chars 30000`,
`--max-output-chars 60000`, `--max-results 25`, `--timeout-seconds 30`, plus
`--audit-log --audit-log-mode full` and a **separate** label/path for this
client:

- `tools/context-mcp/.local/audit/pi-mcp-access.jsonl`, label `pi`

The existing `copilot` and `forge-pi` labels and logs are untouched, so each
client's trace stays distinguishable. The new log is git-ignored by the corpus
repository (`.gitignore:22`) and inherits FALCON source handling restrictions.

Verified before and after wiring: `qualified-context-preflight` exits 0 with
`ok: true` for runtime (Python 3.14.4, SQLite 3.46.1, mcp 2.2.0, FTS5),
configuration, schema snapshots, catalog (67,852 records, revision 90),
review events (1,670 events, 1,377 active) and index freshness. A temporary
stdio client using the exact saved argument list initialized, listed the seven
tools and completed one `status` call, which appended a single `success` record
to the new log. The smoke client closed; no model call was made.

This is retrieval only. The server has no network listener, no embeddings and
no write path; corpus maintenance still goes through the Markdown and
authoritative store CLIs. Registration is not authorization to publish corpus
content, and stdio does not stop a client from forwarding returned text to its
model provider.

Already-running Pi sessions keep the tool list captured at startup, so
`codemode` in this session cannot call `mcp__falcon-context__*` until `/reload`
or a new session. Nothing about Copilot's configuration, global Pi, the
supervised services or the Kata entry changed.

# Falcon MCP audit logging: 2026-10-19 at 17:42

Owner-authorized full audit capture is configured in the existing
`~/.copilot/mcp-config.json` and private
`.local/environment/pi/mcp.json` FALCON server entries. Existing command/root/
reader, timeouts and tool exposure are preserved, including Pi codemode.
Global Pi, credentials, provider/model routing and the supervised services
are unchanged.

Both pass `--audit-log --audit-log-mode full`, with per-client labels
`copilot` and `forge-pi`. Their logs live beneath the corpus root:

- `tools/context-mcp/.local/audit/copilot-mcp-access.jsonl`
- `tools/context-mcp/.local/audit/forge-pi-mcp-access.jsonl`

The directory is 0700 and files/configurations are 0600. Full logs retain
actual tool arguments and exact returned text/errors and inherit source
restrictions. Keep them private; they are not complete inter-agent prose,
authenticated identity, retroactive capture or business acceptance.
Private byte-identical pre-edit config backups are retained in the originating
session's files area, not committed to this repository.

Actual temporary stdio clients using each saved configuration initialized
and completed fresh status reads; each log's label, tool, outcome and exact
response were checked without printing returned text. Native private-Pi
`mcp list` still discovers seven FALCON tools with codemode and the project
Kata tools. No model call was made and all smoke clients closed. Existing
running sessions need reconnect/restart to load the changed arguments; no
supervised service or active session was restarted.

# Parent UI epic: 2026-10-20

At 10:01 the owner supplies CCSMFSSM-4344's XML, generated October 20 at
14:00:43 UTC, and reports beginning the supply-chain-user-interface mirror.
The epic is titled "[EP] FALCON UI Enhancement" and describes only:

> All FALCON UI enhancement, change and updates.

It reports parent CCSMFSSM-3663, workflow status Implementing, custom Epic
Status To Do, unresolved/unassigned, last updated April 29, 2026, and
Definition of Ready/Done both No. Preserve the two status fields separately;
do not reconcile them into a claim about current delivery. No separate
acceptance criteria, Development links or explanation of "NIF changes" is
provided. This establishes broad grouping, not proof of a dependency,
supersession or an unimplemented child feature.

No further ancestor export is needed at this stage. Await the mirror URL
and intended baseline branch/commit, then inspect repository instructions,
the existing warning text/behavior, NIF substitute lookup/AAC response and
test conventions. Resolve code-answerable questions there before returning
business ambiguities to the owner. No new requirement or implementation
Kata is approved by this parent export; no code or mirror was inspected.

# Real-business demo selection: 2026-10-19

At 17:32 the owner supplies a Jira XML export generated October 19 at
21:31:34 UTC. Preserve the description verbatim as the requirement source:

> If the acquisition advice code of the substitute NSN is V or Y then soft warning: "Substitute NSN is terminal or obsolete"
>
> It will taken care with NIF changes.

This refers to the substitute item's AAC, not the maintained item's AAC.
The export reports To Do/unresolved/unassigned, last updated July 8, 2026,
parent CCSMFSSM-4344, FALCON O&M, and Definition of Ready/Done both No.
It contains no separate acceptance-criteria field, Development links,
attachments or subtasks; no comments section is supplied. Do not infer
that an absent export field proves no comments or repository associations
exist in Jira. Its age/status do not prove the behavior is absent from code.

New qualified retrieval:
`REFERENCE/notes/2026-09-29-spud-ui-catalog.md#d168--s158--supply-chain-user-interface`
identifies supply-chain-user-interface as Falcon / fss-ui, an Angular SPA
whose APIService includes NIF REST integration. This is now the strongest
frontend repository lead, replacing the earlier lack of a named UI target,
but not a verified Git owner/URL/branch or inspected ticket-to-code mapping.
The same packet reports generated Cognito configuration and private-network
routing dependencies for local setup; mock configuration alone does not
establish functional sign-in/backend access.

Re-read the NIF backend packet and
`REFERENCE/program/architecture-and-tech-stack.md#nsn-management-lifecycle`:
historical Phrase Code-dependent substitute requirements remain separate
from this AAC warning. The October 15 FSS UI permission walkthrough also
does not identify the browser Git URL. Exact-ticket/parent/soft-warning
search misses are not evidence of absence. Requests above the configured
30,000-character source ceiling were rejected, then complete compact packets
were retrieved within it; an unindexed historical-guide link was not bypassed.

Pending refinement: parent/current-owner confirmation of standalone scope,
warning timing and affected NIF flows, existing nonblocking-warning behavior,
and availability of substitute AAC through the current lookup. Interpret
"soft" as a likely nonblocking warning, not owner-approved interaction design.
Do not assume a backend change, add lookup-failure behavior or alter existing
Phrase Code validation before inspecting code and resolving requirements.
Request the exact supply-chain-user-interface Git URL/default or approved
baseline branch and parent CCSMFSSM-4344 details, not all 33 repositories.
No program code, task records, worker launch or live Jira request was made.

At 17:14 actual read-only Librarian searches/qualified reads support a
provisional CCSMFSSM-1290 recommendation from the owner's Jira screenshot.
Relevant returned locators:

- `REFERENCE/program/what-is-falcon.md#cataloging-and-external-order-handoffs--september-29-intake`:
  historical NIF guidance ties Substitute NSN requirements to selected Phrase
  Codes; it does not settle this ticket's AAC V/Y warning semantics.
- `REFERENCE/notes/2026-09-29-spud-ui-catalog.md#d156--s146--national-item-file-maintenance`:
  generated analysis describes backend NIF acquisition-advice/substitute-item
  validation, not a confirmed frontend repo or inspected implementation.
- `REFERENCE/notes/2026-09-29-spud-ui-catalog.md#d144--s134--falcon-end-users`:
  this is Python user-permission reconciliation, not the browser application.
  Do not choose it merely because the Jira title says FALCON UI.
- `REFERENCE/notes/2026-09-29-falcon-validation-and-requirements.md#nif-bulk-upload-and-mockups--s67--d071-s68--d072`:
  bulk upload has record-level rules, update-rights constraints and planned
  integration/email paths, making the full feature a larger first-demo scope.

Exact ticket-key searches did not return selected indexed hits; that does not
prove absence from raw snapshots. The qualified Jira snapshot coverage read
describes data updated only through September 20, not current Jira. Full
ticket/acceptance criteria, comments, development links and exact repository
are pending owner expansion. Treat AAC versus Phrase Code and warning versus
blocking validation as refinement questions, not new requirements. Homepage
link CCSMFSSM-9566 is a simpler fallback but its target-page readiness is unknown.

At 16:49 the owner confirms FCP repository permission and a WorkSpace path
from GSA VPN source to a GSA GitHub.com repository. Exact URLs, destination
visibility and ticket/build prerequisites remain unknown; source operations
were not requested. GitHub.com hosting is not public repository visibility.
The ZIP alternative remains unselected. Do not reopen settled local/USAi or
newly confirmed repository access as generic permission blockers.

Owner corrects the proposed ticket-sized corpus: the Librarian must consume
all available program documentation and build the knowledge relationships
used to select relevant context. Narrow the demonstration's implementation,
not its intended corpus coverage. FCP requires proper corpus construction;
SPUD outputs alone or a manually selected ticket packet are not equivalent.
An empty corpus builder already exists in another home-directory folder;
obtain its path/read its instructions rather than create a competing template.
Keep Falcon and FCP facts, provenance, stores and sessions separate.
The established Falcon corpus therefore remains the shortest proposed first
demo path, with FCP replication afterward; this is advice, not a selected or
implemented deployment. Audience is AOS leadership, with cross-team reuse the
eventual goal. No existing builder or corpus was inspected in this discussion.

The requested Engineer/Librarian communication evidence needs an explicit
protected trace: ticket/task identity, actual MCP requests/results, qualified
locators, missing/conflicting evidence and resulting decisions. Existing
AgentsView usage-only ingestion does not retain transcript/tool payloads.
Do not describe MCP retrieval as autonomous agent-to-agent conversation or
enable full transcript archiving globally to satisfy this requirement.

# Engineer redistribution requirement: 2026-10-14

The owner requires a reusable platform setup for other project engineers;
private cloud hosting is optional/stretch. Existing bootstrap/setup helpers
are partial and not a verified distribution. `p4ke`/`5xrm` own portable setup;
`jmga` owns later approved cloud planning. Reuse pinned upstream components,
retain licenses/attribution and separate distributable configuration from
per-user credentials and private runtime state. Librarian access must be
provisioned through an approved dependency/access path, not by bundling the
confidential corpus. The initial Ubuntu installer recipe is described below;
target-engineer compatibility and shared-state topology remain unverified.
No container or hosted multi-user architecture is selected.

The 14:25 implementation is `dist/install.sh` plus `install.py`, documentation
and regression tests. It checks Linux x86_64, Python/Node/Pi versions, host
tools, TLS trust, C headers/linker and the existing Librarian executable/runtime.
It initializes parent gitlinks or clones an explicitly supplied platform URL
at an exact commit, then reuses source/toolchain/build/private-setup helpers.
Normal Forge remains default; the temporary local-Kata build is opt-in.
No private state/corpus is redistributed and no OS dependencies/global agent
profiles are automatically changed. Pi 1.0.3 and local Librarian remain external
prerequisites; clean Ubuntu installation is not established complete.

Services default to manual for noninteractive use; interactive installation
asks before enabling/starting four user units. Manager availability, conflicting
unit origins and occupied ports fail explicitly; lingering is never enabled.
Existing `kenn-kopy-*` names remain. Installer locking prevents concurrent
same-checkout runs; settings and local changes are preserved.
`configure-private-pi-tracking` adds offline, usage-only private Pi tracking for
fresh AgentsView without requiring Copilot. Existing configured tracking stays
unchanged. `set-key --private-only` adds an isolated credential handoff; the
existing default shared-key behavior remains unchanged. Runtime isolation here
is private filesystem/configuration, not an OS or cloud/multi-user sandbox.
See `dist/README.md` for commands, prerequisite remedies and remaining boundaries.

# Falcon demo boundary: 2026-10-13

The intended demo is an application informed by real Falcon product
specifications through the existing Librarian MCP, not a synthetic Librarian
or a new Librarian UI. At 16:07 the owner favors waiting for AWS access over
creating a GitHub-hosted demo now. A private GitHub.com repository is not
automatically an approved destination for confidential specification-derived
code, tests, tasks or review text. AWS execution access and approved Git/source
storage are separate prerequisites; do not assume AWS enables Helix access.
No repository/provider configuration or deployment has been authorized.

# Prompt integration discovery: 2026-10-13

The existing private Pi setup loads the pinned Superpowers package. Its
manifest exposes skills plus a Pi extension that injects `using-superpowers`
at startup and after compaction; other skills are discoverable/on-demand.
This is source evidence, not a new runtime adherence/compaction check.

Upstream skills include design approval gates, autonomous plan rulings and
branch-finish/full-suite instructions. Their interaction with owner questions,
repository authority and token limits needs explicit decisions, not wholesale
copying or silent edits. Pi has no standard subagent tool; package discovery
does not establish delegated execution. The current roborev config points at
the same private Pi launcher; dedicated role loading/isolation is not yet
implemented. No upstream/global profile changes were made.

The 11:17 clarification narrows the objective to Forge-native use with
Superpowers; Copilot/global Pi are out of scope. Pinned Forge's `Agent` schema
defines protocol/key/label/command/enabled, not engineering roles. Its Kata
integration reads canonical tasks and owns links/workspace creation, not task
decomposition or mutation. Activity hooks relay agent states and explicitly do
not enable consent/auto-approval. Engineering stops and TDD remain agent/skill/
repository policy, not Forge's reasoning. Detailed evidence and optional-vs-
required workflow distinctions are in `engineering-workflow.md`.

Non-secret saved-config inspection shows one enabled `pi` target, zero quick
actions, `[mcp].enabled` absent/false and Superpowers registered in private Pi.
Read-only live Forge collections confirm zero provider repos/workspaces.
The first collection probe used the wrong `/api` prefix and returned 404;
the existing `/api/v1` helper then succeeded. No configuration was changed.
The native MCP spawn input supports provider items or ad-hoc repositories,
not a direct Kata-task source; UI/API Kata workspace creation is a separate
surface. Do not promise automatic Kata-to-worker dispatch from prompts alone.

At 11:29 private `pi-local.py mcp list` again connects to the read-only
`falcon-context` server (seven tools, private-profile/global scope) and this
checkout's Kata server (16 progressive loaders, project scope). No corpus read,
index refresh or model request was made. Workers reusing this private profile
should retain Falcon access; model-selected retrieval in a real Forge workspace
and each future project binding remain separate acceptance work.

Read the canonical Clanker Constitution at `v2026.08.11` from the author's
repository. It is compact, language-neutral baseline behavior under CC BY 4.0,
not a Jira intake protocol, scheduler or orchestrator implementation. The owner
approved an inactive example at 11:36:
`context/prompt-drafts/jira-refinement.example.md` reproduces the baseline
unchanged with version, Kenn Software attribution and CC BY 4.0 license, then
appends the owner's exact draft-only overlay. Its `.example.md` filename and
context-only location keep it outside live instruction/skill/profile discovery.
No launcher, MCP settings or agent target references it.

The 11:38 project task audit used native list/show commands for all 32 open
tasks and selected comments/dependencies. Scope corrections are recorded in
`status.md`; the inactive example does not complete active prompt, Jira intake
or Forge-worker integration. No task status, body, ownership or link changed.

At 11:46 the owner approves cleanup. Five native `edit` operations prepend
current scopes to preserved historical text; `v3sd` closes with reason
`superseded` and evidence `superseded-by:k03a`. The first close attempt included
`reviewed-paths`, which Kata disallows for that reason and rejected without
mutation; the corrected reason-specific evidence succeeded. Before/after
project snapshots verify 31 open tasks, retained identities/labels/ownership/
metadata and unchanged unrelated tasks. Existing blocking/related links were
read back unchanged. No existing agent configuration was removed; obsolete
Copilot/ACP/new-role work is excluded from current task scopes, not claimed done.

# Current terminal choice: Ghosthub substitute, 2026-10-13

The owner declines Ouijit at 10:07; `jjw1` is closed **wontfix**, not evaluated
as secure/insecure. Do not install it or introduce a competing task ledger.
At 10:28 the owner also declines Herdr (`r27h`, **wontfix**) and accepts the
current local setup. Engineering prompt work moves to a separate dedicated
agent under `k03a`; no additional terminal runtime is on the active agenda.
The dated research below is retained as provenance, not current selection.

Ghosthub fills the **multiplexer-native terminal frontend** layer in
[Kenn's original stack](https://wesmckinney.com/blog/agentic-engineering-aug-2026/),
not Kata's intent ledger or Forge's PR/worktree ownership. That layer can be
covered now without another agent orchestrator.

| Option | Local facts and role | Decision |
| --- | --- | --- |
| Existing Zed + tmux | Installed Zed 1.23.3 and tmux 3.6. Zed offers editor/diffs and terminals; tmux supplies live-process persistence and session/window/pane switching. Works without Forge provider mapping. | Lowest-friction baseline. `scripts/terminal-local.py` supplies a private-socket entrypoint from any WSL terminal or Zed terminal/thread. No installation/global setting change. |
| Existing WSL terminal + tmux | Same backend and native clients, without a GUI dependency. | Fully usable fallback and the portable foundation for later approved SSH/Linux use. Remote connectivity and fresh-host installation are not configured. |
| Ghostty + tmux | Installed Ghostty identifies as `1.3.0-dev+0000000`, channel tip; WSL display variables exist. | Optional frontend, not required or asserted to be a hardened release. No upgrade or GUI trial performed. |
| Herdr | Additional runtime/status machinery and native resume integrations; previous reports remain below. | Declined at 10:28; `r27h` closed wontfix. No installation or active trial. |
| cmux / Ghosthub | [cmux's current app](https://github.com/manaflow-ai/cmux) is Swift/AppKit macOS; Ghosthub was excluded here for the same host mismatch. | Revisit on a future Mac if useful, not a Linux/WSL dependency. |

[Zed Terminal Threads](https://zed.dev/docs/ai/terminal-threads) organize
native CLIs without taking over their auth, provider, MCP or skills. Prefer
that surface or an ordinary integrated terminal; no Pi ACP bridge, Zed model
provider migration or extension is needed. The installed GUI is already
running, but version/process presence is not a demonstrated UI workflow.
Owner should check opening a terminal/thread and attaching the launcher.

The launcher opens/reuses named sessions in this checkout and leaves Forge's
socket alone. It sanitizes inherited credential/actor variables, retains
normal HOME/XDG paths for native Copilot, and pins private Pi's directory.
Use `pi-local.py` for USAi; Copilot inference remains separate. Shells skip
profile/rc loading and the supplied tmux configuration is separate from user
settings. This reduces configuration surprises; it is not sandboxing or proof
of enterprise hardening. Neither Kata's selection nor this baseline implies
all reliability/security work is complete.

The [tmux contract](https://man.openbsd.org/tmux.1) preserves live sessions
over detach/disconnection, not server/WSL restart. Saved native agent sessions
and task records are the durable restart assets. README owns launch/key
bindings/stop instructions; real PTY tests cover reattach, disconnect and
exact-session stop. No automatic attention, reboot recovery, publication,
worktree creation or server deployment is introduced.

# Richard Gill: prompt-agent reference, 2026-10-12

At 23:12 the owner removed this item from active platform tool research.
Review belongs to the agent dedicated to platform prompts (`k03a`); standalone
task `0s6v` is superseded by that work. Retain the sources below as handoff
context, not a recommendation to install extensions. None were installed here.

[Richard Gill](https://richardgill.org/) describes himself as a London software
engineer, formerly at Stripe and running a consultancy; employment history is
self-reported. His public projects include
[llm-ui](https://github.com/richardgill/llm-ui),
[Pi extensions](https://github.com/richardgill/pi-extensions) and
[Overmux](https://github.com/richardgill/overmux). Inspectable implementation and
explicit limitations make him a useful practitioner source, not independent
proof of productivity, production reliability or enterprise suitability.

The [Pi setup](https://github.com/richardgill/pi-extensions/blob/main/PI_SETUP.md)
documents background commands, direct command-output context loading, custom
instruction/skill discovery and tmux/worktree coordination. It acknowledges
subagent polish limitations and includes automatic project trust. Overmux's
README describes a tmux-based, extensible terminal/review environment and
explicitly labels it experimental beta. These are documentation observations,
not local runtime validation.

At 13:01 the owner accepted automatic project trust for this platform because
projects are generally known. This supersedes the earlier recommendation not
to copy that aspect of Gill's personal setup. No trust extension/configuration
was installed or enabled. Any future prompt-agent review should preserve
USAi routing, Falcon MCP and human publication/merge control.

# Personal/tool candidates: 2026-10-12 research

This is source/documentation research only, not installation, runtime
validation, approval for sensitive assets or a selected replacement stack.
The owner dropped Moshi, cmux and Ghosthub on 2026-10-12 at 13:10; they are no
longer active candidates. GitHub CLI setup is deferred, not an open clarification.

| Candidate | Verified product/platform facts | Fit and next evidence |
| --- | --- | --- |
| [Spokenly](https://spokenly.app) | Dictation app with current Windows and Linux builds. Vendor documents local Whisper/Parakeet transcription, cloud providers, BYOK and optional text processing. [Windows](https://spokenly.app/windows) supports Windows 10/11 x64. [Linux](https://spokenly.app/linux) offers deb/rpm/AppImage with desktop/compositor requirements. | Most direct personal-use candidate. Windows-host installation is a practical proposal for dictating into Windows apps/WSL terminals; cross-boundary input is not tested. Begin with local models, Local Only Mode and non-sensitive text. Do not assume Linux desktop dictation controls Windows applications. |
| [Ghostty](https://ghostty.org/docs/about) | Standalone terminal emulator with native Linux GTK and macOS UI, tabs/splits and libghostty core. Created by Mitchell Hashimoto, not Wes McKinney. [Linux packaging](https://ghostty.org/docs/install/binary) varies by distribution; official prebuilt distribution is primarily macOS. | Linux/WSLg candidate, not agent orchestration or a persistent multiplexer. Verify GUI/display/GPU integration and packaging before adopting it. Existing terminal plus tmux remains sufficient. |
| [Ouijit](https://github.com/ouijit/ouijit) | Linux x64/macOS task/worktree/terminal manager. README lists Pi, Claude Code, Codex and OpenCode, SQLite local state, optional sandboxing and AGPL-3.0. [Lifecycle hooks](https://ouijit.com/docs/hooks/) are start/continue/run/review/done. | Strongest new orchestration candidate on Linux. Overlaps Forge workspaces and Kata task authority: trial separately on a synthetic project before deciding replacement/integration. No confirmed Jira connector. Must preserve Pi/USAi profile, Falcon MCP and usage tracking. |

Spokenly's [Local Only Mode](https://spokenly.app/docs/local-only-mode) is
documented by the vendor as blocking network requests except local model
downloads and allowing localhost endpoints. Ordinary mode can send anonymous
analytics and cloud transcription/text processing can transmit content.
These are vendor claims, not a traffic audit or permission to handle GSA data.
Personal tooling must not become a VDI export mechanism.

Ouijit shadows supported harness commands on PATH in its terminals and adds
hooks/CLI context ([harness docs](https://ouijit.com/docs/harnesses/)). Our
absolute private Pi launcher may need explicit integration; bare `pi` currently
resolves preserved 1.0.3 after the requested legacy removal. Hook examples that create PRs or
push are examples, not an approved publication policy. Prefer clean worktrees
for an initial trial; its copy-on-write clone mode can carry ignored files,
including secrets/local state. OS sandbox support is a product capability,
not proof of a configured sandbox on this WSL host.

GitHub CLI is already checksum-pinned locally at 2.102.0 and the isolated
profile is unauthenticated. [Official apt installation](https://github.com/cli/cli/blob/trunk/docs/install_linux.md)
exists, but adds a system package repository/global installation and is not
needed to make this profile usable. The owner deferred CLI setup at 13:10;
no installation/App change is planned while the GSA operating path is unresolved.

## Herdr versus the existing layers: historical research

[Herdr](https://github.com/herdrdev/herdr) is an Apache-2.0 terminal/runtime
manager with a background server, terminal UI, agent-aware status, CLI/socket
automation and optional worktree actions. It runs on Linux/macOS, with native
Windows support documented separately. No GUI/Electron dependency is needed
for the Linux terminal UI. This is documentation research, not a WSL trial.

| Tool | Main authority/layer | Fit to evaluate |
| --- | --- | --- |
| Kata | Durable task intent, dependencies and task records. | Adopted for Engi Platform's backlog at 17:42. Agent hooks/pilot validation remain open; a terminal runtime is not a substitute. |
| Forge | Provider/PR review console plus owned Git worktrees and tmux sessions. | Keep current review/runtime integration while GSA provider access waits. Its tmux backend is an existing contract, not something to silently replace. |
| Ouijit | Task board plus worktrees, terminals and agent lifecycle hooks. | Compare as an alternative local task/execution UI; avoid concurrent competing task authorities. Check clean worktrees and private Pi/USAi integration. |
| Herdr | Persistent terminal processes, pane/workspace layout, agent status and CLI coordination. | Potential complement for standalone Pi/Copilot work, not a replacement for task tracking or provider review. Trial separately from Forge-owned tmux first. |

The [agent documentation](https://herdr.dev/docs/agents/) lists Pi and Copilot,
along with several other harnesses. A host-visible wrapper can use a scoped
`HERDR_AGENT=pi` hint if automatic identification is obscured. Do not export
that hint globally. State detection is a UI/coordination signal, not correctness
or completion evidence. Herdr does not detect agents nested inside an inner
tmux pane; avoid that topology when evaluating agent state.

The [Pi integration](https://herdr.dev/docs/integrations/) honors
`PI_CODING_AGENT_DIR` and installs an extension into that profile, which could
preserve our private profile boundary. Verify Pi 1.0.3 compatibility, startup,
native session resume, Falcon MCP and AgentsView usage before adoption.
Integration installation is not permission to edit global client profiles.

Detach leaves live processes running; after server/machine restart, layout
restoration and supported native-agent resume do not preserve the original
processes. Named sessions isolate runtime/socket state but share global config,
so a trial also needs isolated configuration and explicit cleanup.
Sources: [concepts](https://herdr.dev/docs/concepts/),
[persistence/remote](https://herdr.dev/docs/persistence-remote/),
[configuration](https://herdr.dev/docs/configuration/).

Remote SSH support needs an approved reachable host and cannot bypass the VDI
restriction. Automatic detection-manifest downloads and saved pane history
need deliberate reproducibility/retention choices; neither sandboxing nor
USAi routing is established simply by using Herdr.

## Next work priorities: updated 2026-10-13 at 10:28

Prioritize gaps in this stack over accumulating overlapping tools. These are
recommendations using the documented sources above, not new runtime findings
or approval to install products.

| Priority | Existing Kata task | Target and bounded question |
| --- | --- | --- |
| 1 | `k03a` | Separate dedicated prompt agent: adapt shared engineering policy and focused roles, reusing existing Superpowers and preserving provider/publication boundaries. |
| 2 | `tvbf` | Remaining Kata native attention and Copilot model-driven task pilot; no second ledger or terminal runtime. |
| 3 | `jqwq` | Check the existing Zed terminal/thread UI with the scoped tmux launcher; home-directory access is supplied, ACP remains unnecessary. |

Gill's Pi extensions/setup is excluded from this research queue; the dedicated
platform prompt-writing agent owns that review. Ouijit and Herdr are excluded
by the 2026-10-13 owner decisions; `jjw1` and `r27h` are closed wontfix.

Spokenly (`0rc1`) is a separate personal-productivity trial with local models.
`c3ch` now records the completed existing-tool terminal baseline, not a
Ghostty install or GUI trial. PiPod/Abyss/smolvm
(`vd8j`) remain deferred sandbox research before cloud or broader autonomous
execution; none is selected and profile isolation is still not a sandbox.
Backup/recovery follows its separate authorized scope; no backup rerun is
part of this terminal work.

## Operational and anecdotal evidence: 23:16 request

These are actual operating scenarios plus public issue reports, not local
Herdr/Ouijit trials or independent evidence of productivity. Neither product
is selected or installed. Repository reports were checked on 2026-10-12;
open/merged status is time-sensitive.

| Question | Herdr | Ouijit |
| --- | --- | --- |
| What would I use it for today? | Keep standalone Pi/Copilot terminals, tests and shells in persistent panes; see which agent needs attention and detach/reattach without losing the live process. Complements Kata rather than owning its backlog. | Enter a task on a visual board, start its isolated branch/worktree/terminal, run an agent via a start hook, inspect the diff and advance review state. Overlaps both Kata and Forge rather than simply adding terminal persistence. |
| What persists? | [Session-state contract](https://herdr.dev/docs/session-state/): detach preserves live processes; full server restart restores layout and optionally native agent conversations, not old processes. Screen history is off by default because output may contain secrets. | [Worktree contract](https://ouijit.com/docs/worktrees/): tasks retain their branches/worktrees across board changes; Continue opens another terminal in the existing worktree. This does not establish that a live process survives app/WSL restart. |
| How would our agents fit? | Official native restore lists Pi integration >=2 and Copilot >=2. We must verify resume launches our scoped profiles, not ordinary `pi` with a different provider. No inner tmux topology for status detection. | [Harness docs](https://ouijit.com/docs/harnesses/) explicitly cover Pi, Claude, Codex and OpenCode in Ouijit-owned terminals; Copilot first-class status/CLI-awareness is not documented there. Our absolute Pi launcher must preserve its hooks/wrapper PATH. |
| What could go wrong for this workspace? | A second socket alone is not state isolation; isolate configuration plus named-session state. Existing Forge-owned tmux stays separate. Test both orderly detach and terminal/WSL termination. | Default Quick start copies ignored paths, including `.env` and this large/private `.local/`. Use Clean checkout and an explicit setup hook. Do not let its board silently become a second authoritative ledger or its done hook publish/merge. |

Concrete user/maintainer evidence:

- [Herdr #4920](https://github.com/herdrdev/herdr/issues/4920) is an **open
  macOS/Ghostty 0.9.3 report**: two users describe losing pane processes when
  quitting the terminal, including after explicit detach. A user reports
  signal-level tracing to macOS application-coalition termination; the
  maintainer cannot reproduce the same ordinary-quit path and is still asking
  for details. This is a useful persistence acceptance test, not proof of a
  Linux/WSL defect or a confirmed universal cause.
- [Herdr #5217](https://github.com/herdrdev/herdr/issues/5217) is an **open
  macOS 0.9.3/current-master report** with a scripted reproduction: separate
  `HERDR_SOCKET_PATH` servers share `session.json`, overwrite layouts and can
  duplicate native agent resumes. The reported experiment supports our need
  to isolate state, not just sockets. We have not reproduced or generalized it.
- [Ouijit #302](https://github.com/ouijit/ouijit/issues/302) describes a real
  terminal-stack workflow where suspending an agent with Ctrl-Z left `fg`
  unable to resume it. [PR #312](https://github.com/ouijit/ouijit/pull/312)
  **merged 2026-10-10**, moving startup commands into interactive-shell job
  control and adding real PTY tests for zsh/bash/fish, Ctrl-Z/fg, Ctrl-C and
  wrapper PATH. This is inspectable engineering evidence; a future trial
  must verify its chosen release actually contains the fix.
- [Ouijit #304](https://github.com/ouijit/ouijit/issues/304) reported an
  OpenCode-v2 plugin-load failure. Its linked fix PR #311 merged 2026-10-10.
  This is not a Pi defect, but shows why harness-version compatibility and
  model/profile routing must be demonstrated rather than assumed.
- [Ouijit #299](https://github.com/ouijit/ouijit/issues/299) contains a
  self-reported company trial requesting Linear intake, with the maintainer
  planning support. That is adoption anecdote, not a verified integration or
  benchmark; it is also a reminder that Jira/Linear intake is not established
  merely by having a task board.

Historical 2026-10-12 recommendation was **Herdr first as a bounded complement**, if persistent
standalone terminal/status management is a demonstrated pain point. Its trial
should measure attach/detach process identity, restart/resume/profile fidelity,
Pi/Copilot status versus observed behavior and cleanup, with synthetic work.
Evaluate Ouijit only as an explicit alternative execution/review interface,
measuring clean worktrees, scoped Pi/USAi, permissions and task reconciliation
before considering coexistence. More tools are not themselves an integration
benefit. Existing issue reports do not establish enterprise/GSA readiness.
The 2026-10-13 owner decision supersedes the Ouijit trial and favors the
already-installed tmux baseline before any additional terminal runtime.

## Kata agent-access milestone: 23:16 request

Native scoped stdio MCP now backs both project clients. See README and
`kata-adoption.md` for setup and actual read/actor/scope/retry evidence.
Pi uses codemode and refreshes Kata's progressive catalog successfully.
Copilot discovers the workspace server on new sessions; this running session
uses the scoped CLI. A successful saved Pi/USAi model read now supplements
transport evidence; Copilot model-selected MCP and native attention lifecycle
remain open. No terminal product was needed or installed for this milestone.

## Pi 0.87.1 removal: 2026-10-12

The old shell command was `~/.local/bin/pi` pointing to the managed
`~/.pi/agent/bin/pi` launcher. That launcher selected
`~/.pi/agent/install/releases/0.87.1`, a dedicated npm prefix containing only
the old Pi dependency tree (about 157 MB). Used npm uninstall with scripts
disabled, then removed that exact release directory, installer-only metadata
and launcher. Removed only the now-empty installer directories.

`~/.local/bin/pi` now links to `~/.nvm/versions/node/v26.9.0/bin/pi`, matching
the platform's saved absolute 1.0.3 executable. Both version commands and the
private MCP list pass. Global settings/models/sessions and `bin/rg`/`bin/fd`
remain intact; the separate Node installations are not removed. This is a
host change, not yet a pinned fresh-host installation recipe.

## Supervisor recovery and host backup

`supervisor()` now returns no live supervisor for absent metadata or a missing
process, warning when it retains an exited PID's record. Permission/format
errors and PID identity mismatches still fail explicitly. Status still checks
independent services and their projects; stop with no supervisor signals
nothing and does not claim to have stopped orphaned processes. New startup
retains lock/port checks and writes its own record only after readiness.

Four new regressions include actual exited subprocess PIDs, retained metadata,
safe no-op stop and propagation of non-missing-process errors. All 66
integration tests pass. A real start/status/stop cycle from the stale record
verified Kata health, owner-managed record replacement/removal, and unchanged
AgentsView/roborev/Forge identities. No service unit was restarted.

Host PowerShell reports `OneDriveCommercial` at
`C:\Users\NKIRRISH\OneDrive - CGI Federal, Inc`, and the directory exists.
This verifies a configured local sync location, not cloud backup success,
retention, restore capability or GSA-content authorization.
Proposed destination: a separate `EngiPlatformBackups` folder there, containing
versioned repository source/history/uncommitted-work snapshots after scope
confirmation and archive/restore checks. Do not sync the live Linux checkout,
credentials, `.local/` state, sessions, Falcon corpus or GSA assets wholesale.
No folder, upload or schedule had been created at that checkpoint. The
19:27 authorization below supersedes this historical source-only proposal.

## Sensitive-state OneDrive copy: 2026-10-12 at 19:27

The owner approves the CGI Federal protected OneDrive destination and sensitive
assets, with completed work committed locally and reinstallable dependency
bulk excluded. `scripts/backup_workspace.py` copies this workspace only,
including complete `.git/modules/` history, dirty/untracked source and private
state/credentials. External Falcon/global profiles and host configuration
are not silently included. The archive is restricted material, not a source
artifact or model input. No credentials are read into chat/logs or committed.

The fixed exclusions omit `node_modules`, Python virtualenv/bytecode, npm/build
caches, local downloaded toolchains, generated frontend bundles and compiled
application binaries. Tracked paths take precedence; local Forge
`go.mod`, `bun.lock` and `build.json` are preserved. The first included regular
file inventory is about 335 MB uncompressed, versus roughly 9 GB of original
dependency-heavy checkout data.

SQLite files are identified by header and use the online backup API, covering
committed WAL records; output is standalone DELETE-journal SQLite. Every
database is integrity-checked. Live sockets cannot be copied/restored and are
explicit manifest omissions; other special files and external/absolute links
fail before publication. Non-database files changing during capture fail
explicitly instead of producing a success-shaped archive.

Local staging/extraction precedes the host copy. Verification covers exact
included inventory, SHA-256, permissions/symlinks, original Git HEAD/tracked
state, submodule revisions/object connectivity and database integrity.
Untracked included files are checked by manifest, not by requiring generated
dependencies to survive in Git status. A host checksum mismatch removes only
the newly created copy. Unique UTC/nonce archive names preserve earlier copies.
No temporary staging tree/process remains after completion.

The first host archive is
`EngiPlatformBackups/engi-platform-20261012T233156Z-2a098422.tar.gz`:
185,996,460 bytes, 15,074 inventory entries, 40 online database snapshots,
51 omitted paths, original Git HEAD `91cd7ba`. Its checksum is
`1eb7afc959a2af20650067fcb765c66925505b53e479ce6d0fbb655b3ebe7503`;
a `.sha256` sidecar is adjacent. It contains the initially uncommitted backup
implementation; post-commit archives record their exact Git commit/time in the
embedded manifest rather than requiring self-referential source receipts.
The first run stopped safely on roborev's runtime socket before creating any
host archive; the explicit socket exclusion and regression resolve that case.

Nine new backup tests cover sensitive/dirty work, dependency trimming,
tracked generated stubs, private permissions, SQLite WAL content,
offline submodule restoration, runtime sockets, external links, failed
restore/host-copy cleanup and non-overwriting repeat copies.
Local archive restoration is not a running-application recovery drill, and
local OneDrive placement is not verified cloud upload/retention/recovery.
No automatic schedule, host/global setting or service configuration changed.

## Falcon full-corpus backup extension: 2026-10-12 at 19:51

The owner explicitly authorizes `falcon-docs` under the same protected-OneDrive
rules. Root instructions and the maintenance/catalog/event recovery contracts
were read before acting. Its Git worktree is clean at `fec05a8`. Do not edit
its corpus, add ignored intake/owner TODO to Git, mutate review events, refresh
retrieval indexes or prune retained snapshots. This operation does not grant
program release/ORR authority or include global client profiles.

Metadata-only preflight identifies 60,452 included regular files totaling
78,038,095,118 bytes, and 2,698 reinstallable files totaling 81,216,861 bytes.
The large remainder is principally source assets, extraction/provenance and
retention-bound recovery copies, not removable dependency bulk. Four apparent
external Python links were all inside a named measurement virtualenv; detecting
its `pyvenv.cfg` excludes that installable environment without following links.
No included external links or unsupported special files remain.

`backup_workspace.py` now accepts an explicit `--source`, `--staging-dir` and
repeatable relative `--sqlite-snapshot` paths, retaining default platform use.
Explicit selection snapshots only catalog, review events, the text index and
the graph index. Historical database artifacts/receipts and raw originals are
preserved byte-for-byte, avoiding invalidation of existing receipt hashes.
Archived manifests identify the exact SQLite selection. Distinct source-based
archive names and fast gzip support the larger copy.

Staging uses the session's private, disk-backed `files/` directory outside both
checkouts, with about 857 GB free at preflight; `/tmp` is a 24 GB tmpfs and is
not suitable. Local staging must be removed after completion/failure. The
protected destination has about 660 GB free locally; this says nothing about
cloud quota/upload/retention. No automatic backup schedule is configured.

All 102 focused tests pass, including 14 backup tests. New cases prove named
virtualenv exclusion, disk-backed staging/cleanup, explicit live-database path
validation and byte-identical historical database/receipt preservation.
Existing private permissions, SQLite WAL, dirty work, submodule history,
host-copy cleanup and non-overwriting behaviors remain covered.

Completed host artifact:
`EngiPlatformBackups/falcon-docs-20261012T235557Z-a882cca6.tar.gz`,
22,966,738,780 bytes, SHA-256
`05ada485efa7fefe3feb5dc7be99fc1482d773eaaa08716cbff02979ab9019c7`.
The restored manifest covers 88,398 entries, four consistent live SQLite
snapshots and 27 explicit omissions. Original files and historical recovery
snapshot/receipt bytes passed full inventory/hash verification; Git HEAD is
`fec05a8b41d96840bdcd2b50cad8c18abe2057bb`. Host checksum matches the local
verified archive; an adjacent `.sha256` receipt is persisted.

The disk-backed temporary tree is removed, returning Linux free space to
about 857 GB. Windows reports about 510 GB free after capture versus 660 GB at
preflight: temporary WSL filesystem allocation can grow its host VHD even
after Linux files are removed. Physical VHD reclamation/compaction is not
verified and no WSL/global configuration or trim/compaction operation was
attempted. No temporary files or experiment processes remain.
Kata task `b2bg` is closed with specific archive evidence; cloud delivery,
retention and running-application recovery remain unverified.

# Artifact audit: 2026-10-09

Owner-requested cleanup subagent removed only generated ignored bytecode:
`scripts/__pycache__/{local_env,pi-local,roborev-local,test_local_env}.cpython-314.pyc`
and the resulting empty directory, totaling 140,662 bytes. File headers matched
the source; no references or active application use were found. Git's
tracked/untracked integration inventory was unchanged.

Retained smoke evidence/state: `.local/smoke-34y6xdbz/`,
`.local/smoke-3drucu09/`, `.local/smoke-a583h605/`,
`.local/smoke-dyodi3_p/`, `.local/smoke-hi04l9qk/`,
`.local/smoke-km9q33bz/`, `.local/smoke-kxluwcll/`,
`.local/smoke-ql7by8p_/`, `.local/smoke-vvq67ljo/`,
`.local/smoke-xivdi_ox/`. These contain application configuration/state and
successful/failed diagnostic evidence; documented retention is not permission
to delete them. `.local/forge-manual/` contains auth/configuration, locks and a
database; `.local/smoke/` ownership/relevance remains uncertain. Decide their
retention explicitly before removing private profiles.

Keep `.local/downloads/`, `.local/cache/`, `.local/include/`, `.local/tools/`
for repeatability/toolchains, `.local/environment/{tmp,pi/tmp}/` runtime
compilation/configuration state, and `.local/forge-local-kata/` as the approved
working build. `.local/builds/` was empty. Persistent data, review-demo/evidence,
backups, sessions and user units remain untouched. Application health returned
HTTP 200 with unchanged PIDs; no experiment/process was retained.

# Build and runtime notes

These are observations from the pinned source, not proof of successful startup.
The integration build-lock tests import `bun:test`; run them with the documented
pinned Bun executable, not Node's test runner.
Bootstrap also installs workspace-local GitHub CLI 2.102.0 from the official
Linux-amd64 archive, pinned SHA-256
`bb766f710eef8ede859c18578c72c327597cd4c8a85b06001b1f3843c6019386`.
The isolated `scripts/gh-local.py` launcher shares `GH_CONFIG_DIR` with Forge;
it neither inherits token variables nor changes global CLI/shell settings.

| Component | Build | Isolation and integration |
| --- | --- | --- |
| roborev | Go 1.27+, Bun 1.3.14; `make build` embeds its web UI | Default API is loopback port 7373. Do not run `roborev init` on real repos before configuring review agents: it installs a post-commit hook and starts a daemon. |
| Forge | Go 1.27+, Bun 1.4.0 per package manifest, Node; `make build` | `KENN_FORGE_HOME` isolates config/data. Foreground command is `kenn-forge serve`; default UI port 8091. Workspaces use Git and tmux. |
| Kata | Go 1.27+, Bun 1.3.14; `make build` | `KATA_HOME` isolates SQLite/config; `KATA_SERVER` selects a daemon. Supports CLI, TUI, web UI, task dependencies, MCP, and optional federation/Postgres. |
| AgentsView | Go 1.27+, CGO/C compiler, Node 24.11+; `make build` | `AGENTSVIEW_DATA_DIR` isolates the archive, but session discovery also needs an isolated home/source configuration. `AGENTSVIEW_NO_DAEMON=1` prevents implicit daemon startup. |
| Superpowers | Skill files and a Pi extension; no independent daemon | Package metadata declares `.pi/extensions/superpowers.ts` and `skills/`. Upstream documents `pi -e /path/to/superpowers` for a session-local trial. |

Forge connects to roborev through `[roborev].endpoint`, default
`http://127.0.0.1:7373`. It does not start roborev. Keep
`init_managed_clones` disabled during initial checks.

Temporary local Kata build, implemented on 2026-10-05:

- Forge consumes Svelte/TypeScript source from
  `@kenn-io/kata-ui/packages/kata-ui/src/index.ts`, not Kata's compiled web
  bundle or daemon binary. Its dependency represents the whole Kata repository.
- The locked Git object `c6685725ecd6a31aaea83cf98908e0c866c5d434` is the
  annotated v0.14.3 tag, not a commit as initially recorded. It resolves to
  commit `410ee88bca267b117c845a36f8249890c5160e3b`. Both are already in local
  Kata history; the build exports the resolved commit, not the current checkout.
- Forge also requires the separate Go module `go.kenn.io/kata v0.18.0`.
  Its download exposed another Zscaler block. The temporary build exports
  its exact local commit `91ee2f9215b3aff0795e66b8ed22e8494b13eadb`.
- Run `./scripts/build.sh forge-local-kata` explicitly. Normal `forge` and
  default builds are unchanged. The helper refuses tracked Forge edits,
  exports committed source into a fresh `.local/builds/forge-local-kata-*`
  workspace, and preserves upstream checkouts, pins, and license files.
- In that scratch copy only, the frontend uses `file:../../kata`; the exported
  Kata root gets `name: "kata"` because Bun otherwise writes a nameless
  resolution that its frozen installer cannot parse. UI source is unchanged
  and compared against the installed dependency before compilation.
- Bun derives a separate lock, and a structural check rejects every change
  except the explicit Kata substitution. Installation then uses the frozen
  derived lock. The original remote archive's integrity is not attributed to
  the local source. Other dependencies retain their versions and integrity.
- The scratch `go.mod` gets one version-specific local Kata replacement.
  The helper rejects other edits, builds with `-mod=readonly`, and checks that
  `go.mod` and `go.sum` are unchanged by the build. It does not reroute network
  downloads; other dependencies may still require network access.
- An empty, template-free scratch Git repository prevents formatters inheriting
  the parent's `.local/` ignore rule. Go VCS stamping is disabled for this
  history-free export; actual Forge revision and a `-local-kata` version suffix
  are passed explicitly.
- Outputs are `.local/forge-local-kata/{kenn-forge,kenn-forge-github-app}`,
  the derived `bun.lock`/`go.mod`, and `build.json` with both Kata source
  revisions, Forge revision, version, and lock SHA-256. Successful scratch
  workspaces are removed; failures retain their path for diagnosis.
- Both binaries built twice with identical dependency manifests/provenance.
  This is not a claim of byte-identical binaries or a hermetic build.
  Runtime HTTP verification passed after the user-approved switch to NAT,
  and again on 2026-10-08; details are in `status.md`.
  Remove this variant after the normal build and
  smoke check pass following the IT exception, as tracked in `../TODO.md`.

Forge discovers Kata's daemon catalog through `$KATA_HOME/config.toml`.
Task/workspace integration needs a connected, compatible daemon and repository
mappings; a running Kata process alone does not prove that integration works.

Forge uses Elastic License 2.0, which restricts providing substantial
functionality as a hosted/managed service to third parties. The user's scope
is private/internal deployment, not a customer-facing service. Preserve all
upstream license notices and check the eventual deployment against those terms.

Pi is now 1.0.3 on this host's PATH, upgraded by the user. The 2026-10-08
isolated, offline RPC session still loaded all 15 Superpowers skills.
The Pi extension injects the Superpowers bootstrap at startup and after
compaction; the smoke test verifies skill discovery, not model behavior or
compaction execution. Our bootstrap does not yet pin/install Pi.

Roborev has a Pi adapter. Structured reviews and classification additionally
require its configured JSON-schema extension, currently defaulting to
`npm:@nqbao/pi-json-schema@0.1.1`. It was installed in the private profile on
2026-10-09 and used successfully by bounded manual Pi/USAi review job 1.
The separate auto-design classifier and real-project review remain unverified.
AgentsView Pi/Copilot ingestion is verified below; no-session review-job
accounting is not covered by that ingestion.

# Citrix mapped-drive handoff: 2026-10-12

**Current boundary, owner report at 11:43:** outbound VDI file transfer is not
allowed; assets must be read through the VDI. The handoff layout and copy tests
below are historical research, not instructions to execute under the current
policy. Stop export attempts. Do not substitute clipboard, screen capture/OCR,
transcription, alternate upload channels or tunnels to evade this restriction.
Local asset handling clearance and technical Citrix capability do not override
the enforced transfer policy. An approved in-VDI engineering/model tool path
needs confirmation before installation, asset processing or endpoint use.
SPUD documents were mentioned but not provided; their location and permitted
processing route are unknown.

The owner is downloading the native Citrix client to investigate mapped
drives. Public Citrix Windows documentation confirms that Client drive-mapping
exposes local client drives inside a remote session, as UNC links or mapped
drive letters. It does not map the VDI's filesystem into local WSL or supply
a VPN/network route. Mappings are user/session-scoped and recreated at login.
Exact labels/drive letters depend on configuration.

Effective administrator policy controls feasibility:

- `Client drive redirection` must allow file access.
- `Client fixed drives` must allow the Windows drive used for handoff.
- `Read-only client drive access`, if enabled, prevents the VDI from creating
  or modifying files locally. Local-to-VDI copying may still work, but a
  VDI-to-local export onto that mapped drive cannot.
- HTML5/Chrome upload/download policies are separate from native drive
  redirection; switching clients does not guarantee permission.

Recommended Windows-client layout, not created or verified:
`C:\CitrixTransfer` on an approved local disk, outside OneDrive or other
automatic cloud-sync folders; normally visible from WSL as
`/mnt/c/CitrixTransfer` if C: is mounted there. Use folder-only redirection
where available and permitted; the documentation says it requires server
enablement plus user configuration, so do not assume the native client limits
access to this folder by default. Do not expose credentials or the entire
WSL home through a UNC/network mapping.

First check: launch the actual native session, inspect its local-drive entries,
then copy a non-sensitive marker from Windows into VDI-local storage and a
different marker from VDI-local storage into the Windows transfer folder.
Confirm contents in Windows and WSL. If policy blocks access, record the
restriction and seek administrator enablement; do not change registry/GPO or
bypass controls. Installation/configuration labels are version-dependent.

Use the mapped drive only as a handoff area: keep the authoritative checkout
on the VDI, export a scoped snapshot with repository/branch/baseline SHA,
extract the local working copy onto WSL's Linux filesystem, and return a
reviewed patch. Do not concurrently edit one live checkout from both sides;
session-dependent I/O and Windows/Linux filesystem differences make it a poor
shared build/worktree location. Validate native dependencies/tests on the VDI.
Sensitive model work remains on Pi/USAi. No client install, mapping, transfer,
registry/policy change or GSA connectivity probe was performed here.

Verified public sources:

- [Citrix Workspace app for Windows: Client drive-mapping](https://docs.citrix.com/en-us/citrix-workspace-app-for-windows/client-drive-mapping)
- [Citrix Virtual Apps and Desktops: File Redirection policy settings](https://docs.citrix.com/en-us/citrix-virtual-apps-desktops/policies/reference/ica-policy-settings/file-redirection-policy-settings.html)

# Local project, Pi and Falcon MCP

## Persistent local environment

As of the 2026-10-12 17:55 Kata migration, all four dashboards have independent
boot units. `install-kata-service`/`kata-run` reuse the shared unit installer
and sanitized environment with foreground/no-auto-token startup and no Node
or model credential. Kata readiness checks systemd MainPID against `/ping`,
`/health` against the existing private database/schema/version, and `/kata`
with HTML content negotiation. The shared API/UI must remain on loopback
17777; a separate configured web listener is rejected. The owner has not
requested automatic agent hooks or a backup.

`run` is now only a fallback for the three boot-installable dashboards and
never starts Forge. An empty-child supervisor still writes/removes its own
runtime/shutdown metadata so `stop` cannot hang or interfere with independent
services. `status` exposes `kata_service`; its legacy `stack` field describes
the optional supervisor, not availability of independently running dashboards.

On 2026-10-23 the owner retired Forge's persistent unit and implicit supervisor
membership. `forge-run` remains as an explicit foreground command, resolving
Node from the current PATH unless `--node-executable` is supplied. It retains
the saved binary/config, checks loopback port 18091, and uses the isolated Node,
Pi and GitHub environments. `status` probes an explicitly running Forge and
reads its projects only then; absence is normal. Provider sync stays disabled
at startup only while no repositories are configured; the retained four
mirrors therefore sync whenever Forge is deliberately started. The old unit,
service marker and managed runtime-identity reader were removed, while private
Forge database/config/credentials/clones remain preserved.

GitHub CLI credentials remain in the shared private
`.local/environment/gh/` profile, now authenticated
to github.com for the four selected mirrors. Additional repositories and write
actions remain owner-scoped. README owns login instructions and unit commands.
Earlier, the owner identified the Helix host `github.helix.gsa.gov` and
raised the outside-VPC boundary. CLI `--hostname` uses the bare host, not its
HTTPS URL. No Helix connectivity/authentication request has been performed.
Workstation approval is confirmed, including the owner's 2026-10-12 13:11
reconfirmation; direct Helix access still needs approved network connectivity,
but this is no longer a prerequisite for github.com mirror intake.
The VDI export prohibition remains in force.

2026-10-12 clarification: the owner confirms local GSA asset download/use
clearance; VPN access remains unavailable and admin WorkSpace/VDI tickets are
pending. Standard Citrix VDI export is a proposed interim intake path, not a
verified capability or an authenticated Forge provider. Before exporting,
confirm the approved Citrix download/upload mechanism, target repository and
branch, exact baseline commit, and any uncommitted source changes. Prefer a
tracked-source snapshot excluding credentials/local state, with a reviewed
patch returned for application and native build/tests on the VDI. Git history,
submodules, LFS objects and internal dependencies need explicit consideration;
a source ZIP does not necessarily include them or support an offline build.
Keep sensitive engineering prompts/reviews on the configured Pi/USAi path.
This Copilot session retains independent inference routing; neither local
clearance nor AgentsView tracking changes that. No VPN setup, export/import,
provider change or application-code work has been performed.

Implemented on 2026-10-08 for personal exploration as well as the demo.
All application state is retained under ignored `.local/environment/`; this
is separate from both global home settings and disposable `.local/smoke-*`.
AgentsView and roborev have enabled user-systemd services; no cloud resource or
system-wide service is installed.

```sh
python3 scripts/local_env.py setup \
  --corpus "$HOME/falcon-docs" \
  --forge-binary .local/forge-local-kata/kenn-forge
python3 scripts/local_env.py run
```

Setup creates missing configuration only, preserves existing files/settings,
and rejects unintended changes to recorded executable/corpus paths. `run`
retains all installed independent services and starts only uninstalled ones.
Before Forge's migration it owned Forge/Kata; before any user-service migration,
all four daemons were supervised together. The loopback ports are unchanged, and Falcon is
registered idempotently without changing the checkout.
Ctrl+C stops the supervisor, or from another terminal:

```sh
python3 scripts/local_env.py status
python3 scripts/local_env.py stop
```

Stop checks the saved Linux process start time before signaling its exact PID,
waits for owned daemons, and checks their listener shutdown. Independently
managed AgentsView/roborev are not signaled. Settings/projects/data are never deleted.
Keep `run` in a terminal, or use the documented on-demand `systemd-run` unit
with the shell's non-secret PATH for its NVM Node dependency. Companion logs
append under `.local/environment/logs/`; independent services use the user journal.

Forge remains at http://127.0.0.1:18091/, roborev UI at
http://127.0.0.1:17374/reviews, Kata at http://127.0.0.1:17777/kata,
and AgentsView at http://127.0.0.1:18080/.
Provider synchronization is enabled for the four selected private GSA mirrors;
scoped AgentsView ingestion is enabled.
Use `register /absolute/project/path` for another existing local Git checkout.
For a new project, initialize it separately, then register it; registration
does not create starter source or publish a repository.

Forge's only enabled agent target is Pi (USAi), pointing to
`scripts/pi-local.py`; other built-in model agents are disabled to avoid
accidental alternate-provider use. Shell targets remain available. Roborev's
default Pi command uses the same launcher; automatic hooks remain off.
The wrapper validates Pi 1.0.3 and selects the private profile in its own
process, so it works even after Forge's tmux environment sanitization.
It does not change global Pi settings or grant blanket project trust.
The dedicated tmux socket is `kenn-kopy-local`; terminal sessions may survive
browser navigation and can have independent lifetimes. Stop unwanted sessions
through Forge's session controls; stopping dashboards is not authorization to
kill unrelated tmux sessions or discard work.

Profile/settings locations:

| Location under `.local/environment/` | Purpose |
| --- | --- |
| `environment.json` | Machine-local corpus, Forge binary and exact Pi executable |
| `forge/config.toml`, `forge/forge.db` | Forge settings and persistent project/worktree registry |
| `pi/settings.json`, `pi/mcp.json`, `pi/models.json` | Private Pi resources, context connection and non-secret model configuration |
| `pi/sessions/` | Pi's default persistent session storage in this profile |
| `roborev/`, `kata/`, `agentsview/` | Persistent application configuration/databases |
| `secrets/usai-api-key` | Owner-supplied USAi token, never tracked or printed |

Parent directories are owned `0700`; integration-created settings and keys
are `0600`. Database files may have upstream default file modes but remain
inside inaccessible private parent directories. This is configuration/data
isolation, not an OS sandbox or protection from processes using the same UID.
Keep the profile and any backups private; Git does not back up ignored state.

Pi's Falcon exposure uses `codemode`: Pi 1.0.3's direct MCP adapter truncates
model-facing text over 20 KiB, whereas codemode receives the full MCP result.
The qualified reader must not lose required context silently.
`node scripts/check-pi-mcp.mjs` uses the installed Pi SDK/MCP extension to
check freshness and read one bounded qualified packet without a model request
or printing corpus text. The CLI handshake is:

```sh
python3 scripts/pi-local.py mcp list
```

Actual Forge-launched tmux processes completed both checks, and two subsequent
supervised restarts retained Falcon's project ID and all saved configuration.
Compaction and model-selected tool use still require USAi model-backed checks.

Forge's pinned UI has an **Add an existing local repository** action that does
not require GitHub, reachable directly at `/project-intake`. Its
`POST /api/v1/projects` API accepts `local_path` and
optional `display_name`/`default_branch`; a missing or untracked remote leaves
the project unlinked to provider sync. Local project/worktree registration is
distinct from adding a provider repository in Settings. Falcon is now registered
and USAi is configured; an interactive model-backed Forge retrieval session
still needs a usable UI/access path, not another registration attempt.

### Local-project UI limitation: 13:42 owner report

Live API reads and an isolated headless browser confirmed that Falcon's local
project and primary worktree persist, but `/api/v1/repos` and `/api/v1/workspaces`
are empty. The Repos and Workspaces UI do not display the local project, and
the **Create Workspace** button is disabled. Provider onboarding appears on a
fresh home-page visit despite the local registration; **I'll do this later**
dismisses it. `/project-intake` still offers enabled provider-free local intake.

The contracts are separate: `App.svelte` onboarding checks
`hasConfiguredRepos`, `NewWorkspaceDialog.svelte` loads `RepositoryReads`, and
the workspace sidebar lists the fleet workspace snapshot, not local projects
and their worktrees. Local intake calls `ProjectsService.registerProject` and
returns to `/`. Registration alone therefore does not produce a usable main
workspace UI entry. This establishes the current behavior, not whether the
upstream separation is intentional or a missing integration.

At 13:55 the owner chose to wait for GSA GitHub access and use an approved
real provider-backed demo target, deferring local-project UI changes.
Do not invent identities or publish Falcon.
Direct isolated Pi is available without either. README and TODO now state
this limitation rather than equating API registration with UI readiness.
Private evidence: `.local/environment/runtime/local-project-ui-check.json`.
No repository/workspace was created, provider/remote added, or model called.

The existing pinned Playwright 1.62.1 package was used for live inspection.
Its browser executable was missing, so its matching headless Chromium and
FFmpeg were installed only into ignored `.local/tools/playwright-browsers`
with `PLAYWRIGHT_BROWSERS_PATH`; global configuration was not changed.
All browser contexts/processes were closed. No screenshot or user browser
profile was created/modified.

The user identified `~/falcon-docs` as the local project/context source.
Read its `AGENTS.md` and task-specific guides before operating on it; those
instructions apply there, not across this integration workspace.
The server's operating contract is `tools/context-mcp/README.md` in that
checkout. It is an installed, read-only stdio server, not an HTTP service:

```sh
CORPUS="$HOME/falcon-docs"
"$CORPUS/tools/context-mcp/.venv/bin/qualified-context-preflight" \
  --root "$CORPUS" --reader "$CORPUS/tools/context-index/context_index.py"
```

This non-refreshing preflight passed on 2026-10-08, including SDK dependencies,
FTS5, schema snapshots, catalog/event-store status and selected-index
freshness. It does not prove client connectivity or model authorization.
No rebuild, installation or authoritative write was requested.

The isolated local Pi profile is configured with the stdio executable
`tools/context-mcp/.venv/bin/qualified-context-mcp` from that checkout with
absolute `--root` and `--reader` arguments pointing to the existing corpus
and `tools/context-index/context_index.py`. Setup derives machine-local paths;
do not commit private client configuration or copy corpus data.
Use its existing index/store layout, not a new backend or a worktree snapshot.

Pi 1.0.3's installed CLI and docs confirm native stdio/Streamable HTTP support.
`PI_CODING_AGENT_DIR` selects an isolated profile, including `mcp.json` and
`models.json`. Project `.pi/mcp.json` is an alternative for trusted projects;
never set blanket global trust. MCP available in Copilot is not inherited by
Pi. After configuration, verify `pi mcp list`, `/mcp` in the actual Forge-launched
session, then `status` and a bounded qualified read with known expected content.
Local connection/read checks and restart passed. Repeat after model compaction.

The credential-free `scripts/smoke.py` uses fresh private state each time.
It proves startup/assets/task storage/offline skill discovery, not persistent
project registration, a Pi MCP connection or model-backed work. The separate
persistent launcher above does not repurpose disposable smoke state.

# roborev WSL startup

The 17:00 owner request enabled `kenn-kopy-roborev.service` alongside
AgentsView, leaving Forge/Kata on-demand while GitHub access waits.
`install-roborev-service` uses the shared private user-unit installer and
records the resolved Node executable in its `roborev-run --node-executable`
arguments. The launcher prepends that binary's directory to its sanitized
PATH and verifies the saved Pi 1.0.3 executable. It validates both loopback
bindings and executes the existing daemon with its explicit private config.
No global shell/manager environment change or model credential in the unit/
daemon is required; only the Pi child launcher reads the USAi key.

Health checks require `/api/ping` to match systemd MainPID, `/api/status` to
answer with the same version, and the separate review UI to serve HTML.
The `/reviews` SPA shell requires `Accept: text/html`; an ordinary URL-only
HTTP request gets 404 even while the browser route works. The initial install
hit that readiness mistake; the corrected browser-style check passed.
Both service installers retain occupied-port and ownership checks.

The supervisor now records both independent services, excludes their three
ports from owned startup/shutdown, and refreshes their PIDs in status after
restart. `stop` leaves both running. The existing transient on-demand unit
was restored with only Forge/Kata children; it is not boot-enabled.
No queued/running review existed during migration. Saved app/profile config
hashes, project identity and review counters were unchanged; no hooks/reviews
or model calls were introduced. A structured Pi-backed review remains open.
Repeat installation, service restart with pinned Node under systemd, and
independent stop/start behavior passed. Real WSL reboot remains pending.
Private evidence: `.local/environment/runtime/roborev-service-migration.json`.
README owns operational commands and the separate-stop smoke procedure.

## Review workflow boundaries and remaining configuration

Read-only assessment for the owner's 17:17 question:

- Git post-commit hooks automatically enqueue local reviews independently of
  the coding agent, Forge and GitHub. Manual commit/branch/dirty reviews do not
  require hooks. `init` also handles post-rewrite remapping and pre-push batch
  flushing; these hooks are not commit/push quality gates.
- Generated Git hooks bake in only the executable path. They do not preserve
  the caller's private `ROBOREV_DATA_DIR` or `--server` selection. Before using
  `init --no-daemon`, supply a persistent scoped executable that selects this
  workspace's state and port 17373. At that assessment no launcher existed;
  `scripts/roborev-local.py` now provides it, as verified on 2026-10-09 below.
  A plain global invocation may still use a separate profile/daemon.
- Pi structured reviews explicitly load
  `npm:@nqbao/pi-json-schema@0.1.1` and use `--no-session`; installation and a
  full synthetic structured review are now verified below. These invocations
  will not appear as normal saved Pi sessions in AgentsView. Review-history/Analytics and
  any metadata-only usage bridge need actual telemetry verification.
- Structured review args do not disable all profile extensions/context,
  unlike the separate routing classifier. They restrict ordinary review
  tools to read/grep/find/ls plus JSON output. The private Falcon MCP profile
  exists, but model-selected qualified retrieval in a roborev review is not
  verified; do not assume it has task/acceptance evidence automatically.
- Optional coding-agent hooks feed findings into active supported harnesses.
  Copilot CLI is listed; Pi is not listed in this pinned agent-hook guide.
  These differ from Git hooks and from review-completion event hooks, and
  may steer an agent toward code-changing fix skills.
- Per-repo `.roborev.toml` can specify `agent = "pi"`,
  `review_reasoning`, `review_guidelines`, `exclude_patterns`,
  `post_commit_review` and `post_commit_batch_size`. Keep one worker initially.
  The private Pi wrapper pins provider/model and rejects CLI overrides;
  arbitrary roborev model/provider selections conflict with that contract.
  Do not enable alternate-provider fallback/budget substitution.
- Kata integration is optional and off by default: a project binding plus
  `[kata_context] mode = "current"` pulls referenced task intent; an explicit
  `type = "kata"` completion hook files findings. Its daemon must be available.
  This does not implement Jira import. Forge is a review/workspace client,
  not a prerequisite for local review. Superpowers supplies workflow skills,
  not automatic commit review.

## Isolated schema extension and scoped review: 2026-10-09

Owner approved installation, the scoped launcher and one bounded review, while
deferring project review policy/automatic triggers for joint configuration.

- `install-pi-review-extension` invokes native Pi `install` for
  `npm:@nqbao/pi-json-schema@0.1.1` with the private profile/HOME, from the
  private home directory, without reading/injecting a USAi key. It verifies the
  saved pin. Repeat installation preserved Superpowers and the other settings.
  Package source/dependencies and npm lock live under `pi/npm/`; settings remain
  private. The installed package uses Ajv validation and a `json_output` tool.
- `scripts/roborev-local.py` is an executable Python entrypoint, usable from
  other repositories/minimal hook PATHs. It validates saved loopback bindings,
  pins native CLI `--server 127.0.0.1:17373` and private `ROBOREV_DATA_DIR`, and
  preserves arguments, cwd and stdin. Explicit server selection prevents
  automatic daemon discovery/start/restart; overrides are refused. The
  sanitized child environment carries no model credentials.
- Native Git hook generation accepts the launcher through `--binary`; it does
  not infer it from the wrapping invocation. Native startup/update repair
  replaces custom binaries inside `.git/hooks`. `HooksInsideGitDir` protects
  user-managed external hook paths. A private disposable fixture with spaces
  in its paths preserved an existing hook, generated all three scoped hooks,
  passed shell parsing/post-rewrite execution, and retained their bytes after
  native `repair --git-dir-only --binary <native binary>`. Minimal PATH,
  unrelated HOME and wrong inherited data-dir did not change CLI targeting.
  No hook was installed in a real project or in the bounded review fixture.
- The review fixture at `.local/environment/review-demo-20261009/` is a private,
  unpublished two-commit Git repository with hooks disabled and synthetic
  pricing code/checks. Baseline passed; the intentional arithmetic regression
  produced exactly two expected check failures. Scoped manual `review --type
  default --agent pi --panel none --reasoning fast --wait` queued only job 1.
  `--type code` was rejected before queueing; the native type is `default`.
  Job 1 completed in roughly seven seconds with `agentic=false`, structured
  schema version 2, verdict fail and one high finding at `pricing.py:3`.
  File coverage is two reviewed/zero excluded; the source remains unchanged.
  `review --wait` exit 1 reflects the findings, not an execution failure.
- Durable findings are visible through `show --job 1` and the review UI.
  Private evidence: `runtime/bounded-review-{before,target,job-1}.json`,
  `runtime/scoped-hook-check.json`. No token usage fields were provided by
  the stored job/review JSON; this is unavailable usage, not zero consumption.
  Normal reviews use `--no-session`, so no native saved-Pi accounting claim
  is made. Actual Falcon retrieval/classifier/real-project review remain open.
- README owns install/manual-review commands and future hook-layout cautions.
  Per-repo guidance/hook installation and sandbox evaluation remain in TODO;
  neither read-only review tools nor profile isolation provide an OS sandbox.

# AgentsView is an archive, not a model router

The pinned AgentsView supports Copilot CLI session files under a configured
Copilot root (normally `~/.copilot/`, including `session-state`), as well as
Pi and separate VS Code/Visual Studio Copilot formats. It imports local
session records into its own SQLite archive; it does not need to proxy model
traffic or receive the USAi model key for browsing/search/usage reports.
This is session-log observability, not a process inventory or automatic
visibility into remote GitHub-hosted agents.

The 15:33 owner request enabled scoped ingestion. The isolated HOME is retained,
but `[agents.copilot].dirs` points to `~/.copilot`, and `[agents.pi].dirs`
includes global `~/.pi/agent/sessions` and private
`.local/environment/pi/sessions`. Only these two providers are enabled.
AgentsView's environment omits `PI_CODING_AGENT_DIR` because that native
override otherwise hides the configured multi-directory Pi sources.
`--no-sync` is omitted only when private tracking metadata exists.

`configure-tracking` preserves raw TOML/settings, coordinates with the
application's `config.toml.lock`, and refuses source/content-policy conflicts.
Rerunning the current configuration preserves its bytes. `archive_content`
supports full, transcripts or usage; transcripts is not a redaction guarantee.
The initial `usage` policy retains metrics/activity but excludes transcript
text, thinking, tool payloads and titles. Native client sources are unchanged.
Retention and deliberate fuller-content migration remain separate work.

The first import contained 42 Copilot and 11 global Pi sessions. A real saved
synthetic USAi Pi request added the twelfth Pi session automatically: 481 input
and 9 output tokens, exactly matching the client's 490-token total. Copilot
event growth was automatically rearchived, and 19 historical Copilot sessions
had native per-request store usage at verification; other histories include
shutdown-derived usage. The current Copilot UUID had no native usage-store
rows yet, despite its event/activity updates. Do not infer zero consumption.
Copilot shutdown may finalize metrics, and complete ACP/subagent coverage is
not established. USAi aliases are explicitly unpriced, not authoritative
zero-cost usage.

The real health endpoint is `/api/ping`; other API calls use `/api/v1/...`.
Per-step usage rows require `?breakdown=true` on
`/api/v1/sessions/{id}/usage`; an empty default breakdown is not missing data.
Usage-only Pi metrics live in projected message token fields, whereas Copilot
store metrics also populate standalone `usage_events`.

`install-agentsview-service` generates the private unit under
`.local/environment/systemd/` and links/enables
`kenn-kopy-agentsview.service` in the existing user manager. The launcher
validates its policy, uses loopback/no-browser/no-update-check, and never
receives the USAi key. Health must match systemd's MainPID. Existing systemd
and `Linger=yes` required no privileged boot changes. The unit is enabled and
restart/archive persistence were verified; a real WSL shutdown was not tested.
At that initial migration, AgentsView and roborev started at boot while
Forge/Kata remained on-demand. Subsequent migrations enabled all four units.
README owns startup/service/smoke commands.

The companion supervisor attaches to that unit without owning its process.
Status reports the live independent PID after restart, and stop checks only
owned listener ports. Stop all four current independent units before disposable smoke
checks. Private pre-import configuration/empty-archive backup:
`.local/environment/backups/pre-tracking-20261008T194142Z/`.

Optional generated insights/Recall and semantic search can invoke an agent CLI
or configured model/embedding endpoint. They are separate opt-in model features,
not required ingestion infrastructure; verify USAi-only routing before use.
Publishing sessions to Gist or external archive/database services is also
separate and not authorized by local processing approval.

Archiving Copilot sessions does not route Copilot inference through USAi.
The provider selection we implemented applies to our Pi launcher and the
configured Pi review command; the independently running Copilot client retains
its own model-service configuration.

# USAi LiteLLM integration

## Proposed personal Zed launcher: 2026-10-08

The owner is considering a home-directory command that checks Pi's USAi key
and opens Zed, with manual key generation/handoff. Prefer a thin command
under the existing `~/.local/bin/` convention, pointing at version-controlled
integration code, not an untracked all-in-one service orchestrator.
Credential logic should also work when launching Pi directly or through
Forge; editor startup alone does not protect already-open Zed or live Pi
sessions against subsequent expiry.

Keep the private key out of Zed settings and the editor's environment. Pi's
child launcher/helper should select its explicit profile and read the shared
private key source. Check live authentication without a model prompt, guide
manual replacement with `set-key`, and distinguish HTTP 401 from network
failure. An expired USAi key should disable/block Pi use, not prevent opening
Zed or independently authenticated Copilot. Do not start another AgentsView
instance when its user service is running, or make editor use depend on Forge.

Observed local executables: Zed 1.23.2 at `~/.local/bin/zed`, and Copilot CLI
at `~/.local/bin/copilot`; Copilot help exposes `--acp`. Zed's official
external-agent docs support ACP-hosted Pi and Copilot. The official ACP
registry inspected on 2026-10-08 advertises `pi-acp@0.0.34` (an adapter,
not plain Pi's RPC mode) and `@github/copilot@1.0.93 --acp`.
No adapter was installed or Zed agent setting inspected/changed. Registry
presence does not prove compatibility with the host's Pi 1.0.3, its native
Falcon MCP exposure, or durable session ingestion; verify those before
relying on a Pi ACP setup.

Zed Terminal Threads are the simpler initial alternative: they run the
existing `scripts/pi-local.py` or native Copilot CLI without an ACP adapter.
They retain CLI-owned configuration/auth/MCP; terminal threads are not Zed's
archived agent thread history. AgentsView ingestion remains independently
dependent on durable native session files and its configured source roots.
Copilot uses its own GitHub authentication/model routing, not the USAi key,
and AgentsView observes session files rather than routing requests.

Sources:
https://zed.dev/docs/ai/external-agents,
https://zed.dev/docs/ai/terminal-threads,
https://github.com/agentclientprotocol/registry/blob/main/pi-acp/agent.json,
https://github.com/agentclientprotocol/registry/blob/main/github-copilot-cli/agent.json.

## Global Pi auth helper versus private launcher: 2026-10-08 diagnosis

Normal `pi` uses the owner's global profile, not this integration's private
profile. Its `litellm-usai` alias uses `pi-provider-litellm` 3.2.0. The earlier
auth command called `~/.pi/agent/usai-api-key.py`, which read a literal key
from the active profile's `models.json`. That key differed from the private
runtime key: global `/models` and synthetic requests returned HTTP 401, while
the private runtime returned HTTP 200 and an exact synthetic model reply.
The old helper succeeded even when the service rejected its token; default
startup logging did not report this. Exact expiry/revocation was not established.

At 15:56 the owner approved a simple common handoff. `set-key` now links the
existing global `models.json` `usai` provider and `settings.json`
`litellm.providers.litellm-usai` alias to `scripts/usai-key.py`. That command
uses the same private reader/file as Forge's launcher and prints the token
only to the consuming Pi process. Global literal USAi credentials were
replaced with non-secret command references; other fields, auth.json,
profile/session/MCP isolation and the existing private token were preserved.
The obsolete home helper was not deleted but is no longer referenced by
either configured provider.

Updated global files are `0600`; migration accepts owned regular readable
legacy configs but refuses symlinks or files writable by others. It refuses
saved auth.json entries overriding the affected providers and validates both
global configs before writing either. On a host without those providers,
`set-key` does not create them and explicitly reports zero global links.
The private profile remains independent except for the shared credential.

For diagnosis, keep helper stdout captured in memory: it contains the token.
Do not invoke it directly in a visible terminal or print it. Tool-free
`--no-session --no-context-files --no-approve` synthetic Pi requests can
distinguish auth rejection from model output without transmitting project
content; also disable skills/prompt templates and set a minimal system prompt.
Native `pi auth check` does not load this extension alias and reports
`provider_not_found`; use the actual model/discovery path instead.

## Seven-day key rotation: manual shared handoff

At 15:46 on 2026-10-08, the owner reported that USAi rotates API keys every
seven days and suspects the rejected global key expired. Treat the lifetime
as owner-reported; the observed HTTP 401 does not distinguish expiry from
revocation. The console at `https://gsa.usai.gov/console/key-management`
redirects unauthenticated readers to GSAuth. No approved key-generation or
renewal API/CLI was verified, and no sign-in or key-creation action was taken.

The owner selected simplicity at 15:56: generate a fresh key manually in the
console and run `python3 scripts/local_env.py set-key` once for both CLI and
Forge. The command atomically replaces the private file and maintains the
global credential references described above. No timer, reminder, renewal
API, or additional home launcher was installed.

`set-key` records no authoritative expiry metadata. `pi-local.py` still
injects a launch-time environment snapshot, so restart existing Pi sessions
after replacement. Request-time credential commands are used for global Pi,
but this does not eliminate the private launcher's startup snapshot or
renew a server-expired token. Any future reminder must distinguish actual
issuance/expiry from a local save timestamp. Future unattended renewal must
use a confirmed, authorized USAi interface, not assume stock LiteLLM
`/key/generate` access or automate GSAuth/MFA as a workaround.

## Current provider state: 2026-10-08

The owner reported successful Forge access and key setup, and approved USAi
and this local environment for sensitive information including PII; minimize
unnecessary PII in prompts. Treat this as owner-provided handling authorization,
not a reason to publish data or keys or skip technical deployment controls.

The old saved provider was in global `~/.pi/agent/models.json`, not Forge's
isolated profile. Only non-secret provider metadata was inspected. Its selected
model is `gpt-5.6-sol-latest-guardrails-defaultv2` at
`https://api.gsa.usai.gov/api/v1`. The advertised catalog still contains that
alias. A credential-safe refresh returned 22 model IDs and saved their IDs,
base URL and UTC fetch time to private `.local/environment/usai-models.json`.
The mixed catalog includes embedding models; it is discovery metadata, not a
reason to register every entry as a chat/tool-capable Pi model.

Two synthetic requests to `/chat/completions` confirmed SSE streaming, a
function call and its tool-result continuation for the existing selected
model. `openai-completions` is therefore the verified Pi API type for this
endpoint/model pair. The private profile was configured with that selection,
without copying the global profile's credential fields or changing it.
A real Pi invocation with only the read tool returned a fresh synthetic
fixture's contents; no Falcon content or PII was sent. Reports are private
under `.local/environment/runtime/usai-{protocol,pi}-check.json`.

Normal `scripts/pi-local.py` launches are now model-ready. Model-selected
Falcon MCP usage in Forge, compaction and structured roborev reviews remain
open checks. Do not generalize this protocol result to all catalog entries.

Refresh model IDs without changing Pi's selected model:

```sh
python3 scripts/local_env.py list-models \
  --base-url 'https://CONFIRMED-USAI-API-BASE'
```

The command reads the private credential only in the runtime, requires an
HTTPS base URL without credentials/query/fragment, refuses redirects, bounds
the response, and rejects invalid/empty catalogs rather than saving partial
results. It logs IDs/count only, not credentials or raw error response bodies.

## Private key handoff

The owner should run this command in their own terminal from this repository:

```sh
python3 scripts/local_env.py set-key
```

Paste the key at the hidden prompt and press Enter. The command atomically
stores just the token and newline in
`.local/environment/secrets/usai-api-key`, using `0600` inside a `0700`
directory. It refuses symlinks, permissive files and non-terminal input.
No key is accepted as a command argument, echoed or printed. Repeating the
command replaces the key and maintains the two existing global USAi
credential-command references without changing model selection or other
settings. These references contain paths, not the token; global providers
that are absent are not created.
Tell the next configuring agent only that the file is ready, never its value.

The runtime reads that file directly into the Pi process's `USAI_API_KEY`.
An assisting agent must not `cat` it, attach it to chat, copy it to a manifest,
log it or put it into command arguments. The service supervisor/Forge tmux
server do not receive the key. This protects against accidental disclosure,
not malicious same-account access; use a scoped/revocable key.

Supply the non-secret base URL, exact allowed model alias and API type
separately. Once confirmed, configure them locally:

```sh
python3 scripts/local_env.py configure-provider \
  --base-url 'https://CONFIRMED-USAI-API-BASE' \
  --model 'CONFIRMED-MODEL-ALIAS' \
  --api 'openai-completions'
```

The URL/model above are placeholders; `openai-completions` is the verified
protocol for the current selection. The command also accepts `openai-responses` and
`anthropic-messages`; choose only the protocol verified for the endpoint.
It preserves unrelated custom-provider configuration and stores only
`${USAI_API_KEY}` in Pi's `models.json`, not the token. Restart the Pi session
after changing the model; the wrapper reads a rotated key on every launch.
Run `python3 scripts/pi-local.py` in the intended project or choose Pi (USAi)
in Forge. Without both saved model and private key, normal agent launches fail
explicitly and do not fall back to an alternate provider.

Use an explicit custom provider/model in the isolated Pi profile. Pi's installed
`docs/models.md` documents `models.json` with `baseUrl`, API type, `apiKey`
environment interpolation or a private credential command, and model entries.
Confirm any new USAi URL, model alias and protocol before changing the verified
selection; do not infer that other API types or reasoning parameters are
accepted. Check streaming and a real tool-call round trip, not just model listing.

Keep the key outside Git, chat, command arguments and logs. The owner has
approved real Falcon content processing through USAi/local use. Forge's
agent tmux launcher sanitizes its environment, so exporting a key in the
parent shell alone is not a verified injection path. The private Pi launch
wrapper/profile establishes configuration and credentials in the actual
agent process; roborev's Pi subprocess is configured to use the same wrapper.
Do not silently fall back to another endpoint/provider. The earlier assessment
made no model calls; the later provider verification used synthetic content only.

For a coding/review demo, also verify roborev's required Pi JSON-schema
extension before using structured reviews. Avoid automatic hooks until the
agent/model is working and the target repository's scope is approved.
AgentsView ingestion can follow; its startup alone does not prove that it sees
the demo profile's Pi sessions.

The pinned Kata documents GitHub, Plane and Notion synchronization. No Jira
connector was found in the inspected Kata/Forge docs and Kata implementation.
Treat a one-ticket Jira import as separate integration work: preserve the
original key/URL, acceptance criteria and provenance, initially from an
owner-supplied export or an approved read-only API.

# Local build and smoke commands

```sh
./scripts/bootstrap-sources.sh
./scripts/bootstrap-toolchains.sh
./scripts/build.sh roborev kata agentsview
./scripts/build.sh forge
python3 scripts/smoke.py
```

While the IT exception is pending, opt into the temporary variant:

```sh
./scripts/build.sh forge-local-kata
python3 scripts/smoke.py --only-forge --forge-binary .local/forge-local-kata/kenn-forge
```

`--only-forge` does not start the other tools or Pi. Omitting it preserves
the full-stack smoke behavior; `--forge-binary` selects the artifact explicitly,
with no automatic fallback. The default remains `forge/kenn-forge`.
For an interactive isolated dashboard preview, add `--keep-running`.
After every startup check passes, the supervisor prints its PID and state
directory and keeps the daemons alive. Ctrl+C or SIGTERM to that supervisor
stops its owned services; an unexpected daemon exit also ends the preview.
Without this flag, the existing automatic shutdown behavior is unchanged.
Each invocation creates fresh isolated state (not a production deployment);
the state is retained on disk after exit.
Lockfile guard tests run with:

```sh
.local/tools/bun-1.4.0/node_modules/@oven/bun-linux-x64/bin/bun test scripts/build-forge-local-kata.test.mjs
```

The current toolchain bootstrap supports Linux x86_64. It requires curl, tar,
sha256sum, and npm; builds also require make, a C compiler, and Node 24.11+.
Python 3 and an installed Pi are required for the smoke test. The observed host
has Node 26.9.0 and Pi 1.0.3; these host tools are not installed or pinned by
our bootstrap yet. This is not a hermetic build environment.

Go 1.27.1 is installed under `.local/tools/` after checking its official SHA-256.
Bun 1.3.14 and 1.4.0 are installed there as exact-version native npm packages,
with package scripts disabled. Neither bootstrap edits global settings.
`build.sh` uses frozen Bun lockfiles and AgentsView's upstream `npm ci`,
workspace-local caches, and two Go build workers per invocation. Its default
target list includes all four applications and stops at the first failure.
Pass target names to build the unblocked applications independently.

Roborev and Kata need `sqlite3.h` for sqlite-vec. Our build script stages the
header from each project's pinned go-sqlite3 module, following AgentsView's
existing Makefile pattern, rather than requiring a system-wide package change.
Forge's unfrozen frontend dependency prerequisite is skipped only after a
successful explicit frozen install; no upstream manifest or lockfile is edited.

`smoke.py` creates a fresh private `.local/smoke-*` directory on each run. It
clears inherited credentials/configuration through an explicit environment,
disables telemetry, runs daemons in the foreground, and always attempts
shutdown in `finally`. It does not start system services, install hooks, open a
browser, sync private sessions, or submit model requests.
Shutdown checks process exit and that listener ports can be rebound; failed
connections alone cannot establish shutdown when loopback networking is broken.

| Service | Smoke address |
| --- | --- |
| roborev API | `http://127.0.0.1:17373/api/status` |
| roborev UI | `http://127.0.0.1:17374/reviews` |
| Kata API | `http://127.0.0.1:17777/api/v1/health` |
| Kata UI | `http://127.0.0.1:17777/kata` |
| AgentsView API/UI | `http://127.0.0.1:18080` |
| Forge API/UI, when built | `http://127.0.0.1:18091` |

An occupied port fails the affected startup rather than replacing its owner.
UI probes send `Accept: text/html` and fetch the embedded JavaScript entry
points. These are HTTP/asset checks, not browser-rendering tests. Kata's test
creates and reads a synthetic task. Pi runs offline RPC with the explicit
Superpowers package while the available daemons are running.

Forge is configured to use the smoke roborev endpoint, but this connection is
not yet verified. Provider sync and AgentsView ingestion are
disabled in the smoke test. The script exits nonzero for any blocked or failed
check, including a missing Forge binary, and writes local `results.json` plus
per-service logs before exiting.

## WSL networking diagnosis

This host initially used WSL mirrored networking. The manual Forge invocation
with `KENN_FORGE_HOME`, `serve --host 127.0.0.1 --port 18091 --disable-sync`,
and `TELEMETRY_ENABLED=0` matches the pinned upstream documentation and CLI.
Flags override environment, TOML, and defaults. `/livez` is liveness;
`/healthz` also checks database readiness.

Independent probes reproduced failed IPv4 loopback connectivity both within
WSL and from Windows to WSL, while Windows-native IPv4 and Linux-native IPv6
loopback worked. This narrows the failure below the application layer but
does not identify the responsible network component. See `status.md`.

Do not "fix" mirrored mode by deleting its `loopback0` routes, binding the
application to all interfaces, or disabling firewall/VPN controls. An IPv6
success within Linux does not prove Windows-browser access or repair the
IPv4 endpoints used by the stack. The user restarted WSL without changes;
the failure persisted. The full Windows-home `.wslconfig` was checked against
Microsoft's configuration reference: it already selects mirrored mode and
sets `firewall=false`. No configuration typo explaining the failure was found.
Further diagnosis needs elevated Windows log access or IT-assisted WFP/HNS
tracing; the current session cannot read the existing Windows firewall log.
With explicit user approval, only `networkingMode` was changed to `nat`,
preserving a backup of the original Windows-home `.wslconfig`. After restart,
NAT restored connectivity: the full preview passed and Windows could reach
all four dashboards on localhost. This establishes a working NAT alternative,
not the underlying mirrored-mode defect. NAT is retained for the user's
preview; no further system settings were changed.

# Source references

- `roborev/Makefile`, `roborev/docs/configuration.md`
- `forge/Makefile`, `forge/docs/configuration.md`, `forge/docs/integrations.md`
- `kata/Makefile`, `kata/docs/reference/configuration.md`
- `agentsview/Makefile`, `agentsview/docs/configuration.md`
- `superpowers/README.md`, `superpowers/package.json`
