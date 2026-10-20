# Engi Platform: local engineering environment

A persistent Linux environment for personal exploration and a human-directed
engineering demo. It combines Forge, Pi, Superpowers, roborev, Kata and
AgentsView, with the existing Falcon Context MCP server. USAi LiteLLM is the
required model provider. GSA GitHub/Jira integration and cloud deployment are
later work.

The selected project name is **engi-platform**, formerly Kenn Kopy. The checkout
path, private state, scripts and `kenn-kopy-*` service identifiers have not yet
been migrated; existing commands below still use those identifiers.

Current service evidence and blockers are in [context/status.md](context/status.md).
The distinction between Forge controls and our proposed engineering phases is
documented in [context/engineering-workflow.md](context/engineering-workflow.md).

## Standalone agent terminals: Ghosthub replacement

The lowest-friction baseline on this WSL host is **existing Zed plus tmux**.
Zed is the optional editor/terminal frontend; tmux keeps standalone agent
processes alive across detach or a closed terminal. Any WSL terminal works,
so no GUI or new runtime is required. Kata remains the task authority, Forge
retains its own workspaces/tmux, and AgentsView/roborev keep their existing roles.
Ouijit is declined, not installed.

Open this checkout with `zed .`. In a Zed terminal (or **Agent Panel > new
thread > Terminal**, if available in your build), run:

```sh
python3 scripts/terminal-local.py open pi
```

Inside that persistent shell, run `python3 scripts/pi-local.py` for the private
Pi/USAi profile, with its existing Falcon and Kata MCP configuration. In another
terminal/thread, run `python3 scripts/terminal-local.py open copilot`, then
`copilot`. Copilot keeps its existing authentication/session storage; **its
inference is not USAi**, so sensitive model work stays in Pi.

Press **Ctrl+B, then D** to detach; repeat the same `open` command to reattach,
without launching a second agent. **Ctrl+B, then S** selects sessions,
**Ctrl+B, then C** creates a shell window, and **Ctrl+B, then %** splits a pane.
All these shells start in this checkout. Use separate worktrees before having
agents edit overlapping files concurrently; terminals do not provide worktree
isolation or task ownership.

The launcher also works from home using its absolute path:

```sh
python3 ~/kenn-kopy/scripts/terminal-local.py open pi
python3 ~/kenn-kopy/scripts/terminal-local.py list
```

`python3 scripts/terminal-local.py stop pi` **terminates that session and its
processes**, not the other named sessions or dashboards. Stop agents normally
and detach first when work/session files need saving. An absent server/session
is reported as an error rather than silently replaced.

The launcher uses a private Unix socket under ignored
`.local/environment/runtime/terminal/`, separate from Forge's `kenn-kopy-local`
server. It passes no inherited provider tokens to tmux, does not load your
user tmux configuration, and starts Bash without profile/rc files. Normal HOME
and XDG config/data/cache paths preserve native Copilot state; private Pi's
directory stays pinned, but **use `pi-local.py`**, not a bare `pi`, to load the
USAi key only into the agent. Startup requires neither a model key nor Forge
provider access and changes no global editor/client settings.

This is terminal persistence, **not an OS sandbox, automatic agent attention,
or restart recovery**. WSL shutdown/reboot kills the live processes; reopen
tmux and explicitly resume saved native agent sessions afterward. tmux
attach/detach/disconnect behavior is verified here; Zed's GUI/thread workflow
still needs the owner's interactive check. Installed Ghostty is a development
build and is not required; Herdr is excluded from current work, and cmux's macOS app
is not a replacement for this Linux/WSL host.

## Start and access the environment

Run commands from this repository's root. On this host, all four dashboards
start automatically with WSL as independent user-systemd services. No terminal
or browser autostart is required. Check the saved environment:

```sh
python3 scripts/local_env.py status
```

Configuration/databases are retained, and `~/falcon-docs` remains registered
as a local Forge project. If you intentionally stopped services, restore them:

```sh
systemctl --user start kenn-kopy-kata.service kenn-kopy-forge.service \
  kenn-kopy-roborev.service kenn-kopy-agentsview.service
```

Before installing independent services on another host,
`python3 scripts/local_env.py run` remains a foreground fallback. Keep that
terminal open; the supervisor owns only dashboards not installed as services.

| Application | Local browser address |
| --- | --- |
| Forge: repository/workspace console | http://127.0.0.1:18091/ |
| roborev: reviews | http://127.0.0.1:17374/reviews |
| Kata: tasks | http://127.0.0.1:17777/kata |
| AgentsView: sessions and usage | http://127.0.0.1:18080/ |

In this WSL installation, the Windows browser can use these same localhost
addresses with the current NAT configuration. No public listener, tunnel or
cloud access is configured. Forge syncs the four selected private GSA Falcon
mirrors; profiles without configured repositories retain disabled provider sync.
AgentsView now watches explicit Copilot and Pi session sources; it is not a
model router. Dashboard startup alone does not establish a complete
model-backed coding/review workflow.

