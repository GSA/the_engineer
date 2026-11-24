# Engineer: advanced and maintainer reference

The [README](../README.md) covers everyday use through `./engineer`. This page
documents the lower-level `scripts/local_env.py` commands that `./engineer`
wraps, optional components (Librarian, task context, Jira intake, demos) and
maintenance. Pinned versions: Pi `1.5.2`
(`@earendil-works/pi-coding-agent@1.5.2`).

## Host checks

`./engineer doctor` runs `python3 scripts/local_env.py accept` and adds a
Copilot check and plain next steps.

`accept` checks the Pi pin and extensions, built executables, pinned
submodule gitlinks, the native `kata`/`roborev` links, Pi MCP connections, all
four user services, the saved USAi provider, the presence of the private USAi
key and GitHub login (values are never printed), and, for each `--repo`, the
Forge registration, roborev post-commit hook and protected-branch push guard.
It makes no model call and changes no service. Run it from a login shell so
`systemctl --user` can reach the user manager.

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


## Initialize the platform in another repository

Prerequisites: the four services are up (`python3 scripts/local_env.py status`)
and GitHub is signed in (`./scripts/gh-local.py auth status`). Then, for each
Git checkout:

```bash
python3 scripts/local_env.py init-repo ~/some_repo [--project NAME] [--skip-kata]
python3 scripts/local_env.py accept --repo ~/some_repo
```

`init-repo` is idempotent, never overwrites an existing file, prints one
`OK`/`SKIP`/`WARN`/`ERROR` line per step and a next-steps list, and exits
nonzero on `ERROR`. Its steps:

1. Checks that the path is a non-bare Git checkout.
2. Registers it with Forge (a `WARN` with the manual `register` command if
   Forge is down).
3. Installs the native roborev hooks (`roborev init --no-daemon`) and, when
   absent, writes `.roborev.toml` from `scripts/templates/roborev.toml`.
4. Runs `kata init --project NAME` (default: the directory name, matching
   Kata project names to repository names) unless `.kata.toml` exists or
   `--skip-kata` is given, then reports whether Forge maps that Kata project
   to the repository. Forge derives the mapping from the registered checkout
   and its committed `.kata.toml`; if it reports `unmapped`, add a GitHub
   `origin` remote or map it in Forge Settings > Kata project mappings.
   `.kata.toml` and `.roborev.toml` are committed files: land them through a
   feature branch and pull request, never `main`.
5. Installs the protected-branch push guard and runs the `accept --repo`
   checks, which also report a missing guard.

The guard is a marked block at the top of the repository's `pre-push` hook,
in the common hooks directory, so every linked worktree (including Forge
workspaces) shares it. It rejects a push, force push or deletion of `main` or
`master` unless a person at a terminal types `yes`; agent tool subprocesses
have no terminal and are blocked. It coexists with the roborev `pre-push`
hook in either install order. Remove it with
`python3 scripts/local_env.py init-repo <repo> --remove-guard`.

The guard is a local speed bump: `git push --no-verify` bypasses it. The
backstop is GitHub branch protection on `main`. The repository owner enables it
once per repository, for example:

```bash
./scripts/gh-local.py api -X PUT repos/OWNER/REPO/branches/main/protection \
  --input - <<'JSON'
{"required_status_checks": null, "enforce_admins": true,
 "required_pull_request_reviews": {"required_approving_review_count": 1},
 "restrictions": null, "allow_force_pushes": false, "allow_deletions": false}
JSON
```

## Optional: connect a Librarian instance

Engineer installs and runs without Librarian. Librarian and its corpus are
owner-only today; Librarian becomes a remote MCP server with its own installer
(`the_librarian#a4ra`). To bind an existing instance, set up through its own
repository (`GSA/the_librarian`):

```sh
python3 scripts/local_env.py configure-librarian --librarian-root PATH_TO_LIBRARIAN_INSTANCE
```

### Audit bindings and decision trail

