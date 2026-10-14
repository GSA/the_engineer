import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import urllib.request


SPEC = importlib.util.spec_from_file_location("engi_installer", Path(__file__).with_name("install.py"))
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="engi-installer-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.corpus = self.root / "approved corpus"
        for name in ("tools/context-mcp/.venv/bin/qualified-context-mcp",
                     "tools/context-index/context_index.py"):
            path = self.corpus / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)

    def git(self, root, *args):
        return subprocess.run(
            ["git", "-C", str(root), *args], check=True, capture_output=True, text=True,
            env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"},
        ).stdout.strip()

    def source(self):
        source = self.root / "source"
        source.mkdir()
        self.git(source, "init", "--quiet", "--template=")
        for name in installer.REQUIRED_FILES:
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("")
        self.git(source, "add", ".")
        self.git(source, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "--quiet", "-m", "fixture")
        return source, self.git(source, "rev-parse", "HEAD")

    def test_missing_tools_are_reported_together(self):
        with patch.object(installer.shutil, "which", return_value=None), \
                patch.object(installer.platform, "system", return_value="Linux"), \
                patch.object(installer.platform, "machine", return_value="x86_64"):
            errors = installer.prerequisites(self.corpus)
        for tool in ("git", "curl", "node", "npm", "cc", "tmux", "pi"):
            self.assertTrue(any(tool in error for error in errors), tool)
        self.assertTrue(any("build-essential" in error for error in errors))

    def test_unsupported_architecture_is_reported(self):
        with patch.object(installer.shutil, "which", return_value=None), \
                patch.object(installer.platform, "machine", return_value="aarch64"):
            self.assertTrue(any("x86_64" in error for error in installer.prerequisites(self.corpus)))

    def test_node_and_pi_versions_are_checked(self):
        with patch.object(installer.shutil, "which", return_value="/fake/tool"), \
                patch.object(installer, "capture", side_effect=lambda command, **kw:
                             "v22.0.0" if command[0] == "node" else "0.87.1"), \
                patch.object(installer, "check_c_toolchain"):
            errors = installer.prerequisites(self.corpus)
        self.assertTrue(any("24.11" in error for error in errors))
        self.assertTrue(any("1.0.3" in error for error in errors))

    def test_missing_c_headers_and_linker_are_reported(self):
        with patch.object(installer.shutil, "which", return_value="/fake/tool"), \
                patch.object(installer, "capture", side_effect=lambda command, **kw:
                             "v26.9.0" if command[0] == "node" else "1.0.3"), \
                patch.object(installer, "check_c_toolchain", side_effect=RuntimeError("missing header")):
            errors = installer.prerequisites(self.corpus)
        self.assertTrue(any("libc6-dev" in error for error in errors))

    def test_corpus_is_required_without_downloading_it(self):
        with patch.object(installer.shutil, "which", return_value=None):
            errors = installer.prerequisites(self.root / "absent")
        self.assertTrue(any("qualified-context-mcp" in error for error in errors))
        self.assertTrue(any("context_index.py" in error for error in errors))

    def test_source_credentials_are_rejected(self):
        for source in ("https://user:secret@example.test/repo.git",
                       "https://example.test/repo.git?token=secret",
                       "ssh://user:secret@example.test/repo.git",
                       "user:secret@example.test:repo.git"):
            with self.subTest(source=source), self.assertRaisesRegex(RuntimeError, "credential"):
                installer.validate_source(source)
        installer.validate_source("https://example.test/team/platform.git")
        installer.validate_source("git@example.test:team/platform.git")

    def test_clone_uses_exact_revision_and_preserves_existing_checkout(self):
        source, revision = self.source()
        destination = self.root / "installation with spaces"
        installer.acquire_checkout(destination, str(source), revision)
        self.assertEqual(self.git(destination, "rev-parse", "HEAD"), revision)
        note = destination / "owner-note"
        note.write_text("retained")
        installer.acquire_checkout(destination, str(source), revision)
        self.assertEqual(note.read_text(), "retained")

    def test_existing_checkout_is_never_moved_to_another_revision(self):
        source, revision = self.source()
        destination = self.root / "installed"
        installer.acquire_checkout(destination, str(source), revision)
        with self.assertRaisesRegex(RuntimeError, "revision"):
            installer.acquire_checkout(destination, str(source), "f" * 40)
        self.assertEqual(self.git(destination, "rev-parse", "HEAD"), revision)

    def test_missing_checkout_requires_explicit_source_and_pin(self):
        for source, revision in ((None, None), ("https://example.test/platform.git", None)):
            with self.assertRaisesRegex(RuntimeError, "source.*revision"):
                installer.acquire_checkout(self.root / "absent", source, revision)
        self.assertFalse((self.root / "absent").exists())

    def test_unrelated_directory_is_not_adopted(self):
        with self.assertRaisesRegex(RuntimeError, "platform checkout"):
            installer.acquire_checkout(self.corpus, None, None)

    def test_modified_submodule_is_rejected_before_update(self):
        with patch.object(installer, "capture", return_value=" M tracked-file\n"):
            (self.root / "forge/.git").mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError, "forge.*changes"):
                installer.check_submodules(self.root)

    def test_noninteractive_install_chooses_manual_services(self):
        with patch.object(installer.sys.stdin, "isatty", return_value=False), \
                patch("builtins.input", side_effect=AssertionError("must not prompt")):
            self.assertEqual(installer.service_choice("ask"), "manual")

    def test_service_prompt_requires_explicit_yes(self):
        with patch.object(installer.sys.stdin, "isatty", return_value=True), \
                patch("builtins.input", return_value=""):
            self.assertEqual(installer.service_choice("ask"), "manual")
        with patch.object(installer.sys.stdin, "isatty", return_value=True), \
                patch("builtins.input", return_value="yes"):
            self.assertEqual(installer.service_choice("ask"), "user")
        with patch.object(installer.sys.stdin, "isatty", return_value=True), \
                patch("builtins.input", return_value="maybe"), self.assertRaisesRegex(RuntimeError, "yes or no"):
            installer.service_choice("ask")

    def test_foreign_user_unit_is_not_replaced(self):
        with patch.object(installer, "capture", side_effect=[
                "", "kenn-kopy-forge.service enabled",
                "/some/other/install/kenn-kopy-forge.service"]):
            with self.assertRaisesRegex(RuntimeError, "another installation"):
                installer.check_user_services(self.root)

    def test_manual_instructions_quote_paths_and_cover_all_services(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            installer.instructions(self.root / "installation with spaces", Path("/node with spaces/node"))
        text = output.getvalue()
        for command in ("kata-run", "agentsview-run", "roborev-run", "forge-run", " stop"):
            self.assertIn(command, text)
        self.assertIn("'installation", text.replace(str(self.root) + "/", ""))
        self.assertIn("--node-executable '/node with spaces/node'", text)

    def test_check_mode_does_not_clone_build_configure_or_enable_services(self):
        args = ["--check", "--checkout", str(self.root / "absent"),
                "--corpus", str(self.corpus)]
        with patch.object(installer, "prerequisites", return_value=[]), \
                patch.object(installer, "acquire_checkout", side_effect=AssertionError("clone")), \
                patch.object(installer, "run", side_effect=AssertionError("side effect")), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(installer.main(args), 0)
        self.assertFalse((self.root / "absent").exists())

    def test_failure_is_not_reported_as_success(self):
        with patch.object(installer, "prerequisites", return_value=["missing git"]), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(installer.main(["--corpus", str(self.corpus)]), 1)
        self.assertIn("missing git", errors.getvalue())

    def installation(self):
        for name in ("forge/kenn-forge", ".local/forge-local-kata/kenn-forge",
                     "roborev/bin/roborev", "kata/kata", "agentsview/agentsview"):
            binary = self.root / name
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.touch()
            binary.chmod(0o755)
        environment = MagicMock(PI_VERSION=installer.PI_VERSION)
        patch.object(installer, "load_environment", return_value=environment).start()
        patch.object(installer.shutil, "which", return_value="/usr/bin/node").start()
        patch.object(installer, "check_submodules").start()
        self.addCleanup(patch.stopall)
        return environment

    def test_manual_install_initializes_builds_and_configures_without_services(self):
        self.installation()
        with patch.object(installer, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            installer.install(self.root, self.corpus, "normal", "manual")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0], ["bash", "scripts/bootstrap-sources.sh"])
        self.assertEqual(commands[1], ["bash", "scripts/bootstrap-toolchains.sh"])
        self.assertEqual(commands[2][-4:], ["roborev", "kata", "agentsview", "forge"])
        self.assertTrue(any("configure-private-pi-tracking" in command for command in commands))
        self.assertTrue(any("install-pi-review-extension" in command for command in commands))
        self.assertFalse(any(any(arg.endswith("-service") for arg in command) for command in commands))

    def test_user_install_explicitly_enables_all_four_services(self):
        self.installation()
        with patch.object(installer, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            installer.install(self.root, self.corpus, "local-kata", "user")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[2][-1], "forge-local-kata")
        self.assertEqual([command[-1] for command in commands[-4:]], [
            "install-kata-service", "install-agentsview-service",
            "install-roborev-service", "install-forge-service",
        ])

    def test_occupied_ports_abort_before_source_or_package_changes(self):
        environment = self.installation()
        environment.check_ports.side_effect = RuntimeError("occupied port")
        with patch.object(installer, "run") as run, self.assertRaisesRegex(RuntimeError, "occupied"):
            installer.install(self.root, self.corpus, "normal", "manual")
        run.assert_not_called()

    def test_failed_build_never_configures_or_starts_services(self):
        self.installation()
        with patch.object(installer, "run", side_effect=[
                None, None, subprocess.CalledProcessError(1, "build")]) as run, \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(subprocess.CalledProcessError):
            installer.install(self.root, self.corpus, "normal", "user")
        self.assertEqual(run.call_count, 3)

    def test_successful_command_without_built_artifact_is_not_success(self):
        self.installation()
        (self.root / "kata/kata").unlink()
        with patch.object(installer, "run") as run, contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaisesRegex(RuntimeError, "executable.*kata"):
            installer.install(self.root, self.corpus, "normal", "manual")
        self.assertEqual(run.call_count, 3)

    def test_main_preserves_existing_readable_build_directory(self):
        checkout, _ = self.source()
        local = checkout / ".local"
        local.mkdir(mode=0o755)
        local.chmod(0o755)
        with patch.object(installer, "prerequisites", return_value=[]), \
                patch.object(installer, "install") as install, \
                contextlib.redirect_stdout(io.StringIO()):
            status = installer.main(["--checkout", str(checkout), "--corpus", str(self.corpus),
                                     "--services", "manual"])
        self.assertEqual(status, 0)
        install.assert_called_once()
        self.assertEqual(local.stat().st_mode & 0o777, 0o755)
        self.assertEqual((local / "installer.lock").stat().st_mode & 0o777, 0o600)

    def test_main_rejects_symlink_build_directory_without_touching_target(self):
        checkout, _ = self.source()
        (checkout / ".local").symlink_to(self.corpus, target_is_directory=True)
        with patch.object(installer, "prerequisites", return_value=[]), \
                patch.object(installer, "install") as install, \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            status = installer.main(["--checkout", str(checkout), "--corpus", str(self.corpus),
                                     "--services", "manual"])
        self.assertEqual(status, 1)
        install.assert_not_called()
        self.assertFalse((self.corpus / "installer.lock").exists())

    def test_concurrent_installer_is_rejected(self):
        checkout, _ = self.source()
        local = checkout / ".local"
        local.mkdir(mode=0o700)
        lock = local / "installer.lock"
        fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, "rb") as held:
            installer.fcntl.flock(held, installer.fcntl.LOCK_EX | installer.fcntl.LOCK_NB)
            with patch.object(installer, "prerequisites", return_value=[]), \
                    patch.object(installer, "install") as install, \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()) as errors:
                status = installer.main(["--checkout", str(checkout), "--corpus", str(self.corpus),
                                         "--services", "manual"])
        self.assertEqual(status, 1)
        self.assertIn("Another installer", errors.getvalue())
        install.assert_not_called()

    def test_shell_reports_missing_python(self):
        empty = self.root / "empty-path"
        empty.mkdir()
        result = subprocess.run(
            ["/bin/bash", str(Path(__file__).with_name("install.sh")), "--help"],
            env={**os.environ, "PATH": str(empty)}, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Python 3.11+", result.stderr)

    def test_real_private_setup_and_agentsview_startup(self):
        root = Path(__file__).resolve().parent.parent
        binary = root / "agentsview/agentsview"
        forge = root / "forge/kenn-forge"
        if not forge.is_file():
            forge = root / ".local/forge-local-kata/kenn-forge"
        if not binary.is_file() or not forge.is_file() or not installer.shutil.which("pi"):
            self.skipTest("Requires locally built binaries and Pi for the isolated runtime check")
        environment = installer.load_environment(root)
        state = self.root / "private-state"
        with patch.object(environment, "STATE", state), contextlib.redirect_stdout(io.StringIO()):
            environment.setup(self.corpus, forge)
            environment.configure_private_pi_tracking()
            env = environment.agentsview_environment()
        session = state / "pi/sessions/installer-fixture/test-session.jsonl"
        session.parent.mkdir()
        session.write_text(
            '{"type":"session","version":3,"id":"installer-fixture",'
            '"timestamp":"2026-01-01T10:00:00Z","cwd":"/tmp/installer-fixture"}\n'
            '{"type":"message","id":"u1","timestamp":"2026-01-01T10:00:01Z",'
            '"message":{"role":"user","content":"test-only-private-prompt"}}\n'
            '{"type":"message","id":"a1","parentId":"u1","timestamp":"2026-01-01T10:00:02Z",'
            '"message":{"role":"assistant","content":"test-only-private-response",'
            '"model":"test-model","usage":{"input":10,"output":5}}}\n'
        )
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        log = self.root / "agentsview.log"
        with log.open("w") as stream:
            process = subprocess.Popen([
                str(binary), "serve", "--host", "127.0.0.1", "--port", str(port),
                "--no-browser", "--no-update-check",
            ], env=env, cwd=state / "home", stdout=stream, stderr=subprocess.STDOUT)
        http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            deadline = time.monotonic() + 20
            while True:
                if process.poll() is not None:
                    self.fail(f"Isolated AgentsView exited: {log.read_text()}")
                try:
                    with http.open(f"http://127.0.0.1:{port}/api/v1/settings", timeout=1) as response:
                        settings = json.load(response)
                    break
                except (urllib.error.URLError, TimeoutError):
                    if time.monotonic() >= deadline:
                        self.fail(f"Isolated AgentsView readiness timed out: {log.read_text()}")
                    time.sleep(0.1)
            pi = next(provider for provider in settings["session_providers"] if provider["id"] == "pi")
            self.assertEqual(pi["dirs"], [str(state / "pi/sessions")])
            for provider in settings["session_providers"]:
                for directory in provider["dirs"]:
                    self.assertTrue(Path(directory).is_relative_to(state), directory)
            with contextlib.closing(sqlite3.connect(
                    f"file:{state / 'agentsview/sessions.db'}?mode=ro", uri=True)) as database:
                while not database.execute("SELECT COUNT(*) FROM sessions WHERE agent = 'pi'").fetchone()[0]:
                    if time.monotonic() >= deadline:
                        self.fail(f"Pi fixture was not ingested: {log.read_text()}")
                    time.sleep(0.1)
                previews = database.execute("SELECT first_message FROM sessions WHERE agent = 'pi'").fetchall()
                self.assertTrue(all(row[0] is None for row in previews), previews)
                messages = database.execute("SELECT content, token_usage FROM messages").fetchall()
                self.assertTrue(messages, "Billed usage should be retained")
                self.assertTrue(all(not row[0] for row in messages), messages)
                self.assertTrue(any(json.loads(row[1])["input_tokens"] == 10 for row in messages))
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", port))
            listener.listen(1)


if __name__ == "__main__":
    unittest.main()
