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

## Phase 1 contract (`5xrm`)

- Curate memory entries explicitly at task completion or decision boundaries
  inside repo-local `context/*.md`, Kata closure notes, and Librarian
  `REFERENCE/notes/` rather than auto-ingesting raw transcripts or running a
  separate vector/graph memory container.
- Require provenance on every retained memory item: repository, Kata issue ID or
  commit SHA, date, and verification evidence.
- Container-backed semantic memory (`hindsight`, `the_engineer#zbww`, `#pbqn`)
  was retired after empirical evaluation showed static repo-local context docs +
  Kata + Librarian avoid sidecar container and multi-turn query overhead.
