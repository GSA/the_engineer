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
- Treat roborev findings as unverified claims, not tasks. Inspect the cited
  code, confirm the problem is present, reachable, and within the current task,
  then fix only confirmed findings. Close stale or invalid findings with
  evidence and no code change, leave valid out-of-scope findings open and ask
  the owner, and justify every skipped finding in the review comment. Before
  delivery, reuse review evidence for unchanged reviewed code; otherwise run
  `roborev review --branch --wait --min-severity medium` at most once, followed
  by at most one focused, verified fix pass. Do not re-review merely to obtain
  a passing verdict. Hand recurring or unresolved confirmed findings to the
  owner; pause publication for unresolved task-scoped medium/high/critical
  defects. See `context/engineering-workflow.md` for disposition rules.
- Keep configuration repeatable and secret-free. Never place credentials in
  Git, chat, logs, command arguments, or upstream checkouts.
- Require explicit approval before changing global settings or exposing
  services outside loopback. Use isolated local state and loopback for smoke
  tests, and shut down experimental processes when finished.
