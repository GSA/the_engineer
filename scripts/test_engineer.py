import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import engineer
import host_setup
import local_env


def answers(*replies):
    """An ask() that returns scripted replies and records each question."""
    asked = []
    replies = list(replies)

    def ask(question, default):
        asked.append(question)
        return replies.pop(0) if replies else default
    ask.asked = asked
    return ask


class EngineerTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="engineer-test-", dir=local_env.ROOT / ".local")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.state = self.root / "checkout/.local/environment"
        self.addCleanup(patch.stopall)
        patch.object(local_env, "STATE", self.state).start()
        patch.object(engineer, "HOME", self.home).start()
        patch.object(engineer, "LOCAL", self.root / "checkout/.local").start()
        patch.object(engineer.copilot_env, "TOOLS_BIN", self.home / ".local/engineer/npm/bin").start()
        self.commands = []
        patch.object(engineer, "run", side_effect=self.fake_run).start()

    def fake_run(self, command, **kwargs):
        self.commands.append(command)
        return subprocess.CompletedProcess(command, 0, "active\n", "")

    def installed_state(self):
        local_env.private_dir(self.state)
        local_env.private_dir(self.state / "pi")
        local_env.json_write(self.state / "environment.json", {"forge_binary": "/x", "unit_prefix": "engineer"})
        local_env.json_write(self.state / "pi/models.json", {"providers": {"usai": {
            "baseUrl": "https://usai.example.test/v1", "api": "openai-completions",
            "apiKey": "${USAI_API_KEY}", "models": [{"id": "claude-sonnet-5.5"}]}}})
        local_env.json_write(self.state / "usai.json", {
            "model": "claude-sonnet-5.5", "review_model": "gpt-6.1-sol-latest-guardrails-defaultv2"})


class CommandLineTests(EngineerTestCase):
    def test_every_documented_verb_is_routed_and_none_takes_a_secret(self):
        parser = engineer.build_parser()
        for verb in ("install", "doctor", "start", "stop", "status", "key", "models", "login",
                     "add-repo", "pi", "copilot", "update", "uninstall"):
            with self.subTest(verb=verb):
                self.assertIn(verb, parser.format_help())
        for verb, option in (("install", "--key"), ("key", "--key"), ("install", "--api-key")):
            with self.subTest(option=option), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parser.parse_args([verb, option, "secret"])

    def test_errors_are_one_plain_line_without_a_traceback(self):
        with patch.object(engineer, "doctor", side_effect=RuntimeError("something is off")), \
                contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(engineer.main(["doctor"]), 1)
        self.assertEqual(errors.getvalue(), "Problem: something is off\n")


class EnvironmentTests(EngineerTestCase):
    def test_main_puts_engineers_own_node_and_tools_first_on_path(self):
        with patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}), \
                patch.object(engineer, "doctor", return_value=True):
            engineer.main(["doctor"])
            path = os.environ["PATH"].split(os.pathsep)
        self.assertEqual(path[:2], [str(self.home / ".local/engineer/npm/bin"),
                                    str(self.home / ".local/engineer/node/bin")])

    def test_update_reruns_install_from_the_updated_code(self):
        with patch.object(engineer.os, "execv") as execv:
            engineer.update(engineer.build_parser().parse_args(["update", "--yes"]))
        self.assertEqual(self.commands[0][-2:], ["pull", "--ff-only"])
        argv = execv.call_args.args[1]
        self.assertEqual(argv[1:], [str(engineer.ROOT / "scripts/engineer.py"), "install", "--yes"])


