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
python3 scripts/local_env.py configure-tracking --copilot-dir ~/.copilot \
  --pi-dir ~/.pi/agent/sessions --pi-dir "$PWD/.local/environment/pi/sessions" \
  --archive-content transcripts

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

# 6. Register repos with Forge and install roborev Git hooks.
for repo in ~/kenn-kopy ~/the_librarian ~/the_knowitall; do
  python3 scripts/local_env.py register "$repo"
  roborev init --no-daemon --repo "$repo"
done

# 7. Check the stack.
python3 scripts/local_env.py status
```

If the host has no systemd user services, run `python3 scripts/local_env.py run`
in the foreground and use `python3 scripts/local_env.py stop` to stop it.

`dist/install.sh` is an alternate installer. It is not yet a complete fresh-host
recipe; Kata `p4ke` tracks the gaps. See [dist/README.md](dist/README.md).

## Isolated WSL2 instance and two-layer isolation

For MVP reproduction, intake, and demo rehearsals (`the_engineer#n0vk` and
`the_engineer#t592`), we use a **two-layer isolation strategy** rather than
containerizing individual stdio MCP processes (which breaks `systemd --user`
units, Forge worktree paths, and Librarian's absolute-path index bindings per
`the_librarian` Decision 0004):

1. **Layer 1 — Full-clone MVP instances (`the_engineer#n0vk`)**: Keep upstream
   `~/the_librarian` and `~/the_knowitall` data-empty; unpack/clone dedicated
   program instances (`~/falcon-librarian-mvp` and `~/falcon-knowitall-mvp`)
   with private `.local/` stores pointing to `~/falcon-docs/INBOX/` and
   `~/falcon/*`.
2. **Layer 2 — Dedicated WSL2 Ubuntu 24.04 instance (`the_engineer#t592`)**:
   Create a separate WSL2 distribution on the same Windows host to test clean
   reproduction and run demos without touching your primary WSL environment.

### Creating, snapshotting, and resetting an isolated WSL2 instance

Run these commands in **Windows PowerShell**:

```powershell
# 1. Create a host directory and export a clean Ubuntu 24.04 base rootfs
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\wsl\engineer-mvp"
wsl --export Ubuntu-24.04 "$env:USERPROFILE\wsl\ubuntu-24.04-base.tar"

# 2. Import the isolated 'engineer-mvp' WSL2 instance
wsl --import engineer-mvp "$env:USERPROFILE\wsl\engineer-mvp" "$env:USERPROFILE\wsl\ubuntu-24.04-base.tar" --version 2

# 3. Create the operator account and enable systemd
wsl -d engineer-mvp -u root -- bash -c '
  useradd -m -s /bin/bash -G sudo nkirrish &&
  passwd -d nkirrish &&
  printf "[boot]\nsystemd=true\n\n[user]\ndefault=nkirrish\n" > /etc/wsl.conf
'

# 4. Restart the instance so systemd --user initializes, then open a shell
wsl --terminate engineer-mvp
wsl -d engineer-mvp
```

After completing [Stand it up](#stand-it-up) inside `engineer-mvp`, export a
verified pre-demo snapshot from PowerShell so you can reset to a clean baseline
in under two minutes:

```powershell
# Save a verified pre-demo snapshot
wsl --terminate engineer-mvp
wsl --export engineer-mvp "$env:USERPROFILE\wsl\engineer-mvp-ready.tar"

# Reset to the clean pre-demo baseline at any time
wsl --unregister engineer-mvp
wsl --import engineer-mvp "$env:USERPROFILE\wsl\engineer-mvp" "$env:USERPROFILE\wsl\engineer-mvp-ready.tar" --version 2
```

## Services

| Service | URL | Unit |
| --- | --- | --- |
| Forge | http://127.0.0.1:18091/ (MCP `:18092/mcp`) | `kenn-kopy-forge.service` |
| Kata | http://127.0.0.1:17777/kata | `kenn-kopy-kata.service` |
| roborev | http://127.0.0.1:17374/reviews (API `:17373`) | `kenn-kopy-roborev.service` |
| AgentsView | http://127.0.0.1:18080/ | `kenn-kopy-agentsview.service` |

All services bind to `127.0.0.1`.

## Configuration reference

All state is under `.local/environment/`. Git ignores that directory, and the
files are private (`0600`/`0700`). Set `KENN_KOPY_RUNTIME_ROOT` to use a
different root.

| File | Purpose |
| --- | --- |
| `environment.json` | Corpus path, Forge binary, Pi executable and version, written by `setup` |
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