`librarian-mcp --audit-log --agent-label LABEL` (the_librarian#9e3j) records
the full text each client received, with its SHA-256, in a private
`<root>/.local/audit/<label>-mcp-access.jsonl`. Opt in per binding:

```sh
python3 scripts/local_env.py configure-librarian --librarian-root PATH_TO_LIBRARIAN_INSTANCE --audit \
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

To try Engineer in a separate WSL distro, see [try-in-a-second-wsl-distro.md](try-in-a-second-wsl-distro.md).

## Services

| Service | URL | Unit |
| --- | --- | --- |
| Forge | http://127.0.0.1:18091/ (MCP `:18092/mcp`) | `engineer-forge.service` |
| Kata | http://127.0.0.1:17777/kata | `engineer-kata.service` |
| roborev | http://127.0.0.1:17374/reviews (API `:17373`) | `engineer-roborev.service` |
| AgentsView | http://127.0.0.1:18080/ | `engineer-agentsview.service` |

All services bind to `127.0.0.1`. `ENGINEER_PORT_OFFSET` shifts every port; see
[try-in-a-second-wsl-distro.md](try-in-a-second-wsl-distro.md#ports-are-shared-with-your-other-distros).

## TLS-inspecting corporate proxies

Networks that re-sign HTTPS traffic with a private CA break tools that ignore the
operating-system trust store (venv `pip`, `npm` and Node `fetch`, `httpx`,
`requests`). Forge, the Pi agents and the services therefore receive the CA and
proxy variables below.

- Passed through when set: `SSL_CERT_FILE`, `SSL_CERT_DIR`, `REQUESTS_CA_BUNDLE`,
  `CURL_CA_BUNDLE`, `PIP_CERT`, `NODE_EXTRA_CA_CERTS`, `AWS_CA_BUNDLE`,
  `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`, `ALL_PROXY` (both cases), and the CA
  flags (`--use-openssl-ca`, `--use-system-ca`, `--use-bundled-ca`) in
  `NODE_OPTIONS`. Loopback is always added to `NO_PROXY` when a proxy is set.
- When unset and `/etc/ssl/certs/ca-certificates.crt` exists, `SSL_CERT_FILE`,
  `REQUESTS_CA_BUNDLE`, `PIP_CERT` and `NODE_EXTRA_CA_CERTS` default to it (or to
  your `SSL_CERT_FILE`). Install your organisation's CA into the system store
  (`update-ca-certificates`) and the agents pick it up.
- The default bundle needs no setup. Custom variables and proxies must be in the
  environment the unit starts with: the Forge unit reads the systemd user
  manager's environment (`systemctl --user import-environment VAR ...` or an
  `environment.d` file), and `install-roborev-service` records your shell's
  values. Then restart the units. Restarting Forge ends live agent terminals,
  so do it when agents are idle.

## Configuration reference

All state is under `.local/environment/`. Git ignores that directory, and the
files are private (`0600`/`0700`). Set `ENGINEER_RUNTIME_ROOT` to use a
different root.

| File | Purpose |
| --- | --- |
| `environment.json` | Optional corpus path, Forge binary, Pi executable and version, optional Librarian binding, and any `port_offset`, written by `setup`; rerunning `setup` after upgrading the saved Pi executable in place updates only an older `pi_version` |
| `secrets/usai-api-key` | USAi API key. This is the only place the key is stored. |
| `usai.json` | Active coder `model` and `review_model` |
| `usai-models.json` | Last model catalog fetched from USAi |
| `pi/models.json` | Pi `usai` provider: base URL, API type, and models. The key field is a `!` command (`scripts/usai-key.py`) that Pi runs per request; the file never holds the key. |
| `pi/settings.json` | Pi default provider and model, Superpowers and extension packages (`pi-subagents`, `pi-json-schema`), and subagent defaults (`model: inherit`) |
| `pi/mcp.json` | Pi MCP servers: `kata`, `kenn-forge`, and `falcon-librarian` only where a Librarian is bound |
| `pi/extensions/forge-workspace/` | Forge workspace extension (session hooks, worktree isolation, PR/target registration) |
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

`engineer-task-context` is optional and needs a bound Librarian. It composes
one task-bound evidence packet from the configured Librarian business corpus.
It is a read-only consumer: it never acquires sources, indexes, extracts, or publishes, and it never mutates a Kata
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
engineer-context seams --workspace-root ~/src --format markdown --max-chars 4000
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

The scanner is project-agnostic. Every seam and `detail` string comes from text
it matched in the scanned files, and heuristic findings read "POSSIBLE
MISMATCH" or "marker" so you verify them at the cited line. It carries no
repository names, route tables or behavior notes for any particular system.

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
scripts/jira-intake.py init ~/Downloads/JIRA-123.xml \
  --access-path "owner-supplied XML export"

# 2. Record approved refinements, assumptions, questions and tasks.
$EDITOR .local/jira-intake/JIRA-123/intake.toml

# 3. Validate, review the kata commands, then create the tasks.
scripts/jira-intake.py check  .local/jira-intake/JIRA-123/intake.toml
scripts/jira-intake.py record .local/jira-intake/JIRA-123/intake.toml
scripts/jira-intake.py record .local/jira-intake/JIRA-123/intake.toml --apply
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

## USAi key management and rotation

- `set-key` prompts for the key with hidden input. It rejects keys passed as an
  argument or piped in. The key is written only to `secrets/usai-api-key` (`0600`).
- The private `pi/models.json` points the `usai` provider at `scripts/usai-key.py`,
  which Pi runs for each model request. The key is never placed in the
  environment of Pi or of the shell commands it runs, and config files never
  contain it. Launching Pi migrates an older `${USAI_API_KEY}` placeholder to
  this form. Agents run as your user, so a command that reads
  `secrets/usai-api-key` can still read it; the file mode (`0600`) protects it
  from other users only.
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
   `pi/models.json` and skips embedding models. Main Claude and Gemini models
   get a 400k `contextWindow` and GPT Sol models 272k, each with 32k
   `maxTokens`, so Pi compacts near those caps rather than at its 128k
   default (`USAI_MODEL_LIMITS` in `scripts/local_env.py`). It also sets the coder default
   in `pi/settings.json` and `usai.json`, and syncs `--review-model` to
   `roborev/config.toml`. Omitting `--review-model` clears a previously
   configured reviewer pairing.
3. When `--review-model` is set, the coder and the reviewer must come from
   different model families (Claude, OpenAI, or Gemini), and both must appear
   in `usai-models.json` when its advertised model list is nonempty.
4. `pi-local.py --model` accepts only the coder model, the reviewer model, or
   `gemini-4-argon`. To use another model, run `configure-provider` again.

To add newly published models or switch the coder or reviewer, run steps 1 and
2 again, then run `systemctl --user restart engineer-roborev.service`.

## Daily use

```sh
python3 scripts/terminal-local.py open pi        # persistent tmux session; run scripts/pi-local.py inside it
python3 scripts/terminal-local.py open copilot   # Copilot CLI, for non-sensitive work
kata ready --no-label blocked --no-label deferred --agent && kata claim <id>
roborev review --repo "$PWD" --branch --wait --min-severity medium  # only when existing evidence does not cover unchanged code
```

Delivery allows one branch review and one focused fix pass; see the
[review and disposition rules](../context/engineering-workflow.md#bounded-delivery-review-and-dispositions).
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

Each PR gets proof matched to its change type, posted as a PR comment so
testers need not run anything:

```sh
python3 scripts/demo-capture.py classify          # ui / api / backend / docs + evidence needed
python3 scripts/demo-capture.py capture --walkthrough ...   # UI: captioned walkthrough.gif
python3 scripts/demo-capture.py evidence --data in.json --command 'python3 calc.py' \
  --before origin/main --task ... --demonstrates ...      # API/backend: data, command, output before/after
python3 scripts/demo-capture.py publish .local/demos/<task>/<bundle> --pr 42
```

In a Forge workspace, creating the PR for a Jira-sourced Kata task (or one
labelled `evidence`) prompts the agent with the evidence its change type needs;
other tasks are not prompted. `--walkthrough` builds a GIF only when the branch
changes UI files. `evidence` records the synthetic data, an exact command you
can rerun with your own data via `EVIDENCE_DATA`, and its output. `publish`
uploads with `gh` (2.99+) and verifies the comment. Walkthroughs need Pillow
(`python3-pil`), which `./engineer install` installs.

Bundles land in ignored `.local/demos/` with a provenance manifest and are
uploaded only by `publish`. Use synthetic data only and check every frame and
output before publishing. Manual capture, limits, retention and failure
guidance are in `context/demo-capture.md`.

## Maintenance

- **Run tests:** the commands in [dist/README.md](../dist/README.md#maintainer-checks),
  plus `python -m unittest discover -s tests -p 'test_context_*.py'` in the
  `engineer-task-context` virtual environment.
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
  `python3 scripts/smoke.py --forge-binary forge/kenn-forge`,
  then start the services again. The smoke tests use the same ports, unless
  you set `ENGINEER_PORT_OFFSET` (for example `3000`) to run beside them.
- **Upgrade the toolchain:** `python3 scripts/upgrade.py status` shows how far
  the submodules, Pi and pi-subagents trail upstream. `python3 scripts/upgrade.py run`
  snapshots binaries, data and configs; prepares the latest versions in a
  separate worktree (`.local/upgrade/tree`) and builds and tests them there,
  leaving the live checkout and services untouched; then switches the
  services over. If the switch fails, it rolls back automatically.
  Use `python3 scripts/upgrade.py rollback` to return to the last snapshot by
  hand and `python3 scripts/upgrade.py drill` to rehearse a rollback. Review
  and commit the staged submodule changes afterwards.
- **Keep secrets out of Git:** never put credentials in Git, logs, or command
  arguments.

More detail: [context/tools.md](../context/tools.md),
[context/status.md](../context/status.md), and
[context/system-architecture.md](../context/system-architecture.md).