class KeyTests(EngineerTestCase):
    def setUp(self):
        super().setUp()
        self.installed_state()
        patch.object(engineer.sys.stdin, "isatty", return_value=True).start()

    def save(self, fetch, ask=None, key="test-only-token"):
        with patch.object(engineer.getpass, "getpass", return_value=key), \
                patch.object(engineer.local_env, "fetch_usai_models", side_effect=fetch), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            engineer.save_key(ask or answers())
        return output.getvalue()

    def test_checked_key_is_saved_privately_and_never_printed(self):
        output = self.save(lambda base, key: ["claude-sonnet-5.5", "gpt-6.1-sol-latest-guardrails-defaultv2"])
        path = self.state / "secrets/usai-api-key"
        self.assertEqual(path.read_text(), "test-only-token\n")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("test-only-token", output)
        self.assertIn("USAi accepted the key", output)

    def test_rejected_key_is_not_saved_and_says_so_plainly(self):
        def fetch(base, key):
            raise RuntimeError("USAi model list returned HTTP 401; redirects are refused; response body not logged")
        with self.assertRaisesRegex(RuntimeError, "USAi rejected this key"):
            self.save(fetch)
        self.assertFalse((self.state / "secrets/usai-api-key").exists())

    def test_unreachable_usai_saves_only_after_consent(self):
        def fetch(base, key):
            raise urllib.error.URLError("no route")
        with self.assertRaisesRegex(RuntimeError, "Nothing was saved"):
            self.save(fetch, answers(False))
        self.assertFalse((self.state / "secrets/usai-api-key").exists())
        self.save(fetch, answers(True))
        self.assertTrue((self.state / "secrets/usai-api-key").exists())

    def test_key_needs_a_terminal(self):
        with patch.object(engineer.sys.stdin, "isatty", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "terminal"):
                engineer.save_key(answers())


class ModelMenuTests(unittest.TestCase):
    def test_enter_keeps_current_and_numbers_or_names_select(self):
        options = ["a", "b", "c"]
        for replies, expected in (([""], "b"), (["3"], "c"), (["a"], "a"), (["9", "x", "1"], "a")):
            with self.subTest(replies=replies), contextlib.redirect_stdout(io.StringIO()):
                pending = iter(replies)
                self.assertEqual(engineer.choose("Pick", options, "b", reply=lambda prompt: next(pending)), expected)

    def test_reviewer_choices_exclude_the_coder_family_and_embeddings(self):
        catalog = ["claude-sonnet-5.5", "claude-opus-5.5", "gpt-6.1-sol-latest-guardrails-defaultv2",
                   "gemini-4-argon", "cohere-v4", "llama_4_maverick"]
        self.assertEqual(engineer.chat_models(catalog),
                         ["claude-opus-5.5", "claude-sonnet-5.5", "gemini-4-argon",
                          "gpt-6.1-sol-latest-guardrails-defaultv2"])
        self.assertEqual(engineer.reviewer_models(catalog, "claude-sonnet-5.5"),
                         ["gemini-4-argon", "gpt-6.1-sol-latest-guardrails-defaultv2"])
        self.assertEqual(engineer.copilot_models(catalog), ["claude-opus-5.5", "claude-sonnet-5.5"])


class InstallQuestionTests(EngineerTestCase):
    def test_copilot_defaults_to_usai_for_people_without_copilot(self):
        ask = answers()
        choices = engineer.install_choices(ask, saved={}, copilot_flag=None)
        self.assertEqual(choices, {"copilot": True, "copilot_command": True, "pi_command": True})

    def test_existing_copilot_users_keep_plain_copilot_unless_they_choose_usai(self):
        (self.home / ".copilot").mkdir()
        ask = answers(True)
        choices = engineer.install_choices(ask, saved={}, copilot_flag=None)
        self.assertTrue(choices["copilot"])
        self.assertFalse(choices["copilot_command"])
        self.assertTrue(any("GitHub Copilot" in question for question in ask.asked))

    def test_saved_answers_are_reused_without_asking_again(self):
        saved = {"copilot": False, "copilot_command": False, "pi_command": False}
        ask = answers()
        self.assertEqual(engineer.install_choices(ask, saved=saved, copilot_flag=None), saved)
        self.assertEqual(ask.asked, [])
        self.assertTrue(engineer.install_choices(ask, saved=saved, copilot_flag="yes")["copilot"])

    def test_install_refuses_a_checkout_set_up_by_the_older_scripts(self):
        self.installed_state()
        with self.assertRaisesRegex(RuntimeError, "older scripts"):
            engineer.check_install_owner()


