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

Run these commands from `~/kenn-kopy`. `dist/install.sh` fetches the pinned
submodules and toolchains (Go, Bun, gh, jq in `.local/tools`), builds the four
services, creates private state in `.local/environment/`, links the native
`kata` and `roborev` CLIs (`~/.local/bin`, `~/.kata/config.toml`, `~/.roborev`),
saves the USAi connection, starts the systemd user services, registers repos
with Forge, and installs roborev Git hooks. It stops rather than replace links
or settings that belong to another install, and reruns keep existing state.
See [dist/README.md](dist/README.md) for every option.

```sh
# 1. Check prerequisites, then install.
bash dist/install.sh --check --corpus ~/falcon-docs
bash dist/install.sh --corpus ~/falcon-docs --forge-build local-kata --services user \
  --usai-base-url https://api.gsa.usai.gov/api/v1 --usai-model claude-opus-5.5 \
  --usai-review-model gpt-6.1-sol-latest-guardrails-defaultv2 \
  --register-repo ~/kenn-kopy --register-repo ~/the_librarian

# 2. Enter the USAi key (hidden prompt). To add models beyond the built-in list,
#    see "Loading and changing USAi models" below.
python3 scripts/local_env.py set-key

# 3. Authenticate Forge's isolated GitHub CLI.
./scripts/gh-local.py auth login --hostname github.com --web --git-protocol https --insecure-storage
systemctl --user restart kenn-kopy-forge.service

# 4. Accept the host: read-only PASS/FAIL per check, nonzero exit until done.
python3 scripts/local_env.py accept --repo ~/kenn-kopy --repo ~/the_librarian
python3 scripts/local_env.py status
```

`accept` checks the Pi pin and extensions, built executables, pinned
submodule gitlinks, the native `kata`/`roborev` links, Pi MCP connections, all
four user services, the saved USAi provider, the presence of the private USAi
key and GitHub login (values are never printed), and, for each `--repo`, the
Forge registration and roborev post-commit hook. It makes no model call and
changes no service. Run it from a login shell so `systemctl --user` can reach
the user manager.

Add `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc`; the installer does
not edit shell files. The install tracks only Pi sessions from this install. To
also track Copilot and other Pi transcripts, run `configure-tracking` after
AgentsView is up (see `--help`), then restart `kenn-kopy-agentsview.service`.

If the host has no systemd user services, install with `--services manual`, run
`python3 scripts/local_env.py run` in the foreground, and use
`python3 scripts/local_env.py stop` to stop it. Register each repo afterwards
with `python3 scripts/local_env.py register <repo>` and
`(cd <repo> && roborev init --no-daemon)`.

## Isolated Librarian MVP instance (Layer 1)

Keep `~/the_librarian` free of customer or corpus data. MVP demos use a separate
instance (`~/falcon-librarian-mvp`) with private `.local/` stores (`LCAT`,
`LREV`, `LCTX`) and ignored `config/policy.local.json` and
`config/selection.local.json` for `~/falcon-docs/INBOX/` and `~/falcon/*`:

```sh
python3 scripts/local_env.py provision-librarian-mvp \
  --source ~/the_librarian --dest ~/falcon-librarian-mvp \
  --inbox ~/falcon-docs/INBOX --repos-root ~/falcon --bind-mcp
```

`--bind-mcp` routes the `falcon-context` MCP server in `scripts/pi-local.py` to
that instance. To bind later, run
`python3 scripts/local_env.py configure-librarian --librarian-root ~/falcon-librarian-mvp`.

A second WSL2 distro for rehearsals (Layer 2, `the_engineer#t592`) is deferred
until after the MVP; see [docs/wsl2-rehearsal.md](docs/wsl2-rehearsal.md).

## Services

| Service | URL | Unit |
| --- | --- | --- |
| Forge | http://127.0.0.1:18091/ (MCP `:18092/mcp`) | `kenn-kopy-forge.service` |
| Kata | http://127.0.0.1:17777/kata | `kenn-kopy-kata.service` |
| roborev | http://127.0.0.1:17374/reviews (API `:17373`) | `kenn-kopy-roborev.service` |
| AgentsView | http://127.0.0.1:18080/ | `kenn-kopy-agentsview.service` |

All services bind to `127.0.0.1`. `KENN_KOPY_PORT_OFFSET` shifts every port; see
[docs/wsl2-rehearsal.md](docs/wsl2-rehearsal.md#ports-are-shared-with-your-primary-distro).

## Configuration reference

All state is under `.local/environment/`. Git ignores that directory, and the
files are private (`0600`/`0700`). Set `KENN_KOPY_RUNTIME_ROOT` to use a
different root.

| File | Purpose |
| --- | --- |
| `environment.json` | Corpus path, Forge binary, Pi executable and version, and any `port_offset`, written by `setup`; rerunning `setup` after upgrading the saved Pi executable in place updates only an older `pi_version` |
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
call, writing a private receipt. The probe connects only the server it
registers, so your own `mcp.json` entries are neither launched nor able to
shadow it:

```sh
node scripts/verify-context-runtime.mjs <pi-install> <private agent dir> \
  <engineer-context-mcp> <config> <request> <receipt.json>
```

## Manual Jira-to-Kata intake

`scripts/jira-intake.py` turns one owner-supplied Jira XML export (Jira's
"Export > XML" for a single issue) into human-approved Kata tasks. The full
contract is in `context/jira-intake.md`.

```sh
# 1. Retain the export privately (.local/jira-intake/<KEY>/, mode 0600).
scripts/jira-intake.py init ~/Downloads/CCSMFSSM-1290.xml \
  --access-path "owner-supplied XML export"

# 2. Record approved refinements, assumptions, questions and tasks.
$EDITOR .local/jira-intake/CCSMFSSM-1290/intake.toml

# 3. Validate, review the kata commands, then create the tasks.
scripts/jira-intake.py check  .local/jira-intake/CCSMFSSM-1290/intake.toml
scripts/jira-intake.py record .local/jira-intake/CCSMFSSM-1290/intake.toml
scripts/jira-intake.py record .local/jira-intake/CCSMFSSM-1290/intake.toml --apply
```

Each created task carries the ticket key, URL, export SHA-256, original
description and acceptance criteria, approved refinements, assumptions,
Librarian grounding and `jira.*` metadata. A task with
`adopt = "<project>#<id>"` (and optional `pull_request`) attaches that
traceability to an existing Kata task instead of creating one. Launch work on a task from
**Forge > Workspaces > New workspace**.

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
- **Verify prompt, temporary-plan, and publication gates:** run
  `python3 scripts/workflow-gates.py check-plans --repo . --base main` to verify
  no temporary working plans/specs remain under `.local/plans/` or
  `docs/superpowers/`, or `python3 scripts/workflow-gates.py demo` to run the
  non-model synthetic task demonstration across `private_pi`, `forge_workspace`,
  and `roborev_review`.
- **Run smoke tests:** stop the four services, run
  `python3 scripts/smoke.py --forge-binary .local/forge-local-kata/kenn-forge`,
  then start the services again. The smoke tests use the same ports.
- **Keep secrets out of Git:** never put credentials in Git, logs, or command
  arguments.

More detail: [context/tools.md](context/tools.md),
[context/status.md](context/status.md), and
[context/system-architecture.md](context/system-architecture.md).
