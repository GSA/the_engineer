import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import tomllib
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
        for tool in ("git", "curl", "node", "npm", "cc", "tmux", "pi", "rg", "fd"):
            self.assertTrue(any(tool in error for error in errors), tool)
        self.assertTrue(any("build-essential" in error for error in errors))
        self.assertTrue(any("ripgrep" in error for error in errors))
        self.assertTrue(any("fd-find" in error and "fdfind" in error for error in errors))

    def test_unsupported_architecture_is_reported(self):
        with patch.object(installer.shutil, "which", return_value=None), \
                patch.object(installer.platform, "machine", return_value="aarch64"):
            self.assertTrue(any("x86_64" in error for error in installer.prerequisites(self.corpus)))

    def test_python_without_pip_enabled_venv_is_reported(self):
        with patch.object(installer.shutil, "which", return_value="/fake/tool"), \
                patch.object(installer, "capture", side_effect=lambda command, **kw:
                             "v26.9.0" if command[0] == "node" else "1.0.3"), \
                patch.object(installer, "check_c_toolchain"), \
                patch.object(installer, "check_python_venv", side_effect=RuntimeError("ensurepip missing")):
            errors = installer.prerequisites(self.corpus)
        self.assertTrue(any("python3-venv" in error and "ensurepip missing" in error for error in errors))

    def test_node_and_pi_versions_are_checked(self):
        with patch.object(installer.shutil, "which", return_value="/fake/tool"), \
                patch.object(installer, "capture", side_effect=lambda command, **kw:
                             "v22.0.0" if command[0] == "node" else "0.87.1"), \
                patch.object(installer, "check_c_toolchain"):
            errors = installer.prerequisites(self.corpus)
        self.assertTrue(any("24.11" in error for error in errors))
        self.assertTrue(any("1.4.0" in error for error in errors))

    def test_missing_c_headers_and_linker_are_reported(self):
        with patch.object(installer.shutil, "which", return_value="/fake/tool"), \
                patch.object(installer, "capture", side_effect=lambda command, **kw:
                             "v26.9.0" if command[0] == "node" else "1.4.0"), \
                patch.object(installer, "check_c_toolchain", side_effect=RuntimeError("missing header")):
            errors = installer.prerequisites(self.corpus)
        self.assertTrue(any("libc6-dev" in error for error in errors))

    def test_corpus_is_required_without_downloading_it(self):
        with patch.object(installer.shutil, "which", return_value=None):
            errors = installer.prerequisites(self.root / "absent")
        self.assertTrue(any("qualified-context-mcp" in error for error in errors))
        self.assertTrue(any("context_index.py" in error for error in errors))

    def explicit_librarian(self):
        root = self.root / "empty toolkit"
        executable = root / ".venv/bin/librarian-mcp"
        reader = root / "tools/context-index/context_index.py"
        selection = root / "config/selection.local.json"
        for path in (executable, reader, selection):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
        return executable, reader, root, selection

    def test_explicit_librarian_prerequisites_use_selected_executable(self):
        executable, reader, root, selection = self.explicit_librarian()
        commands = []
        def capture(command, **kwargs):
            commands.append(command)
            if command[0] == "node":
                return "v26.9.0"
            if command[0] == "pi":
                return installer.PI_VERSION
            return ""
        with patch.object(installer.shutil, "which", return_value="/available"), \
                patch.object(installer, "capture", side_effect=capture), \
                patch.object(installer, "check_c_toolchain"), \
                patch.object(installer, "check_python_venv"):
            errors = installer.prerequisites(self.corpus, executable, reader, root, selection)
        self.assertEqual(errors, [])
        self.assertIn([str(executable), "--help"], commands)

    def test_explicit_librarian_missing_selection_and_dependencies_are_visible(self):
        executable, reader, root, selection = self.explicit_librarian()
        selection.unlink()
        with patch.object(installer.shutil, "which", return_value="/available"), \
                patch.object(installer, "capture", side_effect=RuntimeError("missing dependency")), \
                patch.object(installer, "check_c_toolchain"):
            errors = installer.prerequisites(self.corpus, executable, reader, root, selection)
        self.assertTrue(any(str(selection) in error for error in errors))
        self.assertTrue(any("missing dependency" in error for error in errors))

    def test_explicit_librarian_tuple_is_all_or_none(self):
        _, reader, root, _ = self.explicit_librarian()
        with self.assertRaisesRegex(RuntimeError, "together"):
            installer.librarian_binding(self.corpus, None, reader, root, None)

    def test_explicit_librarian_reader_is_optional(self):
        # The current toolkit rejects --reader and loads its reader module from
        # the selected root, so a reader-free binding must be accepted.
        executable, _, root, selection = self.explicit_librarian()
        server, reader, selected, manifest = installer.librarian_binding(
            self.corpus, executable, None, root, selection)
        self.assertEqual((server, reader, selected, manifest), (executable, None, root, selection))

    def test_explicit_librarian_selection_must_stay_within_root(self):
        executable, reader, root, _ = self.explicit_librarian()
        outside = self.root / "outside-selection.json"
        outside.touch()
        with self.assertRaisesRegex(RuntimeError, "within --librarian-root"):
            installer.librarian_binding(self.corpus, executable, reader, root, outside)

    def test_explicit_librarian_root_must_be_readable_and_searchable(self):
        executable, reader, root, _ = self.explicit_librarian()
        real_access = os.access

        def access(path, mode):
            if Path(path) == root and mode & os.X_OK:
                return False
            return real_access(path, mode)

        with patch.object(installer.shutil, "which", return_value="/available"), \
                patch.object(installer.os, "access", side_effect=access), \
                patch.object(installer, "capture", return_value=""), \
                patch.object(installer, "check_c_toolchain"):
            errors = installer.prerequisites(self.corpus, executable, reader, root)
        self.assertTrue(any(str(root) in error for error in errors))

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
        for name in installer.MANAGED_SERVICES:
            unit = f"kenn-kopy-{name}.service"

            def capture(command, **kwargs):
                if "list-unit-files" in command and command[-1] == unit:
                    return f"{unit} enabled"
                if "--property=FragmentPath" in command:
                    return f"/some/other/install/{unit}"
                return ""

            with self.subTest(service=name), \
                    patch.object(installer.shutil, "which", return_value="/usr/bin/tool"), \
                    patch.object(installer, "capture", side_effect=capture), \
                    self.assertRaisesRegex(RuntimeError, "another installation"):
                installer.check_user_services(self.root)

    def test_fresh_host_without_units_passes_user_service_check(self):
        def fake_run(command, **kwargs):
            # systemctl exits 1 when list-unit-files matches nothing, as on a clean host.
            missing = "list-unit-files" in command
            return subprocess.CompletedProcess(command, 1 if missing else 0, "" if missing else "PATH=/usr/bin\n", "")

        with patch.object(installer.shutil, "which", return_value="/usr/bin/tool"), \
                patch.object(installer.subprocess, "run", side_effect=fake_run):
            installer.check_user_services(self.root)

    def test_managed_services_match_runtime_and_supported_install_commands(self):
        environment = installer.load_environment(installer.ROOT)
        self.assertEqual(set(installer.MANAGED_SERVICES), set(environment.SERVICE_PORTS))
        for name in installer.MANAGED_SERVICES:
            with self.subTest(service=name):
                result = subprocess.run(
                    [installer.sys.executable, str(installer.ROOT / "scripts/local_env.py"),
                     f"install-{name}-service", "--help"],
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_manual_instructions_quote_paths_and_cover_all_services(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            installer.instructions(self.root / "installation with spaces", Path("/node with spaces/node"))
        text = output.getvalue()
        for command in ("daemon start --foreground", "agentsview-run", "roborev-run", "forge-run", " stop"):
            self.assertIn(command, text)
        self.assertIn("'installation", text.replace(str(self.root) + "/", ""))
        self.assertIn("--node-executable '/node with spaces/node'", text)

    def test_kata_startup_paths_ignore_inherited_and_stored_database_overrides(self):
        for startup in ("manual", "unit"):
            with self.subTest(startup=startup):
                self.check_kata_startup_store(startup)

    def check_kata_startup_store(self, startup):
        binary = installer.ROOT / "kata/kata"
        if not binary.is_file():
            self.skipTest("Requires the locally built native Kata binary")
        checkout = self.root / f"{startup} installation with spaces"
        home = checkout / ".local/environment/kata"
        home.mkdir(parents=True, mode=0o700)
        target = checkout / "kata/kata"
        target.parent.mkdir()
        target.symlink_to(binary)
        alternatives = [checkout / f"{name}.db" for name in ("inherited-dsn", "legacy-db", "stored-dsn")]
        config = home / "config.toml"
        config.write_text('listen = "127.0.0.1:17777"\n'
                          f'[storage]\ndsn = {json.dumps(str(alternatives[2]))}\n')
        config.chmod(0o600)
        before = config.read_bytes()
        unit_environment = {}
        if startup == "manual":
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                installer.instructions(checkout, Path("/unused/node"))
            command = next(shlex.split(line) for line in output.getvalue().splitlines()
                           if " daemon start --foreground " in line)
        else:
            environment = installer.load_environment(installer.ROOT)
            with patch.object(environment, "STATE", home.parent), \
                    patch.object(environment, "settings", return_value={}), \
                    patch.object(environment, "managed_kata", return_value={}), \
                    patch.object(environment.subprocess, "run", return_value=MagicMock(returncode=0)), \
                    contextlib.redirect_stdout(io.StringIO()):
                environment.install_kata_service()
            unit = (home.parent / "systemd" / environment.KATA_UNIT).read_text().splitlines()
            command = shlex.split(next(line.removeprefix("ExecStart=") for line in unit
                                       if line.startswith("ExecStart=")))
            for line in unit:
                if line.startswith("Environment="):
                    unit_environment.update(
                        entry.split("=", 1) for entry in shlex.split(line.removeprefix("Environment=")))
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        command[command.index("--listen") + 1] = f"127.0.0.1:{port}"
        env = {
            "HOME": str(self.root), "PATH": os.environ["PATH"],
            "KATA_HOME": str(self.root / "wrong-home"),
            "KATA_DSN": str(alternatives[0]), "KATA_DB": str(alternatives[1]),
            "KATA_TELEMETRY_ENABLED": "0", "TELEMETRY_ENABLED": "0",
        }
        env.update(unit_environment)
        log = checkout / "kata.log"
        with log.open("w") as stream:
            process = subprocess.Popen(command, cwd=checkout, env=env,
                                       stdout=stream, stderr=subprocess.STDOUT)
        http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            deadline = time.monotonic() + 15
            while True:
                if process.poll() is not None:
                    self.fail(f"Isolated Kata exited: {log.read_text()}")
                try:
                    with http.open(f"http://127.0.0.1:{port}/api/v1/health", timeout=1) as response:
                        health = json.load(response)
                    break
                except (urllib.error.URLError, TimeoutError):
                    if time.monotonic() >= deadline:
                        self.fail(f"Isolated Kata readiness timed out: {log.read_text()}")
                    time.sleep(0.1)
            self.assertTrue(health["ok"])
            self.assertEqual(health["db_path"], str(home / "kata.db"))
            self.assertTrue((home / "kata.db").is_file())
            self.assertEqual(config.read_bytes(), before)
            for path in alternatives:
                self.assertFalse(path.exists(), f"alternate store was created: {path}")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

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
        (self.root / ".local/environment/roborev").mkdir(parents=True, exist_ok=True)
        environment = MagicMock(PI_VERSION=installer.PI_VERSION,
                                SERVICE_PORTS=dict.fromkeys(installer.MANAGED_SERVICES),
                                KATA_PORT=18777, KATA_URL="http://127.0.0.1:18777",
                                FORGE_PORT=19091, ROBOREV_WEB_PORT=18374, AGENTSVIEW_PORT=19080)
        patch.object(installer, "load_environment", return_value=environment).start()
        patch.object(installer.shutil, "which", return_value="/usr/bin/node").start()
        patch.object(installer.Path, "home", return_value=self.root / "installer-home").start()
        patch.object(installer, "check_submodules").start()
        self.addCleanup(patch.stopall)
        return environment

    def native_kata_binary(self, checkout=None):
        checkout = checkout or self.root / "checkout"
        binary = checkout / "kata/kata"
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_text("#!/bin/sh\nexit 0\n")
        binary.chmod(0o755)
        return checkout, binary

    def test_native_kata_provisioning_is_repeatable_and_preserves_config(self):
        checkout, binary = self.native_kata_binary()
        home = self.root / "home"
        kata_home = home / ".kata"
        kata_home.mkdir(parents=True)
        config_path = kata_home / "config.toml"
        config_path.write_text('[tui]\nmouse = true\n\n[auth]\ntoken = "synthetic-token"\n')

        installer.provision_native_kata_client(checkout, home)
        link = home / ".local/bin/kata"
        first_config = config_path.read_bytes()
        installer.provision_native_kata_client(checkout, home)

        self.assertEqual(link.resolve(), binary.resolve())
        self.assertEqual(config_path.read_bytes(), first_config)
        config = tomllib.loads(config_path.read_text())
        self.assertEqual(config["tui"]["mouse"], True)
        self.assertEqual(config["auth"]["token"], "synthetic-token")
        self.assertEqual(config["active_daemon"], "local")
        self.assertEqual(config["daemon"], [
            {"name": "local", "url": installer.KATA_DAEMON_URL},
        ])

    def test_native_kata_provisioning_refuses_other_active_daemon_before_changes(self):
        checkout, _ = self.native_kata_binary()
        home = self.root / "home"
        kata_home = home / ".kata"
        kata_home.mkdir(parents=True)
        config_path = kata_home / "config.toml"
        config_path.write_text(
            'active_daemon = "other"\n\n[[daemon]]\n'
            'name = "other"\nurl = "http://127.0.0.1:17778"\n'
        )
        original_config = config_path.read_bytes()

        with self.assertRaisesRegex(RuntimeError, "active Kata daemon"):
            installer.provision_native_kata_client(checkout, home)

        self.assertFalse((home / ".local/bin/kata").exists())
        self.assertEqual(config_path.read_bytes(), original_config)

    def test_native_kata_provisioning_refuses_existing_binary(self):
        checkout, _ = self.native_kata_binary()
        home = self.root / "home"
        link = home / ".local/bin/kata"
        link.parent.mkdir(parents=True)
        link.write_text("not the installed Kata binary")

        with self.assertRaisesRegex(RuntimeError, "already exists"):
            installer.provision_native_kata_client(checkout, home)

        self.assertEqual(link.read_text(), "not the installed Kata binary")
        self.assertFalse((home / ".kata/config.toml").exists())

    def test_native_kata_provisioning_preserves_existing_selected_target(self):
        checkout, _ = self.native_kata_binary()
        home = self.root / "home"
        kata_home = home / ".kata"
        kata_home.mkdir(parents=True)
        config_path = kata_home / "config.toml"
        config_path.write_text(
            'active_daemon = "existing"\n\n[[daemon]]\n'
            'name = "existing"\nurl = "http://127.0.0.1:17777"\n'
            '[auth]\ntoken = "synthetic-token"\n'
        )
        original_config = config_path.read_bytes()

        installer.provision_native_kata_client(checkout, home)

        self.assertEqual((home / ".local/bin/kata").resolve(), (checkout / "kata/kata").resolve())
        self.assertEqual(config_path.read_bytes(), original_config)

    def test_native_kata_provisioning_refuses_symlinked_config(self):
        checkout, _ = self.native_kata_binary()
        home = self.root / "home"
        kata_home = home / ".kata"
        kata_home.mkdir(parents=True)
        external_config = self.root / "external-config.toml"
        external_config.write_text('[auth]\ntoken = "synthetic-token"\n')
        (kata_home / "config.toml").symlink_to(external_config)

        with self.assertRaisesRegex(RuntimeError, "config is a symlink"):
            installer.provision_native_kata_client(checkout, home)

        self.assertFalse((home / ".local/bin/kata").exists())
        self.assertEqual(external_config.read_text(), '[auth]\ntoken = "synthetic-token"\n')

    def test_manual_kata_command_clears_inherited_environment(self):
        checkout, binary = self.native_kata_binary()
        binary.write_text(
            f"#!{sys.executable}\nimport json, os\nprint(json.dumps(dict(os.environ)))\n"
        )
        binary.chmod(0o755)
        home = self.root / "home"
        with patch.object(installer.Path, "home", return_value=home), \
                patch.dict(os.environ, {
                    "KATA_AUTH_TOKEN": "synthetic-token",
                    "KATA_AUTH_TOKEN_FILE": "/synthetic/token",
                    "KATA_DSN": "/other/database",
                    "KATA_DB": "/other/legacy.db",
                    "KATA_SERVER": "https://daemon.example",
                    "KATA_TRUST_PRIVATE_NETWORK": "1",
                }):
            command = installer.manual_kata_command(checkout)
            result = subprocess.run(
                command, check=True, capture_output=True, text=True, env=os.environ.copy(),
            )

        service_environment = json.loads(result.stdout)
        self.assertEqual(service_environment["HOME"], str(home))
        self.assertEqual(service_environment["KATA_HOME"], str(checkout / ".local/environment/kata"))
        self.assertEqual(
            service_environment["KATA_DSN"],
            str(checkout / ".local/environment/kata/kata.db"),
        )
        self.assertEqual(service_environment["KATA_DB"], "")
        self.assertNotIn("KATA_AUTH_TOKEN", service_environment)
        self.assertNotIn("KATA_AUTH_TOKEN_FILE", service_environment)
        self.assertNotIn("KATA_SERVER", service_environment)
        self.assertNotIn("KATA_TRUST_PRIVATE_NETWORK", service_environment)

    def test_native_kata_cli_uses_provisioned_target_and_repository_binding(self):
        binary = installer.ROOT / "kata/kata"
        if not binary.is_file() or not os.access(binary, os.X_OK):
            self.skipTest("native Kata binary is not built")
        home = self.root / "home"
        workspace = self.root / "workspace"
        workspace.mkdir()
        (workspace / ".kata.toml").write_text(
            'version = 1\n\n[project]\nname = "spoke-project"\n'
        )
        with socket.socket() as reserved_port:
            reserved_port.bind(("127.0.0.1", 0))
            daemon_url = f"http://127.0.0.1:{reserved_port.getsockname()[1]}"
            with patch.object(installer, "KATA_DAEMON_URL", daemon_url, create=True):
                installer.provision_native_kata_client(installer.ROOT, home)
            result = subprocess.run(
                ["kata", "daemon", "diagnose", "--json"],
                cwd=workspace,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "KATA_HOME": str(home / ".kata"),
                    "KATA_SERVER": "",
                    "KATA_DSN": "",
                    "KATA_DB": "",
                    "PATH": f"{home / '.local/bin'}{os.pathsep}{os.environ.get('PATH', '')}",
                },
                text=True,
                capture_output=True,
                timeout=15,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        diagnosis = json.loads(result.stdout)
        self.assertEqual(diagnosis["kind"], "remote")
        self.assertEqual(diagnosis["endpoint"], daemon_url)
        self.assertEqual(diagnosis["project"], "spoke-project")

    def test_install_propagates_explicit_librarian_binding_to_setup(self):
        self.installation()
        executable, reader, root, selection = self.explicit_librarian()
        with patch.object(installer, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            installer.install(self.root, self.corpus, "normal", "manual",
                              executable, reader, root, selection)
            installer.install(self.root, self.corpus, "normal", "manual",
                              executable, None, root, selection)
        setups = [call.args[0] for call in run.call_args_list if "setup" in call.args[0]]
        self.assertEqual(setups[0][-8:], [
            "--librarian-executable", str(executable),
            "--librarian-reader", str(reader),
            "--librarian-root", str(root),
            "--librarian-selection", str(selection),
        ])
        self.assertEqual(setups[1][-6:], [
            "--librarian-executable", str(executable),
            "--librarian-root", str(root),
            "--librarian-selection", str(selection),
        ])

    def test_manual_install_initializes_builds_and_configures_without_services(self):
        self.installation()
        with patch.object(installer, "run") as run, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            installer.install(self.root, self.corpus, "normal", "manual")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0], ["bash", "scripts/bootstrap-sources.sh"])
        self.assertEqual(commands[1], ["bash", "scripts/bootstrap-toolchains.sh"])
        self.assertEqual(commands[2][-4:], ["roborev", "kata", "agentsview", "forge"])
        self.assertTrue(any("configure-private-pi-tracking" in command for command in commands))
        self.assertTrue(any("install-pi-extensions" in command for command in commands))
        self.assertFalse(any(any(arg.endswith("-service") for arg in command) for command in commands))
        # Kata and Forge MCP servers need running services; manual installs only print the probe.
        self.assertFalse(any("pi-local.py" in " ".join(command) for command in commands))
        self.assertIn("pi-local.py mcp list", output.getvalue())
        home = self.root / "installer-home"
        self.assertEqual((home / ".local/bin/kata").resolve(), (self.root / "kata/kata").resolve())
        config = tomllib.loads((home / ".kata/config.toml").read_text())
        self.assertEqual(config["active_daemon"], "local")
        self.assertEqual(config["daemon"][0]["url"], "http://127.0.0.1:18777")
        self.assertIn("--listen 127.0.0.1:18777", output.getvalue())
        self.assertIn("Forge http://127.0.0.1:19091/", output.getvalue())
        self.assertIn("AgentsView http://127.0.0.1:19080/", output.getvalue())

    def test_user_install_explicitly_enables_all_four_services(self):
        self.installation()
        with patch.object(installer, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            installer.install(self.root, self.corpus, "local-kata", "user")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[2][-1], "forge-local-kata")
        self.assertEqual([command[-1] for command in commands[-6:]], [
            "install-kata-service", "install-agentsview-service",
            "install-roborev-service", "install-forge-service", "list", "status",
        ])
        self.assertEqual(commands[-2][-3:], [str(self.root / "scripts/pi-local.py"), "mcp", "list"])
        self.assertFalse(any("configure-provider" in command for command in commands))

    def test_native_roborev_links_are_repeatable_and_refuse_conflicts(self):
        checkout, _ = self.native_kata_binary()
        binary = checkout / "roborev/bin/roborev"
        binary.parent.mkdir(parents=True)
        binary.write_text("#!/bin/sh\nexit 0\n")
        binary.chmod(0o755)
        (checkout / ".local/environment/roborev").mkdir(parents=True)
        home = self.root / "home"
        installer.provision_native_roborev_client(checkout, home)
        installer.provision_native_roborev_client(checkout, home)
        self.assertEqual((home / ".local/bin/roborev").resolve(), binary.resolve())
        self.assertEqual((home / ".roborev").resolve(),
                         (checkout / ".local/environment/roborev").resolve())
        other = self.root / "other-home"
        (other / ".roborev").mkdir(parents=True)
        (other / ".roborev/config.toml").write_text("synthetic = true\n")
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            installer.check_native_roborev_client(checkout, other)
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            installer.provision_native_roborev_client(checkout, other)
        self.assertEqual((other / ".roborev/config.toml").read_text(), "synthetic = true\n")
        self.assertFalse((other / ".local/bin/roborev").exists())

    def test_install_links_roborev_configures_provider_and_registers_repos(self):
        self.installation()
        repo = self.root / "my repo"
        repo.mkdir()
        provider = {"base_url": "https://usai.example.invalid/api/v1", "model": "coder",
                    "review_model": "reviewer", "api": "openai-completions"}
        output = io.StringIO()
        with patch.object(installer, "run") as run, contextlib.redirect_stdout(output):
            installer.install(self.root, self.corpus, "normal", "user",
                              provider=provider, repos=[repo])
        calls = [(call.args[0], call.kwargs.get("cwd")) for call in run.call_args_list]
        commands = [command for command, _ in calls]
        configure = next(command for command in commands if "configure-provider" in command)
        self.assertEqual(configure[-8:], ["--base-url", provider["base_url"], "--api",
                                          "openai-completions", "--model", "coder",
                                          "--review-model", "reviewer"])
        services = max(i for i, c in enumerate(commands) if c[-1] == "install-forge-service")
        self.assertLess(commands.index(configure), services)
        self.assertEqual(commands[services + 1][-2:], ["register", str(repo)])
        roborev = self.root / "roborev/bin/roborev"
        self.assertEqual(calls[services + 2],
                         ([str(roborev), "init", "--no-daemon", "--binary", str(roborev)], repo))
        self.assertEqual(commands[-1][-1], "status")
        self.assertIn(shlex.join([sys.executable, str(self.root / "scripts/local_env.py"),
                                  "accept", "--repo", str(repo)]), output.getvalue())
        home = self.root / "installer-home"
        self.assertEqual((home / ".local/bin/roborev").resolve(), roborev.resolve())
        self.assertEqual((home / ".roborev").resolve(),
                         (self.root / ".local/environment/roborev").resolve())

    def test_roborev_link_conflict_aborts_before_builds(self):
        self.installation()
        home = self.root / "installer-home"
        (home / ".roborev").mkdir(parents=True)
        with patch.object(installer, "run") as run, \
                self.assertRaisesRegex(RuntimeError, "already exists"):
            installer.install(self.root, self.corpus, "normal", "manual")
        run.assert_not_called()

    def test_register_repo_and_provider_options_are_validated_before_changes(self):
        repo = self.root / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        cases = (
            (["--services", "manual", "--register-repo", str(repo)], "--services user"),
            (["--services", "user", "--register-repo", str(self.root / "absent")], "Git checkout"),
            (["--services", "manual", "--usai-base-url", "https://x.invalid"], "together"),
            (["--check", "--services", "manual", "--register-repo", str(repo)], "--services user"),
        )
        for extra, message in cases:
            with self.subTest(extra=extra), \
                    patch.object(installer, "prerequisites", return_value=[]), \
                    patch.object(installer, "acquire_checkout") as acquire, \
                    patch.object(installer, "install") as install, \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(installer.main(["--corpus", str(self.corpus), *extra]), 1)
            self.assertIn(message, errors.getvalue())
            acquire.assert_not_called()
            install.assert_not_called()

    def test_occupied_ports_abort_before_source_or_package_changes(self):
        environment = self.installation()
        environment.check_ports.side_effect = RuntimeError("occupied port")
        with patch.object(installer, "run") as run, self.assertRaisesRegex(RuntimeError, "occupied"):
            installer.install(self.root, self.corpus, "normal", "manual")
        run.assert_not_called()

    def test_runtime_service_drift_aborts_before_changes(self):
        environment = self.installation()
        environment.SERVICE_PORTS = {"kata": (17777,)}
        with patch.object(installer, "run") as run, \
                self.assertRaisesRegex(RuntimeError, "services differ"):
            installer.install(self.root, self.corpus, "normal", "manual")
        environment.check_ports.assert_not_called()
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