class UninstallTests(EngineerTestCase):
    def manifest(self, **extra):
        record = {"schema": engineer.MANIFEST_SCHEMA, "units": ["engineer-kata.service"],
                  "prefix": True, "kata_config_existed": False, "repos": [], **extra}
        engineer.save_manifest(record)
        return record

    def test_uninstall_without_an_install_record_changes_nothing(self):
        with self.assertRaisesRegex(RuntimeError, "install record"):
            engineer.uninstall(answers(True), purge=False)
        self.assertEqual(self.commands, [])

    def test_uninstall_reverses_only_recorded_items_and_keeps_data(self):
        self.manifest()
        (self.home / ".local/engineer/npm/bin").mkdir(parents=True)
        bin_dir = self.home / ".local/bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "kata").symlink_to(local_env.RUNTIME_ROOT / "kata/kata")
        (bin_dir / "roborev").symlink_to("/somewhere/else/roborev")
        (self.home / ".kata").mkdir()
        (self.home / ".kata/config.toml").write_text('active_daemon = "local"\n')
        host_setup.write_shell_block(host_setup.shell_block("/opt/eng"), self.home)
        local_env.private_dir(self.state)
        (self.state / "keep.db").write_text("tasks")
        units = self.home / ".config/systemd/user"
        units.mkdir(parents=True)
        (units / "engineer-kata.service").symlink_to(self.state / "systemd/engineer-kata.service")
        (units / "other.service").write_text("[Unit]\n")
        with contextlib.redirect_stdout(io.StringIO()):
            engineer.uninstall(answers(True), purge=False)
        self.assertIn(["systemctl", "--user", "disable", "--now", "engineer-kata.service"], self.commands)
        self.assertFalse(any("kenn-kopy" in " ".join(map(str, command)) for command in self.commands))
        self.assertFalse((bin_dir / "kata").is_symlink())
        self.assertTrue((bin_dir / "roborev").is_symlink())
        self.assertFalse((self.home / ".kata/config.toml").exists())
        self.assertFalse((self.home / ".local/engineer").exists())
        self.assertNotIn(host_setup.SHELL_START, (self.home / ".bashrc").read_text())
        self.assertTrue((self.state / "keep.db").exists())
        self.assertFalse((units / "engineer-kata.service").is_symlink())
        self.assertTrue((units / "other.service").exists())
        self.assertIsNone(engineer.load_manifest())

    def test_existing_kata_config_is_left_in_place(self):
        self.manifest(kata_config_existed=True)
        (self.home / ".kata").mkdir()
        (self.home / ".kata/config.toml").write_text("mine\n")
        with contextlib.redirect_stdout(io.StringIO()):
            engineer.uninstall(answers(True), purge=False)
        self.assertEqual((self.home / ".kata/config.toml").read_text(), "mine\n")

    def test_declining_changes_nothing(self):
        self.manifest()
        with contextlib.redirect_stdout(io.StringIO()):
            engineer.uninstall(answers(False), purge=False)
        self.assertEqual(self.commands, [])
        self.assertIsNotNone(engineer.load_manifest())

    def test_purge_needs_the_typed_phrase(self):
        self.manifest()
        local_env.private_dir(self.state)
        with patch("builtins.input", return_value="yes"), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "not deleted"):
                engineer.uninstall(answers(True), purge=True)
        self.assertTrue(self.state.exists())
        self.manifest()
        with patch("builtins.input", return_value="delete my data"), contextlib.redirect_stdout(io.StringIO()):
            engineer.uninstall(answers(True), purge=True)
        self.assertFalse(engineer.LOCAL.exists())


class DoctorTests(EngineerTestCase):
    def test_failures_are_translated_into_engineer_commands(self):
        self.installed_state()
        engineer.save_manifest({"units": [], "repos": []})
        with patch.object(engineer.local_env, "accept", return_value=["usai-key", "service:forge", "github-login"]), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertFalse(engineer.doctor())
        text = output.getvalue()
        self.assertIn("./engineer key", text)
        self.assertIn("./engineer start", text)
        self.assertIn("./engineer login", text)

    def test_doctor_on_a_fresh_checkout_points_at_install(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertFalse(engineer.doctor())
        self.assertIn("./engineer install", output.getvalue())


if __name__ == "__main__":
    unittest.main()
