#!/usr/bin/env python3
"""Private screenshot and video demos of changed behavior in loopback web UIs.

  capture   drive a loopback URL with headless Playwright Chromium and save a
            screenshot, optional video, and a provenance manifest
  import    register a manually captured screenshot or video (fallback)
  handoff   verify a bundle and print reviewer-ready local references
  cleanup   list (default) or delete (--apply) bundles past retention
  doctor    check the Node/Playwright/browser toolchain
  smoke     bounded capture of a synthetic local page

Bundles live under <repo>/.local/demos/ (directories 0700, files 0600) and are
never uploaded; sharing outside this machine needs explicit owner approval.
"""

import argparse
import datetime
import hashlib
import http.server
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
        elif action == "screenshot" and NAME_RE.match(rest) and rest != "final":
            steps.append({"action": "screenshot", "name": rest})
        elif action == "goto":
            steps.append({"action": "goto", "url": require_loopback(rest)})
        else:
            raise CaptureError(
                f"invalid step {raw!r}; use click:SEL, fill:SEL=TEXT, press:SEL=KEY, "
                f"waitfor:SEL, wait:MS (<= {MAX_WAIT_MS}), screenshot:NAME or goto:LOOPBACK_URL"
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


def write_manifest(bundle, manifest):
    path = bundle / "manifest.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return path


def base_manifest(args, repo, info, method):
    return {
        "schema": SCHEMA,
        "task": args.task,
        "demonstrates": args.demonstrates,
        "repository": str(repo),
        **info,
        "method": method,
        "command": shlex.join(["scripts/demo-capture.py", *args.argv]),
        "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "retention_days": args.retention_days,
        "privacy": {
            "published": False,
            "review_before_sharing": True,
            "sharing": "local only; any upload or attachment needs explicit owner approval",
        },
    }


def describe(bundle, path, kind):
    path.chmod(0o600)
    limit = VIDEO_LIMIT if kind == "video" else SCREENSHOT_LIMIT
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
        "Sharing (only after explicit owner approval and review): attach to the named PR or issue,",
        f"e.g. gh pr comment <N> --body-file note.md --attach {bundle / manifest['artifacts'][0]['file']}",
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
        args.viewport, args.no_video, args.full_page = "800x500", False, False
        return capture(args, url=f"http://127.0.0.1:{server.server_address[1]}/")
    finally:
        server.shutdown()
        server.server_close()


# ----------------------------------------------------------------------- CLI


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--repo", default=".", help="project being demonstrated (default: cwd)")
        p.add_argument("--task", required=True, help="Kata/PR reference, e.g. the_engineer#86ey")
        p.add_argument("--demonstrates", required=True, help="behavior the artifact shows")
        p.add_argument("--out-root", help="default <repo>/.local/demos")
        p.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)

    cap = sub.add_parser("capture", help="scripted capture of a loopback URL")
    common(cap)
    cap.add_argument("--url", required=True)
    cap.add_argument("--step", action="append", default=[], help="repeatable; see context/demo-capture.md")
    cap.add_argument("--viewport", default="1280x800")
    cap.add_argument("--no-video", action="store_true")
    cap.add_argument("--full-page", action="store_true")
    cap.add_argument("--timeout", type=int, default=120, help="seconds for the whole capture")

    imp = sub.add_parser("import", help="register a manual capture")
    common(imp)
    imp.add_argument("--steps", required=True, help="how the capture was made")
    imp.add_argument("files", nargs="+")

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
    print(bundle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