From another terminal:

```sh
python3 scripts/local_env.py status
python3 scripts/local_env.py stop
```

If a reboot or interrupted supervisor leaves an old runtime record, `status`
reports the stack stopped, warns that stale metadata was retained, and still
checks the independent services. `stop` with no live supervisor signals nothing.
An occupied owner lock/port or reused PID still fails explicitly; do not remove
metadata or signal an old PID to force recovery. A successful new start replaces
the old record, and normal shutdown removes its own record.

Ctrl+C in the running terminal also stops the supervisor. Shutdown retains
settings, projects, databases and Pi session files. Stop unwanted live terminal
sessions through Forge's session controls; they can have independent lifetimes.
**Stopping the supervisor leaves all four independent services running.**
They are enabled at WSL boot; use each service's `systemctl --user stop` command
to stop it deliberately. The `status` field `stack` describes the optional
supervisor, not overall dashboard availability; `stack: stopped` is normal
when all four service entries are healthy. Occupied ports fail startup rather
than replacing another process.

## Kata tasks for Engi Platform

**Kata project `engi-platform` is the source of truth for this project's open
tasks.** `.kata.toml` binds this checkout; the private database stays under
`.local/environment/kata/`. `TODO.md` is a generated open-task index plus
historical completed entries, not a second backlog. Falcon's tasks are unchanged.
The original open TODO descriptions are preserved in task bodies, including
blockers and provenance. The reproducible redeployment recipe is task **`5xrm`**.

Kata runs under **`kenn-kopy-kata.service`**. Open
**http://127.0.0.1:17777/kata** and select `engi-platform`.
The four Falcon repositories also have separate, currently empty Kata
projects named `supply-chain-user-interface`, `national-item-file-maintenance`,
`standard-acquisition-interface` and `infrastructure`. Select the matching
project for application work; each is linked to its corresponding Forge
repository. Existing platform and Librarian projects are preserved.
From this repository root:

```sh
./scripts/kata-local.py list --agent
./scripts/kata-local.py ready --no-label blocked --no-label deferred --agent
./scripts/kata-local.py show 5xrm
python3 scripts/kata_todo.py
```

The launcher pins this project/workspace and the private loopback daemon,
strips inherited credentials and refuses scope overrides. It does not start a
missing daemon or require a USAi key. Use `--as <actor>` for explicit agent
attribution; search before creating tasks, claim before working and close only
after verified completion with a substantive message and typed evidence.
Refresh `TODO.md` after task changes and before handoff; failed reads leave the
existing index untouched. Detailed decisions/evidence stay in `context/`.

Kata does not launch agents or independently execute close-evidence tests.
Project-scoped MCP access is now configured for private Pi and Copilot;
automatic attention hooks remain open under `tvbf`.
Forge can discover/read tasks, and the four application repository mappings
are configured. No application tasks or task-backed workspaces have been
created. This checkout's agent/CLI scope remains `engi-platform`, not the
application projects. [Adoption details](context/kata-adoption.md)
and the [synthetic evaluation](context/kata-evaluation.md) describe the boundaries.

### Pi and Copilot task access

Repeatable setup and model-free checks, from this checkout:

```sh
python3 scripts/local_env.py install-kata-mcp
python3 scripts/check-kata-mcp.py
node scripts/check-kata-pi.mjs
./scripts/pi-local.py
copilot
```

Setup adds ignored, owner-private `.pi/mcp.json` and `.github/mcp.json` using
absolute local launcher paths. It preserves other server entries and refuses
an existing different `kata` entry, symlinks or non-private configuration.
Rerun after a deliberate path migration. Only this checkout is trusted in the
private Pi profile; an explicit distrust decision is not overwritten. Global
Pi/Copilot settings, Falcon MCP and model routes are unchanged.

Restart existing clients to load the server. Copilot discovers it as a
**workspace** server; the current running conversation cannot acquire new MCP
tools merely by creating a file, so the scoped CLI remains its fallback.
Normal client trust/permission controls still apply; setup does not enable
unrestricted tool approvals.

The stdio adapter fixes actor `pi` or `copilot` and binds `engi-platform`.
It strips inherited model credentials, exposes no new HTTP listener and fails
if the existing daemon is unavailable. These actors are attribution labels,
not authenticated user identities. Scoped MCP refuses cross-project reads/
writes and project administration, but still permits task mutations within this
project; it is not an OS sandbox or a substitute for human authorization.

Kata initially offers 16 `kata.load_*` section loaders. Load discovery,
mutation, coordination or lifecycle as needed, then refresh/search the tool
catalog. Use `kata.status` to inspect the actual actor/owner; search before
create, do not force another actor's claim, and use stable idempotency keys for
create/comment retries. Inbox reads do not acknowledge requests.

