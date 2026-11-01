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
  `blob:` requests load; others are aborted and counted in
  `capture.blocked_requests`.
- `python3 scripts/demo-capture.py smoke` serves a synthetic page on an
  ephemeral loopback port and captures two screenshots and a video. The unit
  suite (`scripts/test_demo_capture.py`) runs the same smoke when `doctor`
  passes.

## Toolchain

`doctor` reports the Node.js binary, the `playwright-core` package and the
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
- Retention defaults to 30 days. `cleanup [--older-than-days N]` lists expired
  bundles; `cleanup --apply` deletes them.

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
