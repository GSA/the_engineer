#!/usr/bin/env python3
"""Read-only health check for the tools agents depend on.

Checks Kata daemon reachability, the Kata project binding of a directory and
Librarian index freshness, and prints the remediation for each failure so an
agent can recover instead of retrying. Nothing is started, repaired or written.

  tool-health.py [--cwd DIR] [--project NAME] [--server URL]
                 [--mcp-config FILE] [--json]

Exit 0 when no check failed (skipped checks do not fail), 1 otherwise.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request

INDEX_TIMEOUT = 60


def environment_defaults():
    """(Kata URL, Pi mcp.json) of this checkout, honouring the saved port offset.

    Reuses local_env so a plain invocation outside the Pi launcher checks the
    managed runtime rather than ~/.pi/agent or the default ports.
    """
    spec = importlib.util.spec_from_file_location("local_env", Path(__file__).with_name("local_env.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    agent_dir = os.environ.get("PI_CODING_AGENT_DIR") or str(module.STATE / "pi")
    return os.environ.get("KATA_SERVER") or module.KATA_URL, Path(agent_dir) / "mcp.json"


def result(name, ok, detail="", action="", skipped=False):
    item = {"name": name, "ok": ok, "detail": detail}
    if action:
        item["action"] = action
    if skipped:
        item["skipped"] = True
    return item


def get_json(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def resolve_from_path(server, cwd):
    """Ask the daemon to resolve `cwd` as native Kata does (.kata.toml, then git alias).

    Returns (project name, None) or (None, daemon message). Resolution creates
    nothing: projects are never created by resolve.
    """
    request = urllib.request.Request(
        f"{server}/api/v1/projects/resolve", data=json.dumps({"start_path": str(cwd)}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)["project"]["name"], None
    except urllib.error.HTTPError as error:
        try:
            return None, json.load(error)["error"]["message"]
        except (ValueError, KeyError, TypeError):
            return None, f"HTTP {error.code}"
    except (OSError, ValueError, KeyError, TypeError) as error:
        return None, str(error)


def find_binding(start, ceiling=None):
    """The project name from the nearest .kata.toml at or above `start`.

    The search stops after `ceiling` when given (tests use it to stay hermetic).
    """
    for directory in (start, *start.parents):
        path = directory / ".kata.toml"
        if path.is_file():
            return tomllib.loads(path.read_text()).get("project", {}).get("name"), path
        if directory == ceiling:
            break
    return None, None


def check_daemon(server):
    try:
        ping = get_json(f"{server}/api/v1/ping")
    except (OSError, ValueError) as error:
        reason = getattr(error, "reason", error)
        return result("kata-daemon", False, f"{server} unreachable: {reason}",
                      "systemctl --user status kenn-kopy-kata.service; restart it if stopped "
                      "(python3 scripts/local_env.py status shows every service). Do not start a second daemon.")
    if not isinstance(ping, dict) or ping.get("service") != "kata":
        return result("kata-daemon", False, f"{server} answered but is not a Kata daemon",
                      "KATA_SERVER points at the wrong service; unset it or use the Kata URL from context/tools.md.")
    return result("kata-daemon", True, f"{server} kata {ping.get('version', '?')}")


def check_project(server, cwd, project, ceiling=None):
    name, source = project, "--project"
    if not name:
        try:
            name, path = find_binding(cwd, ceiling)
        except (OSError, ValueError, AttributeError) as error:
            return result("kata-project", False, f"cannot read .kata.toml: {error}",
                          "Fix the .kata.toml (version = 1, [project] name = \"...\") or pass --project NAME.")
        source = str(path)
    if not name:
        name, why = resolve_from_path(server, cwd)
        source = f"daemon resolution of {cwd}"
    if not name:
        return result("kata-project", False, f"{why}",
                      "Run from the workspace worktree or a repository registered with Kata, or pass "
                      "--project NAME (kata projects list shows names).")
    try:
        projects = get_json(f"{server}/api/v1/projects").get("projects", [])
    except (OSError, ValueError, AttributeError) as error:
        return result("kata-project", False, f"cannot list projects: {error}", "Fix the daemon check first.")
    active = sorted(item["name"] for item in projects if item.get("active", True))
    if name not in active:
        return result("kata-project", False, f"project {name} (from {source}) is not registered",
                      f"Use one of: {', '.join(active)}; or kata init --project {name} in the repository.")
    return result("kata-project", True, f"{name} (from {source})")


def manifest_args(index):
    return ["--manifest", index["manifest"]] if index.get("manifest") else []


def check_index(index):
    if not index:
        return result("index", True, "no Librarian index configured (pi/mcp.json has no falcon-librarian)", skipped=True)
    argv = [index["python"], "-B", "-m", "tools.context_index.context_index", "--root", index["root"],
            *manifest_args(index), "status"]
    try:
        run = subprocess.run(argv, cwd=index["root"], capture_output=True, text=True,
                             stdin=subprocess.DEVNULL, timeout=INDEX_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as error:
        return result("index", False, f"cannot run the index CLI: {error}",
                      f"Check {index['root']} and its .venv exist.")
    try:
        payload = json.loads(run.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return result("index", False, f"index status gave no JSON (exit {run.returncode})",
                      f"Run the index CLI by hand in {index['root']} and read its error.")
    if payload.get("fresh") is True:
        return result("index", True, "fresh")
    # Exit 1 with fresh=false is a state to report, not a tool failure.
    reasons = "; ".join(payload.get("reasons") or ["unknown"])
    return result("index", False, f"stale: {reasons}",
                  f"Rebuild the derived index: python -B -m tools.context_index.context_index "
                  f"--root {index['root']} {' '.join(manifest_args(index))} build".replace("  ", " "))


def index_from_mcp(path):
    """Index settings of the falcon-librarian server (or its legacy falcon-context name) in a Pi mcp.json, if any."""
    try:
        servers = json.loads(Path(path).read_text())["mcpServers"]
        server = servers.get("falcon-librarian") or servers["falcon-context"]
        args = server["args"]
        return {"python": str(Path(server["command"]).parent / "python"),
                "root": args[args.index("--root") + 1],
                "manifest": args[args.index("--manifest") + 1] if "--manifest" in args else None}
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return None


def run_checks(server, cwd, project, index, ceiling=None):
    daemon = check_daemon(server)
    if daemon["ok"]:
        binding = check_project(server, Path(cwd).resolve(), project, ceiling)
    else:
        binding = result("kata-project", False, "not checked: daemon unreachable", skipped=True)
    return [daemon, binding, check_index(index)]


def exit_code(results):
    return 0 if all(item["ok"] for item in results) else 1


def main(argv=None):
    default_server, default_mcp = environment_defaults()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cwd", default=".", help="directory whose Kata binding is checked")
    parser.add_argument("--project", help="check this project instead of the directory's binding")
    parser.add_argument("--server", default=default_server, help="Kata URL (default: KATA_SERVER, else this environment's port)")
    parser.add_argument("--mcp-config", default=str(default_mcp), help="Pi mcp.json naming the Librarian index")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    results = run_checks(args.server.rstrip("/"), args.cwd, args.project, index_from_mcp(args.mcp_config))
    if args.json:
        print(json.dumps({"ok": exit_code(results) == 0, "checks": results}))
    else:
        for item in results:
            label = "SKIP" if item.get("skipped") and item["ok"] else "PASS" if item["ok"] else "FAIL"
            print(f"{label} {item['name']}: {item['detail']}")
            if item.get("action") and not item["ok"] and not item.get("skipped"):
                print(f"  fix: {item['action']}")
    return exit_code(results)


if __name__ == "__main__":
    sys.exit(main())
