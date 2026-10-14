# Objective and decisions

The owner selected `engi-platform` as this integration project's target name
on 2026-10-12 at 12:46. README branding now reflects it. Checkout paths,
private-state paths, stored executable references and service identifiers
remain unchanged pending a deliberate migration. Reproducible scripted setup
is a goal; existing bootstrap/setup scripts are a partial implementation,
not proof of fresh-host reproducibility.

Build a local-first Linux agentic engineering environment inspired by
https://wesmckinney.com/blog/agentic-engineering-aug-2026/.
The broader objective is to turn Jira tickets into reviewed GitHub pull
requests using parallel, human-directed agents with shared context, durable
task tracking, continuous review, and session visibility. Prioritize roborev,
Superpowers, Kenn Forge, task tracking, AgentsView, and Falcon Context.

Current decisions, incorporating the user's 2026-10-04 clarification:

- On 2026-10-14 at 14:25 the owner authorizes beginning an installer under
  `dist/`, including source acquisition, missing-tool/library reporting and
  manual startup guidance or optional Ubuntu service registration. The initial
  recipe reuses existing Linux x86_64 builds and private local configuration;
  user services require explicit consent and no sudo/lingering/global profile
  changes are automatic. Approved local Librarian and Pi remain detected
  prerequisites, not bundled confidential assets. Fresh-host acceptance and
  automatic Pi provisioning remain outstanding; cloud deployment is unchanged.
- On 2026-10-14 at 14:16 the owner requires the engineering platform to be
  redistributable to other engineers on the project. A repeatable setup for
  other engineers is a first-version requirement, not merely recovery of this
  workstation. Cloud deployment of the tools is a stretch goal, not a
  prerequisite. Track portable setup under existing `p4ke`/`5xrm` and cloud
  planning under `jmga`; packaging format, target engineer environments and
  shared versus per-engineer service/state topology remain undecided.
  Distribute tools, attributed prompts and non-secret configuration, not this
  user's credentials, sessions, databases or confidential Falcon corpus.
  No publication, deployment or new network exposure is authorized.
- On 2026-10-13 at 15:57 and 16:07 the owner clarifies that the Falcon demo
  should use real product specifications from the actual Librarian, not
  synthetic context or a demo interface to the Librarian itself. The owner
  favors waiting for AWS access because specification-derived code and task/
  review text may disclose confidential information on GitHub. No new
  repository, GitHub login/sync, push or demo implementation is authorized.
  AWS access alone does not approve a repository destination or establish
  Helix connectivity; confirm the execution, source-storage and data-handling
  boundaries before proceeding. Existing local/USAi approvals remain intact.
- On 2026-10-13 at 11:07 the owner confirms Superpowers as a staple, agrees
  with complementary sources and bounded prompt implementation, and requires
  a clear decomposition path plus deliberate role-profile loading/isolation.
  Keep runtime prompts concise to limit recurring token overhead. Ask all
  outstanding questions and verify assumptions before implementation; exact
  skill adaptation, approval gates, isolation and loading scope remain open.
  At 11:17 the owner clarifies that the objective is full use of Forge with
  Superpowers, not wholesale implementation of every Superpowers workflow or
  a new orchestration system. Prefer existing Forge extension/configuration
  surfaces over recoding it. Copilot and global Pi are out of prompt scope.
  Ask-before-assuming applies to designing these prompts; subsequent agents
  should execute approved steps continuously and escalate consequential scope,
  architecture, authority or cost uncertainty. The owner expects Forge to
  break work into Kata tasks and dispatch implementors; verified source shows
  that decomposition belongs to a human/agent, not a Forge planning engine.
  First-version coordinator/worker topology is not yet agreed. Server use and
  worktrees do not establish OS sandboxing or broader publication permission.
  At 11:29 the owner favors manually decomposing the first Jira tickets into
  Kata tasks, learning the process before a later intake/refinement service.
  Librarian/Falcon MCP access is required for engineering agents. A refinement
  agent is optional for the first demo; the owner proposes retaining an inactive
  Constitution-based sample for future use. Exact draft authority (propose
  tasks versus create them) and its first-version inclusion remain open; no
  Jira service, worker scheduler or live coordinator is authorized by this
  discussion.
  At 11:36 the owner approves saving the unchanged Constitution with their
  exact draft-only Jira refinement overlay as an inactive example and
  committing existing work. The overlay proposes tasks for human approval;
  it cannot modify/add requirements, edit source, write task records, launch
  workers or publish. Saved in `context/prompt-drafts/jira-refinement.example.md`;
  this does not install a coordinator or authorize automated intake.
  At 11:38 the owner asks which existing Kata tasks can be cleaned up.
  The live 32-task audit identifies overlapping workflow/prompt work and stale
  scopes, not completed platform integration. Consolidation/scope changes are
  recommendations pending approval; no task was closed or rewritten.
  At 11:46 the owner approves that cleanup, including non-completion closure
  reasons where appropriate. `v3sd` is now superseded by `k03a`; five surviving
  task scopes are updated with imported text preserved. Current work is
  Forge/private-Pi/Superpowers/Librarian integration, manual Jira intake, Pi
  lifecycle/resume, the remaining Zed GUI check and cloud/application recovery.
  No unfinished integration was marked done. The ledger now has 31 open tasks;
  other deferred/blocked work remains open rather than being assumed abandoned.
