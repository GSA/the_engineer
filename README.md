# The Engineer (`kenn-kopy`)

Local, loopback-only engineering workstation for agent-driven work. It bundles:

- **Forge**: workspaces, agent sessions, and PRs
- **Kata**: task tracker
- **roborev**: automated code review
- **AgentsView**: session and usage history
- **Pi**: coding agent, using GSA **USAi** models
- **Superpowers**: Pi skills

It consumes business context from **The Librarian** and ships a dependency-free
cross-repository seam scanner (`engineer-seams`) for code that spans repositories.

GitHub: `GSA/the_engineer`. Local checkout: `~/kenn-kopy`. Kata project: `the_engineer`.
Service units still use the `kenn-kopy-*` names. Kata `eb48` tracks the rename.

## Requirements

- Ubuntu 24.04+ on x86_64, or WSL2
- Python 3.11+, Node.js 24.11+, Pi `1.5.0`
- A USAi API key
- An approved local corpus path, passed as `--corpus` (always required).
  The default legacy `falcon-docs` binding requires
  `tools/context-mcp/.venv/bin/qualified-context-mcp` and
  `tools/context-index/context_index.py` beneath that path. To use an explicit
  Librarian toolkit instead, also pass `--librarian-executable` and
  `--librarian-root`; the legacy files are not required for that binding.

```sh
sudo apt-get install git curl ca-certificates build-essential libc6-dev \
  tmux python3 python3-venv tar coreutils diffutils ripgrep fd-find
mkdir -p ~/.local/bin && ln -sf /usr/bin/fdfind ~/.local/bin/fd
npm install --prefix ~/.local/engi-pi @earendil-works/pi-coding-agent@1.5.0
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
  --usai-base-url https://api.gsa.usai.gov/api/v1 --usai-model claude-sonnet-5.5 \
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

`python3 scripts/local_env.py verify-pi-policy [--cwd PATH]` shows the
instructions, skills and Forge policy that coder Pi and roborev's structured
review Pi load at `PATH`, failing if a review would inherit coder policy or the
installed coder contract differs from `scripts/pi-coder-contract.md` (rerun
`setup` to reinstall it). It exits before any model request.

`python3 scripts/local_env.py verify-handoff WORKSPACE_ID [--commit SHA]`
checks one Forge Kata workspace end to end with read-only requests: Forge task
detail and project mapping, the worktree branch, the Forge-recorded Pi session,
its AgentsView record and saved resume file, the finished roborev job for the
exact commit in that worktree, and a stored pass, close or comment
disposition. It also reports `GAP native-review-ui`, because Forge renders its
Reviews tab only for pull-request workspaces; open the printed roborev review
link instead.

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

### Audit bindings and decision trail

`librarian-mcp --audit-log --agent-label LABEL` (the_librarian#9e3j) records
the full text each client received, with its SHA-256, in a private
`<root>/.local/audit/<label>-mcp-access.jsonl`. Opt in per binding:

```sh
python3 scripts/local_env.py configure-librarian --librarian-root ~/falcon-librarian --audit \
  [--copilot-config ~/.copilot/mcp-config.json]
