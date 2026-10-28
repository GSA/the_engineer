# Engineer: local engineering environment

A persistent Linux environment for personal exploration and a human-directed
engineering demo. It combines Forge, Pi, Superpowers, roborev, Kata and
AgentsView, with the existing Falcon Context MCP server. USAi LiteLLM is the
required model provider. GSA GitHub repository integration is available;
broader Jira workflow integration and cloud deployment remain later work.

The selected product name is **Engineer** (`engineer`), formerly Engi Platform
and Kenn Kopy. All directory renames are deferred, including the eventual
`~/kenn-kopy` to `~/engineer` move. The existing Kata project `engi-platform`,
checkout/private-state paths and `kenn-kopy-*` service identifiers remain
unchanged until a coordinated migration; commands below use the live identities.

Current service evidence and blockers are in [context/status.md](context/status.md).
The distinction between Forge controls and our proposed engineering phases is
documented in [context/engineering-workflow.md](context/engineering-workflow.md).

The [cross-project architecture](context/system-architecture.md) separates
Engineer execution, Librarian business context/corpus and Knowitall code
context/graphs. Externally owned SPUD is a reuse source, not a required fourth
product. The deferred internal system demonstration is tracked by `engi-platform#hk33`:
one approved real AOS Jira ticket through qualified context, implementation,
review and PR after the three component boundaries work locally. Superseded
`ca6n` will not create a reusable fixture. These public repositories must stay
free of AOS/Falcon-identifying material; private scenario evidence stays in
authorized local state.
[Selective engineering memory](context/engineering-memory.md) describes
decisions, corrections and handoffs rather than full conversation capture.
Memory must demonstrate incremental value over no memory and simple records
before optional runtime work proceeds.

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
All these shells start in this checkout. Forge-linked worktrees inherit
`KENN_KOPY_RUNTIME_ROOT` and resolve managed Kata, roborev, Forge, AgentsView
and private runtime state from this canonical host checkout; they do not need
copied binaries or initialized submodules. An explicit override must be an
existing absolute directory. Use separate worktrees before having
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

Run commands from this repository's root. On this host, Forge, Kata, roborev
and AgentsView start automatically with WSL as independent user-systemd services. No
terminal or browser autostart is required. Check the saved environment:

```sh
python3 scripts/local_env.py status
```

Forge is a required component for launching and managing coding/review agents.
Keep its existing systemd lifecycle owner: the service runs native foreground
`serve` through `forge-run`. Upstream `kenn-forge daemon start` is for standalone
background use; do not start or restart a second lifecycle for this managed
profile. Use `systemctl --user` here.

Configuration/databases are retained. Forge's registered projects are Librarian
(`~/the_librarian`), Knowitall (`~/the_knowitall`), Engineer (`~/kenn-kopy`)
and SPUD (`~/aos-spud`).
If you intentionally stopped services, restore them:

```sh
systemctl --user start kenn-kopy-kata.service kenn-kopy-roborev.service \
  kenn-kopy-agentsview.service kenn-kopy-forge.service
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
cloud access is configured. Forge syncs private `GSA/the_engineer`,
`GSA/the_librarian` and `GSA/aos-spud`, plus public `GSA/the_knowitall`.
The four earlier Falcon mirrors were removed from its catalog, not deleted
from disk. Newly authorized GSA repositories default to public; existing
private repository visibility is unchanged.
Profiles without configured repositories retain disabled provider sync.
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

## Kata tasks for Engineer

**Kata project `engi-platform` is the source of truth for this project's open
tasks.** `.kata.toml` binds this checkout; the private database stays under
`.local/environment/kata/`. `TODO.md` retains historical completed entries,
not a live duplicate task index. Original open descriptions, blockers and
provenance are preserved in Kata. The reproducible redeployment recipe is
task **`5xrm`**.

Kata runs under **`kenn-kopy-kata.service`**. Open
**http://127.0.0.1:17777/kata** and select `engi-platform`.
The four Falcon repositories also have separate Kata
projects named `supply-chain-user-interface`, `national-item-file-maintenance`,
`standard-acquisition-interface` and `infrastructure`. Select the matching
project for application work; their former Forge mappings have been removed.
Existing tasks and history are preserved. The `spud` project now maps to
`GSA/aos-spud`; Engineer and Librarian retain their existing task bindings.
From this repository root, use the native CLI:

```sh
kata list --agent
kata ready --no-label blocked --no-label deferred --agent
kata show 5xrm
kata --project supply-chain-user-interface list --agent
```

The installer creates `~/.local/bin/kata` as a direct symlink to the built
binary and selects the loopback daemon at `http://127.0.0.1:17777` in native
`~/.kata/config.toml`. Existing matching targets are reused; conflicting
binaries or daemon selections are left untouched and reported. Other settings
and credentials are preserved, and shell startup files are not changed. If
`~/.local/bin` is not on `PATH`, invoke the symlink directly or add it to your
shell environment. The service retains its database in
`.local/environment/kata`; no task migration is required. The CLI follows
`.kata.toml` in the current repository and supports Kata's normal selectors and
attribution. In another repository, run
`kata init --project <name> --with-agents` to bind it and add agent guidance.
Search before creating, claim work, and close only with verified evidence.