- Linux is the target. Exclude Ghosthub and all macOS-only tools.
- Begin locally. Later cloud deployment is for private/internal use, not a
  customer-facing hosted service. The intended users and agents must be able
  to connect while on the CGI or GSA VPNs. This refines the earlier generic
  Tailscale/private-VPC assumption; Tailscale is not a selected requirement.
  Default local listeners to loopback. The actual cloud network path and
  authentication/authorization design remain undecided.
- On 2026-10-09 at 15:26 the owner identified GitHub Enterprise at
  `https://github.helix.gsa.gov` and noted this WSL environment is outside the
  GSA VPC. Pause Helix login/repository import until the approved network path
  and permission to handle GSA source/credentials on this host are confirmed.
  VPN reachability and authorization are separate; do not infer a requirement
  or approval from account access or bypass network controls. An approved
  local/VPN path or GSA-managed execution host remains to be decided.
- On 2026-10-12 the owner confirmed clearance to download and use GSA assets
  on this machine, including documents, code and sensitive information,
  preferably cleaned of PII. This resolves the previously open local asset-
  handling permission, not VPN/device eligibility or credential-transfer
  policy. No VPN access is currently available. Admin AWS WorkSpace/VDI tickets
  are pending; the owner plans to boot a standard Citrix VDI and is considering
  an approved export/local-edit/return workflow. No transfer has been performed
  or route selected. Recommend a scoped source snapshot with an exact baseline
  commit and a reviewed patch returned to the original checkout, rather than
  overwriting a repository with a modified ZIP. USAi-only sensitive model
  routing remains in force; local clearance does not authorize other inference
  services. "Librarian" for context and "Engineer" for the engineering platform
  are proposed names only; no implementation rename is authorized.
  At 10:59 the owner reported Citrix mapped-drive functionality and is
  downloading the native client. Citrix documentation confirms client drives
  can appear inside the VDI, subject to administrator redirection/read-only
  policies. Recommend an unsynced Windows transfer folder accessible from
  WSL, with source snapshots/patches copied between separate working trees.
  GSA's effective policy and a bidirectional transfer remain unverified;
  drive mapping does not grant this host direct Helix/network access.
- At 11:43 on 2026-10-12 the owner confirmed that outbound VDI file transfer
  is not allowed and assets must be read through the VDI. This supersedes the
  proposed mapped-drive export/local-edit/return path: treat it as blocked by
  policy, not a technical fault to circumvent. Do not substitute clipboard,
  screenshots/OCR, transcription, email or tunnels as an export workaround.
  Local asset clearance does not override this channel restriction. Approved
  engineering/model tools inside standard VDI remain a possibility to check,
  not permission to install or deploy. Admin WorkSpace/VDI access is pending.
  The owner also identified SPUD output documents as potential work; their
  location, handling permissions and desired deliverable remain unspecified.
  Document development inside VDI or on separately approved local copies
  could proceed without source import. No SPUD content has been accessed.
- At 13:11 on 2026-10-12 the owner reconfirmed that this workstation is
  approved. Local workstation/asset handling approval is settled; do not ask
  for it again. Helix connectivity remains unresolved with VPN access last
  reported unavailable. This confirmation does not change the separate VDI
  export restriction, USAi routing or publication boundaries.