```

- `--audit` adds the flags to the managed Pi/Forge binding (label `pi-forge`);
  `--copilot-config PATH` adds a separate Copilot binding (label `copilot`) and
  preserves other servers in that file. Rerunning is idempotent; omitting
  `--audit` turns auditing off again.
- The command refuses, without writing, when the installed `librarian-mcp`
  lacks either flag (reinstall the adapter from a checkout containing 9e3j).
- Global or repository bindings it does not own (`~/.copilot/mcp-config.json`
  without `--copilot-config`, repo `.pi/mcp.json`, `GLOBAL_PI/mcp.json`,
  `.github/mcp.json`) are listed as unmanaged and never modified.
- Activation: flags take effect only when a client starts a new
  `librarian-mcp` process. Restart or `/reload` Pi and restart Copilot, then
  prove it:
  `node scripts/verify-audit-binding.mjs <pi cli.js> <STATE>/pi <query> <audit log> [label]`
  drives a fresh Pi client through status, search, exact get and a failing get
  and checks that each audit record carries the hash of the payload Pi received.
  If the log cannot be written the call returns an error and no document text.

`python3 scripts/decision-trail.py --kata PROJECT#ID --repo DIR --commits RANGE
--pr OWNER/REPO#N --audit-log LOG --session-file FILE --workspace ID
[--intake DIR] --name NAME` writes a private, read-only retrospective to
`.local/decision-trail/NAME.md`: approved ticket and revision, what the
Librarian returned (hashes, locators, qualification), task/workspace/session,
commits with exact-commit reviews and dispositions, checks, the PR and the
human decision, model roles and quoted rationale. Absent links print `MISSING`
and are never inferred; labels do not prove task or session identity (only
Forge's workspace link and session time overlap do); hidden reasoning is not
captured; returned text is never copied.

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
| `environment.json` | Corpus path, Forge binary, Pi executable and version, optional Librarian binding, and any `port_offset`, written by `setup`; rerunning `setup` after upgrading the saved Pi executable in place updates only an older `pi_version` |
| `secrets/usai-api-key` | USAi API key. This is the only place the key is stored. |
| `usai.json` | Active coder `model` and `review_model` |
| `usai-models.json` | Last model catalog fetched from USAi |
| `pi/models.json` | Pi `usai` provider: base URL, API type, and models. The key field is the `${USAI_API_KEY}` placeholder. |
| `pi/settings.json` | Pi default provider and model, Superpowers and extension packages (`pi-subagents`, `pi-json-schema`), and subagent defaults (`model: inherit`) |
| `pi/mcp.json` | Pi MCP servers: `falcon-context` (Librarian-style corpus), `kata`, and `kenn-forge` |
| `pi/extensions/forge-workspace.ts` | Forge workspace extension (session hooks, worktree isolation, PR/target registration) |
| `forge/config.toml` | Forge host and port, MCP, and agent launchers `pi` (default model) and `pi-argon` (`gemini-4-argon`) |
| `roborev/config.toml` | Daemon address, `pi` agent command, and reviewer model (linked from `~/.roborev`) |
| `kata/config.toml` | Kata listen address |
| `agentsview/config.toml` | AgentsView archive policy and session source directories (paired with `agentsview-tracking.json`) |
| `gh/` | Isolated GitHub CLI login used by Forge and `scripts/gh-local.py` |
| `systemd/` | Generated user units |

Each repo has its own `.roborev.toml` (agent `pi`, reviews batched every 5 commits) and
`.kata.toml` (Kata project binding).

Forge's automatic PR formatter chooses detail and structure by the meaningful
changes, not a file-count tier or bullet quota. A focused fix can stay a short
paragraph; independent changes can use bullets or sections. It preserves task
references and actionable compatibility, migration, and approval notes.

## Task-bound business evidence and cross-repository seams

`engineer-task-context` composes one task-bound evidence packet from the
configured Librarian business corpus. It is a read-only consumer: it never
acquires sources, indexes, extracts, or publishes, and it never mutates a Kata
task. For code that crosses repository boundaries, it also ships the
dependency-free `seams` scanner.

Install it into a private virtual environment (`python3 -m venv .local/context-venv && .local/context-venv/bin/pip install -e '.[test]'` with Python 3.12 or newer) and write
an `engineer.context-config/v2` file naming the Librarian provider:

```json
{
  "schema": "engineer.context-config/v2",
  "librarian": {"project_id": "<business project>", "executable": "<librarian-mcp>",
                "root": "<corpus root>", "reader": null, "selection": null}
}
```

Relative paths resolve against the configuration file. The server program path
keeps the link you select, so a virtual environment's entry point runs with
that environment's prefix. Paths may contain spaces; every provider launch uses
an argument list, never a shell. Leave `librarian.reader` null for a current
Librarian toolkit, which loads its reader module from `root` and refuses an
explicit `--reader`; set it only for a legacy release that requires that
argument.

A collection request names the task and the business locators to read:

```json
{"task": {"daemon_id": "...", "project_uid": "...", "issue_uid": "...", "workspace_id": "..."},
 "business": [{"locator": "documents/guide.md#overview", "required": true}]}
