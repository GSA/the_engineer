# Private demo capture

`scripts/demo-capture.py` lets an agent show changed behavior as screenshots
and a short video, for reviewers who need to see the result rather than a diff.
Capture is scripted headless Chromium against a loopback web UI, with a manual
fallback. Artifacts stay on this machine.

## Scripted capture

Serve the change on `127.0.0.1`/`localhost` with synthetic data, then:

```sh
python3 scripts/demo-capture.py capture --repo . --task the_engineer#86ey \
  --demonstrates "Save updates the status line" \
  --url http://127.0.0.1:8000/ \
  --step screenshot:before --step 'fill:#name=Synthetic User' \
  --step 'click:#save' --step 'waitfor:text=Saved'
```

- Steps run in order: `click:SEL`, `fill:SEL=TEXT`, `press:SEL=KEY`,
  `waitfor:SEL`, `wait:MS` (at most 30000), `screenshot:NAME`,
  `goto:LOOPBACK_URL`. Selectors are Playwright selectors.
- Every run saves `final.png`, `demo.webm` (unless `--no-video`) and
  `manifest.json`. Options: `--viewport WxH` (default `1280x800`),
  `--full-page`, `--timeout SECONDS` (default 120).
- The browser uses a fresh profile (UTC, `en-US`, light theme, reduced motion,
  no permissions, downloads or service workers). Only loopback, `data:` and
  `blob:` requests and WebSockets load; others are aborted and counted in
  `capture.blocked_requests` / `capture.blocked_websockets`. The reachability
  check does not follow redirects.
- `python3 scripts/demo-capture.py smoke` serves a synthetic page on an
  ephemeral loopback port and captures two screenshots and a video. The unit
  suite (`scripts/test_demo_capture.py`) runs the same smoke when `doctor`
  passes.

## Tester walkthrough (UI PRs)

For a UI ticket, add `--walkthrough` (and optionally `--ticket JIRA-KEY`) to
`capture` (or `smoke`). The driver saves `step-NN.png` after the page opens
and after every step; the run then renders `walkthrough.gif` (looping, 960 px
wide, one frame per step under a caption bar `n/N  caption`, 10 MiB cap) and
`walkthrough.md`, a PR-comment draft with the behavior, task, ticket, commit
and numbered steps. Both are recorded in `manifest.json` with SHA-256.

```sh
python3 scripts/demo-capture.py capture --repo . --task the_engineer#8ya9 \
  --ticket JIRA-123 --demonstrates "Save updates the status line" --walkthrough \
  --url http://127.0.0.1:8000/ --step 'fill:#name=Synthetic User' \
  --step 'click:#save' --step 'waitfor:text=Saved'
python3 scripts/demo-capture.py walkthrough .local/demos/<task>/<bundle>  # re-render
```

The GIF is posted as a PR comment, which testers already open; the WebM stays
as the full-motion artifact. Needs Pillow (`doctor` reports `pillow`;
`apt install python3-pil`). Imported manual captures have no steps and cannot
be rendered.

`capture --walkthrough` first classifies the branch diff and refuses to build
a GIF when nothing UI-facing changed, pointing to `evidence` instead. Add
`--ui-pattern GLOB` for a repository's own UI paths, `--base REF` for a
non-`main` base, or `--any-change` to override.

## PR evidence by change type

Jira-sourced (`jira.key`) or `evidence`-labelled Kata tasks get this list
automatically after `gh pr create` in a Forge workspace
(`scripts/pi-extensions/forge-workspace/pr-evidence.ts`); see
`context/engineering-workflow.md#pr-evidence-by-change-type`.

Every PR carries the proof its change type needs, posted as a PR comment:

| `classify` result | Evidence | Command |
| --- | --- | --- |
| `ui` paths (styles, markup, components, templates, static) | Captioned walkthrough GIF | `capture --walkthrough`, then `publish` |
| `api` paths (api/routes/handlers dirs, OpenAPI, proto, GraphQL) | Data used, reproduction command, output | `evidence`, then `publish` |
| `backend` paths (everything else) | Same; bug fixes add output before and after | `evidence --before <merge base>`, then `publish` |
| `docs` only (`*.md`, `docs/`, `context/`) | None | — |

