# Selective engineering memory (`5xrm`)

## Objective

Keep durable engineering decisions, architecture contracts, and verified lessons
discoverable across sessions without bloating per-turn prompt files or mixed
task trackers.

## Responsibility split across tools

| Store | What belongs here |
| --- | --- |
| `AGENTS.md` + `context/{project,tools,status}.md` | Current-state operating agreements, tool commands, and active service/queue summary (kept compact and updated in place). |
| **Kata** (`http://127.0.0.1:17777`) | Actionable work items, dependencies, claims, and closure verification evidence. |
| **Librarian** (`falcon-context`) | Versioned corpus documents and recorded review coverage packets. |
| **AgentsView** (`http://127.0.0.1:18080`) | Historical session transcripts and token/cost telemetry (`transcripts` archive policy). |
| **Hindsight sidecar** (`dist/hindsight.compose.yaml`) | Optional container-backed selective semantic memory (`retain` / `recall` / `reflect`) for curated architectural decisions and post-mortem lessons. |

## Phase 1 contract (awaiting owner sign-off on `5xrm`)

- Curate memory entries explicitly at task completion or decision boundaries
  rather than auto-ingesting raw transcripts.
- Require provenance on every retained memory item: repository, Kata issue ID or
  commit SHA, date, and verification evidence.
- Keep the Hindsight compose stack (`dist/hindsight.compose.yaml`) optional and
  loopback-bound so core Engineer services (`Forge`, `Kata`, `roborev`,
  `AgentsView`) run without container dependencies.
