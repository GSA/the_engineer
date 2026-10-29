# Working agreements

- Read `context/project.md`, `context/tools.md`, and `context/status.md` before
  working. Update current state in place before a handoff, compaction, or the
  end of a substantial task; keep `context/*.md` concise and affirmative rather
  than prepending chronological logs or negative disclaimers.
- Ask before consequential assumptions. Prefer simple code and a useful,
  maintainable result over extensive prose or fast delivery.
- Work incrementally; verify actual behavior before claiming completion.
- Use native `kata` commands and repository `.kata.toml` bindings for tasks.
  Search before creating, claim before working, and close only with verified
  completion/evidence.
- Optional MCP uses native `kata mcp serve`; load the relevant `kata.load_*`
  section and rediscover tools.
- Preserve upstream history, licenses, and local changes. Read a submodule's
  instructions before editing it.
- In Kenn Forge workspace sessions (`AGENTS.override.md` present or
  `KENN_FORGE_RUNTIME_SESSION_KEY` set), finish verified work by pushing the
  workspace branch (`git push -u origin HEAD`), creating or updating a GitHub
  pull request (`gh pr create` / `gh pr edit`), and registering the PR and any
  worked GitHub/Kata items in Forge via `kenn_forge_add_workspace_target` and
  `kenn_forge_add_workspace_kata_target` (confirming with
  `kenn_forge_list_workspace_targets`). Outside a Forge workspace, commit
  completed work locally and require explicit owner approval before pushing or
  amending commits; keep credentials and private assets out of Git.
- Keep temporary specs/plans, including planning-skill output, in ignored
  `.local/plans/` or Kata. Before delivery, document shipped user-facing usage
  in `README.md` and reusable agent-facing usage in `context/`, then remove
  task-generated working specs/plans.
- For Pi `subagent` dispatches, omit `model` or pass `model: "inherit"` (or an
  active `usai/*` model from `pi/models.json`), and omit `model` on
  `action: "resume"`. Use `reviewer` subagents only for Superpowers per-task
  spec/code review; use the native `roborev` CLI and batched post-commit hooks
  for commit and branch reviews.
- Keep configuration repeatable and secret-free. Never place credentials in
  Git, chat, logs, command arguments, or upstream checkouts.
- Require explicit approval before changing global settings or exposing
  services outside loopback. Use isolated local state and loopback for smoke
  tests, and shut down experimental processes when finished.
