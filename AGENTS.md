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
  `KENN_FORGE_RUNTIME_SESSION_KEY` set), edit and commit only in the workspace
  worktree, then push its branch (`git push -u origin HEAD`) and create or
  update a GitHub pull request (`gh pr create` / `gh pr edit`) without asking;
  Forge links that PR to the workspace from its branch. Changes another
  repository needs go on a feature branch and PR there, never on its `main`
  checkout; register those PRs with `kenn_forge_add_workspace_target`, worked
  Kata tasks with `kenn_forge_add_workspace_kata_target`, and confirm with
  `kenn_forge_list_workspace_targets`. Never commit to, push, or offer to push
  `main`, and never merge a PR; merging is the owner's. Outside a Forge workspace, commit completed work
  locally and require explicit owner approval before pushing or amending
  commits; when approved, push a feature branch and open a PR rather than
  pushing `main`. Keep credentials and private assets out of Git.
- Keep temporary specs/plans, including planning-skill output, in ignored
  `.local/plans/` or Kata. Before delivery, document shipped user-facing usage
  in `README.md` and reusable agent-facing usage in `context/`, then remove
  task-generated working specs/plans.
- For Pi `subagent` dispatches, omit `model` or pass `model: "inherit"` (or an
  active `usai/*` model from `pi/models.json`), and omit `model` on
  `action: "resume"`. Use `reviewer` subagents only for Superpowers per-task
  spec/code review; use the native `roborev` CLI and batched post-commit hooks
  for commit and branch reviews.
- Treat roborev findings as unverified claims: fix only confirmed, task-scoped
  findings, run at most one branch review plus one verified fix pass per
  delivery, and hand recurring or out-of-scope findings to the owner. In Forge
  workspaces Pi enforces the budget: a second full-branch review, `roborev
  refine` or unscoped `roborev fix` needs human confirmation, fix passes
  address only the original findings (checked with `roborev review <sha>`),
  and recurring findings trigger a loop self-check. Copilot has no runtime hook.
  Full rules: `context/engineering-workflow.md#bounded-delivery-review-and-dispositions`.
- Librarian and its corpus are owner-only and optional; never make code or
  setup require them (see `context/project.md`).
- Keep configuration repeatable and secret-free. Never place credentials in
  Git, chat, logs, command arguments, or upstream checkouts.
- Require explicit approval before changing global settings or exposing
  services outside loopback. Use isolated local state and loopback for smoke
  tests, and shut down experimental processes when finished.