### From a Kata to a Forge agent

Creating or claiming a Kata does **not** dispatch an agent. The explicit flow is:
choose/claim ready work in Kata, map its project in **Forge Settings > Kata
mappings**, select the task in **New workspace**, then launch the configured
agent. The agent records evidence and closes the task through native Kata;
workspace creation and review completion do not do that automatically.

On daemon `local`, `engi-platform` is **mapped** to `GSA/the_engineer` with
`~/kenn-kopy` as worktree base, `librarian` to `GSA/the_librarian` with
`~/the_librarian`, and `spud` to `GSA/aos-spud` with `~/aos-spud`.
Corpus work now belongs to separate project `falcon-docs`, which remains local
and **unmapped**. All issue history and cross-project relationships are retained.
Per-task `repo` metadata does not control Forge routing. Configured clone paths
can also auto-map through `.kata.toml`; keep toolkit and instance bindings
separate. See the [current handoff and evidence](context/engineering-workflow.md#kata-to-forge-current-pickup-boundary-2026-10-26)
and [private provider onboarding](context/engineering-workflow.md#private-provider-onboarding-2026-10-26-1741-7943).

### Pi and Copilot task access

CLI access needs no MCP adapter. If using MCP, configure the native binary with
`args: ["mcp", "serve"]` and the repository as `cwd`. For example:

```json
{
  "mcpServers": {
    "kata": {
      "command": "/home/nkirrish/kenn-kopy/kata/kata",
      "args": ["mcp", "serve"],
      "cwd": "/home/nkirrish/kenn-kopy",
      "env": { "KATA_SERVER": "http://127.0.0.1:17777" }
    }
  }
}
```

Use your installation paths. Pi reads `.pi/mcp.json`; repository Copilot reads
`.github/mcp.json` (with its client-specific `type`/`tools` fields). Both local
configurations now invoke Kata directly and preserve other servers. Normal
project trust applies; no custom trust installer is needed. Restart/reconnect
existing clients after changing configuration. Check Pi with `pi mcp list`,
or the private profile with `./scripts/pi-local.py mcp list`.

Kata natively binds MCP to the selected workspace project. Section loaders
(`kata.load_*`) expose additional tools on demand; refresh discovery after
loading a section. No custom actor or project allowlist is installed. Configure
`--as <actor>` or `KATA_AUTHOR` when distinct attribution is needed.

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
ports or mismatched service/database identities fail explicitly. Generated units
run the native binary directly with explicit `KATA_HOME` and private `KATA_DSN`,
cleared legacy `KATA_DB`, shared loopback API/UI and no automatic token creation.
Updating source does not regenerate or restart an already running unit.
It needs neither Node
nor a USAi key. The existing user manager/lingering setup starts it with WSL;
no dependency on Forge or the other dashboards is added.

`python3 scripts/local_env.py stop` does not stop Kata. Use
`systemctl --user stop kenn-kopy-kata.service` for deliberate downtime,
or `systemctl --user disable --now kenn-kopy-kata.service` to disable boot
startup without deleting tasks. Start it again before task commands.
The owner-approved workspace backup includes an online snapshot of Kata's
database; repository bindings alone are not a backup.
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
python3 scripts/local_env.py install-roborev-service \
  --binary "$HOME/.local/bin/roborev"
python3 scripts/local_env.py run
```

Skip `stop` if the on-demand stack is already stopped. The service executes
the selected native binary directly, with private HOME/data/config and the
resolved Node directory on PATH so Pi remains available under systemd.
The installer records the binary for existing hook compatibility and foreground
startup; subsequent installs without `--binary` preserve that selection.
A fresh installation without a selection uses the pinned source-built binary.
To change an already-managed executable path, finish reviews and explicitly
stop `kenn-kopy-roborev.service` before passing a different `--binary`.
The installer refuses active binary switches without restarting reviews.
If another start races installation, executable-identity checks reject it and
restore the previous unit and selection rather than leave a future switch armed.
The installer verifies Pi 1.4.0, preserves
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

Install the pinned Forge/roborev extensions using Pi's own package manager:

```sh
python3 scripts/local_env.py install-pi-extensions
```

This installs **`npm:@nqbao/pi-json-schema@0.1.1`** and
**`npm:pi-subagents@0.83.0`** into `.local/environment/pi/npm/` and adds them to
the private Pi settings, preserving Superpowers and the other settings. It
needs package-registry access, not a USAi credential, and can be repeated.
Global Pi configuration is untouched. Roborev explicitly loads the schema
extension; Forge Pi agents receive the subagent dispatch tool needed by
subagent-driven Superpowers workflows.

Use the native release binary for both normal commands and the managed service:

```sh
roborev status
roborev ui
roborev tui
```

`~/.local/bin/roborev` is the owner-updated native v0.73.0 executable, not a
Python wrapper or a symlink that an updater can replace with different routing.
Native `~/.roborev` points to `.local/environment/roborev/`, so the CLI discovers
the same configuration, runtime records, database lock and review history as
systemd. Ensure `~/.local/bin` is on PATH. The original source-built v0.71.0
binary remains in its upstream checkout but is no longer selected by this
installation or its existing hook entrypoints.

On another host, install the native executable through its supported release
mechanism and link its absent default data directory to the configured private
store before using the CLI:

```sh
test ! -e "$HOME/.roborev" &&
  ln -s "$PWD/.local/environment/roborev" "$HOME/.roborev"
```

Do not overwrite an existing directory: first drain its reviews and preserve
its state. This host's secondary store (one canceled job) is retained under
`.local/environment/runtime/roborev-native-9hj3/secondary-profile/`, not merged
into the authoritative history. Its already-open TUI still targets the old
port; close it and run `roborev tui` again.

For later service-managed updates, finish active reviews before restarting:

```sh
roborev pause
# Use roborev status / roborev wait --job ID until running reviews finish.
roborev update --no-restart
systemctl --user restart kenn-kopy-roborev.service
roborev unpause
```

`--no-restart` is native support for systemd/launchd ownership; it also skips
automatic hook/skill rewriting. Do not run a competing `daemon run` or select
a different `ROBOREV_DATA_DIR`. Sharing the default store prevents the previous
update-induced split; it does not prohibit deliberate alternate profiles.

From an approved project, a bounded manual review is:

```sh
roborev review \
  --repo /absolute/path/to/approved/project \
  --type default --agent pi --panel none --reasoning fast --wait
```

Normal CLI use and duplicate prevention need no custom routing script.
Existing Git hooks retain `scripts/roborev-local.py` as a compatibility entrypoint;
it now invokes the same selected native binary, preserving arguments/stdin/cwd,
private state and explicit `127.0.0.1:17373` routing. That compatibility path
still refuses server overrides and native lifecycle/update commands; ordinary
native `roborev` does not. Use systemd for service lifecycle.
`python3 scripts/local_env.py status` retains read-only duplicate diagnostics;
warnings never kill processes. No key is passed in CLI arguments; the configured
private Pi launcher reads it only for the review child.
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
python3 scripts/roborev_hooks.py --profile toolkit "$HOME/the_librarian"
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
non-shell managed hooks and foreign post-rewrite hooks require an explicit
migration rather than unsafe replacement. Native roborev hooks are recognized
by their generated marker and safely upgraded in private staging, including
older versions. Installation metadata records the previous hook settings.
After rollback, retrying refreshes the inactive copy from the original hooks,
so correcting an unsupported original hook does not leave a stale failed copy.
If an installation manifest exists but another tool later changes the active
hooks path, the installer refuses by default. After inspecting that active hook
directory, rerun with `--restage` to explicitly copy it into managed staging
and update the rollback metadata.

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

The current host requires built application binaries, Python 3.11+ with the
Ubuntu **`python3-venv`** package (so repository-local environments include
pip), Node, Git, tmux and user-installed Pi **1.4.0**. Falcon's existing MCP
installation/index must
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

## Forge startup and first session

Forge is an enabled user service alongside Kata, roborev and AgentsView.
Its private database, configuration, project identity, credentials and four
working clones remain under `.local/environment/forge/`. To install the service
repeatably from an already configured checkout:

```sh
python3 scripts/local_env.py install-forge-service
systemctl --user status kenn-kopy-forge.service --no-pager
```

Installation pins the current Node executable for private Pi, preserves saved
settings and binds only **http://127.0.0.1:18091/**. Use `systemctl --user
restart kenn-kopy-forge.service` after deliberate configuration changes, and
`systemctl --user stop kenn-kopy-forge.service` to stop it. An occupied port
is an error, not permission to replace another process.

Without installed units, `python3 scripts/local_env.py run` owns all four
dashboards. It leaves independently managed services alone. `forge-run` remains
available for foreground diagnosis after stopping the unit; never run both.
`status` reports `forge_service` and checks its PID, private runtime identity,
health and dashboard.

For the next browser session using Engineer, Librarian or SPUD:

1. Open http://127.0.0.1:18091/ and choose **Workspaces**, then **New workspace**.
2. Select **gsa/the_engineer**, **gsa/the_librarian** or **gsa/aos-spud** and a
   new branch, or choose the Kata source, daemon **local**, and an agreed task
   in **engi-platform**, **librarian** or **spud** respectively.
   Claim the task through native Kata before work.
3. Choose **Pi (USAi)** to create the worktree and launch the configured agent.
   Give it one bounded task; inspect **Files** and **Diff** before accepting work.
4. Reopen the workspace to return to its sessions. Closing a browser pane does
   not stop the process; use session controls. Commit/review and push/PR creation
   are separate steps, and publication still requires approval.

New Forge-managed clones do not automatically inherit the review hooks from
your existing checkouts. Confirm the intended review setup before real work.
All three create worktrees from their existing checkouts, not new managed
clones; preserve their hooks and uncommitted changes. Librarian is the
data-empty reusable toolkit, not the populated Falcon instance. Its release
package excludes task bindings, deployment data and runtime stores.
The real coding/review pilot has not been run.
For repositories without remotes, see [local-only projects](#local-projects-are-not-provider-repositories).
The upstream [workspace guide](forge/docs/workflows/workspaces.md) explains the
controls in more detail.

### GSA GitHub setup

The four private GSA Falcon mirrors and working clones remain available, but
were removed from Forge's configured catalog on 2026-10-26. Private
`GSA/the_engineer`, `GSA/the_librarian` and `GSA/aos-spud` are configured.
Use **`github.com`** for Forge mirror
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

After login, restart the Forge service so startup identity discovery sees the account.
Then confirm read access to one owner-approved repository:

```sh
./scripts/gh-local.py repo view https://HOST/OWNER/REPO \
  --json nameWithOwner,url,viewerPermission
```

**Repository selection opts into provider sync on the next Forge startup.**
The launcher passes `--disable-sync` only when native Forge configuration has
no repositories. Once read access is confirmed, add the exact approved
repositories through Forge Settings, then run
`systemctl --user restart kenn-kopy-forge.service`.
This host tracks `GSA/the_engineer`, `GSA/the_librarian` and `GSA/aos-spud`;
all three completed sync. The four former Falcon application entries were
removed from Forge's configured catalog on 2026-10-26; their checkouts remain.
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
a backup**. Backup/recovery remains tracked in native Kata.

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

After the owner's 2026-10-26 catalog reset and approved private publication:

| Checkout | Remote | Main workspace dialog |
| --- | --- | --- |
| Engineer: `~/kenn-kopy` | Private `GSA/the_engineer` on GitHub | Synced; `engi-platform` mapping and existing clone configured |
| Librarian: `~/the_librarian` | Private `GSA/the_librarian` on GitHub | Synced; toolkit-only `librarian` mapping and existing clone configured |
| SPUD: `~/aos-spud` | Private `GSA/aos-spud` on GitHub | Synced; `spud` Kata mapping configured |

The prior `falcon-docs` local registration, four application provider entries
and their Kata mappings were removed. All checkouts, the Falcon corpus/MCP
connection, and existing Kata projects/history are retained. One existing
application PR workspace and its worktree were also preserved, not purged.
Engineer and Librarian were published only after owner approval and local
ignore/history checks. Falcon remains local and outside the provider catalog.
Ignore rules do not remove previously tracked content or sanitize history;
check both before publishing a formerly local-only repository.

**No remote is required by Git or Forge's local-project API.** A live synthetic
repository with zero remotes successfully registered, created a new branch and
worktree, ran a tmux-backed terminal in that worktree, refused dirty deletion,
and removed the clean worktree/branch. No provider identity or publication was
needed. Worktree creation requires a commit to branch from; `git init` alone
leaves an unborn branch.

**Current Forge UI limitation:** local project registration does **not**
make a checkout an entry in the provider-backed **Repos** or main workspace
picker. Engineer, Librarian and SPUD now appear there because their real
provider repositories are configured separately.
Registering a remote-free checkout again will not resolve this distinction.

The provider onboarding wizard can be dismissed with **I'll do this later**.
Local registration itself is available at
http://127.0.0.1:18091/project-intake/ using **Add an existing local repository**;
it needs a local path, not provider credentials or a repository URL. This
intake does not make the checkout available in the main workspace UI.

Local projects use separate native `/api/v1/projects/{id}/worktrees` and
worktree `/runtime/sessions` endpoints; the demonstrated API workflow is not
yet a convenient browser workflow. Native project runtime targets support
terminal agents such as the configured Pi, not workspace ACP chat.
Do not fabricate a provider identity, add a fake remote, or publish Falcon to
work around the distinction. For local-only work now, create a separate
worktree with native Git, enter it, and launch the private agent:

```sh
git -C /absolute/path/to/project worktree add -b task/example \
  /absolute/path/to/project-worktrees/example HEAD
cd /absolute/path/to/project-worktrees/example
python3 /absolute/path/to/kenn-kopy/scripts/pi-local.py
```

That fallback keeps work local but is manually managed, not a Forge UI entry.
Only tracked content is present in a new worktree: ignored corpora, credentials,
virtual environments and build outputs are not copied. Do not use a new
worktree as a replacement for an authoritative populated Librarian instance.

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
Stop the dashboard supervisor if running, stop any explicit foreground process,
and stop the four independent units first:

```sh
systemctl --user stop kenn-kopy-kata.service kenn-kopy-roborev.service \
  kenn-kopy-agentsview.service kenn-kopy-forge.service
```

Afterward, restore them with `systemctl --user start kenn-kopy-kata.service
kenn-kopy-roborev.service kenn-kopy-agentsview.service kenn-kopy-forge.service`.

Use native Kata for open work; [TODO.md](TODO.md) retains historical completed
entries. See [context/status.md](context/status.md) for observed results/current
process state, [context/tools.md](context/tools.md) for build and integration
details, and [context/project.md](context/project.md) for objectives and
decisions. Upstream histories and licenses remain in their pinned submodules.
