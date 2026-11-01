#!/usr/bin/env python3
"""Tests for demo-capture.py using only synthetic loopback pages."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "demo-capture.py"
spec = importlib.util.spec_from_file_location("demo_capture", MODULE_PATH)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def run_main(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = demo.main(list(args))
    return code, out.getvalue(), err.getvalue()


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def make_repo(root):
    repo = Path(root) / "project"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "demo@example.invalid")
    git(repo, "config", "user.name", "Demo")
    (repo / ".gitignore").write_text(".local/\n")
    (repo / "index.html").write_text("<h1>synthetic</h1>\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "init")
    return repo


class LoopbackTests(unittest.TestCase):
    def test_accepts_loopback_urls(self):
        for url in (
            "http://127.0.0.1:8080/",
            "http://localhost:3000/x",
            "http://[::1]:9000/",
            "https://127.0.0.5/",
        ):
            demo.require_loopback(url)

    def test_rejects_remote_and_unsupported_urls(self):
        for url in (
            "https://example.com/",
            "http://10.0.0.1/",
            "http://127.0.0.1.example.com/",
            "ftp://127.0.0.1/",
            "javascript:alert(1)",
            "http://user:pw@127.0.0.1/",
        ):
            with self.assertRaises(demo.CaptureError, msg=url) as caught:
                demo.require_loopback(url)
            self.assertIn("loopback", str(caught.exception))


class StepTests(unittest.TestCase):
    def test_parses_supported_steps(self):
        steps = demo.parse_steps(
            [
                "click:#save",
                "fill:#name=Synthetic value",
                "wait:250",
                "press:#name=Enter",
                "screenshot:after-save",
                "goto:http://127.0.0.1:1/next",
            ]
        )
        self.assertEqual(steps[0], {"action": "click", "selector": "#save"})
        self.assertEqual(
            steps[1], {"action": "fill", "selector": "#name", "value": "Synthetic value"}
        )
        self.assertEqual(steps[2], {"action": "wait", "ms": 250})
        self.assertEqual(steps[3], {"action": "press", "selector": "#name", "value": "Enter"})
        self.assertEqual(steps[4], {"action": "screenshot", "name": "after-save"})
        self.assertEqual(steps[5]["action"], "goto")

    def test_rejects_bad_steps_with_guidance(self):
        for bad in ("hover:#x", "wait:abc", "wait:999999", "fill:#x", "screenshot:../x", "goto:https://example.com/"):
            with self.assertRaises(demo.CaptureError, msg=bad):
                demo.parse_steps([bad])


class PrivacyAndLimitTests(unittest.TestCase):
    def test_refuses_tracked_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            with self.assertRaises(demo.CaptureError) as caught:
                demo.ensure_private(repo / "demos")
            self.assertIn("not ignored", str(caught.exception))
            demo.ensure_private(repo / ".local" / "demos")

    def test_oversized_artifact_is_removed_with_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "big.png"
            path.write_bytes(b"x" * 2048)
            with self.assertRaises(demo.CaptureError) as caught:
                demo.enforce_size(path, limit=1024)
            self.assertFalse(path.exists())
            self.assertIn("smaller viewport", str(caught.exception))

    def test_import_registers_manual_capture_privately_with_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            source = Path(tmp) / "manual.png"
            source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
            code, out, err = run_main(
                "import",
                "--repo", str(repo),
                "--task", "the_engineer#86ey",
                "--demonstrates", "Synthetic manual capture",
                "--steps", "Opened the synthetic page and captured the window",
                str(source),
            )
            self.assertEqual(code, 0, err)
            bundle = Path(out.strip().splitlines()[-1])
            self.assertTrue(bundle.is_relative_to(repo / ".local" / "demos"))
            self.assertEqual(stat.S_IMODE(bundle.stat().st_mode), 0o700)
            manifest = json.loads((bundle / "manifest.json").read_text())
            self.assertEqual(manifest["schema"], demo.SCHEMA)
            self.assertEqual(manifest["task"], "the_engineer#86ey")
            self.assertEqual(manifest["commit"], git(repo, "rev-parse", "HEAD"))
            self.assertEqual(manifest["method"], "manual")
            self.assertTrue(manifest["command"].startswith("scripts/demo-capture.py import --repo"))
            self.assertEqual(manifest["privacy"]["published"], False)
            (artifact,) = manifest["artifacts"]
            stored = bundle / artifact["file"]
            self.assertEqual(stat.S_IMODE(stored.stat().st_mode), 0o600)
            self.assertEqual(artifact["sha256"], demo.sha256_file(stored))

    def test_import_rejects_unsupported_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            source = Path(tmp) / "capture.gif"
            source.write_bytes(b"GIF89a")
            code, _, err = run_main(
                "import", "--repo", str(repo), "--task", "x#1",
                "--demonstrates", "d", "--steps", "s", str(source),
            )
            self.assertEqual(code, 2)
            self.assertIn(".png", err)


class HandoffAndCleanupTests(unittest.TestCase):
    def _bundle(self, tmp):
        repo = make_repo(tmp)
        source = Path(tmp) / "manual.png"
        source.write_bytes(b"\x89PNG\r\n\x1a\n")
        _, out, _ = run_main(
            "import", "--repo", str(repo), "--task", "the_engineer#86ey",
            "--demonstrates", "Synthetic", "--steps", "manual", str(source),
        )
        return repo, Path(out.strip().splitlines()[-1])

    def test_handoff_prints_local_links_and_privacy_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, bundle = self._bundle(tmp)
            code, out, err = run_main("handoff", str(bundle))
            self.assertEqual(code, 0, err)
            self.assertIn("the_engineer#86ey", out)
            self.assertIn(str(bundle / "manifest.json"), out)
            self.assertIn("not uploaded", out)
            self.assertNotIn("--attach", out.split("Sharing")[0])

    def test_handoff_detects_tampered_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, bundle = self._bundle(tmp)
            manifest = json.loads((bundle / "manifest.json").read_text())
            (bundle / manifest["artifacts"][0]["file"]).write_bytes(b"changed")
            code, _, err = run_main("handoff", str(bundle))
            self.assertEqual(code, 2)
            self.assertIn("SHA-256", err)

    def test_cleanup_lists_then_deletes_expired_bundles(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, bundle = self._bundle(tmp)
            old = 1_000_000_000
            os.utime(bundle / "manifest.json", (old, old))
            code, out, _ = run_main("cleanup", "--repo", str(repo), "--older-than-days", "30")
            self.assertEqual(code, 0)
            self.assertIn(str(bundle), out)
            self.assertTrue(bundle.exists())
            code, _, _ = run_main("cleanup", "--repo", str(repo), "--older-than-days", "30", "--apply")
            self.assertEqual(code, 0)
            self.assertFalse(bundle.exists())


class ToolchainTests(unittest.TestCase):
    def test_missing_node_reports_actionable_guidance(self):
        report = demo.doctor(env={"PATH": "/nonexistent"}, node=None)
        self.assertFalse(report["ok"])
        self.assertTrue(any("Node.js" in item for item in report["problems"]))
        self.assertTrue(any("manual fallback" in item for item in report["problems"]))

    def test_missing_browser_reports_actionable_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = demo.doctor(env={"PLAYWRIGHT_BROWSERS_PATH": tmp, "PATH": os.environ.get("PATH", "")})
            self.assertFalse(report["ok"])
            self.assertTrue(any("browser" in item.lower() for item in report["problems"]))


@unittest.skipUnless(demo.doctor()["ok"], "Playwright toolchain unavailable; run demo-capture.py doctor")
class BoundedSmokeTests(unittest.TestCase):
    def test_smoke_captures_screenshot_and_video_of_synthetic_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run_main("smoke", "--out-root", tmp, "--timeout", "90")
            self.assertEqual(code, 0, err)
            bundle = Path(out.strip().splitlines()[-1])
            manifest = json.loads((bundle / "manifest.json").read_text())
            kinds = sorted(a["kind"] for a in manifest["artifacts"])
            self.assertEqual(kinds, ["screenshot", "screenshot", "video"])
            for artifact in manifest["artifacts"]:
                path = bundle / artifact["file"]
                self.assertGreater(path.stat().st_size, 0)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertTrue((bundle / "final.png").read_bytes().startswith(b"\x89PNG"))
            video = next(a for a in manifest["artifacts"] if a["kind"] == "video")
            self.assertTrue((bundle / video["file"]).read_bytes().startswith(b"\x1aE\xdf\xa3"))
            self.assertGreaterEqual(manifest["capture"]["blocked_requests"], 1)
            self.assertEqual(manifest["method"], "scripted")


if __name__ == "__main__":
    unittest.main()
