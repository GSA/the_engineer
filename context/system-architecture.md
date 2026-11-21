# Two-product system architecture

## Product roles

| Product | Repository / Checkout | Kata project | Role |
| --- | --- | --- | --- |
| **Librarian** | `GSA/the_librarian` (`~/the_librarian`) | `the_librarian` | Rust CLI and MCP server (`falcon-librarian`) that indexes documentation and recorded review coverage for low-token retrieval (`catalog`, `search`, `get`, `get_many`, `coverage`, `review_events`, `status`). |
| **Engineer** | `GSA/the_engineer` | `the_engineer` | Local engineering platform combining Forge, Pi (`usai`), Superpowers, roborev, Kata, and AgentsView under `.local/environment/`, plus the task-bound Librarian evidence consumer and cross-repository seam scanner (`engineer-context`). |

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

Librarian is owner-only and optional today: teammate installs have no
Librarian or corpus, and the `falcon-librarian` MCP entry above exists only
where one is bound with `configure-librarian`. Librarian becomes a remote MCP
server with its own installer under `the_librarian#a4ra` (hosting in `jmga`).
Each install registers its own repositories with `./engineer add-repo`; the
owner's corpus and repository list stay outside this repository.
