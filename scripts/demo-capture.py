#!/usr/bin/env python3
"""Private screenshot and video demos of changed behavior in loopback web UIs.

  capture   drive a loopback URL with headless Playwright Chromium and save a
            screenshot, optional video, and a provenance manifest
  import    register a manually captured screenshot or video (fallback)
  walkthrough  render a captioned step-by-step GIF and PR-comment draft from a
            bundle captured with --walkthrough
  classify  sort the branch diff into ui/api/backend/docs and name the evidence needed
  evidence  record synthetic test data, the exact command and its output
            (--before REF adds the pre-change output for bug fixes)
  publish   post walkthrough.md + walkthrough.gif or evidence.md on a PR and verify it
  handoff   verify a bundle and print reviewer-ready local references
  cleanup   list (default) or delete (--apply) bundles past retention
  doctor    check the Node/Playwright/browser toolchain
  smoke     bounded capture of a synthetic local page

Bundles live under <repo>/.local/demos/ (directories 0700, files 0600) and stay
local until `publish` posts one on a PR. Use synthetic data only.
"""

import argparse
import datetime
import fnmatch
import hashlib
import http.server
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import urllib.parse
import urllib.request


SCHEMA = "engineer.demo-capture/v1"
REPO_ROOT = Path(__file__).resolve().parent.parent
DRIVER = Path(__file__).resolve().parent / "demo-capture-driver.mjs"
SCREENSHOT_LIMIT = 10 * 1024 * 1024
VIDEO_LIMIT = 50 * 1024 * 1024
MAX_WAIT_MS = 30_000
DEFAULT_RETENTION_DAYS = 30
WALKTHROUGH_LIMIT = 10 * 1024 * 1024  # GitHub's inline image ceiling
WALKTHROUGH_WIDTH = 960
FRAME_MS, LAST_FRAME_MS = 1800, 3500
STEP_FRAME_RE = re.compile(r"^step-(\d{2,})\.png$")
RESERVED_NAME_RE = re.compile(r"^step-\d+$")  # generated walkthrough frames
FORMATS = {".png": "screenshot", ".webm": "video", ".mp4": "video"}
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
MANUAL_FALLBACK = (
    "manual fallback: capture only the application window with an OS tool, then "
    "run `demo-capture.py import` to record provenance"
)


class CaptureError(Exception):
    pass


# ---------------------------------------------------------------- validation


def require_loopback(url):
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    ok = parsed.scheme in ("http", "https") and not parsed.username and not parsed.password
    if ok and host != "localhost":
        try:
            ok = ipaddress.ip_address(host).is_loopback
        except ValueError:
            ok = False
    if not ok:
        raise CaptureError(
            f"{url!r} is not a loopback http(s) URL; serve the change on "
            "127.0.0.1/localhost with synthetic data, or use the manual fallback"
        )
    return url


def parse_steps(raw_steps):
    steps = []
    for raw in raw_steps:
        action, sep, rest = raw.partition(":")
        if not sep:
            raise CaptureError(f"step {raw!r} must look like ACTION:ARGUMENT")
        if action in ("click", "waitfor") and rest:
            steps.append({"action": action, "selector": rest})
        elif action in ("fill", "press") and "=" in rest:
            selector, _, value = rest.partition("=")
            steps.append({"action": action, "selector": selector, "value": value})
        elif action == "wait" and rest.isdigit() and int(rest) <= MAX_WAIT_MS:
            steps.append({"action": "wait", "ms": int(rest)})
        elif action == "screenshot" and NAME_RE.match(rest) and rest != "final" and not RESERVED_NAME_RE.match(rest):
            steps.append({"action": "screenshot", "name": rest})
        elif action == "goto":
            steps.append({"action": "goto", "url": require_loopback(rest)})
        else:
            raise CaptureError(
                f"invalid step {raw!r}; use click:SEL, fill:SEL=TEXT, press:SEL=KEY, "
                f"waitfor:SEL, wait:MS (<= {MAX_WAIT_MS}), screenshot:NAME (not final or step-N) or goto:LOOPBACK_URL"
            )
    return steps


