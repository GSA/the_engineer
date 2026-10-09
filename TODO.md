# TODO

## Persistent local use and first demo

- [x] Locate the existing project and context MCP server in `~/falcon-docs`; confirm the installed server and existing index pass preflight without refresh.
- [x] Confirm the user-installed Pi 1.0.3 has native MCP commands and still discovers Superpowers skills.
- [x] Restore usable loopback connectivity with the user-approved NAT configuration; rerun isolated stack startup successfully.
- [x] Add repeatable, loopback-only start/stop commands with persistent private state for ongoing local use; keep `scripts/smoke.py` disposable and credential-free.
- [x] Register `~/falcon-docs` in Forge's local project API and preserve its ID/settings across restarts. This does not populate the provider-backed Repos/Workspaces UI. Preserve its checkout and ignored authoritative stores; do not publish or run editing agents without explicit scope.
- [ ] Wait for GSA GitHub access and connect an approved real provider/repository to unblock the Forge UI demo. Owner chose this path on 2026-10-08 at 13:55; local-project UI changes are deferred. Do not fabricate provider identities/remotes or publish Falcon as a workaround.
- [x] Connect the isolated Pi 1.0.3 profile to Falcon's existing stdio server; verify a real qualified read from a Forge-launched process and after restart, without model calls.
- [x] Add a hidden terminal prompt/private `0600` credential file for USAi handoff and a Pi launcher that fails explicitly without the configured USAi model/key.
- [x] Obtain the USAi endpoint/current model alias, receive the private key, record approval for sensitive local/USAi use including PII, and verify Chat Completions streaming/tool protocol for the selected model.
- [x] Add root README instructions for persistent setup/run/stop, local access, projects, MCP, key handoff, model discovery and provider configuration.
- [x] Refresh the advertised USAi catalog into private local metadata; preserve the existing selected model and do not infer chat capability from model listing.
- [ ] Verify MCP-backed behavior after real model compaction; local-only checks cannot establish it.
- [ ] Pin/install Pi in bootstrap for fresh-host reproducibility; the local launcher currently validates the user-installed exact 1.0.3 executable.
- [x] Configure the verified USAi model in the isolated Pi profile used by Forge's launcher and verify a real synthetic Pi read-tool round trip.
- [x] Extend `set-key` to cover normal/global and Forge Pi through one private file; replace existing global USAi credential values with shared-reader command references, preserve settings/session separation and verify both CLI providers plus the private launcher. Owner approved the simple manual handoff at 15:56; restart existing Pi sessions after rotation.
- [ ] When supported, investigate an approved USAi renewal API/CLI. Owner chose manual console issuance and shared `set-key` for now, without a reminder service or private request-time-reload machinery; do not assume LiteLLM key-generation access or automate GSAuth/MFA.
- [ ] After agreeing the editor path, add a thin home-accessible Zed launcher reusing shared Pi auth checks and manual key handoff; keep Zed/Copilot usable without a USAi key and avoid duplicate service startup. Prefer existing CLI Terminal Threads initially, or verify a pinned Pi ACP adapter with Pi 1.0.3, Falcon MCP and durable AgentsView-readable sessions before configuring external agents.
- [ ] After resolving the UI/access-path decision, verify a model-selected Falcon MCP answer in the actual Forge Pi session; API/standalone synthetic tool checks do not establish it.
- [x] Install the pinned Pi JSON-schema extension in the isolated profile and complete a bounded USAi-backed roborev review without Forge. On 2026-10-09, synthetic fixture job 1 stored schema-version-2 findings and identified the seeded pricing regression; no real-project hooks or fixes were enabled.
- [ ] Exercise a bounded real-project demo change with human-agreed acceptance criteria and review; the synthetic review fixture does not establish an application coding/demo workflow.
- [x] Add and verify the workspace-bound `scripts/roborev-local.py` CLI/hook launcher selecting private state and the systemd-owned API. Generated hooks, existing-hook preservation, minimal environment and external-hook automatic-repair protection passed in a disposable fixture; no real-project hooks installed.
- [ ] Agree per-repository `.roborev.toml` review/acceptance guidance and exclusions, then enable automatic reviews together with the owner. Preserve/chain existing hooks, use `init --no-daemon --binary <absolute scoped launcher>`, and approve a user-managed per-repo hooks path outside Git metadata: native startup/update repair otherwise replaces the scoped executable inside `.git/hooks`.

