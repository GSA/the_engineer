# The Engineer (`kenn-kopy`)

Local, loopback-only engineering workstation for agent-driven work. It bundles:

- **Forge**: workspaces, agent sessions, and PRs
- **Kata**: task tracker
- **roborev**: automated code review
- **AgentsView**: session and usage history
- **Pi**: coding agent, using GSA **USAi** models
- **Superpowers**: Pi skills

It consumes context from **The Librarian** (business documents) and
**The Knowitall** (code graphs).

GitHub: `GSA/the_engineer`. Local checkout: `~/kenn-kopy`. Kata project: `the_engineer`.
Service units still use the `kenn-kopy-*` names. Kata `eb48` tracks the rename.

## Requirements

- Ubuntu 24.04+ on x86_64, or WSL2
- Python 3.11+, Node.js 24.11+, Pi `1.4.0`
- A USAi API key
- A `falcon-docs` corpus checkout that contains `tools/context-mcp/.venv/bin/qualified-context-mcp`, passed as `--corpus`

```sh
sudo apt-get install git curl ca-certificates build-essential libc6-dev \
  tmux python3 python3-venv zstd tar coreutils diffutils ripgrep fd-find
mkdir -p ~/.local/bin && ln -sf /usr/bin/fdfind ~/.local/bin/fd
npm install --prefix ~/.local/engi-pi @earendil-works/pi-coding-agent@1.4.0
export PATH="$HOME/.local/engi-pi/node_modules/.bin:$PATH"
```

## Stand it up

Run these commands from `~/kenn-kopy`.

```sh
# 1. Fetch pinned submodules, install pinned toolchains (Go, Bun, gh, jq) in .local/tools, and build.
bash scripts/bootstrap-sources.sh
bash scripts/bootstrap-toolchains.sh
bash scripts/build.sh roborev kata agentsview forge-local-kata

# 2. Create private state in .local/environment/.
python3 scripts/local_env.py setup --corpus ~/falcon-docs \
  --forge-binary .local/forge-local-kata/kenn-forge
python3 scripts/local_env.py install-pi-extensions
python3 scripts/local_env.py configure-private-pi-tracking

# 3. Add the USAi key and load models. See the USAi sections below.
python3 scripts/local_env.py set-key
python3 scripts/local_env.py list-models --base-url https://api.gsa.usai.gov/api/v1
python3 scripts/local_env.py configure-provider --base-url https://api.gsa.usai.gov/api/v1 \
  --api openai-completions --model claude-opus-5.5 \
  --review-model gpt-6.1-sol-latest-guardrails-defaultv2

# 4. Install and start the systemd user services.
for s in kata roborev agentsview forge; do python3 scripts/local_env.py install-$s-service; done

# 5. Authenticate Forge's isolated GitHub CLI.
./scripts/gh-local.py auth login --hostname github.com --web --git-protocol https --insecure-storage
systemctl --user restart kenn-kopy-forge.service

# 6. Expose the native roborev and Kata CLIs. ~/.roborev routes roborev to this install.
ln -s "$PWD/roborev/bin/roborev" "$PWD/kata/kata" ~/.local/bin/
ln -s "$PWD/.local/environment/roborev" ~/.roborev
export PATH="$HOME/.local/bin:$PATH" KATA_SERVER="${KATA_SERVER:-http://127.0.0.1:17777}"

# 7. Register repos with Forge and install roborev Git hooks.
for repo in ~/kenn-kopy ~/the_librarian ~/the_knowitall; do
  python3 scripts/local_env.py register "$repo"
  roborev init --no-daemon --repo "$repo"
done

# 8. Check the stack.
python3 scripts/local_env.py status
```

Add the step 6 `export` to `~/.bashrc`. Step 2 tracks only Pi sessions in this
install. To also track Copilot and other Pi transcripts, run `configure-tracking`
after AgentsView is up (see `--help`), then restart `kenn-kopy-agentsview.service`.

If the host has no systemd user services, run `python3 scripts/local_env.py run`
in the foreground and use `python3 scripts/local_env.py stop` to stop it.

`dist/install.sh` is an alternate installer. It is not yet a complete fresh-host
recipe; Kata `p4ke` tracks the gaps. See [dist/README.md](dist/README.md).

## Isolated WSL2 instance and two-layer isolation

MVP reproduction and demo rehearsals (`the_engineer#n0vk`, `the_engineer#t592`)
use two layers instead of containers. Containers would break `systemd --user`
units, Forge worktree paths, and Librarian's absolute index paths
(`the_librarian` Decision 0004).

