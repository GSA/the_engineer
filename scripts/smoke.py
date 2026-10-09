#!/usr/bin/env python3
"""Check local services without credentials, then stop every owned process."""

import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--only-forge", action="store_true", help="do not start the other tools")
parser.add_argument("--keep-running", action="store_true",
                    help="after successful checks, keep services running until interrupted")
parser.add_argument("--forge-binary", default="forge/kenn-forge",
                    help="Forge binary path, relative to the repository or absolute")
options = parser.parse_args()
FORGE_BINARY = (ROOT / options.forge_binary).resolve()
(ROOT / ".local").mkdir(exist_ok=True)
RUN = Path(tempfile.mkdtemp(prefix="smoke-", dir=ROOT / ".local"))
RUN.chmod(0o700)
HOME = RUN / "home"
HOME.mkdir()
WORKSPACE = RUN / "workspace"
WORKSPACE.mkdir()
for name in ("tmp", "runtime"):
    (RUN / name).mkdir(mode=0o700)
ENV = {
    "PATH": os.pathsep.join(
        [str(FORGE_BINARY.parent)]
        + [str(ROOT / p) for p in ("roborev/bin", "kata", "forge", "agentsview")]
        + [os.environ["PATH"]]
    ),
    "HOME": str(HOME),
    "XDG_CONFIG_HOME": str(HOME / ".config"),
    "XDG_DATA_HOME": str(HOME / ".local/share"),
    "XDG_CACHE_HOME": str(HOME / ".cache"),
    "XDG_RUNTIME_DIR": str(RUN / "runtime"),
    "TMPDIR": str(RUN / "tmp"),
    "TERM": "dumb",
    "NO_COLOR": "1",
    "TELEMETRY_ENABLED": "0",
    "ROBOREV_TELEMETRY_ENABLED": "0",
    "KATA_TELEMETRY_ENABLED": "0",
    "AGENTSVIEW_TELEMETRY_ENABLED": "0",
    "ROBOREV_DATA_DIR": str(RUN / "roborev"),
    "KATA_HOME": str(RUN / "kata"),
    "KATA_SERVER": "http://127.0.0.1:17777",
    "KATA_AUTHOR": "smoke-test",
    "KENN_FORGE_HOME": str(RUN / "forge"),
    "AGENTSVIEW_DATA_DIR": str(RUN / "agentsview"),
    "AGENTSVIEW_NO_DAEMON": "1",
    "PI_CODING_AGENT_DIR": str(HOME / ".pi/agent"),
    "PI_OFFLINE": "1",
}
for name in ("roborev", "kata", "forge", "agentsview"):
    (RUN / name).mkdir()
(RUN / "roborev/config.toml").write_text(
    'server_addr = "127.0.0.1:17373"\nmax_workers = 1\n'
    'default_agent = "pi"\n[web]\nlisten = "127.0.0.1:17374"\n'
)
(RUN / "forge/config.toml").write_text(
    'host = "127.0.0.1"\nport = 18091\n'
    '[roborev]\nendpoint = "http://127.0.0.1:17373"\n'
    'init_managed_clones = false\n'
)
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
children = []
results = []
ports = []


def record(name, status, detail):
    results.append({"check": name, "status": status, "detail": detail})
    print(f"{status}: {name}: {detail}", flush=True)


def request(url, accept="application/json"):
    req = urllib.request.Request(url, headers={"Accept": accept})
    with HTTP.open(req, timeout=3) as response:
        return response.read().decode(), response.headers.get_content_type()


def cli(binary, *args, input_text=None):
    result = subprocess.run(
        [binary, *args], cwd=WORKSPACE, env=ENV, input=input_text,
        text=True, capture_output=True, timeout=30,
    )
    if result.returncode:
        raise RuntimeError(f"{binary} exited {result.returncode}: {result.stderr.strip()}")
    return result.stdout


def check_ui(url):
    # Verify real embedded assets, not just a 200 response containing a stub.
    from html.parser import HTMLParser

    class Scripts(HTMLParser):
        paths = None

        def __init__(self):
            super().__init__()
            self.paths = []

        def handle_starttag(self, tag, attrs):
            if tag == "script" and dict(attrs).get("src"):
                self.paths.append(dict(attrs)["src"])

    html, content_type = request(url, "text/html")
    if content_type != "text/html":
        raise RuntimeError(f"UI returned {content_type}")
    parser = Scripts()
    parser.feed(html)
    if not parser.paths:
        raise RuntimeError("UI has no embedded JavaScript entry point")
    for path in parser.paths:
        asset_url = urllib.parse.urljoin(url, path)
        if urllib.parse.urlsplit(asset_url).netloc != urllib.parse.urlsplit(url).netloc:
            raise RuntimeError("UI unexpectedly references an external script")
        body, content_type = request(asset_url, "*/*")
        if "javascript" not in content_type or not body:
            raise RuntimeError("UI script did not return JavaScript")


