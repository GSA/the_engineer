# Upstream components

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

# Real-business demo selection: 2026-10-19

Owner-reported options now include directly accessible FCP GitHub repositories/
SPUD outputs and Falcon WorkSpace access/existing corpus. Exact repositories,
ticket, build/test prerequisites and approved transfer or in-WorkSpace tool
execution remain unverified. A private GSA-organization GitHub.com mirror and
Google Drive ZIP are colleague-reported possibilities, not approved routes.
WorkSpace access may allow in-boundary execution without source export; it
does not establish approved tool installation or runtime readiness.

Recommendation, not selected architecture: choose the first runnable bounded
ticket with sufficient qualified context. Falcon has the corpus head start;
FCP can use a ticket-sized corpus rather than a full documentation rebuild.
A future Librarian template should carry generic tooling/instructions only,
not Falcon facts, Git history, intake records, source IDs, stores or sessions.
Do not regenerate/publish Confluence/Drive documents merely to prepare a demo.

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

`run` is now only a fallback for profiles without all units. An empty-child
supervisor still writes/removes its own runtime/shutdown metadata so `stop`
cannot hang or interfere with independent services. `status` exposes
`kata_service`; its legacy `stack` field describes the optional supervisor,
not availability of independently running dashboards.

`status` can read Forge's projects even with the supervisor stopped. Forge's unit pins Node and
uses the saved binary/config with provider sync disabled. `managed_forge`
validates systemd MainPID, owned runtime metadata/data/config identity,
database health/version/revision and HTML readiness. Native runtime JSON is
0644 inside a 0700 data directory; its reader rejects symlinks and writable-by-
others files rather than assuming this non-secret metadata must be 0600.
Startup readiness retries an unpublished runtime record, but identity/mode
conflicts fail explicitly.

`install-forge-service`/`forge-run --node-executable` reuse the shared user-unit
installer and Node environment. Installer repeatability, independent supervisor
stop, Forge restart and project/config preservation were verified. No credential
variable is present in the Forge daemon environment. GitHub CLI credentials
remain in the shared private `.local/environment/gh/` profile; it is currently
unauthenticated. Host/repository selection and explicit provider-sync enablement
remain owner-scoped next steps. README owns login instructions and unit commands.
The owner subsequently identified the Helix host `github.helix.gsa.gov` and
raised the outside-VPC boundary. CLI `--hostname` uses the bare host, not its
HTTPS URL. No Helix connectivity/authentication request has been performed.
Workstation approval is confirmed, including the owner's 2026-10-12 13:11
reconfirmation; the remaining prerequisite is approved network connectivity,
not another local-handling approval. The VDI export prohibition remains in force.

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
Provider synchronization remains disabled; scoped AgentsView ingestion is enabled.
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