1. **Layer 1 (`n0vk`)**: Keep `~/the_librarian` and `~/the_knowitall` free of
   data. Clone separate instances (`~/falcon-librarian-mvp`,
   `~/falcon-knowitall-mvp`) with private `.local/` stores for
   `~/falcon-docs/INBOX/` and `~/falcon/*`.
2. **Layer 2 (`t592`)**: A second WSL2 Ubuntu 24.04 distro, `engineer-mvp`, on
   the same Windows host. It has its own files, users, and services.

### Ports are shared with your primary distro

All WSL2 distros run in one VM and share one network namespace
([Microsoft: What is WSL](https://learn.microsoft.com/windows/wsl/about)).
`127.0.0.1` in `engineer-mvp` is the same `127.0.0.1` as in your primary distro.
The default ports would collide, or silently reach your primary services.

Set `KENN_KOPY_PORT_OFFSET=1000` in `engineer-mvp` before `setup` or
`dist/install.sh`. `setup` saves it in `environment.json`, so services and later
commands use it. A different value later is an error. The offset must be a
non-negative integer that does not overlap the default ports.

| Service | Primary distro | `engineer-mvp` (offset 1000) |
| --- | --- | --- |
| Forge (MCP) | 18091 (18092) | 19091 (19092) |
| Kata | 17777 | 18777 |
| roborev API, UI | 17373, 17374 | 18373, 18374 |
| AgentsView | 18080 | 19080 |

Both stacks can run at once. Do not stop the primary services.

### Create a clean instance

This needs WSL 2.4.10 or later for Ubuntu's image format. Check with
`wsl --version`. Run in PowerShell. Keep the files under `%LOCALAPPDATA%`,
which OneDrive does not sync.

```powershell
$dir = "$env:LOCALAPPDATA\engineer-wsl"
New-Item -ItemType Directory -Force -Path $dir
wsl --install Ubuntu-24.04 --name engineer-mvp --location "$dir\engineer-mvp"
```

The first launch asks for a user name and password. Set a real password;
`sudo` needs it. Without Microsoft Store access, download the
`ubuntu-24.04.*-wsl-amd64.wsl` image and `SHA256SUMS` from
https://releases.ubuntu.com/noble/, check the hash, and use
`wsl --install --from-file <image>.wsl --name engineer-mvp --location "$dir\engineer-mvp"`.

Inside `engineer-mvp`, enable systemd and keep your user as the default after
an import:

```sh
printf '[boot]\nsystemd=true\n[user]\ndefault=%s\n' "$USER" | sudo tee /etc/wsl.conf
```

Then save the clean baseline from PowerShell. It holds only the stock image and
your account. No repos, keys, or logins.

```powershell
wsl --terminate engineer-mvp
wsl --export engineer-mvp "$dir\engineer-mvp-base.tar"
```

### Stand it up inside `engineer-mvp`

```sh
export KENN_KOPY_PORT_OFFSET=1000
export KATA_SERVER=http://127.0.0.1:18777
```

Add both lines to `~/.bashrc` in `engineer-mvp`. Then follow
[Requirements](#requirements) and [Stand it up](#stand-it-up). `KATA_SERVER` keeps the native `kata` CLI off the primary Kata. Check that
`python3 scripts/local_env.py status` shows `"port_offset": 1000`.
Knowitall has no MCP server yet (`the_knowitall#vz6q`).

### Snapshots and reset

A snapshot taken after `set-key` and `gh-local.py auth login` contains the USAi
key and the GitHub token. Treat it as a secret. Keep it only under
`%LOCALAPPDATA%`. Never copy it to OneDrive, shared drives, Git, or chat.
Delete it when the rehearsal is over.

```powershell
# $dir is "$env:LOCALAPPDATA\engineer-wsl", as above. Save the ready (secret) snapshot:
wsl --terminate engineer-mvp
wsl --export engineer-mvp "$dir\engineer-mvp-ready.tar"

# Reset to it. Use engineer-mvp-base.tar instead to start clean.
wsl --unregister engineer-mvp
wsl --import engineer-mvp "$dir\engineer-mvp" "$dir\engineer-mvp-ready.tar" --version 2
```

After a reset, open `engineer-mvp` and run `python3 scripts/local_env.py status`.
Use the offset URLs in the demo: Forge http://127.0.0.1:19091/ and Kata
http://127.0.0.1:18777/kata.

## Services

| Service | URL | Unit |
| --- | --- | --- |
| Forge | http://127.0.0.1:18091/ (MCP `:18092/mcp`) | `kenn-kopy-forge.service` |
| Kata | http://127.0.0.1:17777/kata | `kenn-kopy-kata.service` |
| roborev | http://127.0.0.1:17374/reviews (API `:17373`) | `kenn-kopy-roborev.service` |
| AgentsView | http://127.0.0.1:18080/ | `kenn-kopy-agentsview.service` |

All services bind to `127.0.0.1`. `KENN_KOPY_PORT_OFFSET` shifts every port; see
[Ports are shared with your primary distro](#ports-are-shared-with-your-primary-distro).

## Configuration reference

All state is under `.local/environment/`. Git ignores that directory, and the
files are private (`0600`/`0700`). Set `KENN_KOPY_RUNTIME_ROOT` to use a
different root.

| File | Purpose |
| --- | --- |
| `environment.json` | Corpus path, Forge binary, Pi executable and version, and any `port_offset`, written by `setup` |
| `secrets/usai-api-key` | USAi API key. This is the only place the key is stored. |
| `usai.json` | Active coder `model` and `review_model` |
| `usai-models.json` | Last model catalog fetched from USAi |
| `pi/models.json` | Pi `usai` provider: base URL, API type, and models. The key field is the `${USAI_API_KEY}` placeholder. |
| `pi/settings.json` | Pi default provider and model, Superpowers package, and subagent defaults (`model: inherit`) |
| `pi/mcp.json` | Pi MCP servers: `falcon-context` (Librarian-style corpus), `kata`, and `kenn-forge` |
| `forge/config.toml` | Forge host and port, MCP, and agent launchers `pi` (default model) and `pi-argon` (`gemini-4-argon`) |
| `roborev/config.toml` | Daemon address, `pi` agent command, and reviewer model (linked from `~/.roborev`) |
| `kata/config.toml` | Kata listen address |
| `gh/` | Isolated GitHub CLI login used by Forge and `scripts/gh-local.py` |
| `systemd/` | Generated user units |

Each repo has its own `.roborev.toml` (agent `pi`, reviews every 5 commits) and
`.kata.toml` (Kata project binding).

## Task-bound business and code evidence

`engineer-task-context` composes one task-bound evidence packet from the
configured Librarian business corpus and a revision-bound Knowitall code
generation. It is a read-only consumer: it never acquires sources, indexes,
extracts, or publishes, and it never mutates a Kata task.

Install it into a private virtual environment (Python 3.12 or newer) and write
an `engineer.context-config/v1` file naming the explicit providers:

```json
{
  "schema": "engineer.context-config/v1",
  "librarian": {"project_id": "<business project>", "executable": "<librarian-mcp>",
                "root": "<corpus root>", "reader": null, "selection": null},
  "knowitall": {"project_id": "<code project>", "repository_id": "<repository>",
                "python": "<venv>/bin/python", "store": "<publication store>"}
}
```

The Knowitall store must already be a published store: an incomplete directory
is refused rather than initialized, because collection never writes provider
state. `knowitall.python` names the interpreter that owns
`knowitall-code-context` 0.1.0; Engineer itself need not be installed there,
because the provider-side bridge runs by path. A failing exchange reports which
prerequisite is missing.

Relative paths resolve against the configuration file. Interpreter and server
program paths keep the link you select, so a virtual environment's `bin/python`
runs with that environment's prefix. Paths may contain spaces; every provider
launch uses an argument list, never a shell. Leave `librarian.reader` null for a
current Librarian toolkit, which loads its reader module from `root` and refuses
an explicit `--reader`; set it only for a legacy release that requires that
argument.

```sh
engineer-context collect --config binding.json --request request.json --output packet.json
engineer-context report --packet packet.json
engineer-context revalidate --config binding.json --packet packet.json --task task.json --output recheck.json
```

`collect` exits 0 only when every required business locator and code query
returned evidence; it exits 2 when the packet is blocked and 1 on invalid input
or I/O. A code query that the owning contract would reject, such as one missing
`query`, naming an unsupported match or carrying a cursor whose binding
changed, is invalid caller input and exits 1 instead of becoming an optional
availability gap. `report` renders provenance, gaps and readiness; `--json` emits the
machine form; raise `--max-bytes` when a packet exceeds the 1 MiB default.
`revalidate` rechecks the whole qualified response and current
required code identity against a sealed packet without changing it. A truncated
code response's `continuation` token can be sent back in a later request to
read the next page of the same generation. A single page is only partial
evidence, so a required paged query is ready only when the packet holds the
whole chain of pages for that query and generation; a lone page is reported as
blocked with the other pages absent. Revalidating a paged request replays it
unchanged and rechecks currency with a separate pinned probe, so held page
tokens keep their own binding.

Packets preserve full provider responses, exact passages, locators, source
hashes, line ranges, snapshot/generation identities, coverage and handling
restrictions. Rendition pieces report their original source location next to
the indexed extraction range, so citations name the real location. Business/code
pairs are only ever `unasserted`: a name or
presentation match never establishes an assertion. Assertions and contributions
are reported as unavailable capabilities pending `the_librarian#923h` and
`the_librarian#rjr5`. Packets can carry restricted source text, so write them
only to private paths and never paste them into shared channels.

Agents reach the same three read-only operations through a stdio MCP server
configured once at startup:

```sh
engineer-context-mcp --config binding.json
```

Verify an actual Pi session's discovery and qualified read without any model
call, writing a private receipt:

```sh
node scripts/verify-context-runtime.mjs <pi-install> <private agent dir> \
  <engineer-context-mcp> <config> <request> <receipt.json>
```

## USAi key management and rotation

- `set-key` prompts for the key with hidden input. It rejects keys passed as an
  argument or piped in. The key is written only to `secrets/usai-api-key` (`0600`).
- `scripts/pi-local.py` reads the key file on every launch and passes the key
  only to that Pi process as `USAI_API_KEY`. Config files never contain the key.
- `set-key` also points any existing global Pi USAi provider in `~/.pi/agent/`
  to `scripts/usai-key.py`, so global Pi reads the same file. Pass
  `--private-only` to skip that.

To rotate the key:

```sh
python3 scripts/local_env.py set-key        # paste the new key
python3 scripts/local_env.py list-models --base-url https://api.gsa.usai.gov/api/v1   # verify that the key works
```

New Forge agent sessions and roborev reviews use the new key automatically, and
no service restart is needed. Restart any Pi sessions that are already running,
such as the tmux `pi` session or open Forge workspaces. A USAi HTTP `401` means
the key is expired or revoked; rotate it as shown above.

## Loading and changing USAi models

1. `list-models` fetches `/models` from USAi into `usai-models.json`. It only
   lists models; it does not test them.
2. `configure-provider` writes every chat model (the built-in list plus the
   fetched catalog) to `pi/models.json` and skips embedding models. It also sets
   the coder default in `pi/settings.json` and `usai.json`, and syncs the
   reviewer model to `roborev/config.toml`.
3. The coder and the reviewer must come from different model families (Claude,
   OpenAI, or Gemini), and both must appear in the fetched catalog.
4. `pi-local.py --model` accepts only the coder model, the reviewer model, or
   `gemini-4-argon`. To use another model, run `configure-provider` again.

To add newly published models or switch the coder or reviewer, run steps 1 and
2 again, then run `systemctl --user restart kenn-kopy-roborev.service`.

## Daily use

```sh
python3 scripts/terminal-local.py open pi        # persistent tmux session; run scripts/pi-local.py inside it
python3 scripts/terminal-local.py open copilot   # Copilot CLI, for non-sensitive work
kata ready --no-label blocked --no-label deferred --agent && kata claim <id>
roborev review --repo "$PWD" --branch --wait     # one branch review before opening a PR
```

In Forge, create a workspace from a Kata task and launch **Pi (USAi)** or
**Pi (Gemini 4 Argon)**. The Forge workspace extension pushes the branch, opens
the PR, and registers the PR and Kata task in Forge.

## Maintenance

- **Back up:** `python3 scripts/backup_workspace.py <dest-dir>` creates a
  verified `.tar.zst` archive of the workspace, including SQLite snapshots.
- **Run tests:** `python3 -m unittest discover -s scripts -p 'test_*.py'` and the
  same command with `-s dist`.
- **Run smoke tests:** stop the four services, run
  `python3 scripts/smoke.py --forge-binary .local/forge-local-kata/kenn-forge`,
  then start the services again. The smoke tests use the same ports.
- **Keep secrets out of Git:** never put credentials in Git, logs, or command
  arguments.

More detail: [context/tools.md](context/tools.md),
[context/status.md](context/status.md), and
[context/system-architecture.md](context/system-architecture.md).
