# Current status

## Scope

The MVP is Librarian plus Engineer, with Engineer's cross-repository seam
scanner (`engineer-context seams`) for code that crosses repository
boundaries. Knowitall is archived. Librarian and its corpus are owner-only and
optional today: teammate installs have neither, and every Engineer code path
works without them. Librarian becomes a remote MCP server with its own
installer under `the_librarian#a4ra`; hosting is planned in `jmga`.

## Current priorities (open Kata tasks, `the_engineer`)

List live work with `kata list` or
`kata ready --no-label blocked --no-label deferred --agent`.

- `wy6y`: a coworker runs the teammate install end to end on a clean Ubuntu
  host (WSL2 and AWS WorkSpaces) and records evidence; related to `9jqt`.
- `8ya9`: PR evidence by change type (walkthrough GIFs, test evidence,
  `publish`) is merged (PR #42); awaits owner review before closure.
- `kt2r`: a repository admin enables GitHub branch protection on `main` for
  `the_engineer` and `the_librarian`; owner/admin action.
- `430a` (P2): upstream Forge change for explicit, evidence-backed Kata
  closure after a confirmed PR merge.
- `3c2c` (P3): AgentsView retention, approved USAi alias pricing and client
  coverage; related to `ef0w`.
- `jmga` (P3, deferred): private hosting for Engineer and a hardened
  Librarian.
- `vg0b` (P3, deferred): OneDrive cloud copy and running-application restore
  checks; related to `5xrm`.

## Live environment (owner install)

- Checkout `~/engineer`, `unit_prefix = "engineer"`. It has no
  `.local/engineer-install.json`, so manage it with `scripts/local_env.py`
  (`./engineer install`/`uninstall` refuse it).
- Units `engineer-{kata,roborev,agentsview,forge}.service` on loopback;
  running versions are in `context/tools.md`, URLs in `README.md`.
- Registered Forge repositories and Kata mappings: `gsa/the_engineer` ->
  `the_engineer`, `gsa/the_librarian` -> `the_librarian`, `gsa/aos-spud` ->
  `spud`.
- Models (`usai.json`, `pi/settings.json`, `roborev/config.toml`): coder
  `claude-sonnet-5.5`, reviewer `gpt-6.1-sol-latest-guardrails-defaultv2`,
  alternate Forge coder target `pi-argon` (`gemini-4-argon`). `pi/models.json`
  holds 26 USAi chat models; `USAI_MODEL_LIMITS` caps main Claude/Gemini at
  400k context and GPT Sol at 272k, each with 32k output.

## Standing gates

- Kata closure is manual: `kata close` only after acceptance is met, with PR
  or commit evidence. Forge's Kata integration is read-only; `430a` tracks
  explicit closure after a merge.
- Server-side protection of `main` awaits `kt2r`; until then the local
  `pre-push` guard and the Pi publication gate are the controls.
- Librarian audit logging (`configure-librarian --audit`) activates on the
  owner install after reinstalling the `librarian-mcp` adapter from
  `~/the_librarian/tools/context-mcp`, rerunning `configure-librarian --audit`
  and restarting clients.

## Where things are documented

| Topic | Location |
| --- | --- |
| Product, boundaries, where knowledge lives | `context/project.md` |
| Services, versions, CLIs, configuration | `context/tools.md` |
| Workflow, review budget, PR evidence | `context/engineering-workflow.md` |
| Runtime topology | `context/system-architecture.md` |
| Jira intake, demo capture, tool failures | `context/jira-intake.md`, `context/demo-capture.md`, `context/tool-failures.md` |
| Teammate and installer usage | `README.md`, `docs/advanced.md`, `dist/README.md` |
