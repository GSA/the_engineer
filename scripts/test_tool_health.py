#!/usr/bin/env python3
"""Tests for tool-health.py against a fake Kata daemon and a fake index CLI."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tool_health", HERE / "tool-health.py")
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)

PROJECTS = [{"name": "the_engineer", "active": True}, {"name": "old", "active": False}]


class Daemon(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/v1/ping":
            body = {"ok": True, "service": "kata", "version": "v1"}
        elif self.path == "/api/v1/projects":
            body = {"projects": PROJECTS}
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        path = json.loads(self.rfile.read(length)).get("start_path", "")
        if self.path == "/api/v1/projects/resolve" and "/gitrepo" in path:
            self.send_response(200)
            body = {"project": {"name": "the_engineer"}}
        else:
            self.send_response(404)
            body = {"error": {"message": "no .kata.toml ancestor and no git ancestor"}}
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, *args):
        pass


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), Daemon)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def bound(self, name="the_engineer"):
        (self.tmp / ".kata.toml").write_text(f'version = 1\n\n[project]\nname = "{name}"\n')
        nested = self.tmp / "a" / "b"
        nested.mkdir(parents=True, exist_ok=True)
        return nested

    def by_name(self, results):
        return {item["name"]: item for item in results}

    def test_reachable_daemon_and_registered_project_pass_from_a_subdirectory(self):
        results = self.by_name(health.run_checks(server=self.url, cwd=self.bound(), project=None, index=None))
        self.assertTrue(results["kata-daemon"]["ok"])
        self.assertTrue(results["kata-project"]["ok"])
        self.assertIn("the_engineer", results["kata-project"]["detail"])

    def test_unreachable_daemon_fails_with_service_remediation_and_skips_project(self):
        results = self.by_name(health.run_checks(server="http://127.0.0.1:1", cwd=self.bound(), project=None, index=None))
        self.assertFalse(results["kata-daemon"]["ok"])
        self.assertIn("kenn-kopy-kata.service", results["kata-daemon"]["action"])
        self.assertTrue(results["kata-project"].get("skipped"))

    def test_no_binding_fails_and_says_to_pass_project(self):
        results = self.by_name(health.run_checks(server=self.url, cwd=self.tmp, project=None, index=None, ceiling=self.tmp))
        self.assertFalse(results["kata-project"]["ok"])
        self.assertIn("--project", results["kata-project"]["action"])

    def test_unbound_directory_that_the_daemon_resolves_through_git_passes(self):
        repo = self.tmp / "gitrepo"
        repo.mkdir()
        results = self.by_name(health.run_checks(server=self.url, cwd=repo, project=None, index=None, ceiling=self.tmp))
        self.assertTrue(results["kata-project"]["ok"])
        self.assertIn("daemon resolution", results["kata-project"]["detail"])

    def test_unbound_directory_the_daemon_cannot_resolve_fails_with_its_message(self):
        results = self.by_name(health.run_checks(server=self.url, cwd=self.tmp, project=None, index=None, ceiling=self.tmp))
        self.assertFalse(results["kata-project"]["ok"])
        self.assertIn("no .kata.toml ancestor", results["kata-project"]["detail"])

    def test_explicit_project_overrides_missing_binding(self):
        results = self.by_name(health.run_checks(server=self.url, cwd=self.tmp, project="the_engineer", index=None))
        self.assertTrue(results["kata-project"]["ok"])

    def test_unregistered_or_inactive_project_fails_and_lists_names(self):
        for name in ("nope", "old"):
            with self.subTest(name=name):
                results = self.by_name(health.run_checks(server=self.url, cwd=self.tmp, project=name, index=None, ceiling=self.tmp))
                self.assertFalse(results["kata-project"]["ok"])
                self.assertIn("the_engineer", results["kata-project"]["action"])
                self.assertIn("Use one of: the_engineer;", results["kata-project"]["action"])

    def test_malformed_kata_toml_is_a_failure_not_a_crash(self):
        (self.tmp / ".kata.toml").write_text("not = [toml")
        results = self.by_name(health.run_checks(server=self.url, cwd=self.tmp, project=None, index=None, ceiling=self.tmp))
        self.assertFalse(results["kata-project"]["ok"])

    def index_cli(self, payload, exit_code):
        script = self.tmp / "fake-python"
        script.write_text(f"#!/bin/sh\necho '{json.dumps(payload)}'\nexit {exit_code}\n")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return {"python": str(script), "root": str(self.tmp), "manifest": str(self.tmp / "m.json")}

    def test_fresh_index_passes(self):
        index = self.index_cli({"command": "status", "fresh": True}, 0)
        results = self.by_name(health.run_checks(server=self.url, cwd=self.bound(), project=None, index=index))
        self.assertTrue(results["index"]["ok"])

    def test_stale_index_exit_one_is_a_reported_state_with_reasons_and_build_action(self):
        index = self.index_cli({"command": "status", "fresh": False, "reasons": ["manifest changed"]}, 1)
        results = self.by_name(health.run_checks(server=self.url, cwd=self.bound(), project=None, index=index))
        self.assertFalse(results["index"]["ok"])
        self.assertIn("manifest changed", results["index"]["detail"])
        self.assertIn("build", results["index"]["action"])

    def test_unparseable_index_output_fails_with_the_exit_code(self):
        script = self.tmp / "bad-python"
        script.write_text("#!/bin/sh\necho oops\nexit 3\n")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        index = {"python": str(script), "root": str(self.tmp), "manifest": "m"}
        results = self.by_name(health.run_checks(server=self.url, cwd=self.bound(), project=None, index=index))
        self.assertFalse(results["index"]["ok"])
        self.assertIn("exit 3", results["index"]["detail"])

    def test_index_not_configured_is_skipped_and_does_not_fail(self):
        results = health.run_checks(server=self.url, cwd=self.bound(), project=None, index=None)
        self.assertTrue(self.by_name(results)["index"]["skipped"])
        self.assertEqual(health.exit_code(results), 0)

    def test_index_config_comes_from_the_pi_mcp_file(self):
        root = self.tmp / "lib"
        (root / ".venv/bin").mkdir(parents=True)
        mcp = self.tmp / "mcp.json"
        mcp.write_text(json.dumps({"mcpServers": {"falcon-context": {
            "command": str(root / ".venv/bin/librarian-mcp"),
            "args": ["--root", str(root), "--manifest", str(root / "sel.json")]}}}))
        self.assertEqual(health.index_from_mcp(mcp), {
            "python": str(root / ".venv/bin/python"), "root": str(root), "manifest": str(root / "sel.json")})
        self.assertIsNone(health.index_from_mcp(self.tmp / "missing.json"))

    def test_index_config_without_a_manifest_is_still_checked(self):
        root = self.tmp / "lib"
        mcp = self.tmp / "mcp.json"
        mcp.write_text(json.dumps({"mcpServers": {"falcon-context": {
            "command": str(root / ".venv/bin/librarian-mcp"), "args": ["--root", str(root)]}}}))
        index = health.index_from_mcp(mcp)
        self.assertEqual(index["root"], str(root))
        self.assertIsNone(index["manifest"])
        script = self.tmp / "py"
        script.write_text('#!/bin/sh\necho "$@" > "$0.args"\necho \'{"fresh": true}\'\n')
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        root.mkdir()
        index["python"] = str(script)
        self.assertTrue(health.check_index(index)["ok"])
        self.assertNotIn("--manifest", Path(f"{script}.args").read_text())

    def test_defaults_come_from_the_managed_environment_not_home(self):
        saved = {key: os.environ.pop(key, None) for key in ("KATA_SERVER", "PI_CODING_AGENT_DIR")}
        self.addCleanup(lambda: os.environ.update({k: v for k, v in saved.items() if v}))
        server, mcp = health.environment_defaults()
        self.assertTrue(server.startswith("http://127.0.0.1:"))
        self.assertEqual(mcp.name, "mcp.json")
        self.assertEqual(mcp.parent.name, "pi")
        self.assertNotIn(".pi/agent", str(mcp))
        os.environ["KATA_SERVER"] = "http://127.0.0.1:9"
        self.assertEqual(health.environment_defaults()[0], "http://127.0.0.1:9")

    def test_main_prints_actions_and_returns_nonzero_on_failure(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = health.main(["--server", "http://127.0.0.1:1", "--cwd", str(self.tmp), "--mcp-config", str(self.tmp / "none")])
        self.assertEqual(code, 1)
        self.assertIn("FAIL kata-daemon", out.getvalue())
        self.assertIn("fix:", out.getvalue())

    def test_main_json_output(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = health.main(["--server", self.url, "--cwd", str(self.bound()), "--json", "--mcp-config", str(self.tmp / "none")])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out.getvalue())["ok"])


if __name__ == "__main__":
    unittest.main()
