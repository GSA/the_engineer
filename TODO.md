# TODO history

Kata project **`engi-platform`** is authoritative for current work. Use native
`kata list`, `kata ready`, or http://127.0.0.1:17777/kata. The generated open-task
index and its refresh requirement were retired during native CLI cleanup.
Historical completed entries below are preserved; this file is not a live ledger.

## Completed before Kata adoption

The entries below are historical Markdown records, not newly asserted Kata
closes. Current state and supporting evidence are in `context/status.md`.

### Engi Platform: next unblocked work

- [x] Check live boot-service health after the 2026-10-12 WSL boot. Forge/roborev/AgentsView are enabled, running and responsive; Kata is stopped/on-demand. Private Pi 1.0.3, all 15 Superpowers skills and Falcon MCP connectivity are verified. See `context/status.md`.
- [x] Remove Pi 0.87.1's managed release, installer metadata and launcher; preserve global settings/credentials/sessions/helpers and pinned 1.0.3. Normal `pi` now links to 1.0.3; private version/MCP checks pass.
- [x] Repair stale supervisor metadata handling after reboot: status reports independent services/stopped Kata with an explicit stale-record warning; missing-metadata stop signals nothing, errors/PID-reuse protections remain intact. 66 tests and real start/status/stop recovery pass; independent service PIDs unchanged.
- [x] Map Forge's actual review/workspace controls versus engineering phases and write an initial role/phase proposal in `context/engineering-workflow.md`. This is not an enabled automatic pipeline.
- [x] Review the owner-supplied [Kent Beck 2025 article](https://newsletter.kentbeck.com/p/augmented-coding-beyond-the-vibes) as potentially dated advice; record retain/adapt choices in `context/engineering-workflow.md`, not a wholesale prompt import.
- [x] Investigate Moshi, Spokenly, cmux, Ghostty, Ghosthub and Ouijit using official sources; record platform constraints, overlap and handling considerations in `context/tools.md`.
- [x] Investigate Herdr's layer/platform/integration fit using official sources. It is an agent-aware terminal/runtime with Pi/Copilot support, not a task tracker or provider review console; findings/comparison are in `context/tools.md`.

GitHub CLI installation/authentication work is deferred per the owner's 13:10
direction while the approved GSA operating path is unresolved.

SPUD output work belongs to the falcon-docs agent per the owner's 12:46
direction; it is not an active Engi Platform task.

### Persistent local use and first demo

- [x] Locate the existing project and context MCP server in `~/falcon-docs`; confirm the installed server and existing index pass preflight without refresh.
- [x] Confirm the user-installed Pi 1.0.3 has native MCP commands and still discovers Superpowers skills.
- [x] Restore usable loopback connectivity with the user-approved NAT configuration; rerun isolated stack startup successfully.
- [x] Add repeatable, loopback-only start/stop commands with persistent private state for ongoing local use; keep `scripts/smoke.py` disposable and credential-free.
- [x] Register `~/falcon-docs` in Forge's local project API and preserve its ID/settings across restarts. This does not populate the provider-backed Repos/Workspaces UI. Preserve its checkout and ignored authoritative stores; do not publish or run editing agents without explicit scope.
- [x] Confirm local GSA asset download/use permission. Owner confirmed on 2026-10-12 for code, documents and sensitive information, preferably cleaned of PII, and reconfirmed workstation approval at 13:11. This does not authorize alternate model routing, credential transfer or prohibited VDI exports.
- [x] Research Citrix native Windows mapped-drive capability and constraints. Official client/policy docs confirm local drives can appear in VDI with two-way access subject to redirection/fixed-drive/read-only policies; this is not VPN access or evidence of GSA's effective settings. Sources and recommended Windows-to-WSL handoff are in `context/tools.md`.
- [x] Connect the isolated Pi 1.0.3 profile to Falcon's existing stdio server; verify a real qualified read from a Forge-launched process and after restart, without model calls.
- [x] Add a hidden terminal prompt/private `0600` credential file for USAi handoff and a Pi launcher that fails explicitly without the configured USAi model/key.
- [x] Obtain the USAi endpoint/current model alias, receive the private key, record approval for sensitive local/USAi use including PII, and verify Chat Completions streaming/tool protocol for the selected model.
- [x] Add root README instructions for persistent setup/run/stop, local access, projects, MCP, key handoff, model discovery and provider configuration.
- [x] Refresh the advertised USAi catalog into private local metadata; preserve the existing selected model and do not infer chat capability from model listing.
- [x] Configure the verified USAi model in the isolated Pi profile used by Forge's launcher and verify a real synthetic Pi read-tool round trip.
- [x] Extend `set-key` to cover normal/global and Forge Pi through one private file; replace existing global USAi credential values with shared-reader command references, preserve settings/session separation and verify both CLI providers plus the private launcher. Owner approved the simple manual handoff at 15:56; restart existing Pi sessions after rotation.
- [x] Install the pinned Pi JSON-schema extension in the isolated profile and complete a bounded USAi-backed roborev review without Forge. On 2026-10-09, synthetic fixture job 1 stored schema-version-2 findings and identified the seeded pricing regression; no real-project hooks or fixes were enabled.
- [x] Add and verify the workspace-bound `scripts/roborev-local.py` CLI/hook launcher selecting private state and the systemd-owned API. Generated hooks, existing-hook preservation, minimal environment and external-hook automatic-repair protection passed in a disposable fixture; no real-project hooks installed.

### Extend and integrate

- [x] Configure explicit Copilot, global Pi and private Pi session sources in AgentsView; import existing history with a usage-only archive and preserve original transcripts. Verified 42 Copilot/12 Pi sessions, historical Copilot per-request usage, automatic current Copilot event updates and a saved USAi Pi session with exactly 490 tracked tokens.
- [x] Enable loopback AgentsView through a repeatable user-systemd service for WSL startup; verify restart/archive persistence and ownership independent of the on-demand stack.
- [x] Enable roborev's loopback daemon/UI at WSL startup alongside AgentsView, with its pinned Node runtime and persistent data; preserve Pi/USAi configuration and independent supervisor ownership. At that migration Forge/Kata stayed on-demand; Forge has since moved to its own unit below. No automatic reviews/hooks were added.
- [x] Enable loopback Forge at WSL startup under its own user unit, preserve project/config identities, pin Node for Pi, and keep Kata-only supervision independent. Verified service reinstall, restart and separate stop/start; installed checksum-pinned local GitHub CLI with a private credential profile, not authentication or provider sync.
- [x] Confirm AgentsView/roborev/Forge startup after a real WSL boot. On 2026-10-12, instance booted at 12:38:31 and all three enabled units entered active/running at 12:38:33; runtime/PID/database/UI checks passed. Kata remains intentionally on-demand; stale supervisor status handling is a separate open defect.
- [x] Run a repository-free Kata evaluation with synthetic tasks: dependency ordering, simultaneous claim conflict, human attention/inbox acknowledgment, completion guards, event cursor, lexical search, create retry and restart persistence passed. Scoped stdio MCP and live Forge daemon/task reads work. Data retained; test processes stopped.