def start(name, binary, args, listener_ports, health, ui):
    if not (ROOT / binary).is_file():
        record(name, "BLOCKED", f"missing binary: {binary}; see build log")
        return False
    try:
        for port in listener_ports:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", port))
        log = open(RUN / f"{name}.log", "w")
        try:
            process = subprocess.Popen(
                [str(ROOT / binary), *args], cwd=WORKSPACE, env=ENV,
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            )
        finally:
            log.close()
        children.append((name, process))
        ports.extend(listener_ports)
        deadline = time.monotonic() + 30
        last_error = "not ready"
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"exited {process.returncode}; see {name}.log")
            try:
                body, content_type = request(health)
                payload = json.loads(body)
                if content_type != "application/json" or not isinstance(payload, dict):
                    raise RuntimeError("health endpoint did not return a JSON object")
                if not payload.get("version"):
                    raise RuntimeError("health endpoint did not identify its build")
                if name in ("kata", "agentsview") and payload.get("ok") is not True:
                    raise RuntimeError("health endpoint did not report ok")
                if name == "agentsview" and (
                    payload.get("healthy") is not True or payload.get("pid") != process.pid
                ):
                    raise RuntimeError("AgentsView is unhealthy or answered from another process")
                if name == "roborev" and (
                    payload.get("max_workers") != 1 or payload.get("running_jobs") != 0
                ):
                    raise RuntimeError("roborev did not start with an idle, single-worker queue")
                if name == "forge" and payload.get("status") != "ok":
                    raise RuntimeError("Forge did not report a healthy database")
                if name == "forge" and not payload.get("revision"):
                    raise RuntimeError("Forge did not identify its source revision")
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
                last_error = str(error)
                time.sleep(0.25)
        else:
            raise RuntimeError(f"readiness timeout: {last_error}")
        check_ui(ui)
        detail = f"API and embedded UI/assets responsive; PID {process.pid}"
        if name == "forge":
            detail += f"; version {payload['version']}; revision {payload['revision']}"
        record(name, "PASS", detail)
        return True
    except (OSError, ValueError, RuntimeError) as error:
        record(name, "FAIL", str(error))
        return False


def interrupt(signum, _frame):
    raise SystemExit(128 + signum)


for sig in (signal.SIGTERM, signal.SIGINT):
    signal.signal(sig, interrupt)

try:
    kata_ready = False
    if not options.only_forge:
        start("roborev", "roborev/bin/roborev", ["daemon", "run"],
              [17373, 17374], "http://127.0.0.1:17373/api/status", "http://127.0.0.1:17374/reviews")
        kata_ready = start(
            "kata", "kata/kata",
            ["daemon", "start", "--foreground", "--no-auto-token", "--listen", "127.0.0.1:17777"],
            [17777], "http://127.0.0.1:17777/api/v1/health", "http://127.0.0.1:17777/kata",
        )
        start("agentsview", "agentsview/agentsview",
              ["serve", "--host", "127.0.0.1", "--port", "18080",
               "--no-browser", "--no-sync", "--no-update-check"],
              [18080], "http://127.0.0.1:18080/api/ping", "http://127.0.0.1:18080/")
    start("forge", FORGE_BINARY, ["serve", "--disable-sync"],
          [18091], "http://127.0.0.1:18091/healthz", "http://127.0.0.1:18091/")

    if kata_ready:
        try:
            cli("kata", "init", "--project", "smoke")
            ref = cli("kata", "create", "Verify isolated task storage", "--quiet").strip()
            stored = json.loads(cli("kata", "show", ref, "--json"))
            if stored["issue"]["title"] != "Verify isolated task storage":
                raise RuntimeError("read-back task title differs")
            record("kata task storage", "PASS", "created and read back an isolated task")
        except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as error:
            record("kata task storage", "FAIL", str(error))

    if not options.only_forge:
        try:
            output = cli(
                "pi", "--offline", "--no-extensions", "--no-context-files",
                "--no-prompt-templates", "--no-themes", "--no-tools", "--no-session",
                "--mode", "rpc", "-e", str(ROOT / "superpowers"),
                input_text='{"id":"skills","type":"get_commands"}\n',
            )
            messages = [json.loads(line) for line in output.splitlines() if line.strip()]
            response = next(item for item in messages if item.get("id") == "skills")
            if not response["success"]:
                raise RuntimeError("Pi rejected get_commands")
            skills = [item for item in response["data"]["commands"] if item["name"].startswith("skill:")]
            if not any(item["name"] == "skill:using-superpowers" for item in skills):
                raise RuntimeError("Superpowers bootstrap skill was not discovered")
            record("pi + superpowers", "PASS", f"{len(skills)} skills loaded through offline RPC; no model call")
        except (OSError, ValueError, KeyError, StopIteration, RuntimeError, subprocess.TimeoutExpired) as error:
            record("pi + superpowers", "FAIL", str(error))

    for name, process in children:
        if process.poll() is not None:
            record(f"{name} concurrent liveness", "FAIL", f"exited early: {process.returncode}")
    if options.keep_running and all(item["status"] == "PASS" for item in results):
        (RUN / "results.json").write_text(json.dumps(results, indent=2) + "\n")
        print(f"Preview running; supervisor PID {os.getpid()}; state: {RUN.relative_to(ROOT)}",
              flush=True)
        print("Send SIGTERM to the supervisor or press Ctrl+C to stop all owned services.",
              flush=True)
        while True:
            time.sleep(1)
            exited = [(name, process) for name, process in children if process.poll() is not None]
            if exited:
                for name, process in exited:
                    record(f"{name} preview liveness", "FAIL", f"exited: {process.returncode}")
                break
finally:
    for name, process in reversed(children):
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            record(f"{name} shutdown", "FAIL", "required SIGKILL after 15 seconds")
        else:
            record(f"{name} shutdown", "PASS", f"PID {process.pid} exited")
    open_ports = []
    for port in ports:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as error:
                open_ports.append(port)
                record("shutdown listeners", "FAIL", f"port {port} unavailable after shutdown: {error}")
    if not open_ports:
        record("shutdown listeners", "PASS", f"all {len(ports)} checked ports are available to bind")
    (RUN / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"Evidence: {RUN.relative_to(ROOT)}", flush=True)

raise SystemExit(1 if any(item["status"] != "PASS" for item in results) else 0)
