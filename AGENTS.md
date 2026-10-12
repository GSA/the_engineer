# Working agreements

- Read `context/project.md`, `context/tools.md`, and `context/status.md` before
  working. Update them with decisions, evidence, blockers, and shutdown state
  before a handoff, compaction, or the end of a substantial task.
- Ask before consequential assumptions. Prefer simple code and a useful,
  maintainable result over extensive prose or fast delivery.
- Work incrementally; verify actual behavior before claiming completion.
- Use `scripts/kata-local.py` for this project's Kata tasks; refresh the
  generated `TODO.md` index with `python3 scripts/kata_todo.py` before handoff.
  Close only with verified completion/evidence; keep detailed findings in `context/`.
- Preserve upstream history, licenses, and local changes. Read a submodule's
  instructions before editing it; do not adopt them workspace-wide.
- Keep configuration repeatable and secret-free. Never place credentials in
  Git, chat, logs, command arguments, or upstream checkouts.
- Do not change global settings, publish, or expose services publicly without
  explicit approval. Use isolated local state and loopback for smoke tests.
- Track processes started for experiments and shut them down when finished.
- Keep this file minimal. Tool details and project history belong in `context/`.
