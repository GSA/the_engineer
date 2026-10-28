# Engineer installer

Engineer is the selected product name. Existing installations retain their
current paths, `engi-platform` Kata binding and `kenn-kopy-*` service names;
directory and runtime-identity migration is deferred.

Initial target: **Ubuntu on Linux x86_64**, including Ubuntu under WSL.
Python 3.11+ and Node.js 24.11+ are required; Ubuntu 24.04+ is the recommended
starting point. This is a source-build installer, not a container, cloud
deployment or confidential-data bundle.

**Known gaps (2026-10-26):** this recipe still requires the legacy Falcon MCP
executable described below, not the renamed data-empty Librarian executable.
Native Kata CLI/client provisioning also remains open reproduction work.
Do not treat this as a complete fresh-host recipe until
Kata `p4ke` reconciles these gaps. See the
[architecture gap inventory](../context/system-architecture.md#concrete-reproduction-gaps).
Forge's `install-forge-service` command is restored; keep all four services.
Forge is required for agent execution, not an optional packaging branch.
No existing service should be changed merely to accommodate this recipe.

From the platform checkout:

```sh
bash dist/install.sh --check --corpus /approved/path/to/falcon-docs
bash dist/install.sh --corpus /approved/path/to/falcon-docs
```

The default asks whether to **enable and start** four systemd **user** services.
Enter defaults to **no**; noninteractive execution also defaults to manual.
One ordered service list drives registration, conflict checks and printed
commands; installation rejects a mismatched runtime service set before builds
or configuration changes.
Explicit alternatives:

```sh
bash dist/install.sh --corpus /approved/path/to/falcon-docs --services manual
bash dist/install.sh --corpus /approved/path/to/falcon-docs --services user
```

## Source acquisition

The installer initializes Forge, Kata, roborev, AgentsView and Superpowers
using the exact Git submodule commits in the platform checkout. URLs live in
its `.gitmodules`; no floating upstream branch is selected. Upstream licenses
and attribution remain in those repositories.

You can distribute this `dist/` directory separately. To obtain the rest of
the platform, supply its **approved Git URL and full release commit SHA**:

```sh
bash dist/install.sh \
  --source APPROVED_PLATFORM_GIT_URL \
  --revision FULL_40_CHARACTER_COMMIT_SHA \
  --checkout "$HOME/engineer" \
  --corpus /approved/path/to/falcon-docs \
  --services manual
```

Use `dist/` from that same platform release. No platform remote URL is assumed
or published by this project. Authentication is handled by Git; never embed
credentials in URLs. Existing checkouts are preserved and a mismatched requested
revision is rejected rather than reset. Preserve local submodule changes before
rerunning. Failed downloads/builds are reported and retained for diagnosis.

## Prerequisites and installation boundaries

`--check` reports missing tools together, checks Node/Pi versions, compiles a
small C headers/linker probe, checks the TLS trust store and runs the Librarian
server's help command to detect missing runtime dependencies. It does not
download source/packages, change persistent configuration or register/start
services. It does not prove corpus freshness, model access or service health.

Required host tools include Bash, Git, curl, tar, coreutils, diffutils, make,
a C compiler/development headers, tmux, ripgrep (`rg`), fd (`fd`), Node/npm,
Python and **Pi 1.0.3**. Forge keeps Pi offline, so these search tools must be
available on `PATH` rather than left for Pi to download at runtime.
The script reports installation guidance; it does **not** run sudo, install
Ubuntu packages, upgrade Node or replace global Pi. A typical Ubuntu OS-tools
installation, performed separately by an authorized user, is:

```sh
sudo apt-get install git curl ca-certificates build-essential libc6-dev \
  tmux python3 tar coreutils diffutils ripgrep fd-find
mkdir -p "$HOME/.local/bin"
ln -s /usr/bin/fdfind "$HOME/.local/bin/fd"
```

Ubuntu names fd's packaged executable `fdfind`; the user-local link supplies
the standard `fd` command expected by Pi. If the link already exists, inspect
it rather than replacing it blindly.

Install an approved Node.js 24.11+ and compatible npm separately. Pi can be
installed in a dedicated user-local prefix, without changing a global profile:

```sh
npm install --prefix "$HOME/.local/engi-pi" @earendil-works/pi-coding-agent@1.0.3
export PATH="$HOME/.local/engi-pi/node_modules/.bin:$PATH"
```

Librarian is an **external approved dependency**, not an automatically cloned
or distributed confidential corpus. Its supplied checkout must contain:

- `tools/context-mcp/.venv/bin/qualified-context-mcp` (working executable).
- `tools/context-index/context_index.py` (readable).

Obtain/install that dependency through its own approved process. This initial
installer uses its existing local stdio MCP interface; a remotely hosted
Librarian is not yet supported by this recipe.

After checks, the installer:

1. Initializes pinned repositories and workspace-local Go/Bun/GitHub CLI.
2. Builds all four applications using existing build helpers.
3. Creates missing private configuration under `.local/environment/`, with
   Superpowers and Librarian access in private Pi.
4. Configures **fresh** AgentsView for private Pi **usage metadata only** and
   installs the pinned Pi structured-review extension. Existing configured
   tracking/settings are preserved; incompatible unconfigured settings fail.
5. Reports Pi MCP discovery and prints manual startup/stop instructions.
6. Registers and starts user services only when explicitly selected.

The normal Forge build is the default. If its known dependency-download path
is blocked, `--forge-build local-kata` explicitly selects the existing temporary
local-source build; there is no silent fallback. See
[`context/tools.md`](../context/tools.md) for provenance and limitations.

Concurrent installers for the same checkout are rejected. Occupied service
ports abort installation before builds/configuration; the installer does not
stop existing processes. Repeated setup preserves state and refuses changes
to saved executable/corpus paths. Stop your existing services deliberately
before rebuilding; do not install over an active platform.

## Startup and credentials

Without service registration, the printed command starts all dashboards in
the foreground. From the installed checkout:

```sh
python3 scripts/local_env.py run
# Ctrl+C stops this supervisor's services; or from another terminal:
python3 scripts/local_env.py stop
```

The installer also prints independent foreground commands for each service.
Its native Kata command pins `KATA_DSN` to the installation's private database
and clears inherited `KATA_DB`, without rewriting retained configuration.
Generated Kata units and the foreground supervisor use the same private-store
boundary. Existing running units are not changed by updating these source files;
deliberate reinstallation/restart is a separate operator action.
Dashboards listen on **loopback only**:

| Service | URL |
| --- | --- |
| Forge | http://127.0.0.1:18091/ |
| Kata | http://127.0.0.1:17777/kata |
| roborev | http://127.0.0.1:17374/reviews |
| AgentsView | http://127.0.0.1:18080/ |

Opt-in service registration requires a working `systemctl --user` manager and
`systemd-analyze`. Existing unit names remain `kenn-kopy-*.service`; a unit from
another installation is rejected, not overwritten. Manage each with:

```sh
systemctl --user status kenn-kopy-forge.service --no-pager
systemctl --user start kenn-kopy-forge.service
systemctl --user stop kenn-kopy-forge.service
systemctl --user disable --now kenn-kopy-forge.service
journalctl --user -u kenn-kopy-forge.service
```

Repeat for `kata`, `roborev` and `agentsview`. User services start when the user
manager starts, normally at login. Boot without login requires separately
approved lingering/systemd configuration; the installer does not enable it or
modify WSL/system settings. `local_env.py stop` does not stop independent units.
If registration fails partway, previously enabled units may remain running.

Dashboards need no model credential. Agents need each engineer's approved
USAi connection and a private key handoff:

```sh
python3 scripts/local_env.py configure-provider \
  --base-url APPROVED_URL --model APPROVED_MODEL --api openai-completions
python3 scripts/local_env.py set-key --private-only
```

The key is entered interactively, hidden, and never supplied as a command
argument. `--private-only` leaves global Pi credentials unchanged. Do not
distribute `.local/`, credentials, sessions, databases or the confidential
Falcon corpus.

Git provider authentication/sync, repository/Kata project onboarding, active
engineering prompts and automated intake are separate work. This installer
does not authorize them or establish a multi-user/cloud security boundary.
Clean-host Ubuntu acceptance remains outstanding; prerequisite checks and
isolated regressions are not a full deployment demonstration.

## Maintainer checks

```sh
python3 -m unittest discover -s dist -p 'test_*.py'
python3 -m unittest discover -s scripts -p test_local_env.py
bash -n dist/install.sh
```