- At 12:46 on 2026-10-12 the owner assigned SPUD output work to the falcon-docs
  agent, not this platform task. Keep the Falcon checkout/corpus untouched.
  Focus here on service readiness, unblocked backlog, engineering prompts and
  Forge's actual workflow controls. Investigate Moshi, Spokenly (personal use),
  cmux/Ghostty/Wes's terminal and Ouijit without installing new products or
  changing model routing during this research. The exact Kent Beck TDD prompt
  link is still needed before claiming to adapt that source. The phrase
  "github apt" needs clarification: `gh` is already installed locally; an apt
  migration or a GitHub App configuration are different consequential tasks.
- At 13:10 on 2026-10-12 the owner requested complete removal of Pi 0.87.1
  and repair of stale-supervisor handling before active prompt work. The legacy
  managed release/installer launcher is now removed; the normal `pi` symlink
  and private launcher both resolve preserved 1.0.3. Shared global settings,
  credentials, sessions and helper binaries were retained.
  Moshi, cmux and Ghosthub are dropped from active evaluation. Evaluate Ouijit
  against Forge/Kata and consider Herdr as a terminal/runtime layer; no new
  runtime is selected or installed. GitHub CLI setup is deferred while the GSA
  operating path is unresolved.
  The owner supplied [Kent Beck's 2025 augmented-coding article](https://newsletter.kentbeck.com/p/augmented-coding-beyond-the-vibes):
  treat its prompt as potentially dated advice, not a replacement contract.
  The requested host OneDrive backup needs explicit content/destination scope;
  the detected account is CGI Federal. Recommend versioned source/history/
  uncommitted-work snapshots, not live checkout or private-state sync. Nothing
  has been uploaded.
- Use a parent integration repository and exact-commit Git submodules.
  Keep our scripts and non-secret configuration separate from upstream source.
- Pi is the default local agent, but shared context must not be Pi-specific.
  The user is aware of native MCP support in Pi 1.x; the work is integration
  with the intended server, not deciding whether Pi can support MCP.
- At 13:01 on 2026-10-12 the owner accepted automatic project trust as a
  platform assumption: projects are generally known, not arbitrary downloads.
  Do not treat per-project trust prompts as a required platform gate. This
  does not change model/data-routing, credential, network or publication/merge
  boundaries. Richard Gill's ideas were initially a standalone backlog task,
  not a wholesale adoption of his setup; no runtime trust configuration was
  changed here. At 23:12 the owner removed that standalone tool-research item
  and assigned its review to the agent dedicated to platform prompts (`k03a`).
  Task `0s6v` is superseded by that work; no Gill extension was installed.
- USAi LiteLLM is the required model interface, clarified on 2026-10-08.
  The owner supplied the private key and approved USAi/local use for sensitive
  information, including PII, on 2026-10-08. Prompting users should
  minimize unnecessary PII. The existing saved USAi endpoint/model were located;
  Chat Completions streaming and a synthetic tool round trip were verified,
  and the isolated Pi provider was configured. Approval is no longer a local
  model-use blocker.
- The owner's standalone global Pi profile is separate from that isolated
  provider. Diagnosis on 2026-10-08 found its USAi helper reading a different,
  service-rejected key from global `models.json` (HTTP 401). The private
  launcher still works. At 15:56 the owner approved the simple shared-key
  approach: `set-key` now updates the private token once and links existing
  global USAi providers to that file without copying the token into config.
  Other settings, MCP configuration and sessions remain separate.
- The owner reports USAi API keys rotate every seven days and suspects expiry
  caused the rejected global key. An approved unattended key-generation or
  renewal interface is not yet established. The owner chose manual issuance
  and one shared `set-key` handoff over more machinery. Restart existing Pi
  sessions after replacement; the private launcher keeps a startup snapshot.
  Automated renewal/reminders and private request-time reload are deferred,
  not implemented or authorization to automate browser SSO.
- At 15:50 the owner expects key generation/handoff to remain manual for now
  and is considering a home-directory launcher for Zed with Pi or Copilot
  agents. Recommended design is a thin editor launcher plus reusable Pi
  credential checks, independent of Forge availability. Zed/ACP integration
  remains proposed; the shared manual key handoff is now implemented.
- At 17:42 on 2026-10-12 the owner selected Kata for this project's existing
  backlog only. Project `engi-platform` is authoritative for open tasks;
  `TODO.md` is a generated index with completed Markdown history retained.
  All 37 open source entries are preserved in 36 imported tasks, combining
  the duplicate Helix-login entries, plus new redeployment task `5xrm`.
  The former tracker-selection task now covers real project-scoped agent
  integration/pilot validation. Falcon's backlog is explicitly out of scope.
  Native `.kata.toml` binding and the private CLI are wired; automatic agent
  hooks/MCP setup are still open work. The owner defers database backups to a
  separate session; do not treat the task index as a backup or start one here.
  See `kata-adoption.md` for operations/provenance and `kata-evaluation.md`
  for the earlier synthetic checks.
- At 17:55 on 2026-10-12 the owner requested a current-state Git commit and
  Kata boot startup alongside the other dashboards. The pre-service snapshot
  is commit `7c6df7d`. Kata now uses independent `kenn-kopy-kata.service`
  ownership with the existing private database and loopback API/UI; the
  optional supervisor must neither duplicate nor stop it. No WSL reboot,
  database backup, Falcon migration, model-route change or new agent hook is
  authorized by this service request. Research recommendations should favor
  existing-stack integration before overlapping new orchestrators.
- At 19:27 on 2026-10-12 the owner requests that completed work be committed
  locally and authorizes a backup including sensitive assets to CGI Federal's
  protected OneDrive under `/mnt/c/Users/NKIRRISH`, excluding reinstallable
  dependency bulk. This supersedes the source-only backup proposal and
  database-backup deferral for this workspace copy. Credentials/private assets
  remain ignored and must never enter Git; no push/publication is authorized.
  Scope is this checkout, its local Git/submodule history, dirty/untracked
  work and private `.local/` assets/state. Falcon/global client profiles,
  external worktrees and host configuration are outside this copy; no VDI
  export is authorized. External/absolute symlinks require an explicit scope
  decision instead of importing assets implicitly.
  `scripts/backup_workspace.py` creates versioned archives with per-database
  online SQLite snapshots and local restore/checksum verification before
  writing to `OneDrive - CGI Federal, Inc/EngiPlatformBackups`. Archives contain
  credentials and sensitive state and are restricted, not Git artifacts.
  Runtime sockets and SQLite sidecars are regenerated rather than copied;
  source/manifests/build recipes are retained despite dependency exclusions.
  Local host copying does not establish cloud sync, retention or application
  recovery, and no automatic schedule is authorized or installed.
- At 19:51 on 2026-10-12 the owner extends the same protected-OneDrive backup
  rules to `~/falcon-docs`. Scope now explicitly includes that separate
  checkout's sensitive raw intake, authoritative stores, provenance,
  retained recovery snapshots/receipts and ignored local files. Its tracked
  work is already clean at `fec05a8`; do not stage raw intake, its ignored
  owner TODO, credentials or historical recovery material into Git.
  This is backup authorization, not corpus editing/SPUD intake, index refresh,
  review-event mutation, publication or backlog migration. Global agent
  profiles/host configuration are not included in the named Falcon request.
  Preserve historical snapshot/receipt bytes, take online copies of the four
  explicit current SQLite stores, exclude reinstallable virtualenvs, and use
  private disk-backed staging outside either checkout for the large corpus.
- At 23:16 on 2026-10-12 the owner requests work on Kata/Pi/Copilot integration
  and more operational/anecdotal evidence for Herdr/Ouijit. Begin with native
  project-scoped MCP and a real task-access pilot, preserving private USAi,
  Falcon and global client settings. Treat terminal products as candidates,
  not selected installations or replacements. Detailed user reports supplement
  vendor documentation; neither proves local WSL behavior or enterprise fit.
  No Herdr/Ouijit install, global profile change, remote exposure or publication
  is authorized by this initial integration/evidence work.
- At 10:07 on 2026-10-13 the owner declines Ouijit and prioritizes a
  minimum-friction Ghosthub substitute, without feature parity or another
  task ledger. Close `jjw1` as wontfix, not a completed trial or a finding that
  Ouijit is insecure. Kata remains the selected tracker; its unverified agent
  lifecycle/recovery work is not waived by this decision. The existing
  Zed/tmux combination is the baseline under `c3ch`: a thin project launcher,
  private standalone tmux socket, native private Pi/USAi and existing Copilot
  state, no global configuration or new terminal runtime. Any WSL terminal
  can attach; Zed's GUI workflow remains an interactive check. Herdr stays
  optional research rather than a dependency. macOS tools may be reconsidered
  on a future Mac, not installed here. Cloud/SSH deployment still needs
  approved connectivity and does not follow from choosing tmux.
- At 10:28 on 2026-10-13 the owner accepts the current local setup and removes
  remaining Herdr tasks. `r27h` is closed wontfix; Herdr and Ouijit are
  excluded from active work, with prior research retained only as history.
  Keep the existing runtime/services unchanged. Engineering policy and prompts
  are the next focus in a separate dedicated agent under `k03a`; this handoff
  does not claim prompt implementation or completion of outstanding integration
  checks.
- Ask questions early rather than assuming. Favor simple code, correctness,
  maintainability, and a useful end product over prose or speed.

Added on 2026-10-04:

- Use a simple root `TODO.md` for the current backlog while task-tracker
  integration is unresolved.
- Investigate agent sandboxing as a longer-term goal. No sandbox technology or
  policy has been selected. Isolating configuration and data for smoke tests
  is not an operating-system sandbox.
  On 2026-10-09 the owner requested tracking PiPod (https://pipod.dev/),
  Abyss (https://abyss.scurry.io/) and smolvm
  (https://github.com/smol-machines/smolvm) as candidates, not installation
  or a technology selection.

# Local use and demo objective: 2026-10-08

The user also wants this environment for ongoing personal use and exploration,
not just a disposable demo. Keep settings, registered projects, task/review
databases and agent sessions persistent locally. Cloud deployment remains a
long-term goal; local use must not depend on it. Pi is the initial default
agent, with Falcon MCP and the required USAi provider.

Get at least one new or existing project usable in the local environment for
a demo, without waiting for GSA GitHub access or AWS. The user identified
`~/falcon-docs` as the existing local project and the home of the context MCP
server. The user upgraded Pi to 1.0.3 for native MCP support.

The persistent local profile now lives in ignored `.local/environment/`.
The existing checkout is registered in Forge's local project API, and its
isolated Pi profile connects to the read-only context server. The configured
USAi provider has completed a synthetic model-backed Pi tool round trip. The 13:42 owner report
revealed that this is not a usable local-project Forge UI workflow: Repos and
workspace creation use the separate provider catalog, which is empty, and
Create Workspace is disabled. Local project intake is available without a
provider at `/project-intake`, but does not populate these screens.

At 13:55 the owner chose to wait for GSA GitHub access, then add a real approved
provider/repository rather than modify the local-project UI. Standalone local
exploration and environment analysis can continue while the Forge UI demo waits.
Do not fabricate a remote/provider identity or publish Falcon to bypass the limitation.
Standalone Pi remains available for local exploration. Model-selected Falcon
context retrieval in an actual Forge session remains a milestone after the
UI/access-path decision. Local project registration does not require GitHub
access; that fact does not establish the main Forge workspace UI is provider-free.
A coding demonstration additionally needs an explicit, bounded change target
and review; registration and retrieval alone do not establish a working
coding/review loop.

The Falcon checkout contains substantial uncommitted/untracked work and
ignored authoritative data. Preserve it. A Git worktree alone would not carry
those files or stores; keep context retrieval pointed at the existing corpus.
Do not turn a demo into permission to edit, publish or copy that corpus.
USAi and the local environment are owner-approved for sensitive information,
including PII; minimize unnecessary personal data in prompts. This does not
authorize publishing the corpus or using alternate providers, and does not
remove source/project handling rules.

Later, after GSA GitHub access is available, connect an approved existing
application repository and import an actual Jira ticket. Start with one
traceable ticket, not a broad synchronization service. AWS, a new context
backend, mirrored-mode repair and removal of the temporary Forge build are
not prerequisites for the first local demonstration.

# Local session visibility and startup: 2026-10-08

Current update, 2026-10-12 at 17:55: all four dashboards have independent boot
units; Kata supersedes its previous on-demand ownership. `run` remains a
foreground fallback for profiles without installed units, not a required
terminal on this host. `stop` affects only a verified optional supervisor.

Earlier update, 2026-10-09 at 15:08: the owner reports GSA GitHub access and
authorized Forge configuration/boot service. Forge now has its own enabled
loopback user unit and retains its settings/database/project IDs. Kata is the
only on-demand child; AgentsView/roborev ownership is unchanged. The local
checksum-pinned GitHub CLI shares an isolated credential profile with Forge,
but it has no login yet. Ask for the approved repository URL/host and require
owner terminal authentication/SSO before connecting it or enabling sync.
Do not treat access granted to an account as authenticated local CLI access,
permission to select all repositories, publish this integration/Falcon, or
launch a coding task. Provider sync remains disabled pending that scope.

At 15:33 the owner authorized Copilot/Pi session tracking, import of existing
local history and AgentsView availability when WSL boots. Configure explicit
sources rather than exposing the clients' whole global configuration or
routing model requests through the archive. This tracking integration changes
neither global client settings nor inference routing; the separately approved
shared USAi credential-source repair is recorded in tool/status context.

The initial archive is usage-only to avoid duplicating transcripts, thinking,
tool payloads and titles. Original client files are preserved. This is an
initial content policy, not a final retention/backup policy. Token visibility
depends on native client records; absent metrics and unpriced USAi aliases
must not be reported as zero consumption or free service.

AgentsView has its own loopback user-systemd service, enabled with the host's
existing systemd/lingering setup. At 17:00 the owner requested roborev as the
next boot service while GSA GitHub access/Forge configuration waited. roborev
gained an independent enabled user unit as well. At that point Forge/Kata stayed
on-demand; the subsequent Forge and Kata migrations now leave all four
independently owned.
The supervisor must not duplicate or stop independently owned services.
Boot availability does not mean opening a browser window or starting all
tools. The first three units were observed starting at the real 12:38 WSL
boot on 2026-10-12; Kata's later boot enablement has restart/lifecycle evidence,
not a new WSL reboot test.
Generated insights, cloud/archive publication and editor/ACP changes are
outside this tracking request.

roborev's boot integration preserves its existing private Pi/USAi configuration
and review databases. The unit records the installed Node executable rather
than relying on shell initialization; the daemon receives no model credential.
Booting the service is not permission to install hooks or queue new reviews.
Model-backed structured review setup remains a separate milestone.

The 17:17 roborev explanation identified two further integration boundaries:
Git hooks must target our private daemon/profile rather than ordinary global
discovery, and structured Pi reviews deliberately use `--no-session`, so
AgentsView's native Pi archive is not complete review-job accounting.
The recommended sequence is a scoped CLI/hook launcher, the pinned schema
extension in the private profile, then an approved manual review before
automatic commit hooks. This is a recommendation/backlog, not permission to
install hooks, enable agent-directed fixes or edit the Falcon checkout.

On 2026-10-09 the owner authorized the isolated schema installation, one bounded
manual review and implementation of the scoped CLI/hook launcher. These are
now verified without Forge: job 1 reviewed a tiny private synthetic regression
repository through Pi/USAi and persisted schema-validated findings identifying
the intended bug. The fixture is retained locally and unpublished. No real
project was edited, hooked or auto-fixed; the application demo remains open.
Per-project review guidance and automatic hooks are deferred for joint setup.

The scoped launcher pins this workspace's state and managed API and preserves
the caller's cwd/stdin. Native startup/update repair would replace its path in
hooks inside Git metadata. A user-managed per-repo hooks directory outside
that metadata preserves the launcher; this was verified only in a disposable
fixture. Agree its layout and preserve existing hooks before any real migration.
Normal review-mode tool restrictions are not an OS sandbox. Structured review
token accounting alongside AgentsView is still unverified/unavailable.

# Shared context: Falcon Context

The intended context MCP server is the Falcon Context server available in this
Copilot session, not a generic filesystem server or the repository's
`context/` directory. The long-term goal is to host its database and server in
the cloud and make the same context available to any authorized, compatible
agent connected through the CGI or GSA VPNs.

Keep the context interface agent-independent. The local server is now located:
`~/falcon-docs/tools/context-mcp/`, using stdio and its existing selected index.
Its documented maintenance path is local, explicit and separate from reads;
publishing this integration project's context still needs an approved route.
Cloud transport, deployment, database ownership and access controls remain
undecided. VPN connectivity is a network-access requirement, not a replacement
for application-level authorization.

The repository's context files remain the durable project/handoff record for
now. They are not automatically ingested into Falcon. The Falcon tools exposed
in this session are read-only; writing these files does not publish them to the
Falcon database.

# Engineering workflow

The 2026-10-12 source investigation and initial role/phase proposal live in
`context/engineering-workflow.md`. Forge's local review statuses and agent
runtime states are not an enforced design-to-TDD pipeline. No new prompts,
quick actions, hooks or automatic publication were enabled by that investigation.

Use the Kenn team's process as a reference: tools and agents can run in
parallel, but humans own intent, design decisions, review, and merge approval.
Their reported success motivates this project; it does not establish that our
integration has the same quality or throughput.

The intended workflow is:

1. Bring in a Jira ticket and relevant shared context; clarify requirements
   and acceptance criteria with a human.
2. Develop and review the design/specification, then track bounded work.
3. Implement in isolated workspaces, with parallel agents where useful.
4. Validate behavior and resolve roborev findings; retain session and usage
   visibility through AgentsView.
5. Open a traceable GitHub PR linked to the originating Jira ticket, with
   human review and explicit merge authorization.

Use Superpowers and the
[Clanker Constitution](https://github.com/kenn-io/constitution) as references
for disciplined agent behavior, alongside our own agreed working rules.
Evaluate and adapt those principles explicitly rather than silently importing
all upstream instructions. The reference process is human-led, not a fully
autonomous ticket-to-merge loop. Falcon Context is our additional shared-context
component; the blog does not establish that Kenn uses an equivalent server.

The Constitution is a reference, not a formally imported/pinned instruction
file in this workspace. Root `AGENTS.md` contains our short working agreements;
the private Pi profile loads Superpowers, not the Constitution. The upstream
v2026.08.11 text was reviewed on 2026-10-08. Business-specific additions are
proposals: USAi-only model routing/secret handling, source-qualified Falcon
evidence, Jira acceptance-criteria provenance, explicit human publication/merge
authority, and end-to-end milestone/archiving controls. They were not silently
adopted or added to `AGENTS.md`.

# Long-term AWS hosting

AWS is the confirmed eventual cloud platform. The owner specified GSA-owned
infrastructure in a GSA VPC and anticipates it being suitable for sensitive
information. GSA AOS has not yet provided the environment, so cloud hosting
is a longer-term objective, not a current deployment task. This is destination
and handling direction, not evidence that cloud access controls/networking
have been implemented or validated. Continue making the approved local
environment useful without provisioning resources elsewhere.

Eventually host Falcon Context and the applicable engineering tools/runtimes
in that environment, with approved connections to Jira and GitHub. No AWS
services, database topology, deployment orchestrator, or VPN routing design
have been selected. Once the environment and constraints are available,
investigate networking, identities and permissions, credential management,
data retention/backups, and agent sandboxing before deploying.

# Reproducibility

`./scripts/bootstrap-sources.sh` restores the submodule revisions recorded in
the parent Git index. After the initial commit is published, a fresh
`git clone --recurse-submodules <repository-url>` also restores those revisions.
The script does not install dependencies, configure agents, or start services.

Never use `git submodule update --remote` in bootstrap or deployment. Upgrades
must explicitly change gitlinks; commit `.gitmodules` changes with their
gitlinks. Preserve upstream histories and licenses.

Pin build/runtime dependencies as they are introduced. Track non-secret
configuration templates and scripts; do not depend on undocumented manual
edits or existing home-directory configuration. Setup must be safe to rerun,
preserve data, and report failures.

The 2026-10-09 owner-requested review/cleanup preserved all integration work and
persistent state, removing only generated bytecode. Older smoke/manual profiles
contain state or retained diagnostic evidence; their retirement needs an
explicit retention decision. Do not equate ignored/private artifacts with
unnecessary files or treat cleanup as permission to discard backups/history.

At 15:00 on 2026-10-09 the owner authorized a local Git snapshot of the recent
integration work. No remote is configured; committing is not publication.
Private runtime data/credentials stay ignored and upstream gitlinks are
unchanged. A code snapshot does not back up the persistent application state.

`.local/` holds ignored workspace-local tools, runtime state, and diagnostic
logs. `.env` files are ignored except secret-free `.env.example` templates.
Submodules have their own ignore rules. Check staged content; ignore rules
alone do not prevent credential leaks.

# Handoff protocol

Keep `status.md` current with completed work, exact reproduction commands,
observed results, remaining blockers, and whether any owned processes remain.
Record durable tool details in `tools.md`. Do not rely on chat history or
agent-private memory. Distinguish a proposal from a decision and a startup
check from working model-backed integration.