## Extend and integrate

- [x] Configure explicit Copilot, global Pi and private Pi session sources in AgentsView; import existing history with a usage-only archive and preserve original transcripts. Verified 42 Copilot/12 Pi sessions, historical Copilot per-request usage, automatic current Copilot event updates and a saved USAi Pi session with exactly 490 tracked tokens.
- [x] Enable loopback AgentsView through a repeatable user-systemd service for WSL startup; verify restart/archive persistence and ownership independent of the on-demand stack.
- [x] Enable roborev's loopback daemon/UI at WSL startup alongside AgentsView, with its pinned Node runtime and persistent data; preserve Pi/USAi configuration and independent supervisor ownership. Forge/Kata remain on-demand pending GitHub access. No automatic reviews/hooks were added.
- [ ] Confirm AgentsView/roborev startup after a real WSL shutdown/reboot when active sessions can safely be interrupted; service enablement, existing lingering and restart are verified.
- [ ] Establish ongoing AgentsView retention and an approved USAi alias-pricing source; missing client metrics/unpriced models must not be represented as zero usage/free inference. Verify ACP/subagent coverage when those client paths are introduced.
- [ ] Decide how to account for roborev's structured Pi review usage alongside AgentsView: the pinned adapter uses `--no-session`, so native Pi discovery will not archive those jobs. Verify actual review telemetry before adding a metadata-only bridge; never synthesize usage.
- [ ] Verify Forge-to-roborev/Kata integration; if Kata is retained, establish daemon discovery and repository mappings for the intended project.
- [ ] Decide whether to retain Kata or use a simpler task database.
- [ ] Adapt the Kenn workflow and Clanker Constitution into agreed project practices.
- [ ] After GSA GitHub access is available, connect an approved existing application repository and verify scoped read access before enabling writes.
- [ ] Define a one-ticket Jira import path with ticket key/URL, original acceptance criteria and provenance; start with an owner-supplied export or approved read-only API. Do not assume Forge/Kata GitHub issue support is Jira import.
- [ ] Exercise the human-reviewed Jira-ticket-to-GitHub-PR workflow, retaining ticket/PR traceability and explicit publication/merge approval.
- [ ] Establish the approved context-contribution/update path; this repository's `context/` files are not automatically ingested into Falcon.

## Maintenance and longer term

- [ ] Decide retention/retirement of older `.local/smoke-*`, `.local/forge-manual/` and `.local/smoke/` profiles before deleting their state/auth/diagnostic evidence. The 2026-10-09 cleanup removed only proven disposable bytecode; retained runs are listed in `context/tools.md`.
- [ ] Establish backup/recovery for `.local/environment/` settings, databases and Pi sessions before relying on them for important work; ignored persistent state is not a backup.
- [ ] Resolve the last-confirmed Zscaler archive blocks with IT (URLs in `context/status.md`) and retry the normal frozen Forge build. This is not a first-demo blocker while the explicit local-source variant works.
- [ ] Remove the temporary `forge-local-kata` build target, helper/tests, and `.local/forge-local-kata/` artifacts once the normal frozen `./scripts/build.sh forge` build and its smoke check pass. Remove workaround documentation and return to the default Forge binary; retain the upstream pins.
- [ ] If mirrored WSL networking is needed later, investigate its unresolved loopback defect with IT; NAT currently works. Do not alter VPN routes to bypass policy.
- [ ] Longer term, after GSA AOS provides AWS: plan private hosting for Falcon Context and the engineering tools, CGI/GSA VPN access, and approved Jira/GitHub connections.
- [ ] Longer term: investigate agent sandboxing, including filesystem/worktree access, network access, credentials, MCP subprocesses, and resource limits. Evaluate [PiPod](https://pipod.dev/), [Abyss](https://abyss.scurry.io/), and [smolvm](https://github.com/smol-machines/smolvm), as requested on 2026-10-09; no solution selected or installed.
