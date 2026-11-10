# Engineer installer

Engineer is the selected product name. Existing installations retain their
current paths, `engi-platform` Kata binding and `kenn-kopy-*` service names;
directory and runtime-identity migration is deferred.

Initial target: **Ubuntu on Linux x86_64**, including Ubuntu under WSL.
Python 3.11+ and Node.js 24.11+ are required; Ubuntu 24.04+ is the recommended
starting point. This is a source-build installer, not a container, cloud
deployment or confidential-data bundle.

**Known gaps (2026-10-29):** omitted Librarian options retain the legacy Falcon
layout described below. The data-empty Librarian toolkit is available through
an explicit opt-in binding; it is not selected or migrated automatically.
The installer provisions the native Kata CLI and client target, and
`local_env.py accept` verifies a finished host read-only; a clean Ubuntu
full-host run remains part of Kata `p4ke`. See the
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
Explicit service alternatives:

```sh
bash dist/install.sh --corpus /approved/path/to/falcon-docs --services manual
bash dist/install.sh --corpus /approved/path/to/falcon-docs --services user
```

To select a data-empty Librarian toolkit instead of the legacy Falcon command,
supply its executable and data root together. Selection remains optional and is
passed through only when explicitly supplied; add `--librarian-reader` only for
a legacy release that still takes its reader CLI as an argument:

```sh
bash dist/install.sh --check \
  --corpus /approved/path/to/the_librarian \
  --librarian-executable /approved/path/to/the_librarian/.venv/bin/librarian-mcp \
  --librarian-root /approved/path/to/the_librarian \
  --librarian-selection /approved/path/to/the_librarian/config/selection.local.json
```

Use the same options without `--check` for installation. Omit
`--librarian-selection` to retain that toolkit instance's default manifest.
Partial explicit bindings fail rather than guessing a command or root.

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
Python and **Pi 1.5.0**. Forge keeps Pi offline, so these search tools must be
available on `PATH` rather than left for Pi to download at runtime.
The script reports installation guidance; it does **not** run sudo, install
Ubuntu packages, upgrade Node or replace global Pi. A typical Ubuntu OS-tools
installation, performed separately by an authorized user, is:

```sh
sudo apt-get install git curl ca-certificates build-essential libc6-dev \
  tmux python3 python3-venv tar coreutils diffutils ripgrep fd-find
mkdir -p "$HOME/.local/bin"
ln -s /usr/bin/fdfind "$HOME/.local/bin/fd"
```

Ubuntu names fd's packaged executable `fdfind`; the user-local link supplies
the standard `fd` command expected by Pi. If the link already exists, inspect
it rather than replacing it blindly.

Install an approved Node.js 24.11+ and compatible npm separately. Pi can be
installed in a dedicated user-local prefix, without changing a global profile:

```sh
npm install --prefix "$HOME/.local/engi-pi" @earendil-works/pi-coding-agent@1.5.0
export PATH="$HOME/.local/engi-pi/node_modules/.bin:$PATH"
```

Librarian is an **external approved dependency**, not an automatically cloned
or distributed confidential corpus. With no explicit binding options, its
supplied checkout must contain:

- `tools/context-mcp/.venv/bin/qualified-context-mcp` (working executable).
- `tools/context-index/context_index.py` (readable).

That omitted-option route preserves existing Falcon commands and saved
configuration shape. The explicit toolkit route requires a readable root and a
working executable; an explicitly supplied legacy reader or selected manifest
must also be readable. Preflight runs the selected executable's `--help` to
expose missing
runtime dependencies. Setup saves the exact selected binding and refuses later
mismatches instead of probing aliases or silently migrating it. Reruns preserve
unrelated MCP entries and existing state.

Obtain/install the dependency through its own approved process. Both routes use
local stdio MCP; a remotely hosted Librarian is not supported by this recipe.

After checks, the installer:

1. Initializes pinned repositories and workspace-local Go/Bun/GitHub CLI.
2. Builds all four applications using existing build helpers.
3. Creates the native `~/.local/bin/kata` symlink and selects the loopback
   daemon in `~/.kata/config.toml`. Exact existing targets are reused;
   conflicting binaries or daemon selections stop installation. Unrelated
   settings and credentials are preserved, and shell startup files are not
   changed.
4. Creates missing private configuration under `.local/environment/`, with
   Superpowers and Librarian access in private Pi.
5. Configures **fresh** AgentsView for private Pi **usage metadata only** and
   installs the pinned Pi structured-review extension. Existing configured
   tracking/settings are preserved; incompatible unconfigured settings fail.
