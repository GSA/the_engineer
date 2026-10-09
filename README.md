# Kenn Kopy: local engineering environment

A persistent Linux environment for personal exploration and a human-directed
engineering demo. It combines Forge, Pi, Superpowers, roborev, Kata and
AgentsView, with the existing Falcon Context MCP server. USAi LiteLLM is the
required model provider. GSA GitHub/Jira integration and cloud deployment are
later work.

## Start and access the environment

Run commands from this repository's root. If setup is already complete, start
the saved environment directly:

```sh
python3 scripts/local_env.py run
```

Keep that terminal open. On this host, AgentsView and roborev run independently
as user-systemd services; the supervisor starts Forge and Kata on IPv4
loopback and connects to them. Configuration/databases are retained, and
`~/falcon-docs` remains registered as a local Forge project. Before installing
the independent services, the supervisor owns all four dashboards.

| Application | Local browser address |
| --- | --- |
| Forge: repository/workspace console | http://127.0.0.1:18091/ |
| roborev: reviews | http://127.0.0.1:17374/reviews |
| Kata: tasks | http://127.0.0.1:17777/kata |
| AgentsView: sessions and usage | http://127.0.0.1:18080/ |

In this WSL installation, the Windows browser can use these same localhost
addresses with the current NAT configuration. No public listener, tunnel or
cloud access is configured. Provider synchronization remains disabled.
AgentsView now watches explicit Copilot and Pi session sources; it is not a
model router. Dashboard startup alone does not establish a complete
model-backed coding/review workflow.

From another terminal:

```sh
python3 scripts/local_env.py status
python3 scripts/local_env.py stop
```

Ctrl+C in the running terminal also stops the supervisor. Shutdown retains
settings, projects, databases and Pi session files. Stop unwanted live terminal
sessions through Forge's session controls; they can have independent lifetimes.
**Stopping this stack leaves independent AgentsView and roborev running.**
Both are enabled at WSL boot; Forge and Kata remain on-demand while GSA GitHub
access is pending. Occupied ports fail startup rather than replacing another
process.

For an on-demand stack without an open terminal, this systemd host also supports:

```sh
systemd-run --user --unit=kenn-kopy-local --collect \
  --setenv=PATH="$PATH" \
  --property=WorkingDirectory="$PWD" --property=UMask=0077 \
  --description='On-demand Kenn Kopy dashboards' \
  /usr/bin/python3 "$PWD/scripts/local_env.py" run
```

Do not use this while another supervisor is running. This transient unit is
not enabled at boot. Passing the shell's non-secret `PATH` is necessary here
because Pi uses the user-installed NVM Node runtime. Use the same `status`/
`stop` commands; inspect failures with
`journalctl --user -u kenn-kopy-local.service`.

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

**Future hook setup requires an agreed per-project layout.** Pass this
executable's absolute path as `--binary` and use `init --no-daemon`; merely
invoking `init` through the launcher does not select its executable for hooks.
This roborev version rewrites managed hooks inside `.git/hooks` to the native
binary on daemon startup/updates. To retain the scoped executable, use an
explicitly approved, per-repository user-managed hooks directory outside Git
metadata through `core.hooksPath`, preserving/chaining existing hooks.
That protected layout was checked in a disposable fixture, including paths
with spaces and automatic-repair preservation. Do not change a real project's
hooks path or install hooks before agreeing its review rules and hook migration.
Manual review can maintain existing roborev hooks, but does not install them
from scratch.

Normal structured reviews use read-only tools and `--no-session`; this is
**not an OS sandbox**, and those jobs do not become ordinary saved Pi sessions
in AgentsView. Review usage accounting and sandbox selection remain in TODO.

## First-time setup

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
| `systemd/`, `agentsview-service.json`, `roborev-service.json`, `agentsview-tracking.json` | Generated user units, independent ownership and non-secret source/policy metadata |
| `secrets/usai-api-key` | Private USAi credential |

Application Settings and the appropriate private configuration files are the
places to make changes. Restart affected services after startup-setting edits.
State survives normal stop/start and WSL restarts, but **ignored state is not
a backup**. Backup/recovery remains tracked in [TODO.md](TODO.md).

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
The owner chose to wait for GSA GitHub access and add a real provider/repository;
local-project/worktree UI changes are deferred.
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
Stop the dashboard supervisor if running **and** stop both independent units
first:

```sh
systemctl --user stop kenn-kopy-roborev.service kenn-kopy-agentsview.service
```

Afterward, restore them with `systemctl --user start kenn-kopy-roborev.service
kenn-kopy-agentsview.service`; restart the on-demand dashboards if needed.

See [TODO.md](TODO.md) for open work, [context/status.md](context/status.md) for
observed results/current process state, [context/tools.md](context/tools.md)
for build and integration details, and [context/project.md](context/project.md)
for objectives and decisions. Upstream histories and licenses remain in their
pinned submodules.
