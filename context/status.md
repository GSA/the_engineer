# Status: 2026-10-04

## Completed

- Read the reference post; downloaded the five retained upstream projects.
- Removed Ghosthub. Initialized the parent repository on `main` and registered
  exact-commit submodules without changing their source.
- Added and exercised `scripts/bootstrap-sources.sh` twice, including from
  another working directory. All submodules matched their recorded gitlinks.
- Moved detailed context out of `AGENTS.md` into this directory. This is the
  durable handoff/compaction entry point, linked from the minimal `AGENTS.md`.
- Added workspace-local toolchain bootstrap, source build, and coordinated
  smoke/shutdown scripts. Build/toolchain details are in `tools.md`.
- Built roborev, Kata, and AgentsView from the exact pinned source revisions,
  including their actual web bundles. All five upstream worktrees remain clean.
- Added root `TODO.md`, including the requested longer-term sandboxing
  investigation. No sandbox implementation or product selection is implied.
- Investigated Pi MCP setup; recorded version requirements and acceptance
  checks in `tools.md`. Pi remains at 0.87.1; no MCP configuration or runtime
  upgrade was made because the intended server has not been identified.

## Startup results

The three available daemons ran concurrently in isolated state directories,
alongside a short-lived Pi/Superpowers RPC session.

| Component/check | Observed result |
| --- | --- |
| roborev | API and embedded browser UI/JavaScript assets responded. No review was submitted. |
| Kata | API and embedded browser UI/JavaScript assets responded; created a synthetic task and read it back through the CLI. |
| AgentsView | Health API and embedded browser UI/JavaScript assets responded. Ingestion was intentionally disabled. |
| Pi + Superpowers | Pi 0.87.1 loaded all 15 Superpowers skills in offline RPC mode with no credentials or model calls. |
| Forge | Blocked before compilation by required Zscaler VPN authentication on the user's side; not a dependency defect. |
| Shutdown | All three owned daemon PIDs exited; all four ports they used stopped accepting connections. Pi exited too. |

Run `python3 scripts/smoke.py` to reproduce. It currently returns exit status 1
because Forge is unavailable; this is intentional, not an all-green result.
HTTP/asset probes are not interactive browser tests, and concurrent startup is
not proof of complete cross-tool integration.

## Issues and recovery

| Issue | Action and current state |
| --- | --- |
| Missing Go and Bun | Installed checksum-verified Go 1.27.1 and exact-version Bun binaries under `.local/tools/`. Added a repeatable bootstrap; no system installation. |
| Missing `sqlite3.h` in roborev/Kata builds | Initially confirmed by extracting a development package locally. Final build uses headers from each project's pinned go-sqlite3 module instead. Both rebuilt successfully. |
| UI probes returned 404 | The first smoke probe lacked the browser `Accept` header. Corrected the harness to request canonical `/reviews` and `/kata` navigation with `Accept: text/html`; both then passed. Not an upstream defect. |
| Forge download HTTP 403 | Frozen Bun install failed fetching `https://api.github.com/repos/kenn-io/kata/tarball/c668572`, returning a Zscaler page. On 2026-10-03 the user clarified that this requires their Zscaler VPN authentication, not a dependency fix. They plan to log in and rerun the Forge build on 2026-10-04. Leave dependency pins unchanged; no workaround is needed. |

- The earlier commit-identity blocker is resolved: effective Git identity was
  confirmed on 2026-10-04 after the user's configuration. No global settings
  were changed by the agent. The initial parent commit is authorized.
- A new untracked `.kata.toml` was observed on 2026-10-04. It was not created by
  this turn's work and has been left untouched and outside the staged changes.
- Forge's lockfile pins the Kata UI archive to commit
  `c6685725ecd6a31aaea83cf98908e0c866c5d434`, not our newer Kata submodule.
  Do not substitute the submodule as though it were the same dependency.
  Wait for the user's Zscaler login before retrying its build.
- LiteLLM URL, credentials, model names, and API compatibility are pending.
  No model-backed review or coding workflow can be confirmed yet. Forge-to-
  roborev/Kata integration, Pi session ingestion, and private-cloud deployment
  are also unverified.
- The parent has no remote configured; nothing has been published.

## Evidence and shutdown state

Build logs are `.local/logs/{roborev,kata,agentsview,forge}-build.log`.
Each smoke run records `.local/smoke-*/results.json` and service logs. These are
ignored machine-local artifacts, not required handoff context; this document
captures the important outcomes without private runtime data.

Latest completed run: `.local/smoke-km9q33bz/results.json`. Roborev PID 21076,
Kata PID 21137, and AgentsView PID 21151 all exited. Ports 17373, 17374, 17777,
and 18080 were confirmed closed. The run exited 1 solely for the missing Forge
binary; all executed checks passed.

All application processes started for these checks are stopped. No system
services, persistent tmux sessions, or repository hooks were installed.
Toolchains, binaries, build caches, and isolated test databases are retained on
disk to support the next attempt; they consume disk but no running CPU/memory.

## Resume order

1. Confirm the intended context MCP server and select a pinned Pi version with
   compatible MCP support before configuring it; follow `tools.md`.
2. After the user authenticates to Zscaler, rerun `./scripts/build.sh forge`
   without changing its lockfile. The user plans to do this on 2026-10-04.
3. Rerun the smoke script, then verify Forge's actual roborev/Kata connections.
4. Agree on Pi/LiteLLM model configuration and safe credential injection before
   testing real reviews, agent sessions, or session ingestion.
