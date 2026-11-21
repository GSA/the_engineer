# Engineer installer internals

Teammates install with `./engineer install` (see the [README](../README.md)).
This page covers the lower-level installer that `./engineer install` runs,
`dist/install.sh` / `dist/install.py`, for maintainers.

Target: **Ubuntu 24.04+ on Linux x86_64**, including WSL2 and AWS WorkSpaces.
It is a source-build installer, not a container, cloud deployment or data
bundle.

## What `./engineer install` adds

`scripts/engineer.py` adds the following around `dist/install.py --services user --guided`:

- `scripts/host_setup.py` installs missing Ubuntu packages with `sudo apt-get`
  after asking. It also installs Node.js 24.11.1 (SHA-256 pinned, only when no
  Node 24.11+ is on `PATH`), Pi `1.5.2` and, optionally, Copilot CLI `1.0.111`
  under `~/.local/engineer/`, links `fdfind` as `~/.local/bin/fd`, offers to set
  `[boot] systemd=true` in `/etc/wsl.conf` on WSL, and writes one marked block
  in `~/.bashrc`.
- `scripts/copilot_env.py` gives Copilot a private `COPILOT_HOME`
  (`.local/environment/copilot`) with the kata and kenn-forge MCP servers, the
  coder contract as instructions and Superpowers as a plugin directory, and
  launches it with USAi BYOK settings. The key is read per request through
  `scripts/usai-key.py` (`COPILOT_PROVIDER_API_KEY_COMMAND`). Only Claude
  models are offered, because in a live check GPT Sol returned 422 and Gemini
  rejected Copilot's tool schema.
- The key prompt, the GitHub sign-in, `doctor` (which wraps
  `local_env.py accept`) and the install record
  `.local/engineer-install.json`. `./engineer uninstall` reverses exactly the
  items in that record. A checkout that has `.local/environment/` but no
  record is refused by `./engineer install` and `uninstall`.

## Running `dist/install.sh` directly

```sh
bash dist/install.sh --check                      # prerequisites only; changes nothing
bash dist/install.sh --services user \
  --usai-base-url https://api.gsa.usai.gov/api/v1 --usai-model claude-sonnet-5.5 \
  --usai-review-model gpt-6.1-sol-latest-guardrails-defaultv2 \
  --register-repo ~/some-repo
```

Without `--services`, the installer asks whether to enable and start the four
user services (the default is no). `--services manual` configures everything
without registering units; then run `python3 scripts/local_env.py run` in the
foreground and `python3 scripts/local_env.py stop` from another terminal.

Librarian is optional and owner-only today; teammate installs have none. To
bind an existing instance at install time, pass
`--librarian-executable` and `--librarian-root` (plus optional
`--librarian-selection`). Use `--librarian-reader` only for a legacy release
that takes its reader as an argument. The legacy Falcon layout is still
accepted with `--corpus PATH`. Partial bindings fail rather than guessing.

`dist/install.sh` does not run `sudo` and does not install Ubuntu packages,
Node or Pi; `--check` lists what is missing. It does:

1. Initialize the pinned Forge, Kata, roborev, AgentsView and Superpowers
   submodules and the workspace-local Go, Bun, GitHub CLI and jq toolchains.
2. Build the four applications.
3. Link `~/.local/bin/kata` and select the loopback daemon in
   `~/.kata/config.toml`, link `~/.local/bin/roborev` and `~/.roborev`. It
   reuses exact existing links and stops when another install owns them.
4. Create missing private configuration under `.local/environment/`
   (Superpowers, pi-subagents and MCP for private Pi; Forge agent targets; roborev
   reviewer; AgentsView tracking of private Pi usage and guarded-Sol pricing).
5. Save the non-secret USAi connection when the `--usai-*` options are given.
6. With `--services user`, enable and start the units, run `init-repo` for
   each `--register-repo`, and print `local_env.py status`.

Reruns preserve existing state and refuse changes to saved paths. Concurrent
installers for the same checkout are rejected. Occupied ports abort before
any build.

## Services and identities

Installs record `"unit_prefix": "engineer"` in
`.local/environment/environment.json` and get these units:

```sh
systemctl --user status engineer-forge.service --no-pager
journalctl --user -u engineer-forge.service
```

Repeat for `kata`, `roborev` and `agentsview`. A unit owned by another checkout is rejected, not overwritten. User services
start with the user manager (normally at login). Starting at boot without a
login requires lingering, which the installer does not enable.

`ENGINEER_PORT_OFFSET` (for example `1000`) shifts every port, including the
`~/.kata/config.toml` client URL. `ENGINEER_RUNTIME_ROOT` selects a different
runtime checkout. See
[docs/try-in-a-second-wsl-distro.md](../docs/try-in-a-second-wsl-distro.md).

## Credentials

Dashboards need no credential. Agents need a USAi key, entered only at a hidden
prompt (`./engineer key`, or `python3 scripts/local_env.py set-key
--private-only`) and stored in `.local/environment/secrets/usai-api-key`
(`0600`). Forge's isolated GitHub login is created with `./engineer login`
(`scripts/gh-local.py auth login`). Never distribute `.local/`, credentials,
sessions or databases.

## Host acceptance

`python3 scripts/local_env.py accept [--repo PATH]...` prints `PASS`/`FAIL`
for the Pi pin and extensions, executables, pinned submodules, native links,
Pi MCP connections, each user service, the USAi provider, the presence of the
USAi key and GitHub login, and each repository's Forge registration, roborev
hook and push guard. It prints `SKIP librarian` when no Librarian is bound.
It makes no model call, changes nothing and never prints credentials.

### Disposable fresh-host run

`dist/container/run-acceptance.sh [REVISION]` builds a rootless Podman Ubuntu
24.04 image that has systemd, git, python3 and passwordless sudo and nothing
else. The run clones the revision, runs `./engineer install --yes --copilot yes`,
`./engineer add-repo ~/engineer` and `./engineer doctor`, then exits with
`doctor`'s status. Set `ENGINEER_SOURCE` to a local checkout to test an
unpushed revision; it is mounted read-only. Logs and an
`engineer.acceptance-receipt/v2` receipt go to ignored `.local/acceptance/`.
`KEEP=1` keeps the container so you can run `./engineer key` and
`./engineer login` inside it. The host must allow rootless Podman user
namespaces (`newuidmap`).

### Pins, mirrors and receipts

Before any download or build, `install.py` (including `--check`) probes that
each pinned submodule commit can be fetched from its `.gitmodules` URL and
stops with one diagnostic per pin otherwise. `--submodule-mirror NAME=URL`
supplies an owner-approved source for one run, without editing `.gitmodules`.
The agentsview pin tracks upstream `main`. When `GOPROXY` is unset, builds use
`GOPROXY=https://proxy.golang.org|direct`.

Each install writes a private, secret-free receipt to
`.local/install-receipts/install-<UTC>.json` (`engineer.install-receipt/v1`),
including on failure. It records timings per phase, prompt wait time, applied
defaults, mirrors, platform revision and pins. Add other manual fixes with
`--record-fix TEXT`.

## Maintainer checks

```sh
python3 -m unittest discover -s dist -p 'test_*.py'
python3 -m unittest discover -s scripts -p 'test_*.py'
bash -n dist/install.sh dist/container/run-acceptance.sh engineer
```
