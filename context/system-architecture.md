# Two-product system architecture

## Product roles

| Product | Repository / Checkout | Kata project | Role |
| --- | --- | --- | --- |
| **Librarian** | `GSA/the_librarian` (`~/the_librarian`) | `librarian` | Rust CLI and MCP server (`falcon-librarian`) that indexes documentation and recorded review coverage for low-token retrieval (`catalog`, `search`, `get`, `get_many`, `coverage`, `review_events`, `status`). |
| **Engineer** | `GSA/the_engineer` (`~/kenn-kopy`) | `engi-platform` | Local engineering platform combining Forge, Pi (`usai`), Superpowers, roborev, Kata, and AgentsView under `.local/environment/`, plus the task-bound Librarian evidence consumer and cross-repository seam scanner (`engineer-context`). |

Knowitall (`GSA/the_knowitall`) is archived on GitHub and has no local
checkout, Kata project or Forge registration.

## Runtime topology on the WSL host

```text
+-------------------------------------------------------------------+
| Engineer (.local/environment/ + user systemd on 127.0.0.1)        |
|                                                                   |
|  Forge (:18091) ----> spawns Pi (scripts/pi-local.py, provider=usai)
|    |                    |-- MCP: falcon-librarian (Librarian binary)|
|    |                    |-- MCP: kata mcp serve (:17777)          |
|    |                    `-- Extensions: pi-subagents, superpowers |
|    |-- reads/maps ---> Kata daemon (:17777, kata/kata.db)         |
|    `-- inspects -----> roborev daemon (:17373 / UI :17374)        |
|                                                                   |
|  AgentsView (:18080) -> archives Pi + Copilot transcripts         |
+-------------------------------------------------------------------+
```

## Corpus and target repositories

- **Historical Falcon documentation packet**: `~/falcon-docs` (bound to Kata
  project `falcon-docs`), indexed by Librarian for `falcon-librarian` MCP queries.
- **Falcon application repositories**: `~/falcon/backend` (`falcon-backend`),
  `~/falcon/frontend` (`falcon-frontend`), `~/falcon/exec-dashboard`
  (`falcon-exec-dashboard`), and `~/falcon/mcp` (`falcon-mcp`).
- **Adjacent project**: `~/aos-spud` (`GSA/aos-spud`, Kata project `spud`).

<a id="concrete-reproduction-gaps"></a>
## Host bundle reproduction notes (`dist/`)

When reproducing this environment on a new Linux/WSL host via `dist/install.sh`:

1. **Systemd vs. foreground supervision**: `dist/install.py` runs
   `scripts/local_env.py setup`, which configures `.local/environment/`. On
   hosts using user systemd, install or refresh the four `kenn-kopy-*.service`
   units (`install-kata-service`, `install-roborev-service`,
   `install-agentsview-service`, `install-forge-service`); otherwise use
   `python3 scripts/local_env.py run`. (Tracked in Kata `t14m`.)
2. **Forge binary**: `kenn-kopy-forge.service` runs the
   `forge/kenn-forge` binary built from the pinned `forge/` submodule by
   `scripts/build.sh forge`.
3. **Private credentials**: `set-key` (`USAi`) and `gh-local.py auth login`
   (`GitHub`) are interactive post-install steps per machine.
