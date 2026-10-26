import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

import local_env


class LocalEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="local-env-test-", dir=local_env.ROOT / ".local")
        self.addCleanup(self.temporary.cleanup)
        cwd = Path.cwd()
        self.addCleanup(os.chdir, cwd)
        self.root = Path(self.temporary.name)
        self.state = self.root / "environment"
        self.addCleanup(patch.stopall)
        patch.object(local_env, "STATE", self.state).start()
        self.global_pi = self.root / "global-pi"
        self.global_pi.mkdir()
        patch.object(local_env, "GLOBAL_PI", self.global_pi).start()
        self.corpus = self.root / "corpus"
        server = self.corpus / "tools/context-mcp/.venv/bin/qualified-context-mcp"
        server.parent.mkdir(parents=True)
        server.touch()
        reader = self.corpus / "tools/context-index/context_index.py"
        reader.parent.mkdir(parents=True)
        reader.touch()
        self.binary = self.root / "forge"
        self.binary.touch()
        self.binary.chmod(0o755)
        patch.object(local_env.shutil, "which", return_value="/usr/bin/pi").start()
        patch.object(local_env, "verify_pi", return_value="/usr/bin/pi").start()
        # Forge may be explicitly running on the developer host; tests model the
        # normal stopped state unless a test opts into a probe response.
        patch.object(local_env, "forge_probe", return_value=None).start()
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.setup(self.corpus, self.binary)

    def provider(self):
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.configure_provider("https://usai.example.test/v1", "demo-model", "openai-completions")

    def key(self):
        local_env.private_write(self.state / "secrets/usai-api-key", "test-only-token\n", replace=True)

    def test_setup_preserves_edited_settings(self):
        path = self.state / "pi/settings.json"
        content = '{"theme":"light","custom":"retained"}\n'
        local_env.private_write(path, content, replace=True)
        forge = self.state / "forge/config.toml"
        edited = forge.read_text() + "\n# user setting retained\n"
        local_env.private_write(forge, edited, replace=True)
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.setup(self.corpus, self.binary)
        self.assertEqual(path.read_text(), content)
        self.assertEqual(forge.read_text(), edited)

    def test_setup_rejects_unintentional_path_change(self):
        other = self.root / "other-forge"
        other.touch()
        with self.assertRaisesRegex(RuntimeError, "differs"):
            local_env.setup(self.corpus, other)

    def test_profile_is_private_and_uses_existing_corpus(self):
        for path in (self.state, self.state / "secrets", self.state / "pi"):
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
        mcp = json.loads((self.state / "pi/mcp.json").read_text())
        server = mcp["mcpServers"]["falcon-context"]
        self.assertIn(str(self.corpus), server["args"])
        self.assertEqual(server["exposure"], "codemode")
        self.assertEqual((self.state / "pi/mcp.json").stat().st_mode & 0o777, 0o600)

    def test_missing_usai_fails_without_fallback(self):
        with self.assertRaisesRegex(RuntimeError, "no provider fallback"):
            local_env.pi_launch([])

    def test_key_is_only_in_pi_environment(self):
        self.provider()
        self.key()
        command, env = local_env.pi_launch(["--no-session", "-p", "Synthetic test"])
        self.assertEqual(command[1:5], ["--provider", "usai", "--model", "demo-model"])
        self.assertEqual(env["USAI_API_KEY"], "test-only-token")
        self.assertNotIn("test-only-token", " ".join(command))
        self.assertNotIn("USAI_API_KEY", local_env.base_environment())
        self.assertNotIn("test-only-token", (self.state / "pi/models.json").read_text())

    def test_selected_model_removed_from_catalog_fails_before_loading_key(self):
        self.provider()
        path = self.state / "pi/models.json"
        config = json.loads(path.read_text())
        config["providers"]["usai"]["models"] = [{"id": "new-unverified-model"}]
        local_env.json_write(path, config, replace=True)
        with patch.object(local_env, "load_usai_key") as key, \
                self.assertRaisesRegex(RuntimeError, "missing from pi/models.json"):
            local_env.pi_launch(["--no-session", "-p", "Synthetic test"])
        key.assert_not_called()

    def test_credential_free_mcp_command(self):
        command, env = local_env.pi_launch(["mcp", "list"])
        self.assertEqual(command, ["/usr/bin/pi", "mcp", "list"])
        self.assertNotIn("USAI_API_KEY", env)

    def test_terminal_uses_separate_private_socket_and_native_copilot_home(self):
        with patch.object(local_env.shutil, "which", return_value="/usr/bin/tmux"), \
                patch.dict(os.environ, {
                    "USAI_API_KEY": "test-only-token", "GITHUB_TOKEN": "test-only-token",
                    "TMUX": "foreign-server", "KATA_REF": "foreign-task",
                }):
            command, env = local_env.terminal_launch("open", "pi")
        self.assertEqual(command, [
            "/usr/bin/tmux", "-S", str(self.state / "runtime/terminal/tmux.sock"),
            "-f", str(local_env.ROOT / "scripts/terminal.tmux.conf"),
            "new-session", "-A", "-s", "pi", "-c", str(local_env.ROOT),
        ])
        self.assertEqual((self.state / "runtime/terminal").stat().st_mode & 0o777, 0o700)
        self.assertEqual(env["HOME"], str(Path.home()))
        self.assertEqual(env["PI_CODING_AGENT_DIR"], str(self.state / "pi"))
        for variable in ("USAI_API_KEY", "GITHUB_TOKEN", "TMUX", "KATA_REF"):
            self.assertNotIn(variable, env)
        self.assertNotIn("test-only-token", " ".join(command))
        self.assertEqual(local_env.base_environment()["HOME"], str(self.state / "home"))

    def test_terminal_preserves_native_xdg_paths_without_changing_settings(self):
        before = (self.state / "environment.json").read_bytes()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/test/config"}):
            _, env = local_env.terminal_launch("open")
        self.assertEqual(env["XDG_CONFIG_HOME"], "/test/config")
        self.assertEqual((self.state / "environment.json").read_bytes(), before)

    def test_terminal_stops_only_exact_named_session(self):
        command, _ = local_env.terminal_launch("stop", "pi")
        self.assertEqual(command[-3:], ["kill-session", "-t", "=pi"])
        command, _ = local_env.terminal_launch("list")
        self.assertIn("list-sessions", command)
        self.assertNotIn("new-session", command)

    def test_terminal_rejects_invalid_actions_and_session_targets(self):
        for name in ("", "-pi", "pi:1", "pi.work", "*", "pi;echo", "x" * 49):
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, "session names"):
                local_env.terminal_launch("stop", name)
        with self.assertRaisesRegex(RuntimeError, "terminal action"):
            local_env.terminal_launch("kill-server")
        with patch.object(local_env.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "tmux is missing"):
                local_env.terminal_launch("open")

    def test_terminal_rejects_symlink_or_regular_file_as_socket(self):
        local_env.terminal_launch("list")
        path = self.state / "runtime/terminal/tmux.sock"
        path.symlink_to(self.state / "environment.json")
        with self.assertRaisesRegex(RuntimeError, "owned tmux socket"):
            local_env.terminal_launch("open")
        path.unlink()
        path.touch()
        with self.assertRaisesRegex(RuntimeError, "owned tmux socket"):
            local_env.terminal_launch("list")

    def test_terminal_entrypoint_executes_scoped_command(self):
        with patch.object(sys, "argv", ["terminal-local.py", "list"]), \
                patch.object(os, "execve") as execute, \
                patch.object(os, "umask", return_value=0o077), \
                patch.object(os, "chdir") as chdir:
            with self.assertRaises(SystemExit) as exit_result:
                runpy.run_path(str(local_env.ROOT / "scripts/terminal-local.py"), run_name="__main__")
        self.assertIsNone(exit_result.exception.code)
        self.assertIn("list-sessions", execute.call_args.args[1])
        chdir.assert_not_called()

    def test_terminal_entrypoint_refuses_noninteractive_open(self):
        with patch.object(sys, "argv", ["terminal-local.py", "open"]), \
                patch.object(sys.stdin, "isatty", return_value=False), \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exit_result:
                runpy.run_path(str(local_env.ROOT / "scripts/terminal-local.py"), run_name="__main__")
        self.assertEqual(exit_result.exception.code, 2)

    def test_review_extension_installation_is_private_pinned_and_preserves_settings(self):
        path = self.state / "pi/settings.json"
        config = json.loads(path.read_text())
        config["theme"] = "retained"
        local_env.json_write(path, config, replace=True)
        before = config.copy()

        def install(command, **kwargs):
            self.assertEqual(command, ["/usr/bin/pi", "install", local_env.PI_REVIEW_EXTENSION])
            self.assertEqual(kwargs["cwd"], self.state / "home")
            self.assertEqual(kwargs["env"]["PI_CODING_AGENT_DIR"], str(self.state / "pi"))
            self.assertNotIn("USAI_API_KEY", kwargs["env"])
            self.assertTrue(kwargs["check"])
            config["packages"] = list(dict.fromkeys([*config["packages"], local_env.PI_REVIEW_EXTENSION]))
            local_env.json_write(path, config, replace=True)

        with patch.object(local_env.subprocess, "run", side_effect=install) as run:
            with contextlib.redirect_stdout(io.StringIO()):
                local_env.install_pi_review_extension()
                local_env.install_pi_review_extension()
        self.assertEqual(run.call_count, 2)
        self.assertEqual(config["theme"], before["theme"])
        self.assertIn(str(local_env.ROOT / "superpowers"), config["packages"])
        self.assertEqual(config["packages"].count(local_env.PI_REVIEW_EXTENSION), 1)
        self.assertEqual(list(self.global_pi.iterdir()), [])

    def test_review_extension_installation_reports_failure_and_wrong_profile(self):
        with patch.object(local_env.subprocess, "run", side_effect=local_env.subprocess.CalledProcessError(
                1, ["pi", "install"])):
            with self.assertRaises(local_env.subprocess.CalledProcessError):
                local_env.install_pi_review_extension()
        with patch.object(local_env.subprocess, "run"):
            with self.assertRaisesRegex(RuntimeError, "isolated profile"):
                local_env.install_pi_review_extension()

    def test_scoped_roborev_pins_profile_endpoint_and_preserves_arguments(self):
        binary = local_env.ROOT / "roborev/bin/roborev"
        with patch.object(local_env.os, "access", return_value=True):
            with patch.object(Path, "is_file", return_value=True):
                with patch.dict(os.environ, {
                    "ROBOREV_DATA_DIR": "/wrong-profile", "USAI_API_KEY": "not-inherited",
                    "OPENAI_API_KEY": "not-inherited",
                }):
                    for args in (["status"], ["post-commit", "--quiet"],
                                 ["remap", "amend"], ["review", "--repo", "/path with spaces", "HEAD"]):
                        command, env = local_env.roborev_launch(args)
                        self.assertEqual(command, [str(binary), "--server", "127.0.0.1:17373", *args])
                        self.assertEqual(env["ROBOREV_DATA_DIR"], str(self.state / "roborev"))
                        self.assertNotIn("USAI_API_KEY", env)
                        self.assertNotIn("OPENAI_API_KEY", env)

    def test_scoped_roborev_rejects_server_overrides_and_missing_binary(self):
        for args in (["--server", "remote", "status"], ["status", "--server=remote"]):
            with self.subTest(args=args), self.assertRaisesRegex(RuntimeError, "pins the private server"):
                local_env.roborev_launch(args)
        with patch.object(Path, "is_file", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "missing executable"):
                local_env.roborev_launch(["status"])

    def test_managed_roborev_refuses_native_lifecycle_and_update(self):
        for args in (["daemon", "start"], ["daemon", "run"], ["daemon", "restart"],
                     ["--verbose", "daemon", "stop"], ["update"],
                     ["--from-skill", "daemon", "run"],
                     ["--verbose=true", "daemon", "run"]):
            with self.subTest(args=args), self.assertRaisesRegex(RuntimeError, "systemctl"):
                local_env.roborev_launch(args)
        with patch.object(Path, "is_file", return_value=True), \
                patch.object(local_env.os, "access", return_value=True):
            command, _ = local_env.roborev_launch(["review", "--repo", "daemon"])
        self.assertEqual(command[-1], "daemon")

    def test_roborev_selected_native_binary_is_shared_by_commands_and_child_path(self):
        binary = self.root / "native/bin/roborev"
        binary.parent.mkdir(parents=True)
        binary.touch()
        binary.chmod(0o755)
        local_env.json_write(self.state / "roborev-service.json",
                             {"unit": local_env.ROBOREV_UNIT, "binary": str(binary)})
        self.assertEqual(local_env.roborev_command()[0], str(binary))
        command, env = local_env.roborev_launch(["status"])
        self.assertEqual(command[0], str(binary))
        self.assertEqual(env["PATH"].split(os.pathsep)[1], str(binary.parent))
        binary.unlink()
        with self.assertRaisesRegex(RuntimeError, "missing executable"):
            local_env.roborev_command()
        local_env.json_write(self.state / "roborev-service.json",
                             {"binary": "relative/roborev"}, replace=True)
        with self.assertRaisesRegex(RuntimeError, "absolute path"):
            local_env.roborev_binary()

    def test_roborev_warnings_distinguish_managed_and_unmanaged_processes(self):
        proc = self.root / "proc"
        for pid, cmd in ((111, b"/native/roborev\0daemon\0run\0"),
                         (222, b"/native/roborev\0daemon\0run\0"),
                         (333, b"/native/roborev\0status\0")):
            entry = proc / str(pid)
            entry.mkdir(parents=True)
            (entry / "cmdline").write_bytes(cmd)
        with patch.object(local_env, "user_service_pid", return_value=111), \
                patch.object(local_env, "supervisor", return_value=None), \
                patch.object(local_env.socket, "socket") as socket:
            socket.return_value.__enter__.return_value.connect_ex.return_value = 1
            warnings = local_env.roborev_warnings(proc_root=proc)
            self.assertEqual(len(warnings), 1)
            self.assertIn("PID 222", warnings[0])
            socket.return_value.__enter__.return_value.connect_ex.return_value = 0
            warnings = local_env.roborev_warnings(proc_root=proc)
            self.assertEqual(sum("7373" in w for w in warnings), 2)
        with patch.object(local_env, "user_service_pid", side_effect=RuntimeError("inactive")), \
                patch.object(local_env, "supervisor", return_value={"children": {"roborev": 111}}), \
                patch.object(local_env.socket, "socket") as socket:
            socket.return_value.__enter__.return_value.connect_ex.return_value = 1
            self.assertEqual(len(local_env.roborev_warnings(proc_root=proc)), 1)
        with patch.object(local_env, "user_service_pid", return_value=111), \
                patch.object(local_env, "supervisor", side_effect=RuntimeError("stale identity")), \
                patch.object(local_env.socket, "socket") as socket:
            socket.return_value.__enter__.return_value.connect_ex.return_value = 1
            self.assertEqual(len(local_env.roborev_warnings(proc_root=proc)), 1)

    def test_scoped_roborev_entrypoint_executes_without_changing_directory(self):
        command = ["/native/roborev", "--server", "127.0.0.1:17373", "status"]
        env = {"ROBOREV_DATA_DIR": "/private"}
        with patch.object(local_env, "roborev_launch", return_value=(command, env)) as launch, \
                patch.object(local_env, "roborev_warnings", return_value=[]):
            with patch.object(os, "execve") as execute, patch.object(os, "chdir") as chdir:
                with patch.object(os, "umask"), patch.object(local_env.sys, "argv", ["launcher", "status"]):
                    runpy.run_path(str(local_env.ROOT / "scripts/roborev-local.py"))
        launch.assert_called_once_with(["status"])
        execute.assert_called_once_with(command[0], command, env)
        chdir.assert_not_called()

    def test_scoped_roborev_entrypoint_reports_errors(self):
        output = io.StringIO()
        with patch.object(local_env, "roborev_launch", side_effect=RuntimeError("not configured")):
            with patch.object(os, "umask"), contextlib.redirect_stderr(output):
                with self.assertRaises(SystemExit) as error:
                    runpy.run_path(str(local_env.ROOT / "scripts/roborev-local.py"))
        self.assertEqual(error.exception.code, 1)
        self.assertIn("ERROR: not configured", output.getvalue())

    def test_permissive_key_is_rejected(self):
        self.provider()
        self.key()
        (self.state / "secrets/usai-api-key").chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, "private regular file"):
            local_env.pi_launch([])

    def test_symlink_key_is_rejected(self):
        self.provider()
        target = self.root / "outside-key"
        target.write_text("test-only-token")
        (self.state / "secrets/usai-api-key").symlink_to(target)
        with self.assertRaises(OSError):
            local_env.pi_launch([])
        with self.assertRaises(OSError):
            local_env.private_write(self.state / "secrets/usai-api-key", "replacement", replace=True)
        self.assertEqual(target.read_text(), "test-only-token")

    def test_invalid_key_does_not_appear_in_error(self):
        for bad in ("test-only-token\nanother-line", "test-only-token\x00"):
            with self.subTest(), self.assertRaises(RuntimeError) as error:
                local_env.validate_key(bad)
            self.assertNotIn(bad, str(error.exception))

    def test_model_and_key_overrides_are_rejected(self):
        for flag in ("--api-key", "--api-key=anything", "--provider", "--model=other"):
            with self.subTest(flag=flag), self.assertRaisesRegex(RuntimeError, "saved USAi model"):
                local_env.pi_launch([flag])

    def test_provider_updates_preserve_unrelated_configuration(self):
        path = self.state / "pi/models.json"
        local_env.json_write(path, {"providers": {"local": {"models": [{"id": "keep"}]}}})
        self.provider()
        self.assertIn("local", json.loads(path.read_text())["providers"])

    def test_provider_rejects_embedded_credentials_and_plaintext(self):
        for url in ("http://usai.example.test/v1", "https://token@usai.example.test/v1",
                    "https://usai.example.test/v1?key=test"):
            with self.subTest(url=url), self.assertRaisesRegex(RuntimeError, "HTTPS without credentials"):
                local_env.configure_provider(url, "model", "openai-completions")

    def test_pid_reuse_is_not_signaled(self):
        local_env.json_write(self.state / "runtime/supervisor.json",
                             {"pid": os.getpid(), "start_time": "not-the-current-process"})
        with patch.object(local_env.os, "kill") as kill, self.assertRaisesRegex(RuntimeError, "reused"):
            local_env.stop()
        kill.assert_not_called()

    def save_exited_supervisor(self):
        with local_env.subprocess.Popen(
                [local_env.sys.executable, "-c", "pass"],
                stdout=local_env.subprocess.DEVNULL, stderr=local_env.subprocess.DEVNULL) as process:
            process.wait(timeout=10)
        path = self.state / "runtime/supervisor.json"
        local_env.json_write(path, {"pid": process.pid, "start_time": "previous-instance"})
        return path

    def test_status_retains_stale_metadata_and_reports_independent_services(self):
        path = self.save_exited_supervisor()
        before = path.read_bytes()
        external = {"agentsview": {"unit": local_env.AGENTSVIEW_UNIT, "pid": 123}}
        errors = io.StringIO()
        with patch.object(local_env, "managed_services", return_value=external):
            with contextlib.redirect_stderr(errors):
                result = local_env.status()
        self.assertEqual(result["stack"], "stopped")
        self.assertIsNone(result["supervisor"])
        self.assertEqual(result["agentsview_service"], external["agentsview"])
        self.assertIsNone(result["forge"])
        self.assertEqual(path.read_bytes(), before)
        self.assertIn("stale supervisor metadata retained", errors.getvalue())

    def test_stop_with_exited_supervisor_signals_nothing_and_retains_metadata(self):
        path = self.save_exited_supervisor()
        before = path.read_bytes()
        output = io.StringIO()
        with patch.object(local_env.os, "kill") as kill:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                local_env.stop()
        kill.assert_not_called()
        self.assertEqual(path.read_bytes(), before)
        self.assertIn("No live supervisor", output.getvalue())
        self.assertIn("no process was signaled", output.getvalue())
        self.assertFalse((self.state / "runtime/shutdown.json").exists())

    def test_stop_without_supervisor_metadata_signals_nothing(self):
        with patch.object(local_env.os, "kill") as kill:
            with contextlib.redirect_stdout(io.StringIO()):
                local_env.stop()
        kill.assert_not_called()

    def test_supervisor_read_errors_remain_visible(self):
        local_env.json_write(self.state / "runtime/supervisor.json",
                             {"pid": os.getpid(), "start_time": "current"})
        with patch.object(local_env, "process_identity", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                local_env.supervisor()

    def test_key_handoff_requires_terminal(self):
        with patch.object(local_env.sys.stdin, "isatty", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "terminal"):
                local_env.set_key()
        self.assertFalse((self.state / "secrets/usai-api-key").exists())

    def test_private_only_key_handoff_does_not_read_or_change_global_profiles(self):
        self.cli_providers()
        before = {path.name: path.read_bytes() for path in self.global_pi.iterdir()}
        with patch.object(local_env.sys.stdin, "isatty", return_value=True), \
                patch.object(local_env.getpass, "getpass", return_value="test-only-token"), \
                patch.object(local_env, "link_cli_key", side_effect=AssertionError("global access")), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            local_env.set_key(private_only=True)
        self.assertEqual(local_env.load_usai_key(), "test-only-token")
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.global_pi.iterdir()})
        self.assertIn("Global Pi credentials were not changed", output.getvalue())

    def cli_providers(self):
        models = {"providers": {
            "usai": {"apiKey": "old-test-only-token", "models": [{"id": "retained"}]},
            "other": {"apiKey": "$OTHER_KEY"},
        }}
        settings = {"theme": "retained", "packages": ["retained-package"], "litellm": {
            "providers": {"litellm-usai": {"apiKey": "!old-helper", "baseUrl": "https://usai.example.test"}},
            "mcp": {"enabled": False},
        }}
        for name, config in (("models.json", models), ("settings.json", settings)):
            (self.global_pi / name).write_text(json.dumps(config))
            (self.global_pi / name).chmod(0o644)
        return models, settings

    def test_set_key_links_both_profiles_without_copying_token_or_settings(self):
        models, settings = self.cli_providers()
        before = (self.state / "pi/settings.json").read_bytes()
        output = io.StringIO()
        for token in ("first-test-only-token", "rotated-test-only-token"):
            with patch.object(local_env.sys.stdin, "isatty", return_value=True):
                with patch.object(local_env.getpass, "getpass", return_value=token):
                    with contextlib.redirect_stdout(output):
                        local_env.set_key()
            self.assertEqual(local_env.load_usai_key(), token)
            cli_models = json.loads((self.global_pi / "models.json").read_text())
            cli_settings = json.loads((self.global_pi / "settings.json").read_text())
            command = cli_models["providers"]["usai"]["apiKey"]
            self.assertTrue(command.startswith("!"))
            self.assertIn(str(local_env.ROOT / "scripts/usai-key.py"), command)
            self.assertEqual(cli_settings["litellm"]["providers"]["litellm-usai"]["apiKey"], command)
            models["providers"]["usai"]["apiKey"] = command
            settings["litellm"]["providers"]["litellm-usai"]["apiKey"] = command
            self.assertEqual(cli_models, models)
            self.assertEqual(cli_settings, settings)
            for name in ("models.json", "settings.json"):
                path = self.global_pi / name
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertNotIn(token, path.read_text())
            self.assertNotIn(token, output.getvalue())
        self.assertEqual((self.state / "pi/settings.json").read_bytes(), before)
        self.assertEqual((self.state / "secrets/usai-api-key").stat().st_mode & 0o777, 0o600)
        self.assertIn("2 existing global Pi", output.getvalue())

    def test_set_key_does_not_create_unconfigured_global_providers(self):
        output = io.StringIO()
        with patch.object(local_env.sys.stdin, "isatty", return_value=True):
            with patch.object(local_env.getpass, "getpass", return_value="test-only-token"):
                with contextlib.redirect_stdout(output):
                    local_env.set_key()
        self.assertEqual(local_env.load_usai_key(), "test-only-token")
        self.assertEqual(list(self.global_pi.iterdir()), [])
        self.assertIn("0 existing global Pi", output.getvalue())

    def test_cli_key_link_rejects_symlink_without_replacing_private_key(self):
        self.cli_providers()
        self.key()
        path = self.global_pi / "settings.json"
        content = path.read_bytes()
        path.unlink()
        target = self.root / "outside-settings"
        target.write_bytes(content)
        path.symlink_to(target)
        before = (self.global_pi / "models.json").read_bytes()
        with patch.object(local_env.sys.stdin, "isatty", return_value=True):
            with patch.object(local_env.getpass, "getpass", return_value="new-test-only-token"):
                with self.assertRaises(OSError):
                    local_env.set_key()
        self.assertEqual((self.global_pi / "models.json").read_bytes(), before)
        self.assertEqual(target.read_bytes(), content)
        self.assertEqual(local_env.load_usai_key(), "test-only-token")

    def test_cli_key_link_rejects_writable_config_and_saved_auth_override(self):
        self.cli_providers()
        path = self.global_pi / "models.json"
        before = path.read_bytes()
        path.chmod(0o666)
        with self.assertRaisesRegex(RuntimeError, "non-writable-by-others"):
            local_env.link_cli_key()
        path.chmod(0o644)
        local_env.json_write(self.global_pi / "auth.json", {
            "litellm-usai": {"type": "api_key", "key": "test-only-token"},
        })
        with self.assertRaisesRegex(RuntimeError, "auth.json overrides"):
            local_env.link_cli_key()
        self.assertEqual(path.read_bytes(), before)

    def test_cli_key_link_invalid_config_does_not_partially_update_other_profile(self):
        self.cli_providers()
        path = self.global_pi / "settings.json"
        before = (self.global_pi / "models.json").read_bytes()
        for config in ([], {"litellm": []}, {"litellm": {"providers": []}}):
            path.write_text(json.dumps(config))
            with self.subTest(config=config), self.assertRaises(RuntimeError):
                local_env.link_cli_key()
            self.assertEqual((self.global_pi / "models.json").read_bytes(), before)

    def test_set_key_rejects_unsafe_private_key_before_changing_cli_configs(self):
        self.cli_providers()
        self.key()
        (self.state / "secrets/usai-api-key").chmod(0o644)
        before = {name: (self.global_pi / name).read_bytes() for name in ("models.json", "settings.json")}
        with patch.object(local_env.sys.stdin, "isatty", return_value=True):
            with patch.object(local_env.getpass, "getpass", return_value="new-test-only-token"):
                with self.assertRaisesRegex(RuntimeError, "private regular file"):
                    local_env.set_key()
        for name, content in before.items():
            self.assertEqual((self.global_pi / name).read_bytes(), content)

    def test_credential_helper_reads_current_private_key_without_logs(self):
        for token in ("first-test-only-token", "rotated-test-only-token"):
            local_env.private_write(self.state / "secrets/usai-api-key", token + "\n", replace=True)
            output, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                runpy.run_path(str(local_env.ROOT / "scripts/usai-key.py"))
            self.assertEqual(output.getvalue(), token + "\n")
            self.assertEqual(errors.getvalue(), "")

    def test_credential_helper_missing_key_fails_explicitly_without_stdout(self):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            with self.assertRaises(SystemExit) as error:
                runpy.run_path(str(local_env.ROOT / "scripts/usai-key.py"))
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("ERROR:", errors.getvalue())

    def test_model_discovery_saves_only_metadata_without_changing_provider(self):
        self.provider()
        self.key()
        provider_before = (self.state / "pi/models.json").read_bytes()
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = json.dumps({
            "data": [{"id": "model-b"}, {"id": "model-a"}, {"id": "model-b"}],
        }).encode()
        output = io.StringIO()
        with patch.object(local_env.urllib.request, "build_opener", return_value=opener):
            with contextlib.redirect_stdout(output):
                ids = local_env.list_models("https://usai.example.test/v1/")
        self.assertEqual(ids, ["model-a", "model-b"])
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://usai.example.test/v1/models")
        saved = (self.state / "usai-models.json").read_text()
        self.assertNotIn("test-only-token", saved + output.getvalue())
        self.assertEqual((self.state / "pi/models.json").read_bytes(), provider_before)
        self.assertEqual((self.state / "usai-models.json").stat().st_mode & 0o777, 0o600)

    def test_model_discovery_refuses_redirects_and_does_not_log_body(self):
        self.key()
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError(
            "https://usai.example.test/v1/models", 302, "redirect", {}, None)
        with patch.object(local_env.urllib.request, "build_opener", return_value=opener) as build:
            with self.assertRaisesRegex(RuntimeError, "redirects are refused"):
                local_env.list_models("https://usai.example.test/v1")
            handler = build.call_args.args[0]
            self.assertIsNone(handler.redirect_request(None, None, 302, "", {}, "https://other.example"))
        self.assertFalse((self.state / "usai-models.json").exists())

    def test_invalid_model_list_preserves_previous_catalog(self):
        self.key()
        saved = self.state / "usai-models.json"
        local_env.json_write(saved, {"models": ["retained"]})
        before = saved.read_bytes()
        opener = MagicMock()
        for payload in ({"data": []}, {"data": [{"id": None}]}, {"other": []}):
            opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()
            with self.subTest(payload=payload):
                with patch.object(local_env.urllib.request, "build_opener", return_value=opener):
                    with self.assertRaises(RuntimeError):
                        local_env.list_models("https://usai.example.test/v1")
                self.assertEqual(saved.read_bytes(), before)

    def tracking_sources(self):
        copilot = self.root / "copilot"
        (copilot / "session-state").mkdir(parents=True)
        pi = self.root / "pi-sessions"
        pi.mkdir()
        path = self.state / "agentsview/config.toml"
        local_env.private_write(path, '# retained comment\ncursor_secret = "test-only-secret"\n')
        patch.object(local_env, "agentsview_request", return_value={
            "session_providers": [{"id": "copilot"}, {"id": "pi"}, {"id": "claude"}],
        }).start()
        return copilot, pi, path

    def test_private_pi_tracking_is_offline_and_only_uses_private_sessions(self):
        with patch.object(local_env, "agentsview_request", side_effect=AssertionError("network")), \
                contextlib.redirect_stdout(io.StringIO()):
            local_env.configure_private_pi_tracking()
        config_path = self.state / "agentsview/config.toml"
        config = local_env.tomllib.loads(config_path.read_text())
        self.assertEqual(config["archive_content"], "usage")
        self.assertEqual(config["agents"], {"pi": {"dirs": [str(self.state / "pi/sessions")]}})
        self.assertEqual(config_path.stat().st_mode & 0o777, 0o600)
        metadata = self.state / "agentsview-tracking.json"
        self.assertEqual(json.loads(metadata.read_text())["pi_dirs"], [str(self.state / "pi/sessions")])
        before = (config_path.read_bytes(), metadata.read_bytes())
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.configure_private_pi_tracking()
        self.assertEqual(before, (config_path.read_bytes(), metadata.read_bytes()))

    def test_private_pi_tracking_preserves_existing_configured_sources(self):
        copilot, pi, config = self.tracking_sources()
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.configure_tracking(copilot, [pi], "usage")
        metadata = self.state / "agentsview-tracking.json"
        before = (config.read_bytes(), metadata.read_bytes())
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.configure_private_pi_tracking()
        self.assertEqual(before, (config.read_bytes(), metadata.read_bytes()))

    def test_private_pi_tracking_rejects_unconfigured_existing_settings(self):
        config = self.state / "agentsview/config.toml"
        local_env.private_write(config, 'archive_content = "full"\n')
        with self.assertRaisesRegex(RuntimeError, "existing AgentsView"):
            local_env.configure_private_pi_tracking()
        self.assertEqual(config.read_text(), 'archive_content = "full"\n')
        self.assertFalse((self.state / "agentsview-tracking.json").exists())

    def test_tracking_preserves_config_and_scopes_sources(self):
        copilot, pi, path = self.tracking_sources()
        before = path.read_text()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            local_env.configure_tracking(copilot, [pi, self.state / "pi/sessions"], "usage")
        config = local_env.tomllib.loads(path.read_text())
        self.assertIn(before, path.read_text())
        self.assertEqual(config["archive_content"], "usage")
        self.assertEqual(config["disabled_agents"], ["claude"])
        self.assertEqual(config["agents"]["copilot"]["dirs"], [str(copilot)])
        self.assertEqual(config["agents"]["pi"]["dirs"], [str(pi), str(self.state / "pi/sessions")])
        self.assertNotIn("test-only-secret", output.getvalue())
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_tracking_rerun_preserves_config_bytes(self):
        copilot, pi, path = self.tracking_sources()
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.configure_tracking(copilot, [pi], "usage")
            before = path.read_bytes()
            local_env.configure_tracking(copilot, [pi], "usage")
        self.assertEqual(path.read_bytes(), before)

    def test_tracking_refuses_overwriting_different_archive_policy(self):
        copilot, pi, path = self.tracking_sources()
        local_env.private_write(path, 'archive_content = "full"\n', replace=True)
        before = path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "archive_content differs"):
            local_env.configure_tracking(copilot, [pi], "usage")
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((self.state / "agentsview-tracking.json").exists())

    def test_tracking_rejects_wrong_copilot_root(self):
        _, pi, _ = self.tracking_sources()
        with self.assertRaisesRegex(RuntimeError, "session-state"):
            local_env.configure_tracking(pi, [pi], "usage")

    def test_tracking_refuses_busy_config_without_writes(self):
        copilot, pi, path = self.tracking_sources()
        before = path.read_bytes()
        with open(str(path) + ".lock", "w") as lock:
            local_env.fcntl.flock(lock, local_env.fcntl.LOCK_EX | local_env.fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, "config is busy"):
                local_env.configure_tracking(copilot, [pi], "usage")
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((self.state / "agentsview-tracking.json").exists())

    def test_tracking_refuses_changing_existing_sources(self):
        copilot, pi, path = self.tracking_sources()
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.configure_tracking(copilot, [pi], "usage")
        before = path.read_bytes()
        metadata = (self.state / "agentsview-tracking.json").read_bytes()
        other = self.root / "other-pi-sessions"
        other.mkdir()
        with self.assertRaisesRegex(RuntimeError, "pi directories differ"):
            local_env.configure_tracking(copilot, [other], "usage")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual((self.state / "agentsview-tracking.json").read_bytes(), metadata)

    def test_agentsview_environment_does_not_override_multi_directory_pi_sources(self):
        env = local_env.agentsview_environment()
        self.assertNotIn("PI_CODING_AGENT_DIR", env)
        self.assertNotIn("USAI_API_KEY", env)
        self.assertEqual(env["HOME"], str(self.state / "home"))
        self.assertEqual(env["AGENTSVIEW_TELEMETRY_ENABLED"], "0")

    def test_agentsview_command_enables_sync_only_when_tracking_is_configured(self):
        self.assertIn("--no-sync", local_env.agentsview_command())
        local_env.json_write(self.state / "agentsview-tracking.json", {})
        self.assertNotIn("--no-sync", local_env.agentsview_command())

    def test_systemd_paths_are_quoted_and_specifiers_escaped(self):
        self.assertEqual(local_env.systemd_quote('/path with spaces/100%/$name/a"b'),
                         '"/path with spaces/100%%/$$name/a\\"b"')
        with self.assertRaisesRegex(RuntimeError, "line breaks"):
            local_env.systemd_quote("/path\ninjection")

    def test_stopped_stack_status_does_not_query_forge(self):
        with patch.object(local_env, "managed_agentsview", return_value={"pid": 123}) as managed:
            with patch.object(local_env, "api") as api:
                result = local_env.status()
        self.assertEqual(result["stack"], "stopped")
        self.assertEqual(result["agentsview_service"]["pid"], 123)
        api.assert_not_called()
        managed.assert_called_once()

    def test_running_status_refreshes_independent_service_pid(self):
        local_env.json_write(self.state / "runtime/supervisor.json", {})
        saved = {"pid": 456, "external_services": {"agentsview": {"pid": 123}}}
        current = {"unit": local_env.AGENTSVIEW_UNIT, "pid": 789}
        with patch.object(local_env, "managed_agentsview", return_value=current):
            with patch.object(local_env, "supervisor", return_value=saved):
                with patch.object(local_env, "api", return_value={"projects": []}):
                    result = local_env.status()
        self.assertEqual(result["stack"], "running")
        self.assertEqual(result["supervisor"]["external_services"]["agentsview"], current)
        self.assertEqual(result["agentsview_service"], current)

    def test_managed_agentsview_refuses_another_process(self):
        local_env.json_write(self.state / "agentsview-service.json", {"unit": local_env.AGENTSVIEW_UNIT})
        with patch.object(local_env.subprocess, "run", return_value=MagicMock(
                stdout="MainPID=123\nActiveState=active\n")):
            with patch.object(local_env, "agentsview_request", return_value={
                    "pid": 456, "healthy": True, "version": "test"}):
                with self.assertRaisesRegex(RuntimeError, "does not match"):
                    local_env.managed_agentsview()

    def test_agentsview_health_uses_the_actual_ping_endpoint(self):
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = b'{"healthy":true}'
        with patch.object(local_env, "HTTP", opener):
            self.assertTrue(local_env.agentsview_request("GET", "/ping")["healthy"])
        self.assertEqual(opener.open.call_args.args[0].full_url, "http://127.0.0.1:18080/api/ping")

    def node_executable(self):
        node = self.root / "node-runtime/bin/node"
        node.parent.mkdir(parents=True)
        node.touch()
        node.chmod(0o755)
        return node

    def test_roborev_environment_pins_node_without_credentials(self):
        node = self.node_executable()
        with patch.dict(os.environ, {"PATH": "/usr/bin:/bin", "USAI_API_KEY": "not-inherited"}):
            env = local_env.node_environment(node)
        self.assertEqual(env["PATH"].split(os.pathsep)[0], str(node.parent))
        self.assertNotIn("USAI_API_KEY", env)
        self.assertEqual(env["PI_CODING_AGENT_DIR"], str(self.state / "pi"))

    def test_roborev_rejects_missing_node_and_nonlocal_bindings(self):
        with self.assertRaisesRegex(RuntimeError, "missing executable Node"):
            local_env.node_environment(self.root / "missing-node")
        config = self.state / "roborev/config.toml"
        local_env.private_write(config, 'server_addr = "0.0.0.0:17373"\n', replace=True)
        with self.assertRaisesRegex(RuntimeError, "loopback"):
            local_env.validate_roborev_config()

    def test_roborev_service_installation_preserves_settings_and_records_node(self):
        node = self.node_executable()
        binary = self.root / "native-roborev"
        binary.touch()
        binary.chmod(0o755)
        config = self.state / "roborev/config.toml"
        before = config.read_bytes()
        def systemctl(command, **kwargs):
            inactive = ("is-active" in command
                        and not (self.state / "roborev-service.json").exists())
            return MagicMock(returncode=3 if inactive else 0)

        with patch.object(local_env.shutil, "which", return_value=str(node)):
            with patch.object(local_env.subprocess, "run", side_effect=systemctl) as run, \
                    patch.object(local_env, "check_ports"):
                with patch.object(local_env, "managed_roborev", return_value={"pid": 123}):
                    with contextlib.redirect_stdout(io.StringIO()):
                        local_env.install_roborev_service(binary)
                        first = (self.state / "systemd" / local_env.ROBOREV_UNIT).read_bytes()
                        local_env.install_roborev_service()
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual((self.state / "systemd" / local_env.ROBOREV_UNIT).read_bytes(), first)
        text = first.decode()
        self.assertIn(f'ExecStart="{binary}" "daemon" "run"', text)
        self.assertIn(str(node.parent), text)
        self.assertIn(f'Environment="ROBOREV_DATA_DIR={self.state / "roborev"}"', text)
        self.assertIn(f'WorkingDirectory={self.state / "home"}\n', text)
        self.assertNotIn("local_env.py", text)
        self.assertIn("WantedBy=default.target", text)
        self.assertNotIn("USAI_API_KEY", text)
        self.assertIn(unittest.mock.call(
            ["systemctl", "--user", "enable", "--now", local_env.ROBOREV_UNIT],
            check=True, timeout=60), run.call_args_list)
        self.assertTrue((self.state / "roborev-service.json").exists())
        self.assertEqual(local_env.roborev_binary(), binary)

    def test_roborev_binary_change_refuses_active_service_without_mutation(self):
        node = self.node_executable()
        binary = self.root / "replacement-roborev"
        binary.touch()
        binary.chmod(0o755)
        marker = self.state / "roborev-service.json"
        local_env.json_write(marker, {"unit": local_env.ROBOREV_UNIT})
        before = marker.read_bytes()
        with patch.object(local_env.shutil, "which", return_value=str(node)), \
                patch.object(local_env.subprocess, "run", return_value=MagicMock(returncode=0)), \
                patch.object(local_env, "install_user_service") as install, \
                self.assertRaisesRegex(RuntimeError, "finish reviews and stop"):
            local_env.install_roborev_service(binary)
        install.assert_not_called()
        self.assertEqual(marker.read_bytes(), before)
        self.assertFalse((self.state / "systemd").exists())

    def test_managed_roborev_refuses_another_process(self):
        local_env.json_write(self.state / "roborev-service.json", {"unit": local_env.ROBOREV_UNIT})
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = (
            b'{"pid":456,"ok":true,"version":"test"}')
        with patch.object(local_env, "user_service_pid", return_value=123):
            with patch.object(local_env, "HTTP", opener):
                with self.assertRaisesRegex(RuntimeError, "does not match"):
                    local_env.managed_roborev()

    def test_managed_roborev_checks_database_and_web_health(self):
        local_env.json_write(self.state / "roborev-service.json", {"unit": local_env.ROBOREV_UNIT})
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.read.side_effect = [b'{"pid":123,"ok":true,"version":"test"}', b'{"version":"test"}']
        response.status = 200
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        with patch.object(local_env, "user_service_pid", return_value=123):
            with patch.object(local_env, "HTTP", opener):
                service = local_env.managed_roborev()
        self.assertEqual(service["pid"], 123)
        self.assertEqual([call.args[0] for call in opener.open.call_args_list[:2]], [
            "http://127.0.0.1:17373/api/ping", "http://127.0.0.1:17373/api/status",
        ])
        request = opener.open.call_args_list[2].args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:17374/reviews")
        self.assertEqual(request.get_header("Accept"), "text/html")

    def test_supervised_ports_exclude_both_independent_services(self):
        self.assertEqual(local_env.supervised_ports({}), local_env.PORTS)
        self.assertEqual(local_env.supervised_ports({"agentsview": {}}),
                         (17373, 17374, 17777, 18091))
        self.assertEqual(local_env.supervised_ports({"agentsview": {}, "roborev": {}}),
                         (17777, 18091))

    def test_stop_preserves_both_independent_services(self):
        external = {
            "agentsview": {"unit": local_env.AGENTSVIEW_UNIT},
            "roborev": {"unit": local_env.ROBOREV_UNIT},
        }
        local_env.json_write(self.state / "runtime/shutdown.json", {"ok": True})
        with patch.object(local_env, "supervisor", return_value={"pid": 123, "external_services": external}):
            with patch.object(local_env.os, "kill") as kill:
                with patch.object(local_env, "check_ports") as ports:
                    with contextlib.redirect_stdout(io.StringIO()):
                        local_env.stop()
        kill.assert_called_once_with(123, local_env.signal.SIGTERM)
        ports.assert_called_once_with((17777, 18091))

    def test_status_includes_roborev_without_starting_forge(self):
        service = {"unit": local_env.ROBOREV_UNIT, "pid": 123}
        with patch.object(local_env, "managed_services", return_value={"roborev": service}):
            with patch.object(local_env, "api") as api:
                result = local_env.status()
        self.assertEqual(result["roborev_service"], service)
        self.assertIsNone(result["agentsview_service"])
        api.assert_not_called()

    def test_forge_run_is_explicit_and_uses_current_node_when_unspecified(self):
        node = self.node_executable()
        with patch.object(local_env.shutil, "which", return_value=str(node)):
            with patch.object(local_env, "check_ports") as ports:
                with patch.object(local_env.os, "execve", side_effect=RuntimeError("exec")) as execute:
                    with self.assertRaisesRegex(RuntimeError, "exec"):
                        local_env.forge_run()
        ports.assert_called_once_with((local_env.FORGE_PORT,))
        executable, command, environment = execute.call_args.args
        self.assertEqual(executable, str(self.binary))
        self.assertEqual(command[0], str(self.binary))
        self.assertEqual(environment["PATH"].split(os.pathsep)[0], str(node.parent))
        self.assertFalse((self.state / "forge-service.json").exists())

    def test_forge_command_retains_private_config_and_disabled_sync(self):
        command = local_env.forge_command(local_env.settings())
        self.assertEqual(command[0], str(self.binary))
        self.assertIn(str(self.state / "forge/config.toml"), command)
        self.assertIn("--disable-sync", command)
        self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")
        local_env.private_write(self.state / "forge/config.toml", 'host = "0.0.0.0"\nport = 18091\n',
                                replace=True)
        with self.assertRaisesRegex(RuntimeError, "loopback"):
            local_env.validate_forge_config()

    def test_forge_command_enables_sync_only_with_configured_repositories(self):
        config = self.state / "forge/config.toml"
        local_env.private_write(
            config,
            config.read_text() + '\n[[repos]]\nowner = "example"\nname = "service"\n',
            replace=True,
        )
        before = config.read_bytes()
        command = local_env.forge_command(local_env.settings())
        self.assertNotIn("--disable-sync", command)
        self.assertIn(str(config), command)
        self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")
        self.assertEqual(config.read_bytes(), before)

    def test_status_reports_explicit_forge_without_claiming_service_management(self):
        forge = {"managed": False, "version": "test", "revision": "commit"}
        local_env.forge_probe.return_value = forge
        with patch.object(local_env, "api", return_value={"projects": []}) as api:
            result = local_env.status()
        self.assertEqual(result["forge"], forge)
        self.assertEqual(result["projects"], {"projects": []})
        api.assert_called_once_with("GET", "/projects")

    def test_all_persistent_services_leave_no_supervised_ports(self):
        self.assertEqual(local_env.supervised_ports(dict.fromkeys(local_env.SERVICE_PORTS)), ())

    def test_forge_service_installation_preserves_state_and_pins_node(self):
        node = self.node_executable()
        config = self.state / "forge/config.toml"
        database = self.state / "forge/forge.db"
        database.write_bytes(b"persistent-workspace-fixture")
        before = config.read_bytes()
        with patch.object(local_env.shutil, "which", return_value=str(node)):
            with patch.object(local_env.subprocess, "run", return_value=MagicMock(returncode=0)) as run:
                with patch.object(local_env, "managed_forge", return_value={"pid": 123}):
                    with contextlib.redirect_stdout(io.StringIO()):
                        local_env.install_forge_service()
                        first = (self.state / "systemd" / local_env.FORGE_UNIT).read_bytes()
                        local_env.install_forge_service()
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(database.read_bytes(), b"persistent-workspace-fixture")
        self.assertEqual((self.state / "systemd" / local_env.FORGE_UNIT).read_bytes(), first)
        self.assertIn('"forge-run" "--node-executable" ' + local_env.systemd_quote(node), first.decode())
        self.assertIn("WantedBy=default.target", first.decode())
        self.assertNotIn("USAI_API_KEY", first.decode())
        self.assertIn(unittest.mock.call(
            ["systemctl", "--user", "enable", "--now", local_env.FORGE_UNIT],
            check=True, timeout=60), run.call_args_list)
        self.assertEqual(json.loads((self.state / "forge-service.json").read_text()),
                         {"unit": local_env.FORGE_UNIT})

    def forge_runtime(self, **overrides):
        runtime = {"pid": 123, "service": "kenn-forge", "version": "test",
                   "address": "127.0.0.1:18091",
                   "metadata": {"data_dir": str(self.state / "forge"),
                                "config_path": str(self.state / "forge/config.toml")}}
        local_env.json_write(self.state / "forge/daemon.123.json",
                             {**runtime, **overrides}, replace=True)

    def forge_opener(self, **overrides):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.read.return_value = json.dumps(
            {"status": "ok", "version": "test", "revision": "commit", **overrides}).encode()
        response.status = 200
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        return opener

    def test_managed_forge_checks_runtime_health_and_dashboard(self):
        self.forge_runtime()
        opener = self.forge_opener()
        with patch.object(local_env, "user_service_pid", return_value=123):
            with patch.object(local_env, "HTTP", opener):
                service = local_env.managed_forge(required=True)
        self.assertEqual(service, {"unit": local_env.FORGE_UNIT, "pid": 123,
                                   "version": "test", "revision": "commit"})
        self.assertEqual([call.args[0] for call in opener.open.call_args_list], [
            "http://127.0.0.1:18091/healthz", "http://127.0.0.1:18091/",
        ])

    def test_managed_forge_requires_marker_unless_installing(self):
        with patch.object(local_env, "user_service_pid") as pid:
            self.assertIsNone(local_env.managed_forge())
        pid.assert_not_called()

    def test_managed_forge_rejects_wrong_runtime_identity(self):
        for key, value in (("pid", 456), ("service", "other"), ("address", "0.0.0.0:18091"),
                           ("metadata", {"data_dir": "/other", "config_path": "/other/config"})):
            with self.subTest(key=key):
                self.forge_runtime(**{key: value})
                with patch.object(local_env, "user_service_pid", return_value=123):
                    with self.assertRaisesRegex(RuntimeError, "runtime identity"):
                        local_env.managed_forge(required=True)

    def test_managed_forge_rejects_invalid_health_and_dashboard(self):
        self.forge_runtime()
        with patch.object(local_env, "user_service_pid", return_value=123):
            for key, value in (("status", "error"), ("version", "other"), ("revision", "")):
                with self.subTest(key=key):
                    with patch.object(local_env, "HTTP", self.forge_opener(**{key: value})):
                        with self.assertRaisesRegex(RuntimeError, "database health"):
                            local_env.managed_forge(required=True)
            opener = self.forge_opener()
            opener.open.return_value.__enter__.return_value.headers = {"Content-Type": "application/json"}
            with patch.object(local_env, "HTTP", opener):
                with self.assertRaisesRegex(RuntimeError, "dashboard"):
                    local_env.managed_forge(required=True)

    def test_status_reports_managed_forge_without_unmanaged_probe(self):
        service = {"unit": local_env.FORGE_UNIT, "pid": 123, "version": "test", "revision": "commit"}
        with patch.object(local_env, "managed_services", return_value={"forge": service}):
            with patch.object(local_env, "api", return_value={"projects": []}):
                result = local_env.status()
        self.assertEqual(result["forge_service"], service)
        self.assertEqual(result["forge"], {"managed": True, **service})
        local_env.forge_probe.assert_not_called()

    def test_supervisor_launches_and_stops_only_unmanaged_forge(self):
        external = {name: {"unit": name + ".service", "pid": 123}
                    for name in ("kata", "roborev", "agentsview")}
        process = MagicMock(pid=456)
        process.poll.return_value = None
        with patch.object(local_env, "managed_services", return_value=external), \
                patch.object(local_env, "check_ports") as ports, \
                patch.object(local_env, "HTTP", self.forge_opener()), \
                patch.object(local_env.subprocess, "Popen", return_value=process) as start, \
                patch.object(local_env.time, "sleep", side_effect=SystemExit(0)), \
                patch.object(local_env.signal, "signal"), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                local_env.serve()
        start.assert_called_once()
        self.assertEqual(start.call_args.args[0], local_env.forge_command(local_env.settings()))
        self.assertEqual(ports.call_args_list, [
            unittest.mock.call((18091,)), unittest.mock.call((18091,)),
        ])
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=15)
        self.assertFalse((self.state / "runtime/supervisor.json").exists())

    def test_kata_service_installation_preserves_profile_and_is_repeatable(self):
        config = self.state / "kata/config.toml"
        database = self.state / "kata/kata.db"
        database.write_bytes(b"persistent-task-fixture")
        before = config.read_bytes()
        with patch.object(local_env.subprocess, "run", return_value=MagicMock(returncode=0)) as run:
            with patch.object(local_env, "managed_kata", return_value={"pid": 123}):
                with contextlib.redirect_stdout(io.StringIO()):
                    local_env.install_kata_service()
                    first = (self.state / "systemd" / local_env.KATA_UNIT).read_bytes()
                    local_env.install_kata_service()
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(database.read_bytes(), b"persistent-task-fixture")
        self.assertEqual((self.state / "systemd" / local_env.KATA_UNIT).read_bytes(), first)
        self.assertIn(f'ExecStart="{local_env.ROOT / "kata/kata"}" "daemon" "start"', first.decode())
        self.assertIn(f'Environment="KATA_HOME={self.state / "kata"}"', first.decode())
        self.assertNotIn("local_env.py", first.decode())
        self.assertIn("WantedBy=default.target", first.decode())
        self.assertNotIn("USAI_API_KEY", first.decode())
        self.assertIn(unittest.mock.call(
            ["systemctl", "--user", "enable", "--now", local_env.KATA_UNIT],
            check=True, timeout=60), run.call_args_list)
        self.assertEqual(json.loads((self.state / "kata-service.json").read_text()),
                         {"unit": local_env.KATA_UNIT})

    def test_kata_rejects_nonlocal_or_separate_web_bindings_and_missing_binary(self):
        for content in ('listen = "0.0.0.0:17777"\n',
                        'listen = "127.0.0.1:17777"\n[web]\nlisten = "0.0.0.0:17778"\n'):
            local_env.private_write(self.state / "kata/config.toml", content, replace=True)
            with self.assertRaisesRegex(RuntimeError, "loopback"):
                local_env.validate_kata_config()
        with patch.object(Path, "is_file", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "missing executable Kata"):
                local_env.kata_command()

    def kata_opener(self, *, pid=123, health=None):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.read.side_effect = [
            json.dumps({"pid": pid, "service": "kata", "ok": True, "version": "test"}).encode(),
            json.dumps(health if health is not None else {
                "ok": True, "version": "test", "schema_version": 30,
                "api_schema_version": "0.24.0", "db_path": str(self.state / "kata/kata.db"),
            }).encode(),
        ]
        response.status = 200
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        return opener

    def test_managed_kata_checks_service_database_and_html_readiness(self):
        opener = self.kata_opener()
        with patch.object(local_env, "user_service_pid", return_value=123):
            with patch.object(local_env, "HTTP", opener):
                result = local_env.managed_kata(required=True)
        self.assertEqual(result, {"unit": local_env.KATA_UNIT, "pid": 123,
                                 "version": "test", "schema_version": 30,
                                 "api_schema_version": "0.24.0"})
        self.assertEqual([call.args[0] for call in opener.open.call_args_list[:2]], [
            "http://127.0.0.1:17777/api/v1/ping", "http://127.0.0.1:17777/api/v1/health",
        ])
        request = opener.open.call_args_list[2].args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:17777/kata")
        self.assertEqual(request.get_header("Accept"), "text/html")

    def test_managed_kata_requires_ownership_marker_unless_installing(self):
        with patch.object(local_env, "user_service_pid") as pid:
            self.assertIsNone(local_env.managed_kata())
        pid.assert_not_called()

    def test_managed_kata_rejects_another_process(self):
        with patch.object(local_env, "user_service_pid", return_value=123):
            with patch.object(local_env, "HTTP", self.kata_opener(pid=456)):
                with self.assertRaisesRegex(RuntimeError, "managed user service"):
                    local_env.managed_kata(required=True)

    def test_managed_kata_rejects_wrong_database_and_invalid_health(self):
        good = {"ok": True, "version": "test", "schema_version": 30,
                "api_schema_version": "0.24.0", "db_path": str(self.state / "kata/kata.db")}
        for key, value in (("db_path", "/wrong/kata.db"), ("schema_version", 0),
                           ("schema_version", True), ("api_schema_version", ""),
                           ("version", "other"), ("ok", False)):
            with self.subTest(key=key, value=value):
                with patch.object(local_env, "user_service_pid", return_value=123):
                    with patch.object(local_env, "HTTP", self.kata_opener(health={**good, key: value})):
                        with self.assertRaisesRegex(RuntimeError, "private profile"):
                            local_env.managed_kata(required=True)

    def test_all_four_independent_services_leave_no_supervised_ports(self):
        self.assertEqual(local_env.supervised_ports(dict.fromkeys(local_env.SERVICE_PORTS)), ())

    def test_stopped_supervisor_status_still_reports_kata(self):
        service = {"unit": local_env.KATA_UNIT, "pid": 123}
        with patch.object(local_env, "managed_services", return_value={"kata": service}):
            with patch.object(local_env, "api") as api:
                result = local_env.status()
        self.assertEqual(result["stack"], "stopped")
        self.assertEqual(result["kata_service"], service)
        api.assert_not_called()

    def test_supervisor_without_owned_children_cleans_up_and_keeps_services(self):
        external = {name: {"unit": name + ".service", "pid": 123}
                    for name in local_env.SERVICE_PORTS}
        with patch.object(local_env, "managed_services", return_value=external):
            with patch.object(local_env, "check_ports") as ports:
                with patch.object(local_env, "register_project"):
                    with patch.object(local_env.subprocess, "Popen") as start:
                        with patch.object(local_env.time, "sleep", side_effect=SystemExit(0)):
                            with patch.object(local_env.signal, "signal"):
                                with contextlib.redirect_stdout(io.StringIO()):
                                    with self.assertRaises(SystemExit):
                                        local_env.serve()
        start.assert_not_called()
        self.assertEqual(ports.call_args_list, [unittest.mock.call(()), unittest.mock.call(())])
        self.assertFalse((self.state / "runtime/supervisor.json").exists())
        self.assertEqual(json.loads((self.state / "runtime/shutdown.json").read_text()),
                         {"ok": True, "errors": []})

    def test_stop_preserves_all_independent_services(self):
        external = {name: {"unit": name + ".service"} for name in local_env.SERVICE_PORTS}
        local_env.json_write(self.state / "runtime/shutdown.json", {"ok": True})
        with patch.object(local_env, "supervisor", return_value={"pid": 123, "external_services": external}):
            with patch.object(local_env.os, "kill") as kill:
                with patch.object(local_env, "check_ports") as ports:
                    with contextlib.redirect_stdout(io.StringIO()):
                        local_env.stop()
        kill.assert_called_once_with(123, local_env.signal.SIGTERM)
        ports.assert_called_once_with(())

    def test_github_cli_uses_private_profile_without_inherited_tokens(self):
        with patch.object(Path, "is_file", return_value=True):
            with patch.object(local_env.os, "access", return_value=True):
                with patch.dict(os.environ, {"GH_TOKEN": "not-inherited",
                                             "GITHUB_TOKEN": "not-inherited",
                                             "USAI_API_KEY": "not-inherited"}):
                    command, env = local_env.github_cli_launch(["api", "user"])
        self.assertEqual(command, [str(local_env.GH_BINARY), "api", "user"])
        self.assertEqual(env["GH_CONFIG_DIR"], str(self.state / "gh"))
        self.assertNotIn("GH_PROMPT_DISABLED", env)
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "USAI_API_KEY"):
            self.assertNotIn(name, env)
        self.assertEqual((self.state / "gh").stat().st_mode & 0o777, 0o700)

    def test_github_cli_rejects_missing_tool(self):
        with patch.object(Path, "is_file", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "bootstrap-toolchains"):
                local_env.github_cli_launch(["--version"])

    def test_service_readiness_waits_for_runtime_record(self):
        readiness = MagicMock(side_effect=[FileNotFoundError("not published yet"), {"pid": 123}])
        with patch.object(local_env.subprocess, "run", return_value=MagicMock(returncode=3)):
            with patch.object(local_env, "check_ports"), patch.object(local_env.time, "sleep"):
                local_env.install_user_service(local_env.AGENTSVIEW_UNIT, "agentsview-run", "test",
                                               (18080,), readiness)
        self.assertEqual(readiness.call_count, 2)


if __name__ == "__main__":
    unittest.main()
