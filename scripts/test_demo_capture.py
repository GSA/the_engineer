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


def synthetic_frames(directory, count, size=(1280, 800)):
    from PIL import Image, ImageDraw

    paths = []
    for index in range(count):
        image = Image.new("RGB", size, (246, 248, 250))
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 40, 40 + 100 * (index + 1), 140), fill=(30, 100, 200))
        path = Path(directory) / f"step-{index:02d}.png"
        image.save(path)
        paths.append(path)
    return paths


@unittest.skipUnless(demo.doctor()["pillow"], "Pillow unavailable")
class WalkthroughTests(unittest.TestCase):
    def test_step_captions_are_tester_readable(self):
        steps = demo.parse_steps(["fill:#name=Synthetic User", "click:#save", "waitfor:text=Saved",
                                  "press:#name=Enter", "wait:500", "screenshot:after"])
        captions = [demo.step_caption(s) for s in steps]
        self.assertEqual(captions[0], "Enter \u201cSynthetic User\u201d in #name")
        self.assertEqual(captions[1], "Click #save")
        self.assertEqual(captions[2], "Wait for text=Saved")
        self.assertEqual(captions[3], "Press Enter in #name")
        self.assertEqual(captions[4], "Wait 500 ms")
        self.assertEqual(captions[5], "Screenshot: after")

    def test_render_makes_looping_captioned_gif(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            frames = synthetic_frames(tmp, 3)
            out = demo.render_walkthrough(frames, ["Open", "Click #save", "Saved"], Path(tmp) / "w.gif", title="T")
            data = out.read_bytes()
            self.assertTrue(data.startswith(b"GIF89a"))
            with Image.open(out) as gif:
                self.assertEqual(gif.n_frames, 3)
                self.assertEqual(gif.info["loop"], 0)
                self.assertEqual(gif.size[0], demo.WALKTHROUGH_WIDTH)  # downscaled from 1280
                self.assertGreater(gif.size[1], 600)  # frame plus caption bar
                gif.seek(2)
                self.assertEqual(gif.info["duration"], demo.LAST_FRAME_MS)
            self.assertLess(len(data), demo.WALKTHROUGH_LIMIT)

    def test_render_rejects_mismatched_captions(self):
        with tempfile.TemporaryDirectory() as tmp:
            frames = synthetic_frames(tmp, 2)
            with self.assertRaises(demo.CaptureError):
                demo.render_walkthrough(frames, ["only one"], Path(tmp) / "w.gif")

    def _scripted_bundle(self, tmp, frames=3):
        repo = make_repo(tmp)
        bundle = Path(tmp) / "bundle"
        bundle.mkdir(mode=0o700)
        synthetic_frames(bundle, frames)
        steps = demo.parse_steps(["fill:#name=Synthetic User", "click:#save"])
        args = type("A", (), dict(task="the_engineer#8ya9", demonstrates="Save updates status",
                                  retention_days=30, argv=["capture"], ticket="SYN-1"))
        manifest = demo.base_manifest(args, repo, demo.git_info(repo)[1], "scripted")
        manifest["capture"] = {"url": "http://127.0.0.1:1/", "steps": steps}
        manifest["artifacts"] = [demo.describe(bundle, p, "screenshot") for p in sorted(bundle.glob("step-*.png"))]
        demo.write_manifest(bundle, manifest)
        return bundle

    def test_walkthrough_command_adds_verified_gif_and_comment_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._scripted_bundle(tmp)
            code, out, err = run_main("walkthrough", str(bundle))
            self.assertEqual(code, 0, err)
            manifest = json.loads((bundle / "manifest.json").read_text())
            kinds = {a["file"]: a["kind"] for a in manifest["artifacts"]}
            self.assertEqual(kinds["walkthrough.gif"], "walkthrough")
            self.assertEqual(kinds["walkthrough.md"], "note")
            self.assertEqual(stat.S_IMODE((bundle / "walkthrough.gif").stat().st_mode), 0o600)
            note = (bundle / "walkthrough.md").read_text()
            for expected in ("Save updates status", "the_engineer#8ya9", "SYN-1", manifest["commit"][:12],
                             "1. Open the page", "2. Enter \u201cSynthetic User\u201d in #name", "3. Click #save"):
                self.assertIn(expected, note)
            self.assertIn("publish", out)
            self.assertIn("demo-capture.py publish", out)
            self.assertNotIn("uploaded to", out)
            demo.load_verified(bundle)  # manifest hashes still verify
            # rerun replaces rather than duplicates
            self.assertEqual(run_main("walkthrough", str(bundle))[0], 0)
            again = json.loads((bundle / "manifest.json").read_text())
            self.assertEqual([a["file"] for a in again["artifacts"]].count("walkthrough.gif"), 1)

    def test_walkthrough_refuses_bundle_without_step_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            source = Path(tmp) / "manual.png"
            source.write_bytes(b"\x89PNG\r\n\x1a\n")
            _, out, _ = run_main("import", "--repo", str(repo), "--task", "t#1",
                                 "--demonstrates", "x", "--steps", "manual", str(source))
            code, _, err = run_main("walkthrough", out.strip().splitlines()[-1])
            self.assertEqual(code, 2)
            self.assertIn("--walkthrough", err)

    def test_generated_frame_names_are_reserved(self):
        for name in ("step-00", "step-7", "step-100"):
            with self.assertRaises(demo.CaptureError):
                demo.parse_steps([f"screenshot:{name}"])
        demo.parse_steps(["screenshot:steps", "screenshot:before"])

    def test_frames_sort_numerically_past_99(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            for index in (0, 1, 10, 11, 99, 100):
                (bundle / f"step-{index:02d}.png").write_bytes(b"x")
            names = [p.name for p in demo.ordered_step_frames(bundle)]
            self.assertEqual(names, ["step-00.png", "step-01.png", "step-10.png",
                                     "step-11.png", "step-99.png", "step-100.png"])

    def test_failed_rerender_keeps_existing_walkthrough(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._scripted_bundle(tmp)
            self.assertEqual(run_main("walkthrough", str(bundle))[0], 0)
            before = (bundle / "walkthrough.gif").read_bytes()
            original = demo.require_pillow

            def missing():
                raise demo.CaptureError("Pillow is required")

            demo.require_pillow = missing
            try:
                code, _, err = run_main("walkthrough", str(bundle))
            finally:
                demo.require_pillow = original
            self.assertEqual(code, 2)
            self.assertIn("Pillow", err)
            self.assertEqual((bundle / "walkthrough.gif").read_bytes(), before)
            self.assertTrue((bundle / "walkthrough.md").is_file())
            demo.load_verified(bundle)

    def test_walkthrough_refuses_frame_count_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._scripted_bundle(tmp, frames=2)
            code, _, err = run_main("walkthrough", str(bundle))
            self.assertEqual(code, 2)
            self.assertIn("recapture", err)


class ClassifyTests(unittest.TestCase):
    def test_classifies_paths_by_change_type(self):
        result = demo.classify_paths([
            "README.md", "docs/design.md", "context/status.md",
            "web/static/app.css", "src/components/Button.tsx", "templates/index.html",
            "src/app/api/routes.py", "openapi.yaml",
            "src/engine/store.py", "scripts/tool.sh",
        ])
        self.assertEqual(result["docs"], ["README.md", "context/status.md", "docs/design.md"])
        self.assertEqual(result["ui"], ["src/components/Button.tsx", "templates/index.html", "web/static/app.css"])
        self.assertEqual(result["api"], ["openapi.yaml", "src/app/api/routes.py"])
        self.assertEqual(result["backend"], ["scripts/tool.sh", "src/engine/store.py"])

    def test_evidence_required_per_type(self):
        self.assertEqual(demo.required_evidence({"ui": ["a.css"], "api": [], "backend": [], "docs": []}),
                         ["walkthrough"])
        self.assertEqual(demo.required_evidence({"ui": [], "api": ["api/x.py"], "backend": ["y.py"], "docs": []}),
                         ["test-evidence"])
        self.assertEqual(demo.required_evidence({"ui": [], "api": [], "backend": [], "docs": ["a.md"]}), [])

    def test_extra_ui_patterns(self):
        result = demo.classify_paths(["src/screens/home.py"], ui_patterns=["src/screens/*"])
        self.assertEqual(result["ui"], ["src/screens/home.py"])

    def test_classify_command_reads_branch_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            git(repo, "branch", "base")
            (repo / "style.css").write_text("body{}\n")
            git(repo, "add", ".")
            git(repo, "commit", "-q", "-m", "ui")
            code, out, err = run_main("classify", "--repo", str(repo), "--base", "base")
            self.assertEqual(code, 0, err)
            report = json.loads(out)
            self.assertEqual(report["changes"]["ui"], ["style.css"])
            self.assertEqual(report["evidence"], ["walkthrough"])

    def test_walkthrough_skipped_without_ui_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            git(repo, "branch", "base")
            (repo / "tool.py").write_text("print(1)\n")
            git(repo, "add", ".")
            git(repo, "commit", "-q", "-m", "backend")
            self.assertEqual(demo.classify(repo, "base")["changes"]["ui"], [])
            (repo / "page.html").write_text("<p>x</p>\n")  # untracked UI work counts
            self.assertEqual(demo.classify(repo, "base")["changes"]["ui"], ["page.html"])


    def test_capture_walkthrough_refuses_branch_without_ui_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            git(repo, "branch", "base")
            (repo / "tool.py").write_text("print(1)\n")
            git(repo, "add", ".")
            git(repo, "commit", "-q", "-m", "backend")
            code, _, err = run_main("capture", "--repo", str(repo), "--task", "t#1", "--demonstrates", "x",
                                    "--url", "http://127.0.0.1:9/", "--walkthrough", "--base", "base")
            self.assertEqual(code, 2)
            self.assertIn("no UI changes", err)
            self.assertIn("evidence", err)
            self.assertFalse((repo / ".local").exists())

class EvidenceTests(unittest.TestCase):
    def _repo_with_fix(self, tmp):
        repo = make_repo(tmp)
        (repo / "calc.py").write_text("import json,os,sys\nd=json.load(open(os.environ['EVIDENCE_DATA']))\nprint(d['a']-d['b'])\n")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "buggy")
        git(repo, "branch", "base")
        (repo / "calc.py").write_text("import json,os,sys\nd=json.load(open(os.environ['EVIDENCE_DATA']))\nprint(d['a']+d['b'])\n")
        git(repo, "commit", "-q", "-am", "fix")
        data = Path(tmp) / "input.json"
        data.write_text('{"a": 2, "b": 3}\n')
        return repo, data

    def test_evidence_records_data_command_and_before_after_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, data = self._repo_with_fix(tmp)
            code, out, err = run_main(
                "evidence", "--repo", str(repo), "--task", "the_engineer#8ya9", "--ticket", "SYN-2",
                "--demonstrates", "Sum is correct", "--data", str(data),
                "--command", 'python3 calc.py', "--before", "base",
            )
            self.assertEqual(code, 0, err)
            bundle = Path(out.strip().splitlines()[-1])
            _, manifest = demo.load_verified(bundle)
            runs = {r["label"]: r for r in manifest["capture"]["runs"]}
            self.assertEqual(runs["before"]["exit_code"], 0)
            self.assertEqual((bundle / runs["before"]["stdout"]).read_text(), "-1\n")
            self.assertEqual((bundle / runs["after"]["stdout"]).read_text(), "5\n")
            self.assertEqual(runs["before"]["commit"], git(repo, "rev-parse", "base"))
            note = (bundle / "evidence.md").read_text()
            for expected in ("Sum is correct", "the_engineer#8ya9", "SYN-2", '{"a": 2, "b": 3}',
                             "EVIDENCE_DATA=", "python3 calc.py", "Before", "After", "-1", "5",
                             manifest["capture"]["data"][0]["sha256"][:12]):
                self.assertIn(expected, note)
            self.assertEqual(git(repo, "worktree", "list").count("\n"), 0)  # temp worktree removed

    def test_evidence_without_before_and_failing_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, data = self._repo_with_fix(tmp)
            code, out, err = run_main(
                "evidence", "--repo", str(repo), "--task", "t#1", "--demonstrates", "Rejects input",
                "--data", str(data), "--command", "echo bad >&2; exit 3",
            )
            self.assertEqual(code, 0, err)
            bundle = Path(out.strip().splitlines()[-1])
            _, manifest = demo.load_verified(bundle)
            self.assertEqual([r["label"] for r in manifest["capture"]["runs"]], ["after"])
            self.assertEqual(manifest["capture"]["runs"][0]["exit_code"], 3)
            note = (bundle / "evidence.md").read_text()
            self.assertIn("exit code 3", note)
            self.assertIn("bad", note)
            self.assertNotIn("Before", note)

    def test_relative_out_root_still_feeds_before_and_after_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, data = self._repo_with_fix(tmp)
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                code, out, err = run_main("evidence", "--repo", str(repo), "--out-root", "rel-demos",
                                          "--task", "t#1", "--demonstrates", "x", "--data", str(data),
                                          "--command", "python3 calc.py", "--before", "base")
            finally:
                os.chdir(cwd)
            self.assertEqual(code, 0, err)
            bundle = Path(out.strip().splitlines()[-1])
            self.assertTrue(bundle.is_absolute())
            runs = demo.load_verified(bundle)[1]["capture"]["runs"]
            self.assertEqual([r["exit_code"] for r in runs], [0, 0])

    def test_reproduction_sets_every_data_variable(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, data = self._repo_with_fix(tmp)
            other = Path(tmp) / "second.json"
            other.write_text("{}\n")
            code, out, err = run_main("evidence", "--repo", str(repo), "--task", "t#1", "--demonstrates", "x",
                                      "--data", str(data), "--data", str(other), "--command", "true")
            self.assertEqual(code, 0, err)
            note = (Path(out.strip().splitlines()[-1]) / "evidence.md").read_text()
            self.assertIn("EVIDENCE_DATA_FILES=path/to/input.json:path/to/second.json", note)

    def test_single_file_reproduction_sets_data_files_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, data = self._repo_with_fix(tmp)
            code, out, err = run_main("evidence", "--repo", str(repo), "--task", "t#1", "--demonstrates", "x",
                                      "--data", str(data), "--command", 'cat "$EVIDENCE_DATA_FILES"')
            self.assertEqual(code, 0, err)
            note = (Path(out.strip().splitlines()[-1]) / "evidence.md").read_text()
            line = next(l for l in note.splitlines() if l.startswith("EVIDENCE_DATA="))
            self.assertIn("EVIDENCE_DATA_FILES=path/to/input.json", line)
            run = subprocess.run(["bash", "-c", line.replace("path/to/input.json", str(data))], cwd=repo,
                                 capture_output=True, text=True, env={"PATH": os.environ["PATH"]})
            self.assertEqual(run.stdout, data.read_text())

    def test_evidence_requires_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, _ = self._repo_with_fix(tmp)
            code, _, err = run_main("evidence", "--repo", str(repo), "--task", "t#1",
                                    "--demonstrates", "x", "--data", str(Path(tmp) / "absent.json"),
                                    "--command", "true")
            self.assertEqual(code, 2)
            self.assertIn("absent.json", err)


class PublishTests(unittest.TestCase):
    def _fake_gh(self, tmp, comment_body_marker="https://github.com/user-attachments/assets/abc"):
        log = Path(tmp) / "gh.log"
        script = Path(tmp) / "gh"
        script.write_text(f"""#!/bin/sh
printf '%s\\n' "$PWD" "$@" >> {log}
if [ "$1 $2" = "repo view" ]; then echo o/r; exit 0; fi
if [ "$1 $2" = "pr comment" ]; then echo https://github.com/o/r/pull/7#issuecomment-1; exit 0; fi
if [ "$1 $2" = "pr view" ]; then
  echo '{{"comments":[{{"url":"https://github.com/o/r/pull/7#issuecomment-1","body":"![w]({comment_body_marker})"}}]}}'
  exit 0
fi
exit 9
""")
        script.chmod(0o755)
        return script, log

    def test_publish_posts_walkthrough_and_records_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = WalkthroughTests._scripted_bundle(WalkthroughTests(), tmp)
            self.assertEqual(run_main("walkthrough", str(bundle))[0], 0)
            gh, log = self._fake_gh(tmp)
            os.environ["DEMO_CAPTURE_GH"] = str(gh)
            try:
                code, out, err = run_main("publish", str(bundle), "--pr", "7", "--gh-repo", "o/r")
            finally:
                del os.environ["DEMO_CAPTURE_GH"]
            self.assertEqual(code, 0, err)
            calls = log.read_text()
            self.assertIn("--attach\nwalkthrough.gif", calls)
            self.assertIn("--body-file\nwalkthrough.md", calls)
            self.assertIn(str(bundle), calls)
            _, manifest = demo.load_verified(bundle)
            self.assertTrue(manifest["privacy"]["published"])
            self.assertEqual(manifest["privacy"]["published_to"], "https://github.com/o/r/pull/7#issuecomment-1")
            self.assertIn("issuecomment-1", out)

    def test_publish_fails_when_attachment_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = WalkthroughTests._scripted_bundle(WalkthroughTests(), tmp)
            run_main("walkthrough", str(bundle))
            gh, _ = self._fake_gh(tmp, comment_body_marker="./walkthrough.gif")
            os.environ["DEMO_CAPTURE_GH"] = str(gh)
            try:
                code, _, err = run_main("publish", str(bundle), "--pr", "7")
            finally:
                del os.environ["DEMO_CAPTURE_GH"]
            self.assertEqual(code, 2)
            self.assertIn("not uploaded", err)
            self.assertFalse(demo.load_verified(bundle)[1]["privacy"]["published"])

    def test_publish_derives_repo_from_manifest_when_not_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = WalkthroughTests._scripted_bundle(WalkthroughTests(), tmp)
            run_main("walkthrough", str(bundle))
            gh, log = self._fake_gh(tmp)
            os.environ["DEMO_CAPTURE_GH"] = str(gh)
            try:
                code, _, err = run_main("publish", str(bundle), "--pr", "7")
            finally:
                del os.environ["DEMO_CAPTURE_GH"]
            self.assertEqual(code, 0, err)
            calls = log.read_text().split("\n")
            repo = json.loads((bundle / "manifest.json").read_text())["repository"]
            self.assertEqual(calls[0:3], [repo, "repo", "view"])  # resolved in the project checkout
            self.assertEqual(calls.count("--repo"), 2)  # comment and read-back both target o/r

    def test_publish_refuses_bundle_without_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = WalkthroughTests._scripted_bundle(WalkthroughTests(), tmp)
            code, _, err = run_main("publish", str(bundle), "--pr", "7")
            self.assertEqual(code, 2)
            self.assertIn("walkthrough", err)


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

    def test_cleanup_honours_each_bundle_retention(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, bundle = self._bundle(tmp)
            manifest_path = bundle / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["captured_at"] = "2000-01-01T00:00:00+00:00"
            manifest["retention_days"] = 100_000
            manifest_path.write_text(json.dumps(manifest))
            run_main("cleanup", "--repo", str(repo), "--apply")
            self.assertTrue(bundle.exists())
            manifest["retention_days"] = 1
            manifest_path.write_text(json.dumps(manifest))
            code, out, _ = run_main("cleanup", "--repo", str(repo))
            self.assertIn(str(bundle), out)
            run_main("cleanup", "--repo", str(repo), "--apply")
            self.assertFalse(bundle.exists())

    def test_cleanup_lists_then_deletes_expired_bundles(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, bundle = self._bundle(tmp)
            manifest_path = bundle / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["captured_at"] = "2000-01-01T00:00:00+00:00"
            manifest_path.write_text(json.dumps(manifest))
            code, out, _ = run_main("cleanup", "--repo", str(repo), "--older-than-days", "30")
            self.assertEqual(code, 0)
            self.assertIn(str(bundle), out)
            self.assertTrue(bundle.exists())
            code, _, _ = run_main("cleanup", "--repo", str(repo), "--older-than-days", "30", "--apply")
            self.assertEqual(code, 0)
            self.assertFalse(bundle.exists())


class PreflightTests(unittest.TestCase):
    def test_preflight_does_not_follow_redirects(self):
        import http.server, threading
        hits = []

        class Target(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.path)
                self.send_response(200)
                self.end_headers()

            def log_message(self, *_):
                pass

        target = http.server.HTTPServer(("127.0.0.1", 0), Target)

        class Redirect(Target):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{target.server_address[1]}/remote")
                self.end_headers()

        source = http.server.HTTPServer(("127.0.0.1", 0), Redirect)
        for server in (target, source):
            threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            demo.preflight(f"http://127.0.0.1:{source.server_address[1]}/", 5)
        finally:
            for server in (target, source):
                server.shutdown()
                server.server_close()
        self.assertEqual(hits, [])


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
            self.assertGreaterEqual(manifest["capture"]["blocked_websockets"], 1)
            self.assertEqual(manifest["method"], "scripted")

    @unittest.skipUnless(demo.doctor()["pillow"], "Pillow unavailable")
    def test_smoke_walkthrough_renders_one_frame_per_step(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run_main("smoke", "--walkthrough", "--out-root", tmp, "--timeout", "90")
            self.assertEqual(code, 0, err)
            bundle = Path(out.strip().splitlines()[-1])
            self.assertEqual(len(list(bundle.glob("step-*.png"))), 5)  # open + 4 steps
            with Image.open(bundle / "walkthrough.gif") as gif:
                self.assertEqual(gif.n_frames, 5)
            self.assertIn("Enter \u201cSynthetic User\u201d in #name", (bundle / "walkthrough.md").read_text())
            demo.load_verified(bundle)


if __name__ == "__main__":
    unittest.main()