```sh
python3 scripts/demo-capture.py classify [--base origin/main] [--ui-pattern GLOB]
python3 scripts/demo-capture.py evidence --repo . --task the_engineer#8ya9 \
  --demonstrates "Totals add both fields" --data tests/fixtures/input.json \
  --command 'python3 calc.py' --before origin/main
python3 scripts/demo-capture.py publish .local/demos/<task>/<bundle> --pr 42
```

- `classify` reads `git diff BASE...HEAD`, local edits and untracked files and
  prints JSON with the paths per type and the `evidence` list.
- `evidence` copies each `--data` file into the bundle and runs `--command`
  with `bash -c` from the repository root, with `EVIDENCE_DATA` set to the
  first copy (`EVIDENCE_DATA_FILES` lists all). `--before REF` runs the same
  command in a temporary detached worktree at REF, so a bug fix shows output
  before and after. `evidence.md` states the data (inline when at most 4 KiB),
  the exact reproduction command with `EVIDENCE_DATA` for a human to swap in
  modified data, and stdout/stderr with exit codes (first 60 lines; full
  output stays in the bundle). Use synthetic data only.
- `publish BUNDLE --pr N [--gh-repo OWNER/REPO]` runs `gh pr comment
  --body-file walkthrough.md --attach walkthrough.gif` (or `evidence.md`) from
  the bundle, reads the comment back, confirms the GIF became a
  `user-attachments` asset URL, and records `privacy.published_to` in the
  manifest. On a partial failure it stops; fix the comment on the PR instead of
  reposting. Needs gh >= 2.99.

## Toolchain

`doctor` reports the Pillow availability, the Node.js binary, the `playwright-core` package and the
browser directory. It reuses an existing `playwright-core` from the Engineer
`.local/cache/bun/links/` cache (override with `ENGINEER_PLAYWRIGHT_CORE`) and
browsers from `.local/tools/playwright-browsers` (override with
`PLAYWRIGHT_BROWSERS_PATH`), choosing the newest package whose headless
Chromium and FFmpeg revisions are installed. Nothing is downloaded
automatically; `doctor` prints the exact install command for that ignored
directory when browsers are missing.

## Manual fallback

When the app is not a loopback web UI (desktop app, remote-only, headless
CLI/API), capture only the application window with an OS tool after closing
notifications and unrelated windows, then record provenance:

```sh
python3 scripts/demo-capture.py import --repo . --task the_engineer#86ey \
  --demonstrates "..." --steps "How it was captured" shot.png clip.webm
```

`import` accepts `.png`, `.webm` and `.mp4` and copies them into a bundle. For
CLI changes, prefer a transcript of the command and its output.

## Storage, provenance and limits

- Bundles: `<repo>/.local/demos/<task>/<UTC stamp>-<commit12>/`, directories
  `0700`, files `0600`. A destination Git would track is refused.
- `manifest.json` (`engineer.demo-capture/v1`) records task, behavior shown,
  repository, commit, branch, dirty flag, method, exact command, steps, URL,
  capture time, retention, privacy state and each file's size and SHA-256.
- Limits: screenshots 10 MiB, videos 50 MiB. An oversized file is deleted with
  guidance (smaller viewport, fewer steps, `--no-video`, no `--full-page`).
- Retention defaults to 30 days (`--retention-days`). `cleanup` lists bundles
  past their own `captured_at` + `retention_days`; `--older-than-days N`
  overrides that, and `--apply` deletes them.

## Failure guidance

| Condition | Result |
| --- | --- |
| Non-loopback URL or `goto` step | Refused; serve locally or use the manual fallback. |
| App not reachable | Refused before launch; start the app or use the fallback. |
| Node, `playwright-core` or browser missing | `doctor` names the gap and the fix. |
| Step fails or exceeds `--timeout` | Exit 2 with the last browser error; partial bundle kept. |
| Oversized artifact | File deleted with size-reduction guidance. |

No display is needed; capture is headless.

## Handoff and privacy boundary

`handoff BUNDLE` re-verifies every SHA-256 and prints the task, commit,
behavior and `file://` links to paste into a Kata comment, review note or PR
handoff. Only `publish` uploads.

The owner pre-approves agents publishing walkthroughs and evidence notes on
their own PRs (Kata `8ya9`, 2026-11-16). Captures and evidence use synthetic
data only. Before publishing, check every frame and output for credentials,
personal data, notifications, unrelated windows and customer content
(including Falcon/AOS), because the repository is public. Other attachments
still need owner approval. Do not commit artifacts.
