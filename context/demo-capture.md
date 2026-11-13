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

## Tester walkthrough (GIF)

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

Choices (Kata `8ya9`): GIF over WebM/strip because GitHub inlines it in PR
descriptions and comments with no player; the WebM stays as the full-motion
artifact. Testers already open the PR, so the PR comment is the single
"latest walkthrough + status" page; no dashboard or Jira/Kata upload.
Needs Pillow (`doctor` reports `pillow`; `apt install python3-pil`). Imported
manual captures have no steps and cannot be rendered.

Delivery is a human-approved step. After reviewing every frame, with owner
approval for that file and PR, run the printed command (gh >= 2.99, the
`github-pr-media` flow):

```sh
cd <bundle> && gh pr comment <PR> --repo <OWNER/REPO> \
  --body-file walkthrough.md --attach walkthrough.gif
```

`gh` rewrites `./walkthrough.gif` in the body to the uploaded asset URL.

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
handoff. Capture and handoff never upload or publish anything.

Before sharing, a human reviews every frame for credentials, personal data,
notifications, unrelated windows and customer content (including Falcon/AOS).
Attaching to a PR or issue (`gh pr comment N --attach FILE`) needs explicit
owner approval for that file and target, and the repository is public. Do not
commit artifacts.