```

```sh
engineer-context collect --config binding.json --request request.json --output packet.json
engineer-context report --packet packet.json
engineer-context revalidate --config binding.json --packet packet.json --task task.json --output recheck.json
engineer-context seams --workspace-root ~/falcon --format markdown --max-chars 4000
```

`collect` exits 0 only when every required business locator returned
evidence; it exits 2 when the packet is blocked and 1 on invalid input or I/O.
`report` renders provenance, gaps and readiness; `--json` emits the machine
form; raise `--max-bytes` when a packet exceeds the 1 MiB default.
`revalidate` rechecks the Librarian binding and each whole qualified response
against a sealed packet without changing it.

Packets (`engineer.task-context/v2`) preserve full provider responses, exact
passages, locators, source hashes, line ranges, coverage and handling
restrictions. Rendition pieces report their original source location next to
the indexed extraction range, so citations name the real location. Assertions
and contributions are reported as unavailable capabilities pending
`the_librarian#923h` and `the_librarian#rjr5`. Packets can carry restricted
source text, so write them only to private paths and never paste them into
shared channels.

`seams` scans local repositories for cross-repository and cross-layer edges (UI
HTTP calls to API Gateway routes, CDK stacks to Lambda handlers, orphan or stub
handler directories, async queue/stream wiring, and CloudFormation cross-stack
imports). It prints compact `file:line` citations, and supports `--kind`,
`--query` and `--format compact|markdown|json`.

Agents reach the same four read-only operations (`collect`, `report`,
`revalidate`, and `seams`) through a stdio MCP server configured once at
startup (`engineer-seams` is also installed as a standalone CLI entry point
for the same scanner):

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

## Tool-call failure diagnosis

`python3 scripts/tool-health.py` checks Kata reachability, the current
directory's Kata project binding and Librarian index freshness, and prints the
fix for each failure. `python3 scripts/tool-failures.py --pi DIR --copilot DIR`
reports the most common failed tool calls in agent history; the latest results
are in `context/tool-failures.md`. The Forge Pi extension adds a one-line
`Recovery:` hint to failed tool results for recurring causes.

## Value case

`context/value-case.md` is a one-page template for the estimated value of a
run: labeled estimates, the mechanism, quick checks and what would falsify the
claim. Fill private copies under ignored `.local/value-case/`.

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

The default Forge coder (`Pi (USAi)`) uses `claude-sonnet-5.5`. New sessions
pick up model changes automatically; restart an existing Pi session to switch.
The alternate `Pi (Gemini 4 Argon)` target and the reviewer model are independent.

1. `list-models` fetches `/models` from USAi into `usai-models.json`. It only
   lists models; it does not test them.
2. `configure-provider --base-url <url> --model <coder> [--review-model <reviewer>] --api openai-completions`
   writes every chat model (the built-in list plus the fetched catalog) to
   `pi/models.json` and skips embedding models. It also sets the coder default
   in `pi/settings.json` and `usai.json`, and syncs `--review-model` to
   `roborev/config.toml`. Omitting `--review-model` clears a previously
   configured reviewer pairing.
3. When `--review-model` is set, the coder and the reviewer must come from
   different model families (Claude, OpenAI, or Gemini), and both must appear
   in `usai-models.json` when its advertised model list is nonempty.
4. `pi-local.py --model` accepts only the coder model, the reviewer model, or
   `gemini-4-argon`. To use another model, run `configure-provider` again.

To add newly published models or switch the coder or reviewer, run steps 1 and
2 again, then run `systemctl --user restart kenn-kopy-roborev.service`.

## Daily use

```sh
python3 scripts/terminal-local.py open pi        # persistent tmux session; run scripts/pi-local.py inside it
python3 scripts/terminal-local.py open copilot   # Copilot CLI, for non-sensitive work
kata ready --no-label blocked --no-label deferred --agent && kata claim <id>
roborev review --repo "$PWD" --branch --wait --min-severity medium  # only when existing evidence does not cover unchanged code
```

