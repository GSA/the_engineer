# Objective and decisions

Build a local-first Linux agentic engineering environment inspired by
https://wesmckinney.com/blog/agentic-engineering-aug-2026/.
The broader objective is to turn Jira tickets into reviewed GitHub pull
requests using parallel, human-directed agents with shared context, durable
task tracking, continuous review, and session visibility. Prioritize roborev,
Superpowers, Kenn Forge, task tracking, AgentsView, and Falcon Context.

Current decisions, incorporating the user's 2026-10-04 clarification:

- Linux is the target. Exclude Ghosthub and all macOS-only tools.
- Begin locally. Later cloud deployment is for private/internal use, not a
  customer-facing hosted service. The intended users and agents must be able
  to connect while on the CGI or GSA VPNs. This refines the earlier generic
  Tailscale/private-VPC assumption; Tailscale is not a selected requirement.
  Default local listeners to loopback. The actual cloud network path and
  authentication/authorization design remain undecided.
- Use a parent integration repository and exact-commit Git submodules.
  Keep our scripts and non-secret configuration separate from upstream source.
- Pi is the default local agent, but shared context must not be Pi-specific.
  The user is aware of native MCP support in Pi 1.x; the work is integration
  with the intended server, not deciding whether Pi can support MCP.
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
- Evaluate Kata before deciding whether a simpler database-backed task tracker
  is sufficient.
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
next boot service while GSA GitHub access/Forge configuration waits. roborev
now has an independent enabled user unit as well. Forge/Kata stay on-demand;
their supervisor must not duplicate or stop either independently owned service.
Boot availability does not mean opening a browser window or starting all
tools. Actual WSL reboot verification remains pending a safe interruption.
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
