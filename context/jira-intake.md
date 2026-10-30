# Manual Jira-to-Kata intake

The first approved Jira tickets reach Kata through a manual, human-approved
intake. `scripts/jira-intake.py` holds the mechanics; people make every
decision. Later automated ingestion or refinement extracts its process from
this contract.

## Access path

- Input is one single-issue Jira XML export supplied by the owner, or another
  read path the owner explicitly approves. Record that path with
  `init --access-path`.
- Follow the VDI export restriction (Kata `6bxa`) and approved model and data
  routes. Use only exports that already reached the workstation by an approved
  route.

## Retained source and provenance

`init` writes `.local/jira-intake/<KEY>/` (directory `0700`, files `0600`) and
refuses any destination Git would track:

- `source.xml`: the export, byte for byte.
- `source.json`: key, URL, summary, type, status, parent, dates, original
  description and acceptance criteria (HTML and plain text), custom fields, and
  provenance (access path, file name, SHA-256, retention time).
- `intake.toml`: the decomposition draft, opening with the original text as
  comments.

`check` and `record` fail if `source.xml` no longer matches its SHA-256. Keep
ticket text out of Git, chat and logs.

## Refinement record (`intake.toml`)

- `[[refinement]]`: an owner-approved clarification, with `approved_by` and
  `approved_at`. A task lists the refinements it implements.
- `[[assumption]]`: a working assumption without approval. Every task body
  carries it under "Assumptions (unapproved)".
- `[[question]]`: an open ambiguity. A `blocking = true` question needs a
  `resolution` before anything is recorded; consequential ambiguity is resolved
  by the owner, never by the intake agent.
- `[[task]]`: one bounded Kata task per target Kata project, with `title`,
  `outcome`, `acceptance`, `depends_on`, `refinements`, `grounding` (Librarian
  qualified references), and `approved_by`/`approved_at`.

Original acceptance criteria stay unchanged in `source.json`; refinements and
assumptions live beside them.

## Recording tasks

- `check` reports every gap: no tasks, missing approval, unknown or cyclic
  dependencies, unapproved refinements, unresolved blocking questions.
- `record` prints the `kata create` commands in dependency order; `--apply`
  runs them. Each task gets `jira.key`, `jira.url`, `jira.source_sha256` and
  `jira.intake_task` metadata, an idempotency key `jira-<KEY>-<task id>`, and
  `--blocked-by` links to its dependencies. Task bodies go to private
  `bodies/<task id>.md` files passed with `--body-file`, so previews print no
  ticket text.
- A task with `adopt = "<project>#<short id>"` attaches the intake to an
  existing Kata task instead of creating one: `record` sets the same `jira.*`
  metadata on it and appends the approved body as a comment. An optional
  `pull_request` URL is recorded as `jira.pull_request` and in the body. `recorded.json` maps intake task
  ids to Kata refs, so a rerun skips tasks already created.

## Grounding and launch

- Ground each task with qualified Librarian (`falcon-context`) references in
  `grounding`, and collect an `engineer.task-context/v1` packet before acting
  (see `engineering-workflow.md`).
- A person launches each recorded task from **Forge > Workspaces > New
  workspace**; the intake creates tasks only.

## Agent drafting

`prompt-drafts/jira-refinement.example.md` is a draft-only prompt: an agent
may propose `intake.toml` content for human approval. People approve the
entries and run `record --apply`.