Delivery allows one branch review and one focused, tested fix pass, not
repeated review-until-clean cycles. Record dispositions and revision/fix
evidence in Kata; reuse them across resumes, reloads, and skill transitions.
Leave valid out-of-scope findings open for the owner. Hand recurring or
unresolved confirmed findings to the owner and pause publication for unresolved
task-scoped medium/high/critical defects; low findings do not block delivery.
See [review and disposition rules](context/engineering-workflow.md#bounded-delivery-review-and-dispositions).
`setup` adds missing medium-severity and passing-review auto-close defaults to
existing private roborev configs without replacing explicit overrides.

In Forge, create a workspace from a Kata task and launch **Pi (USAi)** or
**Pi (Gemini 4 Argon)**. The Forge workspace extension pushes the branch, opens
the PR, and registers the PR and Kata task in Forge. In a Kata-task workspace,
`scripts/pi-local.py` sets `KATA_REF` to the task, so Kata's Pi attention
adapter (installed by `install-pi-extensions`) marks it `work.attention ok`
while Pi runs and `needs-human` ("session ended without hand-off") after
`/quit` or SIGHUP, keeping any explicit hand-off the agent already set.

## Demo screenshots and video

Agents can show changed behavior to reviewers as screenshots and a short
video, captured headlessly from a loopback web UI:

```sh
python3 scripts/demo-capture.py doctor   # check Node, Playwright and browser
python3 scripts/demo-capture.py capture --task the_engineer#86ey \
  --demonstrates "What changed" --url http://127.0.0.1:8000/ --step 'click:#save'
python3 scripts/demo-capture.py handoff .local/demos/<task>/<bundle>
```

Bundles land in ignored `.local/demos/` with a provenance manifest and are
never uploaded. Review every frame before sharing; attaching to a PR or issue
needs your explicit approval. Manual capture, limits, retention and failure
guidance are in `context/demo-capture.md`.

## Maintenance

- **Back up:** `python3 scripts/backup_workspace.py <dest-dir>` creates a
  verified `.tar.gz` archive (plus `.sha256` checksum) of the workspace,
  including SQLite snapshots.
- **Run tests:** `python3 -m unittest discover -s scripts -p 'test_*.py'`, the
  same command with `-s dist`, and `python -m unittest discover -s tests -p 'test_context_*.py'`
  in the `engineer-task-context` virtual environment.
- **Verify prompt, temporary-plan, and publication gates:** run
  `python3 scripts/workflow-gates.py check-plans --repo . --base main` to verify
  no temporary working plans/specs remain under `.local/plans/` or
  `docs/superpowers/`, or `python3 scripts/workflow-gates.py demo` to run the
  non-model synthetic task demonstration across `private_pi`, `forge_workspace`,
  and `roborev_review`. Pi agents cannot merge a PR or push to `main` unless
  you confirm the call in the Pi UI; pushing a workspace branch and opening a
  PR never asks, including when the push follows a `cd` or a new branch in the
  same command.
- **Run smoke tests:** stop the four services, run
  `python3 scripts/smoke.py --forge-binary .local/forge-local-kata/kenn-forge`,
  then start the services again. The smoke tests use the same ports, unless
  you set `KENN_KOPY_PORT_OFFSET` (for example `3000`) to run beside them.
- **Upgrade the toolchain:** `python3 scripts/upgrade.py status` shows how far
  the submodules, Pi and pi-subagents trail upstream. `python3 scripts/upgrade.py run`
  snapshots binaries, data and configs; moves everything to the latest
  versions; builds and tests the result away from the live services; then
  switches the services over. If any step fails, it rolls back automatically.
  Use `python3 scripts/upgrade.py rollback` to return to the last snapshot by
  hand and `python3 scripts/upgrade.py drill` to rehearse a rollback. Review
  and commit the staged submodule changes afterwards.
- **Keep secrets out of Git:** never put credentials in Git, logs, or command
  arguments.

More detail: [context/tools.md](context/tools.md),
[context/status.md](context/status.md), and
[context/system-architecture.md](context/system-architecture.md).
