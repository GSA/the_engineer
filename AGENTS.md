# Working agreements

- Read `context/project.md`, `context/tools.md`, and `context/status.md` before
  working. Update them with decisions, evidence, blockers, and shutdown state
  before a handoff, compaction, or the end of a substantial task.
- Ask before consequential assumptions. Prefer simple code and a useful,
  maintainable result over extensive prose or fast delivery.
- Work incrementally; verify actual behavior before claiming completion.
- Use native `kata` commands and repository `.kata.toml` bindings for tasks.
  Search before creating, claim before working, and close only with verified
  completion/evidence. Keep detailed findings in `context/`.
- Optional MCP uses native `kata mcp serve`; load the relevant `kata.load_*`
  section and rediscover tools. Access does not authorize force claims or publication.
- Preserve upstream history, licenses, and local changes. Read a submodule's
  instructions before editing it; do not adopt them workspace-wide.
- Commit completed workspace work locally; keep credentials and private
  assets out of Git. Committing does not authorize pushing or publication.
  Use new commits for fixes; amend commits only with explicit owner approval.
- For coding work, keep temporary specs/plans, including planning-skill output,
  in ignored `.local/plans/` or Kata; override skill defaults that commit them.
  Before delivery, document shipped user-facing usage in `README.md` and
  reusable agent-facing usage in `context/`, then remove task-generated working
  specs/plans. Do not retain them as renamed context documents or ADRs.
- For Pi `subagent` dispatches in the isolated USAi profile, omit `model` or
  pass `model: "inherit"` (or an active `usai/*` model from `pi/models.json`);
  never request external `openai-codex/*` or `anthropic/*` models.
- Keep configuration repeatable and secret-free. Never place credentials in
  Git, chat, logs, command arguments, or upstream checkouts.
- Do not change global settings, publish, or expose services publicly without
  explicit approval. Use isolated local state and loopback for smoke tests.
- Track processes started for experiments and shut them down when finished.
- Keep this file minimal. Tool details and project history belong in `context/`.