6. Links the native `~/.local/bin/roborev` CLI and `~/.roborev` (this
   install's roborev state). Exact existing links are reused; any other file,
   directory or link at either path stops installation before builds.
7. Optionally saves the non-secret USAi connection (`--usai-base-url`,
   `--usai-model`, optional `--usai-review-model`, `--usai-api`) through
   `configure-provider`. No key is read and no model call is made.
8. Reports Pi MCP discovery and prints manual startup/stop instructions.
9. Registers and starts user services only when explicitly selected. With
   `--services user`, each repeatable `--register-repo PATH` (an existing Git
   checkout) is registered with Forge and receives roborev Git hooks
   (`roborev init --no-daemon`), then `local_env.py status` runs.
10. Prints the `local_env.py accept` command (with each `--register-repo` as
    `--repo`) to run after the interactive credential steps.

Forge is built from the pinned `forge/` submodule (`scripts/build.sh forge`).

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
The installed CLI at `~/.local/bin/kata` selects the loopback client target in
`~/.kata/config.toml`. The installer does not edit shell startup files; invoke
that path directly or add `~/.local/bin` to `PATH` yourself if needed.
Dashboards listen on **loopback only**:

| Service | URL |
| --- | --- |
| Forge | http://127.0.0.1:18091/ |
| Kata | http://127.0.0.1:17777/kata |
| roborev | http://127.0.0.1:17374/reviews |
| AgentsView | http://127.0.0.1:18080/ |

Export `KENN_KOPY_PORT_OFFSET` (for example `1000`) before installing to shift
every port, including the `~/.kata/config.toml` client URL. A second WSL2
distro needs this because it shares `127.0.0.1` with the first; see
[docs/wsl2-rehearsal.md](../docs/wsl2-rehearsal.md).

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
USAi connection and a private key handoff. Pass the `--usai-*` installer
options, or configure the connection afterwards; then enter the key:

```sh
python3 scripts/local_env.py configure-provider \
  --base-url APPROVED_URL --model APPROVED_MODEL --api openai-completions
python3 scripts/local_env.py set-key --private-only
```

The key is entered interactively, hidden, and never supplied as a command
argument. `--private-only` leaves global Pi credentials unchanged. Do not
distribute `.local/`, credentials, sessions, databases or the confidential
Falcon corpus.

Git provider authentication (`scripts/gh-local.py auth login`), Kata project
onboarding, active engineering prompts and automated intake are separate work. This installer
does not authorize them or establish a multi-user/cloud security boundary.
## Host acceptance

After installation and the credential steps, run the read-only check:

```sh
python3 scripts/local_env.py accept --repo ~/kenn-kopy
```

It prints `PASS`/`FAIL` for the Pi pin and extensions, executables, pinned
submodules, native links, Pi MCP connections, each user service, the USAi
provider, USAi key and GitHub login presence, and each `--repo`'s Forge
registration and roborev hook, with the next command for each failure. It
exits nonzero while any check fails and never prints credential values.
### Disposable fresh-host run

`dist/container/run-acceptance.sh [REVISION]` builds a rootless Podman Ubuntu
24.04 image with systemd, clones the pushed revision, runs
`dist/install.sh --check`, a full `--services user --register-repo` install
against a synthetic corpus, then `accept`, and exits with `accept`'s status. Logs go to ignored
`.local/acceptance/`. `KEEP=1` keeps the container for the interactive
`set-key` and `gh-local.py auth login` steps; `GOPROXY` is forwarded (use
`https://proxy.golang.org|direct` behind a TLS proxy that returns 403 for
some modules).

Set `SUBMODULE_MIRRORS="agentsview=/path/or/URL"` to supply an owner-approved
source for a pin that upstream cannot serve (host paths are mounted read-only;
nothing is published). Each run writes `*.json` (`engineer.acceptance-receipt/v1`:
revision, elapsed and per-phase seconds, `accept` exit, mirrors) beside the log and
copies the installer's own receipt out of the container.

On 2026-11-01 revision `8bfdd6d` installed end to end and `accept` passed
12/14; the two failures are the expected missing USAi key and GitHub login.
That run fetched the `agentsview` pin from a local mirror, because the pin was
not published on `kenn-io/agentsview`. The pin now names a commit published on
the `biggestbinary/agentsview` fork, which the installer uses as its built-in
default `agentsview` mirror until the carried pricing commit lands upstream.

### Pin preflight, mirrors and receipts

Before any download or build, `install.py` (including `--check`) probes that
each pinned repository's gitlink commit is fetchable from its `.gitmodules`
URL (or a supplied mirror), and otherwise stops with one diagnostic per pin
naming the repository, commit, source and the owner decision needed. It never
pushes, publishes, resets or edits `.gitmodules`. After the owner publishes a
commit (for example `git -C agentsview push APPROVED_REMOTE_URL
49b1c6c8...:refs/heads/APPROVED_BRANCH`), either move the gitlink or rerun with
`--submodule-mirror agentsview=APPROVED_REMOTE_URL`; the mirror is applied only
to that run through git's `url.<mirror>.insteadOf` environment settings.

`agentsview` defaults to the owner-approved mirror
`https://github.com/biggestbinary/agentsview.git`, so a clean install needs no
flag; an explicit `--submodule-mirror agentsview=URL` replaces it (pass the
`.gitmodules` URL to fetch from upstream directly). The installer prints the
default it applied and records it in the receipt's `applied_defaults` and
`submodule_mirrors`. Other repositories have no default mirror.

Source and build steps run with `GOPROXY=https://proxy.golang.org|direct` when
`GOPROXY` is unset (`proxy,direct` only falls back on 404/410, so a TLS proxy's
403 for `go.kenn.io` stops the build); an explicit `GOPROXY` is preserved.

Each install writes a private secret-free receipt to
`.local/install-receipts/install-<UTC>.json` (`engineer.install-receipt/v1`),
also on failure: UTC start/finish and elapsed seconds, per-phase seconds
(`pin-preflight`, `sources`, `toolchains`, `build`, ...), hands-on seconds
(interactive prompt wait), `manual_fixes` from repeatable `--record-fix TEXT`,
applied defaults such as the GOPROXY value and default mirrors, mirrors, platform revision and pins.
Operators add other hands-on minutes and workarounds with `--record-fix`
or in the Kata `ef0w` record; credential steps are timed separately by hand.

## Maintainer checks

```sh
python3 -m unittest discover -s dist -p 'test_*.py'
python3 -m unittest discover -s scripts -p test_local_env.py
bash -n dist/install.sh
```
