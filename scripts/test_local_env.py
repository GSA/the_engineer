import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

import local_env


class LocalEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="local-env-test-", dir=local_env.ROOT / ".local")
        self.addCleanup(self.temporary.cleanup)
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
        patch.object(local_env.shutil, "which", return_value="/usr/bin/pi").start()
        patch.object(local_env, "verify_pi", return_value="/usr/bin/pi").start()
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

    def test_credential_free_mcp_command(self):
        command, env = local_env.pi_launch(["mcp", "list"])
        self.assertEqual(command, ["/usr/bin/pi", "mcp", "list"])
        self.assertNotIn("USAI_API_KEY", env)

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

    def test_scoped_roborev_entrypoint_executes_without_changing_directory(self):
        command = ["/native/roborev", "--server", "127.0.0.1:17373", "status"]
        env = {"ROBOREV_DATA_DIR": "/private"}
        with patch.object(local_env, "roborev_launch", return_value=(command, env)) as launch:
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

    def test_key_handoff_requires_terminal(self):
        with patch.object(local_env.sys.stdin, "isatty", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "terminal"):
                local_env.set_key()
        self.assertFalse((self.state / "secrets/usai-api-key").exists())

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
            env = local_env.roborev_environment(node)
        self.assertEqual(env["PATH"].split(os.pathsep)[0], str(node.parent))
        self.assertNotIn("USAI_API_KEY", env)
        self.assertEqual(env["PI_CODING_AGENT_DIR"], str(self.state / "pi"))

    def test_roborev_rejects_missing_node_and_nonlocal_bindings(self):
        with self.assertRaisesRegex(RuntimeError, "missing executable Node"):
            local_env.roborev_environment(self.root / "missing-node")
        config = self.state / "roborev/config.toml"
        local_env.private_write(config, 'server_addr = "0.0.0.0:17373"\n', replace=True)
        with self.assertRaisesRegex(RuntimeError, "loopback"):
            local_env.validate_roborev_config()

    def test_roborev_service_installation_preserves_settings_and_records_node(self):
        node = self.node_executable()
        config = self.state / "roborev/config.toml"
        before = config.read_bytes()
        with patch.object(local_env.shutil, "which", return_value=str(node)):
            with patch.object(local_env.subprocess, "run", return_value=MagicMock(returncode=0)) as run:
                with patch.object(local_env, "managed_roborev", return_value={"pid": 123}):
                    with contextlib.redirect_stdout(io.StringIO()):
                        local_env.install_roborev_service()
                        first = (self.state / "systemd" / local_env.ROBOREV_UNIT).read_bytes()
                        local_env.install_roborev_service()
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual((self.state / "systemd" / local_env.ROBOREV_UNIT).read_bytes(), first)
        text = first.decode()
        self.assertIn('"roborev-run" "--node-executable" ' + local_env.systemd_quote(node), text)
        self.assertIn("WantedBy=default.target", text)
        self.assertNotIn("USAI_API_KEY", text)
        self.assertIn(unittest.mock.call(
            ["systemctl", "--user", "enable", "--now", local_env.ROBOREV_UNIT],
            check=True, timeout=60), run.call_args_list)
        self.assertTrue((self.state / "roborev-service.json").exists())

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


if __name__ == "__main__":
    unittest.main()