def ensure_private(directory):
    """Refuse a destination that Git would track."""
    probe = Path(directory)
    while not probe.exists():
        probe = probe.parent
    result = subprocess.run(
        ["git", "-C", str(probe), "check-ignore", "-q", "--no-index", str(directory)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode == 1:
        raise CaptureError(
            f"{directory} is inside a Git checkout and not ignored by Git; "
            "use the default <repo>/.local/demos/ or add an ignore rule"
        )


def make_private_dir(path):
    ensure_private(path)
    old = os.umask(0o077)
    try:
        path.mkdir(parents=True, exist_ok=False)
    finally:
        os.umask(old)
    path.chmod(0o700)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def enforce_size(path, limit):
    size = path.stat().st_size
    if size > limit:
        path.unlink()
        raise CaptureError(
            f"{path.name} is {size} bytes, over the {limit}-byte limit and was deleted; "
            "use a smaller viewport, fewer steps, shorter waits, --no-video or no --full-page"
        )
    return size


# ----------------------------------------------------------------- toolchain


def engineer_roots():
    roots = [REPO_ROOT]
    try:
        common = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        roots.append(Path(common).parent)
    except (OSError, subprocess.CalledProcessError):
        pass
    return list(dict.fromkeys(roots))


def browsers_path(env):
    configured = env.get("PLAYWRIGHT_BROWSERS_PATH")
    if configured:
        return Path(configured)
    for root in engineer_roots():
        candidate = root / ".local" / "tools" / "playwright-browsers"
        if candidate.is_dir():
            return candidate
    return engineer_roots()[-1] / ".local" / "tools" / "playwright-browsers"


def revisions(core):
    data = json.loads((core / "browsers.json").read_text())
    return {item["name"]: item["revision"] for item in data["browsers"]}


def core_candidates(env):
    if env.get("ENGINEER_PLAYWRIGHT_CORE"):
        return [Path(env["ENGINEER_PLAYWRIGHT_CORE"])]
    found = []
    for root in engineer_roots():
        found += sorted((root / ".local" / "cache" / "bun" / "links").glob(
            "playwright-core@*/node_modules/playwright-core"), reverse=True)
    return found


def doctor(env=None, node="auto", video=True):
    env = dict(os.environ if env is None else env)
    problems = []
    if node == "auto":
        node = shutil.which("node", path=env.get("PATH", ""))
    if not node:
        problems.append("Node.js was not found on PATH; install Node 18+ or use the " + MANUAL_FALLBACK)
    browsers = browsers_path(env)
    core = None
    candidates = [c for c in core_candidates(env) if (c / "browsers.json").is_file()]
    if not candidates:
        problems.append(
            "playwright-core was not found; set ENGINEER_PLAYWRIGHT_CORE to an existing "
            "node_modules/playwright-core (no packages are downloaded), or use the " + MANUAL_FALLBACK
        )
    for candidate in candidates:
        rev = revisions(candidate)
        shell = browsers / f"chromium_headless_shell-{rev.get('chromium-headless-shell')}"
        ffmpeg = browsers / f"ffmpeg-{rev.get('ffmpeg')}"
        if (shell / "INSTALLATION_COMPLETE").exists() and (not video or (ffmpeg / "INSTALLATION_COMPLETE").exists()):
            core = candidate
            break
    if candidates and core is None:
        rev = revisions(candidates[0])
        problems.append(
            f"no headless browser matching playwright-core under {browsers} "
            f"(need chromium_headless_shell-{rev.get('chromium-headless-shell')} and "
            f"ffmpeg-{rev.get('ffmpeg')}); install them only into that ignored directory with "
            f"PLAYWRIGHT_BROWSERS_PATH={browsers} node {candidates[0]}/cli.js install "
            "chromium-headless-shell ffmpeg, set PLAYWRIGHT_BROWSERS_PATH, or use --no-video "
            "or the " + MANUAL_FALLBACK
        )
    return {
        "ok": not problems,
        "node": node,
        "playwright_core": str(core) if core else None,
        "browsers_path": str(browsers),
        "pillow": importlib.util.find_spec("PIL") is not None,
        "problems": problems,
    }


# ------------------------------------------------------------------ manifest


def git_info(repo):
    def run(*args):
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)

    top = run("rev-parse", "--show-toplevel")
    if top.returncode != 0:
        raise CaptureError(f"{repo} is not a Git checkout; pass --repo for the project being demonstrated")
    commit = run("rev-parse", "HEAD").stdout.strip() or None
    dirty = bool(run("status", "--porcelain", "--untracked-files=no").stdout.strip())
    branch = run("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or None
    return Path(top.stdout.strip()), {"commit": commit, "branch": branch, "dirty": dirty}


def bundle_dir(out_root, task, commit):
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", task).strip("-") or "task"
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(out_root) / slug / f"{stamp}-{(commit or 'nocommit')[:12]}"


def write_manifest(bundle, manifest, replace=False):
    path = bundle / "manifest.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if replace else os.O_EXCL), 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return path


def base_manifest(args, repo, info, method):
    return {
        "schema": SCHEMA,
        "task": args.task,
        "demonstrates": args.demonstrates,
        "ticket": getattr(args, "ticket", None),
        "repository": str(repo),
        **info,
        "method": method,
        "command": shlex.join(["scripts/demo-capture.py", *args.argv]),
        "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "retention_days": args.retention_days,
        "privacy": {
            "published": False,
            "review_before_sharing": True,
            "sharing": "local until `publish` posts it to the PR; synthetic data only, review frames first",
        },
    }


def describe(bundle, path, kind):
    path.chmod(0o600)
    limit = {"video": VIDEO_LIMIT, "walkthrough": WALKTHROUGH_LIMIT}.get(kind, SCREENSHOT_LIMIT)
    size = enforce_size(path, limit)
    return {"kind": kind, "file": path.name, "bytes": size, "sha256": sha256_file(path)}


# ------------------------------------------------------------------ commands


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect answer already proves the app is up; never follow it."""

    def redirect_request(self, *_args, **_kwargs):
        return None


def preflight(url, timeout):
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        opener.open(url, timeout=min(timeout, 10)).close()
    except urllib.error.HTTPError as answered:
        answered.close()
    except OSError as exc:
        raise CaptureError(
            f"{url} is not reachable ({exc}); start the app on loopback first. "
            "For a headless CLI/API change, capture terminal output instead or use the " + MANUAL_FALLBACK
        ) from None


def capture(args, url=None):
    url = require_loopback(url or args.url)
    steps = parse_steps(args.step)
    if args.walkthrough:
        require_pillow()
        if not getattr(args, "skip_ui_check", False) and not args.any_change:
            report = classify(args.repo, args.base, args.ui_pattern)
            if not report["changes"]["ui"]:
                raise CaptureError(
                    f"no UI changes since {report['base']} (needs {report['evidence'] or 'nothing'}); "
                    "record API/backend proof with `demo-capture.py evidence`, add --ui-pattern for "
                    "this repository's UI paths, or pass --any-change"
                )
    report = doctor(video=not args.no_video)
    if not report["ok"]:
        raise CaptureError("; ".join(report["problems"]))
    repo, info = git_info(args.repo)
    out_root = Path(args.out_root) if args.out_root else repo / ".local" / "demos"
    bundle = bundle_dir(out_root, args.task, info["commit"])
    width, _, height = args.viewport.partition("x")
    if not (width.isdigit() and height.isdigit() and 320 <= int(width) <= 1920 and 240 <= int(height) <= 1200):
        raise CaptureError("--viewport must be WIDTHxHEIGHT within 320x240..1920x1200")
    preflight(url, args.timeout)
    make_private_dir(bundle)
    job = {
        "playwright_core": report["playwright_core"],
        "url": url,
        "steps": steps,
        "out_dir": str(bundle),
        "viewport": [int(width), int(height)],
        "video": not args.no_video,
        "full_page": args.full_page,
        "step_timeout_ms": 10_000,
        "step_pause_ms": 600,
        "step_shots": bool(args.walkthrough),
    }
    env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": report["browsers_path"]}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(job, handle)
    try:
        proc = subprocess.run(
            [report["node"], str(DRIVER), handle.name],
            capture_output=True, text=True, env=env, timeout=args.timeout,
        )
    except subprocess.TimeoutExpired:
        raise CaptureError(
            f"capture exceeded {args.timeout}s and was stopped; shorten the steps or raise --timeout"
        ) from None
    finally:
        os.unlink(handle.name)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-5:])
        raise CaptureError(f"browser capture failed; partial bundle kept at {bundle}:\n{tail}")
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    manifest = base_manifest(args, repo, info, "scripted")
    manifest["capture"] = {
        "url": url,
        "steps": steps,
        "viewport": args.viewport,
        "browser": "playwright chromium-headless-shell (fresh profile, UTC, en-US)",
        "playwright_core": Path(report["playwright_core"]).parent.parent.name,
        "blocked_requests": result["blocked_requests"],
        "blocked_websockets": result["blocked_websockets"],
    }
    manifest["artifacts"] = [describe(bundle, bundle / a["file"], a["kind"]) for a in result["artifacts"]]
    write_manifest(bundle, manifest)
    if args.walkthrough:
        build_walkthrough(bundle)
    return bundle


def import_capture(args):
    repo, info = git_info(args.repo)
    sources = [Path(s) for s in args.files]
    for source in sources:
        if source.suffix.lower() not in FORMATS:
            raise CaptureError(f"{source.name}: supported formats are {', '.join(FORMATS)}")
        if not source.is_file():
            raise CaptureError(f"{source} does not exist")
    out_root = Path(args.out_root) if args.out_root else repo / ".local" / "demos"
    bundle = bundle_dir(out_root, args.task, info["commit"])
    make_private_dir(bundle)
    manifest = base_manifest(args, repo, info, "manual")
    manifest["capture"] = {"steps": args.steps, "sources": [s.name for s in sources]}
    artifacts = []
    for index, source in enumerate(sources, 1):
        dest = bundle / f"manual-{index}{source.suffix.lower()}"
        shutil.copyfile(source, dest)
        artifacts.append(describe(bundle, dest, FORMATS[source.suffix.lower()]))
    manifest["artifacts"] = artifacts
    write_manifest(bundle, manifest)
    return bundle


# --------------------------------------------------------------- walkthrough


def require_pillow():
    try:
        import PIL  # noqa: F401
    except ImportError:
        raise CaptureError(
            "Pillow is required for walkthroughs (Debian/Ubuntu: apt install python3-pil, "
            "or pip install pillow); the PNG and WebM artifacts do not need it"
        ) from None


def step_caption(step):
    """Tester-readable text for one scripted step."""
    action = step["action"]
    if action == "click":
        return f"Click {step['selector']}"
    if action == "fill":
        return f"Enter \u201c{step['value']}\u201d in {step['selector']}"
    if action == "press":
        return f"Press {step['value']} in {step['selector']}"
    if action == "waitfor":
        return f"Wait for {step['selector']}"
    if action == "wait":
        return f"Wait {step['ms']} ms"
    if action == "goto":
        return f"Open {step['url']}"
    return f"Screenshot: {step['name']}"


def render_walkthrough(frames, captions, out_path, title=None):
    """Write a looping GIF: each PNG frame under a caption bar ("n/N  caption")."""
    require_pillow()
    from PIL import Image, ImageDraw, ImageFont

    if not frames or len(frames) != len(captions):
        raise CaptureError("a walkthrough needs one caption per frame and at least one frame")
    try:
        font = ImageFont.load_default(size=18)
    except TypeError:  # Pillow without FreeType sizing
        font = ImageFont.load_default()
    images = []
    for path in frames:
        with Image.open(path) as source:
            image = source.convert("RGB")
        if image.width > WALKTHROUGH_WIDTH:
            image = image.resize((WALKTHROUGH_WIDTH, max(1, round(image.height * WALKTHROUGH_WIDTH / image.width))))
        images.append(image)
    width, height = images[0].size
    bar = 64
    total = len(images)
    rendered = []
    for number, (image, caption) in enumerate(zip(images, captions), 1):
        text = f"{number}/{total}  {caption}"
        if number == 1 and title:
            text = f"{text}\n{title}"
        canvas = Image.new("RGB", (width, height + bar), (24, 26, 31))
        canvas.paste(image.resize((width, height)) if image.size != (width, height) else image, (0, 0))
        draw = ImageDraw.Draw(canvas)
        lines = []
        for part in text.split("\n"):
            lines += textwrap.wrap(part, max(20, width // 10)) or [""]
        draw.multiline_text((12, height + 8), "\n".join(lines[:2]), fill=(235, 238, 245), font=font)
        rendered.append(canvas.convert("P", palette=Image.ADAPTIVE, colors=128))
    durations = [FRAME_MS] * (total - 1) + [LAST_FRAME_MS]
    rendered[0].save(out_path, format="GIF", save_all=True, append_images=rendered[1:], duration=durations, loop=0, optimize=True)
    return out_path


def walkthrough_note(manifest):
    commit = (manifest.get("commit") or "uncommitted")[:12]
    ticket = manifest.get("ticket")
    steps = manifest["capture"].get("steps") or []
    lines = [
        f"### Walkthrough: {manifest['demonstrates']}",
        "",
        f"Task `{manifest['task']}`" + (f" \u00b7 ticket `{ticket}`" if ticket else "")
        + f" \u00b7 commit `{commit}`" + (" (dirty tree)" if manifest.get("dirty") else ""),
        "",
        "![Walkthrough of the change](./walkthrough.gif)",
        "",
        "Steps:",
        "",
        "1. Open the page",
    ]
    lines += [f"{i}. {step_caption(step)}" for i, step in enumerate(steps, 2)]
    lines += ["", "_Captured with synthetic data only; frames reviewed before upload._"]
    return "\n".join(lines) + "\n"


def ordered_step_frames(bundle):
    """Generated frames in numeric order (step-100 follows step-99)."""
    frames = [(int(m.group(1)), p) for p in Path(bundle).iterdir() if (m := STEP_FRAME_RE.match(p.name))]
    return [p for _, p in sorted(frames)]


def build_walkthrough(bundle):
    """Render walkthrough.gif and walkthrough.md for a bundle with step frames.

    Outputs are rendered beside the bundle's files first and swapped in only
    after validation, so a failed re-render leaves the verified bundle intact.
    """
    require_pillow()
    bundle, manifest = load_verified(bundle)
    frames = ordered_step_frames(bundle)
    steps = (manifest.get("capture") or {}).get("steps")
    if not frames or steps is None:
        raise CaptureError(
            f"{bundle} has no step frames; capture it with `capture --walkthrough` "
            "(imported manual captures have no scripted steps)"
        )
    if len(frames) != len(steps) + 1 or [int(STEP_FRAME_RE.match(p.name).group(1)) for p in frames] != list(range(len(frames))):
        raise CaptureError(f"{bundle} has {len(frames)} step frames for {len(steps)} steps; recapture")
    captions = ["Open the page"] + [step_caption(step) for step in steps]
    gif, note = bundle / "walkthrough.gif", bundle / "walkthrough.md"
    new_gif, new_note = bundle / ".walkthrough.gif.tmp", bundle / ".walkthrough.md.tmp"
    try:
        render_walkthrough(frames, captions, new_gif, title=manifest["demonstrates"])
        old = os.umask(0o077)
        try:
            new_note.write_text(walkthrough_note(manifest))
        finally:
            os.umask(old)
        new_gif.chmod(0o600)
        enforce_size(new_gif, WALKTHROUGH_LIMIT)
        new_gif.replace(gif)
        new_note.replace(note)
    finally:
        new_gif.unlink(missing_ok=True)
        new_note.unlink(missing_ok=True)
    manifest["artifacts"] = [a for a in manifest["artifacts"] if a["file"] not in (gif.name, note.name)]
    manifest["artifacts"] += [describe(bundle, gif, "walkthrough"), describe(bundle, note, "note")]
    write_manifest(bundle, manifest, replace=True)
    return bundle


def walkthrough_instructions(bundle):
    return "\n".join([
        f"Walkthrough: {bundle / 'walkthrough.gif'} (caption draft: {bundle / 'walkthrough.md'})",
        "Review every frame, then post it on the PR (gh >= 2.99):",
        f"  python3 scripts/demo-capture.py publish {shlex.quote(str(bundle))} --pr <PR>",
    ])


# ------------------------------------------------------- PR change evidence

DOC_SUFFIXES = {".md", ".rst", ".txt", ".adoc"}
DOC_DIRS = {"docs", "doc", "context"}
UI_SUFFIXES = {".css", ".scss", ".sass", ".less", ".html", ".htm", ".tsx", ".jsx", ".vue", ".svelte", ".astro"}
UI_DIRS = {"components", "templates", "static", "public", "frontend", "ui", "pages", "views", "styles", "assets"}
API_DIRS = {"api", "apis", "routes", "endpoints", "handlers", "graphql"}
API_NAME_RE = re.compile(r"(openapi|swagger)[^/]*\.(ya?ml|json)$|\.(proto|graphql)$", re.IGNORECASE)
NOTE_FILES = ("walkthrough.md", "evidence.md")
INLINE_DATA_LIMIT = 4096
INLINE_OUTPUT_LINES = 60


def classify_paths(paths, ui_patterns=()):
    """Group changed paths into docs, ui, api and backend (first match wins)."""
    groups = {"docs": [], "ui": [], "api": [], "backend": []}
    for path in sorted(set(paths)):
        parts = Path(path).parts
        dirs = {part.lower() for part in parts[:-1]}
        suffix = Path(path).suffix.lower()
        if any(fnmatch.fnmatch(path, pattern) for pattern in ui_patterns):
            group = "ui"
        elif suffix in DOC_SUFFIXES or (dirs & DOC_DIRS and suffix not in UI_SUFFIXES):
            group = "docs"
        elif suffix in UI_SUFFIXES or dirs & UI_DIRS:
            group = "ui"
        elif dirs & API_DIRS or API_NAME_RE.search(path):
            group = "api"
        else:
            group = "backend"
        groups[group].append(path)
    return groups


def required_evidence(groups):
    """UI changes need a walkthrough; API/backend changes need test evidence."""
    needed = []
    if groups["ui"]:
        needed.append("walkthrough")
    if groups["api"] or groups["backend"]:
        needed.append("test-evidence")
    return needed


def default_base(repo):
    for ref in ("origin/main", "main"):
        if subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "-q", ref],
                          capture_output=True).returncode == 0:
            return ref
    raise CaptureError("no origin/main or main to compare with; pass --base REF")


def changed_paths(repo, base):
    """Paths changed on the branch since its merge base with BASE, plus local edits."""
    def lines(*args):
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
        if result.returncode != 0:
            raise CaptureError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return [line for line in result.stdout.splitlines() if line]

    return sorted(set(lines("diff", "--name-only", f"{base}...HEAD") + lines("diff", "--name-only", "HEAD")
                      + lines("ls-files", "--others", "--exclude-standard")))


def classify(repo, base=None, ui_patterns=()):
    top, _ = git_info(repo)
    base = base or default_base(top)
    groups = classify_paths(changed_paths(top, base), ui_patterns)
    return {"base": base, "changes": groups, "evidence": required_evidence(groups)}


def has_ui_changes(repo, base=None, ui_patterns=()):
    return bool(classify(repo, base, ui_patterns)["changes"]["ui"])


def fenced(text, info=""):
    fence = "```"
    while fence in text:
        fence += "`"
    return f"{fence}{info}\n{text.rstrip(chr(10))}\n{fence}"


def clip(text):
    lines = text.splitlines()
    if len(lines) <= INLINE_OUTPUT_LINES:
        return text, False
    return "\n".join(lines[:INLINE_OUTPUT_LINES]), True


def run_evidence_command(command, cwd, env, timeout):
    try:
        proc = subprocess.run(["bash", "-c", command], cwd=cwd, env=env, capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise CaptureError(f"`{command}` exceeded {timeout}s; shorten it or raise --timeout") from None
    return proc.returncode, proc.stdout, proc.stderr


def write_private(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(text)


def evidence(args):
    """Record test data, an exact reproduction command and its output (before/after)."""
    sources = [Path(item).resolve() for item in args.data]
    for source in sources:
        if not source.is_file():
            raise CaptureError(f"--data {source} does not exist; pass the synthetic input the test used")
    repo, info = git_info(args.repo)
    out_root = Path(args.out_root).resolve() if args.out_root else repo / ".local" / "demos"
    bundle = bundle_dir(out_root, args.task, info["commit"])
    make_private_dir(bundle)
    manifest = base_manifest(args, repo, info, "evidence")
    data, artifacts = [], []
    for index, source in enumerate(sources, 1):
        dest = bundle / f"data-{index}{source.suffix.lower()}"
        shutil.copyfile(source, dest)
        artifacts.append(describe(bundle, dest, "data"))
        data.append({"source": str(source), "file": dest.name, "sha256": artifacts[-1]["sha256"],
                     "bytes": artifacts[-1]["bytes"]})
    env = {**os.environ, "EVIDENCE_DATA": str(bundle / data[0]["file"]),
           "EVIDENCE_DATA_FILES": os.pathsep.join(str(bundle / item["file"]) for item in data)}
    runs = []
    plan = ([("before", args.before)] if args.before else []) + [("after", None)]
    for label, ref in plan:
        if ref is None:
            code, out, err = run_evidence_command(args.test_command, repo, env, args.timeout)
            commit = info["commit"]
        else:
            commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", f"{ref}^{{commit}}"],
                                    capture_output=True, text=True).stdout.strip()
            if not commit:
                raise CaptureError(f"--before {ref!r} is not a commit in {repo}")
            with tempfile.TemporaryDirectory(prefix="demo-evidence-") as tmp:
                tree = Path(tmp) / "tree"
                subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "--detach", str(tree), commit],
                               check=True, capture_output=True)
                try:
                    code, out, err = run_evidence_command(args.test_command, tree, env, args.timeout)
                finally:
                    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(tree)],
                                   capture_output=True)
        record = {"label": label, "ref": ref or "HEAD", "commit": commit, "exit_code": code}
        for stream, text in (("stdout", out), ("stderr", err)):
            path = bundle / f"{label}.{stream}.txt"
            write_private(path, text)
            artifacts.append(describe(bundle, path, "output"))
            record[stream] = path.name
        runs.append(record)
    manifest["capture"] = {"command": args.test_command, "data": data, "runs": runs,
                           "data_env": "EVIDENCE_DATA (first file), EVIDENCE_DATA_FILES (all)"}
    note = bundle / "evidence.md"
    write_private(note, evidence_note(manifest, bundle))
    artifacts.append(describe(bundle, note, "note"))
    manifest["artifacts"] = artifacts
    write_manifest(bundle, manifest)
    return bundle


def evidence_note(manifest, bundle):
    capture = manifest["capture"]
    commit = (manifest.get("commit") or "uncommitted")[:12]
    ticket = manifest.get("ticket")
    lines = [
        f"### Test evidence: {manifest['demonstrates']}",
        "",
        f"Task `{manifest['task']}`" + (f" \u00b7 ticket `{ticket}`" if ticket else "")
        + f" \u00b7 commit `{commit}`" + (" (dirty tree)" if manifest.get("dirty") else ""),
        "",
        "**Data used** (synthetic):",
        "",
    ]
    for item in capture["data"]:
        name = Path(item["source"]).name
        lines.append(f"- `{name}` ({item['bytes']} bytes, sha256 `{item['sha256'][:12]}`)")
        raw = (bundle / item["file"]).read_bytes()
        if len(raw) <= INLINE_DATA_LIMIT:
            try:
                lines += ["", fenced(raw.decode("utf-8")), ""]
            except UnicodeDecodeError:
                pass
    names = [f"path/to/{Path(item['source']).name}" for item in capture["data"]]
    assign = f"EVIDENCE_DATA={shlex.quote(names[0])}"
    if len(names) > 1:
        assign += f" EVIDENCE_DATA_FILES={shlex.quote(os.pathsep.join(names))}"
    lines += [
        "",
        "**How it was tested** (run from the repository root; point `EVIDENCE_DATA` at your own "
        "modified copy to reproduce with different data):",
        "",
        fenced(f"{assign} bash -c {shlex.quote(capture['command'])}", "sh"),
        "",
    ]
    if len(capture["data"]) > 1:
        lines += ["`EVIDENCE_DATA_FILES` lists every data file, separated by `:`.", ""]
    for run in capture["runs"]:
        title = {"before": "Before", "after": "After"}[run["label"]] if len(capture["runs"]) > 1 else "Output"
        lines.append(f"**{title}** (`{run['ref']}` at `{run['commit'][:12]}`, exit code {run['exit_code']}):")
        lines.append("")
        for stream in ("stdout", "stderr"):
            text = (bundle / run[stream]).read_text()
            if stream == "stderr" and not text:
                continue
            shown, clipped = clip(text)
            lines += [f"{stream}:" , "", fenced(shown or "(empty)"), ""]
            if clipped:
                lines += [f"_First {INLINE_OUTPUT_LINES} lines shown; full output kept in the local evidence bundle._", ""]
    return "\n".join(lines).rstrip() + "\n"


def gh_binary():
    return os.environ.get("DEMO_CAPTURE_GH", "gh")


def publish(bundle, pr, repo=None):
    """Post the bundle's note (and walkthrough GIF) as a PR comment and verify it."""
    bundle, manifest = load_verified(bundle)
    names = {artifact["file"] for artifact in manifest["artifacts"]}
    note = next((name for name in NOTE_FILES if name in names), None)
    if note is None:
        raise CaptureError(f"{bundle} has no walkthrough.md or evidence.md; run `walkthrough` or `evidence` first")
    attach = ["walkthrough.gif"] if note == "walkthrough.md" and "walkthrough.gif" in names else []
    if not repo:
        found = subprocess.run([gh_binary(), "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                               cwd=manifest["repository"], capture_output=True, text=True, timeout=60)
        repo = found.stdout.strip()
        if found.returncode != 0 or "/" not in repo:
            raise CaptureError(f"cannot resolve the GitHub repository of {manifest['repository']}; pass --gh-repo OWNER/REPO")
    target = ["--repo", repo]
    command = [gh_binary(), "pr", "comment", str(pr), *target, "--body-file", note]
    for name in attach:
        command += ["--attach", name]
    proc = subprocess.run(command, cwd=bundle, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        raise CaptureError(f"gh pr comment failed (exit {proc.returncode}); attachments may be partial:\n"
                           f"{proc.stderr.strip()}")
    url = (proc.stdout.strip().splitlines() or [""])[-1]
    view = subprocess.run([gh_binary(), "pr", "view", str(pr), *target, "--json", "comments"],
                          cwd=bundle, capture_output=True, text=True, timeout=60)
    try:
        body = next(c["body"] for c in json.loads(view.stdout)["comments"] if c.get("url") == url)
    except (ValueError, KeyError, StopIteration):
        raise CaptureError(f"posted {url or 'a comment'} but could not read it back; check the PR before reposting") from None
    for name in attach:
        if "user-attachments/assets/" not in body or f"./{name}" in body:
            raise CaptureError(f"{name} was not uploaded in {url}; fix the comment on the PR instead of reposting")
    manifest["privacy"].update({
        "published": True,
        "published_to": url,
        "published_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    })
    write_manifest(bundle, manifest, replace=True)
    return url


def load_verified(bundle):
    bundle = Path(bundle).resolve()
    try:
        manifest = json.loads((bundle / "manifest.json").read_text())
    except (OSError, ValueError) as exc:
        raise CaptureError(f"{bundle} has no readable manifest.json ({exc})") from None
    if manifest.get("schema") != SCHEMA:
        raise CaptureError(f"{bundle}/manifest.json is not {SCHEMA}")
    for artifact in manifest["artifacts"]:
        path = bundle / artifact["file"]
        if not path.is_file() or sha256_file(path) != artifact["sha256"]:
            raise CaptureError(f"{path} is missing or its SHA-256 no longer matches the manifest")
    return bundle, manifest


def handoff(bundle):
    bundle, manifest = load_verified(bundle)
    commit = manifest.get("commit") or "uncommitted"
    lines = [
        f"Demo for {manifest['task']} at {commit[:12]}{' (dirty tree)' if manifest.get('dirty') else ''}",
        f"Demonstrates: {manifest['demonstrates']}",
        f"Captured {manifest['captured_at']} ({manifest['method']}); manifest: {bundle / 'manifest.json'}",
    ]
    for artifact in manifest["artifacts"]:
        lines.append(f"- {artifact['kind']}: {(bundle / artifact['file']).as_uri()} ({artifact['bytes']} bytes)")
    lines += [
        "Artifacts are local and not uploaded. Review every frame before sharing.",
        "Sharing: `demo-capture.py publish BUNDLE --pr N` posts the walkthrough or evidence note;",
        f"other files: gh pr comment <N> --body-file note.md --attach {bundle / manifest['artifacts'][0]['file']}",
    ]
    return "\n".join(lines)


def expired(out_root, days=None):
    """Bundles whose captured_at plus retention (or the override) has passed."""
    now = datetime.datetime.now(datetime.timezone.utc)
    found = []
    for path in sorted(Path(out_root).glob("*/*/manifest.json")):
        try:
            manifest = json.loads(path.read_text())
            captured = datetime.datetime.fromisoformat(manifest["captured_at"])
            keep = manifest.get("retention_days", DEFAULT_RETENTION_DAYS) if days is None else days
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if now - captured > datetime.timedelta(days=keep):
            found.append(path.parent)
    return found


SMOKE_PAGE = b"""<!doctype html><html><head><meta charset="utf-8"><title>Synthetic demo</title>
<style>body{font:20px sans-serif;margin:40px;background:#f6f8fa}#status{margin-top:20px;font-weight:bold}
button{font-size:20px;padding:8px 16px}</style></head><body>
<h1>Synthetic change demo</h1><p>Fixture page for demo-capture smoke tests; no real data.</p>
<label>Name <input id="name"></label> <button id="save">Save</button>
<div id="status">Not saved</div>
<img alt="" src="https://example.invalid/tracking.png" width="1" height="1">
<script>try{new WebSocket('wss://example.invalid/socket')}catch(e){}</script>
<script>document.getElementById('save').onclick=()=>{document.getElementById('status').textContent=
'Saved: '+document.getElementById('name').value;};</script></body></html>"""


class SmokeHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(SMOKE_PAGE)

    def log_message(self, *_):
        pass


def smoke(args):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SmokeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        args.task = "engineer-demo-smoke"
        args.demonstrates = "Synthetic save button updates the status line"
        args.repo = REPO_ROOT
        args.step = ["screenshot:before", "fill:#name=Synthetic User", "click:#save", "waitfor:text=Saved"]
        args.viewport, args.no_video, args.full_page, args.ticket = "800x500", False, False, None
        args.skip_ui_check = True
        return capture(args, url=f"http://127.0.0.1:{server.server_address[1]}/")
    finally:
        server.shutdown()
        server.server_close()


# ----------------------------------------------------------------------- CLI


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)  # options must not reuse dest "command"

    def common(p):
        p.add_argument("--repo", default=".", help="project being demonstrated (default: cwd)")
        p.add_argument("--task", required=True, help="Kata/PR reference, e.g. the_engineer#86ey")
        p.add_argument("--demonstrates", required=True, help="behavior the artifact shows")
        p.add_argument("--ticket", help="optional Jira/tracker key recorded in the manifest")
        p.add_argument("--out-root", help="default <repo>/.local/demos")
        p.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)

    cap = sub.add_parser("capture", help="scripted capture of a loopback URL")
    common(cap)
    cap.add_argument("--url", required=True)
    cap.add_argument("--step", action="append", default=[], help="repeatable; see context/demo-capture.md")
    cap.add_argument("--viewport", default="1280x800")
    cap.add_argument("--no-video", action="store_true")
    cap.add_argument("--full-page", action="store_true")
    cap.add_argument("--walkthrough", action="store_true",
                     help="also save a frame per step and render a captioned walkthrough.gif")
    cap.add_argument("--timeout", type=int, default=120, help="seconds for the whole capture")
    cap.add_argument("--base", help="branch base for the UI-change check (default origin/main)")
    cap.add_argument("--ui-pattern", action="append", default=[], help="extra glob counted as UI")
    cap.add_argument("--any-change", action="store_true", help="build the walkthrough without UI changes")

    cls = sub.add_parser("classify", help="classify the branch diff as ui/api/backend/docs")
    cls.add_argument("--repo", default=".")
    cls.add_argument("--base", help="default origin/main, else main")
    cls.add_argument("--ui-pattern", action="append", default=[], help="extra glob counted as UI")

    evi = sub.add_parser("evidence", help="record test data, reproduction command and output")
    common(evi)
    evi.add_argument("--data", action="append", required=True, help="synthetic input file (repeatable)")
    evi.add_argument("--command", dest="test_command", required=True, help="shell command; reads $EVIDENCE_DATA")
    evi.add_argument("--before", help="also run on this ref (e.g. the merge base) for before/after output")
    evi.add_argument("--timeout", type=int, default=300)

    pub = sub.add_parser("publish", help="post walkthrough.md + GIF or evidence.md as a PR comment")
    pub.add_argument("bundle")
    pub.add_argument("--pr", required=True)
    pub.add_argument("--gh-repo", help="OWNER/REPO of the PR (default: gh's current repository)")

    imp = sub.add_parser("import", help="register a manual capture")
    common(imp)
    imp.add_argument("--steps", required=True, help="how the capture was made")
    imp.add_argument("files", nargs="+")

    walk = sub.add_parser("walkthrough", help="render walkthrough.gif and a PR-comment draft from a bundle")
    walk.add_argument("bundle")

    hand = sub.add_parser("handoff", help="verify a bundle and print reviewer references")
    hand.add_argument("bundle")

    clean = sub.add_parser("cleanup", help="list or delete bundles past retention")
    clean.add_argument("--repo", default=".")
    clean.add_argument("--out-root")
    clean.add_argument("--older-than-days", type=int, help="override each bundle's retention_days")
    clean.add_argument("--apply", action="store_true")

    sub.add_parser("doctor", help="check the capture toolchain")

    smk = sub.add_parser("smoke", help="bounded capture of a synthetic page")
    smk.add_argument("--out-root")
    smk.add_argument("--timeout", type=int, default=90)
    smk.add_argument("--retention-days", type=int, default=1)
    smk.add_argument("--walkthrough", action="store_true")
    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    args.argv = argv
    try:
        if args.command == "capture":
            bundle = capture(args)
        elif args.command == "import":
            bundle = import_capture(args)
        elif args.command == "smoke":
            bundle = smoke(args)
        elif args.command == "classify":
            print(json.dumps(classify(args.repo, args.base, args.ui_pattern), indent=2))
            return 0
        elif args.command == "evidence":
            bundle = evidence(args)
        elif args.command == "publish":
            print(f"published {publish(args.bundle, args.pr, args.gh_repo)}")
            return 0
        elif args.command == "walkthrough":
            bundle = build_walkthrough(args.bundle)
        elif args.command == "handoff":
            print(handoff(args.bundle))
            return 0
        elif args.command == "cleanup":
            out_root = Path(args.out_root) if args.out_root else git_info(args.repo)[0] / ".local" / "demos"
            for path in expired(out_root, args.older_than_days):
                if args.apply:
                    shutil.rmtree(path)
                print(("deleted " if args.apply else "expired ") + str(path))
            return 0
        else:
            report = doctor()
            print(json.dumps(report, indent=2))
            return 0 if report["ok"] else 1
    except CaptureError as exc:
        print(f"demo-capture: {exc}", file=sys.stderr)
        return 2
    print(handoff(bundle))
    if (bundle / "walkthrough.gif").is_file():
        print(walkthrough_instructions(bundle))
    print(bundle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