A real Pi/USAi read pilot loaded discovery/coordination and retrieved `tvbf`
with actor `pi` and owner `copilot`. For a bounded no-filesystem pilot use
`--no-builtin-tools`; an allowlist containing only `codemode` or `tool_search`
also suppresses the underlying MCP proxy tools, so it is not a working Kata
allowlist. No Copilot model-driven MCP pilot or native attention hooks are
claimed verified yet. Transport checks are not those milestones.

Inspect, restart or read the service journal:

```sh
systemctl --user status kenn-kopy-kata.service --no-pager
systemctl --user restart kenn-kopy-kata.service
journalctl --user -u kenn-kopy-kata.service
```

For first-time migration, stop a supervisor that owns Kata, then install:

```sh
python3 scripts/local_env.py stop
python3 scripts/local_env.py install-kata-service
```

The installer is repeatable and preserves the existing config/database; occupied
ports or mismatched service/database identities fail explicitly. The unit runs
the daemon in the foreground with a sanitized, credential-free environment,
shared loopback API/UI and no automatic token creation. It needs neither Node
nor a USAi key. The existing user manager/lingering setup starts it with WSL;
no dependency on Forge or the other dashboards is added.

`python3 scripts/local_env.py stop` does not stop Kata. Use
`systemctl --user stop kenn-kopy-kata.service` for deliberate downtime,
or `systemctl --user disable --now kenn-kopy-kata.service` to disable boot
startup without deleting tasks. Start it again before task/index commands.
The owner-approved workspace backup now includes an online snapshot of Kata's
database; private persistence and the Markdown index alone are not a backup.
See [Persistence and projects](#persistence-and-projects) for the backup command
and the remaining application/cloud recovery boundary.

## AgentsView tracking and WSL startup

Open **http://127.0.0.1:18080/**. The initial archive contains **54 sessions:
42 Copilot and 12 Pi**, including one-shot/automated sessions hidden by some
default UI filters. This includes existing history and one synthetic saved Pi
session used to confirm automatic ingestion and exact token accounting.
Copilot's current event-file growth is also picked up automatically.

The configured sources are `~/.copilot`, `~/.pi/agent/sessions` and
`.local/environment/pi/sessions`. AgentsView reads the native clients' files;
neither client needs a proxy, extra API key or per-turn import hook.
Copilot's `session-store.db` supplies per-request metrics where available.
Some active/older sessions have no recorded token data; missing metrics are
not evidence of zero consumption.
USAi aliases currently have no verified cost rates, so unpriced usage is
**not free usage** or an authoritative bill.

The initial policy is **usage-only**: session/activity metadata and token
records are archived, but transcript text, thinking, tool payloads and titles
are excluded. Original client files are unchanged. Transcript replay/search
features are consequently limited. Other agent sources, telemetry, generated
insights and external publication are not enabled by this integration.
The archive and private pre-import backup live under `.local/environment/`.

The existing `kenn-kopy-agentsview.service` is enabled in the user manager;
WSL already has systemd and user lingering enabled. It starts when this WSL
instance boots, without a terminal. This unit does **not** open a Windows
browser window or start other dashboards; roborev has its own boot unit below.

```sh
systemctl --user status kenn-kopy-agentsview.service --no-pager
systemctl --user restart kenn-kopy-agentsview.service
journalctl --user -u kenn-kopy-agentsview.service
```

A service restart retained the archive and left the companion dashboards
running. An actual WSL shutdown/reboot was not performed during active work.

For first-time configuration/migration, with AgentsView already reachable
through `local_env.py run`, use:

```sh
python3 scripts/local_env.py configure-tracking \
  --copilot-dir "$HOME/.copilot" \
  --pi-dir "$HOME/.pi/agent/sessions" \
  --pi-dir "$PWD/.local/environment/pi/sessions" \
  --archive-content usage
python3 scripts/local_env.py stop
python3 scripts/local_env.py install-agentsview-service
python3 scripts/local_env.py run
```

Source directories must exist; omit a global Pi source that is not present.
The private Pi sessions directory is created by the tracking command.
Configuration and service installation are safe to repeat; conflicting
source/policy settings are refused rather than overwritten. Deliberately
review a content-policy migration before changing it; do not delete the
archive or ownership metadata to bypass these checks.

To stop only AgentsView, use
`systemctl --user stop kenn-kopy-agentsview.service`; start it again with
`systemctl --user start kenn-kopy-agentsview.service` before using the stack.
To remove boot startup while retaining its archive, use
`systemctl --user disable --now kenn-kopy-agentsview.service`.

## roborev startup and review availability

roborev is running at **http://127.0.0.1:17374/reviews**, with its API at
http://127.0.0.1:17373/. `kenn-kopy-roborev.service` is enabled for WSL startup
alongside AgentsView. It retains `.local/environment/roborev/` settings and
review databases and does not require Forge or GitHub access.

```sh
systemctl --user status kenn-kopy-roborev.service --no-pager
systemctl --user restart kenn-kopy-roborev.service
journalctl --user -u kenn-kopy-roborev.service
```

For first-time installation/migration, confirm no reviews are queued/running
before stopping the existing supervised daemon. From a shell with the
installed Pi/Node runtime available:

```sh
python3 scripts/local_env.py stop
python3 scripts/local_env.py install-roborev-service
python3 scripts/local_env.py run
```

Skip `stop` if the on-demand stack is already stopped. The installer records
the resolved Node executable in the generated private unit so Pi remains
available under systemd's minimal PATH. It verifies Pi 1.0.3, preserves
configuration and refuses occupied ports instead of replacing another daemon.
Installation is repeatable. If deliberately moving to another compatible
Node installation, rerun the installer and restart the service.

The daemon receives **no USAi key**. The configured private Pi launcher reads
it only when an agent is launched. The boot migration installed no Git hooks
and queued no reviews. A subsequent bounded manual Pi/USAi review completed
successfully; setup and access are described below.

To stop only roborev, use `systemctl --user stop kenn-kopy-roborev.service`.
To remove boot startup while retaining review data, use
`systemctl --user disable --now kenn-kopy-roborev.service`.
Start it again before running the on-demand stack; the supervisor will not
duplicate an independently managed daemon. Service restart and independent
stop/start ownership were verified; a full WSL reboot remains untested.

### Isolated Pi reviews without Forge

Install the pinned structured-output extension using Pi's own package manager:

```sh
python3 scripts/local_env.py install-pi-review-extension
```

This installs **`npm:@nqbao/pi-json-schema@0.1.1`** into
`.local/environment/pi/npm/` and adds it to the private Pi settings, preserving
Superpowers and the other settings. It needs package-registry access, not a
USAi credential, and can be repeated. Global Pi configuration is untouched.
Roborev explicitly loads the extension and supplies the review JSON schema.
The extension validates the result before roborev stores it.

Use the scoped executable rather than a global `roborev` command:

```sh
./scripts/roborev-local.py status
./scripts/roborev-local.py show --job 1
```

From an approved project, a bounded manual review is:

```sh
/absolute/path/to/kenn-kopy/scripts/roborev-local.py review \
  --repo /absolute/path/to/approved/project \
  --type default --agent pi --panel none --reasoning fast --wait
```

The launcher preserves the caller's working directory, arguments and stdin,
selects `.local/environment/roborev/`, and pins the API to `127.0.0.1:17373`.
Server overrides are refused. An unavailable explicit endpoint fails instead
of starting/discovering another daemon. No key is read by this launcher or
passed in CLI arguments; the daemon launches the private Pi/USAi child.
Forge and GitHub are not involved. Use the saved USAi model rather than
`--model`/`--provider` overrides, which the Pi launcher rejects.

On 2026-10-09, **job 1** reviewed one synthetic regression commit in the private,
unpublished `.local/environment/review-demo-20261009/` fixture. It returned
schema-version-2 JSON and correctly identified the high-severity pricing bug
at `pricing.py:3`: a 20% discount returned 20 rather than the payable 80.
The job is completed, not failed; `review --wait` returns **exit 1 when findings
fail the review**. The intentionally broken fixture is retained for inspection,
not as production code. Its Git hooks are disabled. Falcon was not edited and
no automatic reviews were enabled in real repositories.

### Automatic commit reviews

On 2026-10-20 the owner enabled automatic reviews in **this platform checkout,
`~/falcon-docs`, and all four `~/falcon/<repository>` clones**. Every new local
commit queues one standard-reasoning Pi review through the existing USAi
profile, with one daemon worker. Existing history is not backfilled.
Automatic fixes, agent lifecycle hooks, roborev GitHub polling and publication
remain disabled. Reviews do not block commits or pushes.

The repeatable installer takes explicit, approved main-checkout paths:

```sh
python3 scripts/roborev_hooks.py --profile platform "$PWD"
python3 scripts/roborev_hooks.py --profile corpus "$HOME/falcon-docs"
python3 scripts/roborev_hooks.py --profile application \
  "$HOME/falcon/supply-chain-user-interface" \
  "$HOME/falcon/national-item-file-maintenance" \
  "$HOME/falcon/standard-acquisition-interface" \
  "$HOME/falcon/infrastructure"
```

It writes a machine-local `.roborev.toml` with actionable-defect guidelines,
per-commit review policy and generated/runtime-directory exclusions. Local
`.git/info/exclude` entries keep that config and snapshots out of Git; no
application/corpus source or tracked ignore file is changed. Existing differing
review configs are refused, not overwritten.

Each repository's `core.hooksPath` selects its own private directory under
`.local/environment/roborev/hooks/`. The installer copies existing hooks without
changing their originals, then uses `init --no-daemon --binary <scoped launcher>`
to install post-commit, post-rewrite and pre-push hooks. All six repositories
initially had only inactive sample hooks. Supported shell hooks are chained;
non-shell managed hooks or an existing post-rewrite hook require an explicit
migration rather than unsafe replacement. Installation metadata records the
previous hook settings.
After rollback, retrying refreshes the inactive copy from the original hooks,
so correcting an unsupported original hook does not leave a stale failed copy.

This external hook location prevents native startup/update repair from
replacing the scoped launcher. Missing-launcher errors are visible and never
fall back to global roborev discovery. Native enqueue failures are recorded
in `.local/environment/roborev/post-commit.log`.

Watch results in `./scripts/roborev-local.py tui` or
http://127.0.0.1:17374/reviews. The browser route needs `Accept: text/html` for
command-line HTTP checks. Linked worktrees inherit these hooks and the
untracked main-checkout review config; separate clones, including future
Forge-managed clones, need their own approved installation.

To disable hooks in any of these six originally unconfigured repositories:

```sh
git -C /absolute/path/to/repository config --local --unset core.hooksPath
```

That restores the untouched `.git/hooks` directory. For another repository
with prior settings, restore the values recorded in its `installation.json`
instead of blindly unsetting them.

Normal structured reviews use read-only tools and `--no-session`; this is
**not an OS sandbox**, and those jobs do not become ordinary saved Pi sessions
in AgentsView. Review usage accounting and sandbox selection remain in TODO.

## First-time setup

For a portable, prerequisite-reporting entrypoint, use
[`dist/install.sh`](dist/README.md). It initializes pinned source repositories,
builds the applications, creates private configuration and prints manual
startup commands. Ubuntu user-service registration/startup is explicitly
optional. It requires an approved existing Librarian installation and reports
missing host tools rather than installing system packages or changing global
agent profiles. Clean-host acceptance is still outstanding.

The current host has built application binaries, Python 3.11+, Node, Git, tmux
and user-installed Pi **1.0.3**. Falcon's existing MCP installation/index must
be present under `~/falcon-docs`. Setup validates Pi's exact version but does
not install it or modify global Pi configuration.

```sh
python3 scripts/local_env.py setup \
  --corpus "$HOME/falcon-docs" \
  --forge-binary .local/forge-local-kata/kenn-forge
```

The Forge binary above is the explicit temporary local-source build used on
this host while its normal dependency downloads are blocked. There is no
automatic fallback. After the normal build is unblocked, migrate the recorded
binary path deliberately; see [tool/build details](context/tools.md).

Setup creates missing settings only. Repeating it preserves existing settings
and rejects accidental changes to saved executable/corpus paths. Do not delete
the state directory to change a setting.

## Forge boot service and GSA GitHub setup

Forge runs independently at **http://127.0.0.1:18091/** under
`kenn-kopy-forge.service`. It retains the existing private database/config and
Falcon project ID. Its unit records the Node executable for Pi; it does not
depend on interactive NVM initialization or put credentials into the unit.
Kata has its own boot service, not a Forge startup dependency.

```sh
systemctl --user status kenn-kopy-forge.service --no-pager
systemctl --user restart kenn-kopy-forge.service
journalctl --user -u kenn-kopy-forge.service
```

For first-time migration, ensure there are no active workspaces/terminal
sessions before stopping a supervisor that currently owns Forge:

```sh
python3 scripts/local_env.py stop
python3 scripts/local_env.py install-forge-service
python3 scripts/local_env.py run
```

Skip `stop` if the stack is already stopped. The installer is repeatable and
refuses occupied ports; do not stop unrelated services to bypass its checks.
Once installed, `status` still reports Forge and its projects when the
on-demand stack is stopped. Disable boot startup, retaining data, with
`systemctl --user disable --now kenn-kopy-forge.service`; start the service
again before running the on-demand stack.

As of 2026-10-20, the four private GSA Falcon mirrors and working clones are
available; normal `gh` can access them. Use **`github.com`** for Forge mirror
intake, not the original enterprise host `github.helix.gsa.gov`. Direct Helix
connectivity is no longer a prerequisite for these mirrors. Local workstation
handling approval is settled; the separate Citrix VDI export prohibition is
unchanged.

Forge's isolated GitHub profile is now authenticated on this host. Other
installations need their own owner-terminal login. The workspace-local
GitHub CLI **2.102.0** is installed by `scripts/bootstrap-toolchains.sh` using
the official release archive and a pinned SHA-256. No global installation or
shell settings change is needed:

```sh
./scripts/gh-local.py --version
```

The launcher and Forge share ignored `.local/environment/gh/`, not your global
GitHub CLI profile. Both drop inherited tokens and use the same private HOME.
Authenticate in **your own terminal**, replacing `HOST` with the confirmed
bare host from the approved repository URL (`github.com` for the GSA mirrors,
without `https://`):

```sh
./scripts/gh-local.py auth login --hostname HOST --web \
  --git-protocol https --insecure-storage
./scripts/gh-local.py api --hostname HOST user --jq .login
```

Complete the browser/SSO flow yourself; authorize the GSA organization if its
policy requires it. If WSL cannot open a browser, open the printed login URL
in your Windows browser. Never paste a token/device code into chat or run
`gh auth token` for manual inspection. The named `--insecure-storage` option
keeps the credential in this private file-based profile rather than a shared
system keyring: its directory is `0700` and the launcher sets umask `0077`.
This is filesystem protection, not an OS sandbox; do not copy the profile
into Git. Follow GSA's approved authentication method if CLI OAuth is restricted.

After login, restart Forge so startup identity discovery sees the account.
Then confirm read access to one owner-approved repository:

```sh
./scripts/gh-local.py repo view https://HOST/OWNER/REPO \
  --json nameWithOwner,url,viewerPermission
```

**Repository selection opts into provider sync on the next Forge startup.**
The launcher passes `--disable-sync` only when native Forge configuration has
no repositories. Once read access is confirmed, add the exact approved
repositories through Forge Settings, then restart `kenn-kopy-forge.service`.
This host now tracks only `GSA/supply-chain-user-interface`,
`GSA/national-item-file-maintenance`, `GSA/standard-acquisition-interface` and
`GSA/infrastructure`; all four completed their initial sync.
Forge's built-in notification sync lists the signed-in user's threads and
filters them to tracked repositories; it has no notification-off setting.
Do not select all GSA repositories, add remotes to this integration
repo, publish Falcon, enable write actions/hooks, or launch a coding task as
part of initial authentication. The next milestone is one provider-backed
workspace with Pi/USAi and qualified context, followed by an agreed bounded task.

## Persistence and projects

All local state lives under ignored **`.local/environment/`**, separate from
global home configuration and disposable smoke runs.

| Path under `.local/environment/` | Contents |
| --- | --- |
| `environment.json` | Machine-local executable and corpus paths |
| `forge/config.toml`, `forge/forge.db` | Forge settings and project/worktree records |
| `pi/` | Isolated Pi settings, MCP/model configuration and session files |
| `roborev/`, `kata/`, `agentsview/` | Persistent application state |
| `logs/` | Appended on-demand logs; independent services use the user journal |
| `systemd/`, `agentsview-service.json`, `roborev-service.json`, `forge-service.json`, `kata-service.json`, `agentsview-tracking.json` | Generated user units, independent ownership and non-secret source/policy metadata |
| `gh/` | Isolated GitHub CLI login used by Forge; credentials must never be tracked |
| `secrets/usai-api-key` | Private USAi credential |

Application Settings and the appropriate private configuration files are the
places to make changes. Restart affected services after startup-setting edits.
State survives normal stop/start and WSL restarts, but **ignored state is not
a backup**. Backup/recovery remains tracked in [TODO.md](TODO.md).

On 2026-10-12 the owner approved the CGI Federal OneDrive destination and
sensitive local assets. A versioned workspace archive now lives under
`C:\Users\NKIRRISH\OneDrive - CGI Federal, Inc\EngiPlatformBackups`.
This is an archive copy, not live-checkout synchronization. Repeat explicitly:

```sh
python3 scripts/backup_workspace.py \
  '/mnt/c/Users/NKIRRISH/OneDrive - CGI Federal, Inc/EngiPlatformBackups'
```

The archive includes this checkout's source, complete local Git/submodule
history, uncommitted/untracked work and ignored private state, including
sensitive documents, credentials, sessions and application databases.
**Treat it as restricted material; never commit it or share it as an ordinary
attachment.** External Falcon assets, global Pi/Copilot profiles, host settings
and external Git worktrees are outside this workspace copy. Symlinks are
preserved without following them; external/absolute links require a scope
decision.

Reinstallable dependency trees, caches, toolchains and compiled outputs are
omitted, but tracked source/stubs, dependency manifests and the local Forge
build recipe are retained. SQLite uses individually consistent online backup
snapshots, including committed WAL data, instead of copying live database/WAL
files. Runtime sockets are not restorable and are recorded as omitted.
`backup-manifest.json` inside the archive records every included file/hash,
permissions, database, exclusion and Git revision. Before the host copy is
written, a local extraction verifies those contents, Git/submodule object
connectivity and SQLite integrity; the host copy also gets a verified SHA-256
sidecar. Prior archives are not overwritten.

To inspect or recover, first check the sidecar with `sha256sum -c` in the backup
directory, then use Linux `tar -xzf` into a **new, private directory** with
`umask 077`, not over a running checkout. Git history and archive file
permissions are preserved. Reinstall the omitted dependencies and review
machine-local paths, stale process/lock metadata and credentials before
installing units or starting restored applications. Database snapshots are
not one cross-service transaction. Restoring/running all applications and
downloading a copy from the cloud have not been exercised.

The initial local host copy is complete; OneDrive cloud delivery, retention and
cloud recovery remain unverified. There is no automatic backup schedule.

### Falcon corpus backup

The owner separately approved `~/falcon-docs` on 2026-10-12. Its tracked work
was already committed; raw intake, sensitive originals, provenance, retained
recovery snapshots/receipts and ignored owner files remain archive content,
not new Git files. The full copy is complete in the same protected folder:
`falcon-docs-20261012T235557Z-a882cca6.tar.gz` (22,966,738,780 bytes), with an
adjacent SHA-256 sidecar. Future explicit copies use a distinct
`falcon-docs-<UTC>-<nonce>.tar.gz` archive.

Falcon's large retained asset tree requires disk-backed staging, not this
host's 24 GB `/tmp`. Choose an existing private Linux directory **outside
both checkouts** with room for the snapshot, archive and restored copy:

```sh
python3 scripts/backup_workspace.py \
  '/mnt/c/Users/NKIRRISH/OneDrive - CGI Federal, Inc/EngiPlatformBackups' \
  --source /home/nkirrish/falcon-docs \
  --staging-dir /absolute/private/disk-backed-directory \
  --sqlite-snapshot REFERENCE/catalog/catalog.sqlite3 \
  --sqlite-snapshot REFERENCE/review-events/events.sqlite3 \
  --sqlite-snapshot tools/context-index/.local/index.sqlite3 \
  --sqlite-snapshot tools/context-graph/.local/graph.sqlite3
```

Explicit SQLite selection takes online snapshots only of the listed current
stores. Other database artifacts, especially retained historical snapshots,
are copied byte-for-byte with their receipts; never transform or prune them
as dependency bulk. Python environments identified by `pyvenv.cfg` are
reinstallable dependencies even when named differently from `.venv`.
Fast gzip compression keeps full-corpus copies practical without changing
source bytes or archive restoration rules. Global Pi/Copilot profiles are
still outside the two named workspace archives.

Register another existing local Git checkout while Forge is running:

```sh
python3 scripts/local_env.py register /absolute/path/to/project
```

For a new project, create and initialize its Git repository first, then
register it. Registration does not generate starter code or publish a repo.
`falcon-docs` stays in its existing location; setup does not copy its corpus,
edit it, install Git hooks or grant permission to change its authoritative
stores. Its own `AGENTS.md` and task guides govern work there.

### Local projects are not provider repositories

**Current Forge UI limitation:** `falcon-docs` is registered in the local
project registry, with its existing primary worktree. It does **not** appear
in **Repos** or the workspace list: those screens use a separate
provider-repository/workspace catalog. With no tracked provider repositories,
**Create Workspace** is disabled. Registering the checkout again will not
resolve this.

The provider onboarding wizard can be dismissed with **I'll do this later**.
Local registration itself is available at
http://127.0.0.1:18091/project-intake/ using **Add an existing local repository**;
it needs a local path, not provider credentials or a repository URL. This
intake does not make the checkout available in the main workspace UI.

A complete Forge UI demo still needs an approved provider-backed repository.
The owner reports GSA GitHub access is now available; local authentication and
the specific repository are not yet configured. The owner chose this route;
local-project/worktree UI changes remain deferred.
Do not fabricate a provider identity, add a fake remote, or publish Falcon to
work around the distinction. Standalone Pi below remains available for local
exploration without a cloud repository.

## Pi and Falcon Context MCP

Once a usable Forge workspace is available, select **Pi (USAi)** there.
While the local-project UI gap remains, launch the same isolated agent
directly from your project directory:

```sh
python3 /absolute/path/to/kenn-kopy/scripts/pi-local.py
```

This wrapper establishes the private Pi profile and USAi credentials inside
the actual agent process, including when Forge sanitizes the tmux environment.
Other built-in model agents are disabled by default; shells remain available.
Global `~/.pi/agent` settings are not automatically inherited.

Normal CLI Pi and Forge Pi now share only the private USAi key file, not their
settings or sessions. `set-key` also points the existing global `usai` and
`litellm-usai` providers at the private credential reader. It preserves their
other configuration and does not create global providers that are absent.
Do not run the credential reader directly: its stdout contains the token.

Falcon is a read-only **stdio** MCP server, not a separate dashboard or HTTP
endpoint. The private `.local/environment/pi/mcp.json` points to its existing
installation and corpus. Check the connection from this repository:

```sh
python3 scripts/pi-local.py mcp list
node scripts/check-pi-mcp.mjs
```

The second command performs a bounded qualified read through Pi's MCP
integration without a model call or logging corpus text. In a live Pi session,
use `/mcp` to inspect the connection. Model-selected retrieval and behavior
after compaction require separate model-backed verification.

### Returning reusable context discoveries

Follow `INBOX/README.md#agent-context-contributions` in the configured Librarian
checkout. Read-only engineering/review agents return a finding with its
provenance, limits and task/run reference; submission requires a separate,
explicitly authorized context-maintenance handoff. That route owns receipts,
assessment, canonical updates and returned disposition. A response alone is
not submission, and this platform's `context/` files are not automatically
ingested. No MCP write permission or background queue follows from access.

## USAi credential and provider setup

On this host, the owner has supplied the key. The isolated Pi profile is now
configured with the previously saved USAi model, and Chat Completions streaming
plus a synthetic tool-call round trip worked through both the API and Pi.
The refreshed discovery catalog contains 22 advertised IDs. These results apply
to the selected model, not every advertised model; model-driven Falcon retrieval
from Forge and post-compaction behavior remain to be exercised.

Store or rotate the key from your own terminal:

```sh
python3 scripts/local_env.py set-key
```

Paste it at the **hidden prompt**, not into a command argument or chat. The
command writes the token once to `.local/environment/secrets/usai-api-key`
with `0600` permissions inside a private directory. It also updates only the
credential-command references in the existing global Pi USAi providers,
replacing any old literal USAi key with a reference to `scripts/usai-key.py`.
Updated global configuration files are private (`0600`); no token is copied
into settings. Saved `auth.json` overrides cause an explicit error rather
than silently overriding an unrelated credential.

One manual replacement now covers **normal CLI Pi and Forge's isolated Pi**.
Their configuration, MCP setup and session directories remain separate.
Tell a configuring agent that the file is ready; never send its value.
The private launcher supplies the key only to Pi's environment, not to the
dashboard supervisor/tmux server. **Restart existing Pi sessions after
rotation** because the private launcher captures the key at startup.
USAi's seven-day lifetime is owner-reported; no renewal API, timer or
six-day reminder has been installed. Generate a fresh key manually in the
[USAi console](https://gsa.usai.gov/console/key-management), then run `set-key`.

Refresh the advertised model IDs using the private credential:

```sh
python3 scripts/local_env.py list-models \
  --base-url 'https://CONFIRMED-USAI-API-BASE'
```

Replace the placeholder with the API base URL, including any required API
path prefix. The command requests `<base-url>/models` and saves a timestamped
private catalog in `.local/environment/usai-models.json`. It refuses redirects
and does not log the credential. Discovery does not select a default model,
modify Pi's provider settings or prove chat/streaming/tool-call compatibility.

Once the model alias and protocol are confirmed:

```sh
python3 scripts/local_env.py configure-provider \
  --base-url 'https://CONFIRMED-USAI-API-BASE' \
  --model 'CONFIRMED-MODEL-ALIAS' \
  --api 'CONFIRMED-PI-API-TYPE'
```

Accepted Pi API types are `openai-completions` (Chat Completions),
`openai-responses` and `anthropic-messages`. A saved API type or successful
model listing is a candidate, **not protocol verification**. Confirm streaming
and a tool-call round trip before treating the agent as ready. Normal launches
require both the saved USAi model configuration and key; they fail explicitly
instead of falling back to another provider.

The owner has approved **USAi and this local environment for sensitive
information, including PII**. Prompting users should minimize unnecessary PII.
This does not make keys, transcripts or corpus content publishable, authorize
alternate model providers, or remove project/source-specific handling rules.
Private permissions are not an OS sandbox; same-account processes can access
the files.

Cloud deployment remains pending. The owner's intended destination is
GSA-owned infrastructure within a GSA VPC. That direction does not establish
implemented networking, identity, access control, backups or operational
readiness; those remain deployment work, not blockers for approved local use.

## Disposable checks and further work

This is distinct from the persistent environment:

```sh
python3 scripts/smoke.py --forge-binary .local/forge-local-kata/kenn-forge
```

The smoke script creates fresh isolated state, supplies no credentials, checks
startup/assets/task storage/offline skills, and shuts down its own processes.
Do not run it alongside the persistent environment: they use the same ports.
Stop the dashboard supervisor if running **and** stop all four independent units
first:

```sh
systemctl --user stop kenn-kopy-kata.service kenn-kopy-forge.service \
  kenn-kopy-roborev.service kenn-kopy-agentsview.service
```

Afterward, restore them with `systemctl --user start kenn-kopy-kata.service
kenn-kopy-forge.service kenn-kopy-roborev.service kenn-kopy-agentsview.service`.

See [TODO.md](TODO.md) for open work, [context/status.md](context/status.md) for
observed results/current process state, [context/tools.md](context/tools.md)
for build and integration details, and [context/project.md](context/project.md)
for objectives and decisions. Upstream histories and licenses remain in their
pinned submodules.
