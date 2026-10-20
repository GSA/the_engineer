import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import local_env
import roborev_hooks


class RoborevHookTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="review-hooks-", dir=local_env.ROOT / ".local")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo with spaces"
        self.repo.mkdir()
        self.git("init", "--quiet")
        self.state = self.root / "state"
        self.state.mkdir(mode=0o700)
        self.launcher = self.root / "scripts/roborev-local.py"
        self.launcher.parent.mkdir()
        self.log = self.root / "calls"
        self.input_log = self.root / "input"
        self.launcher.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$*" >> "' + str(self.log) + '"\n'
            'case "$1" in remap) cat >> "' + str(self.input_log) + '";; esac\n'
        )
        self.launcher.chmod(0o755)
        self.native = local_env.ROOT / "roborev/bin/roborev"
        self.addCleanup(patch.stopall)
        patch.object(local_env, "ROOT", self.root).start()
        patch.object(local_env, "STATE", self.state).start()
        patch.object(roborev_hooks, "run_roborev", side_effect=self.run_native).start()

    def git(self, *args):
        return roborev_hooks.git(self.repo, *args)

    def run_native(self, repo, *args):
        if args[0] == "init":
            args = ("install-hook", "--binary", str(self.launcher))
        result = subprocess.run(
            [str(self.native), *args], cwd=repo, check=True, capture_output=True, text=True,
            env={**os.environ, "ROBOREV_TELEMETRY_ENABLED": "0"},
        )
        return result.stdout + ("Repo registered with running daemon\n" if args[0] == "install-hook" else "")

    def install(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return roborev_hooks.install(self.repo, "platform")

    def test_local_config_native_hooks_and_repeat_install(self):
        hooks = self.install()
        self.assertEqual(self.git("config", "--local", "core.hooksPath"), str(hooks))
        self.assertEqual(self.git("status", "--short"), "")
        self.assertFalse((self.repo / ".gitignore").exists())
        self.assertEqual((self.repo / ".roborev.toml").read_text(), roborev_hooks.review_config("platform"))
        before = {p.name: p.read_bytes() for p in hooks.iterdir()}
        self.assertEqual(self.install(), hooks)
        self.assertEqual(before, {p.name: p.read_bytes() for p in hooks.iterdir()})
        subprocess.run([str(hooks / "post-commit")], cwd=self.repo, check=True)
        self.assertEqual(self.log.read_text(), "post-commit\n")

    def test_original_hooks_and_pre_push_stdin_and_failure_are_preserved(self):
        original = self.repo / ".git/hooks"
        marker = self.root / "original-input"
        (original / "pre-push").write_text(
            '#!/bin/sh\ncat > "' + str(marker) + '"\nexit 7\n'
        )
        (original / "pre-push").chmod(0o755)
        (original / "post-commit").write_text('#!/bin/sh\nprintf "original\\n" >> "' + str(self.log) + '"\n')
        (original / "post-commit").chmod(0o755)
        before = {name: (original / name).read_bytes() for name in ("pre-push", "post-commit")}
        hooks = self.install()
        subprocess.run([str(hooks / "post-commit")], cwd=self.repo, check=True)
        self.assertEqual(self.log.read_text(), "post-commit\noriginal\n")
        result = subprocess.run([str(hooks / "pre-push"), "origin", "unused"], cwd=self.repo, input=b"ref data\n")
        self.assertEqual(result.returncode, 7)
        self.assertEqual(marker.read_bytes(), b"ref data\n")
        self.assertEqual(before, {name: (original / name).read_bytes() for name in before})

    def test_rewrite_receives_stdin(self):
        hooks = self.install()
        subprocess.run([str(hooks / "post-rewrite"), "amend"], cwd=self.repo, input=b"old new\n", check=True)
        self.assertEqual(self.input_log.read_bytes(), b"old new\n")

    def test_linked_worktree_inherits_hooks_and_local_review_config(self):
        self.git("-c", "core.hooksPath=/dev/null", "-c", "user.name=Hook Test",
                 "-c", "user.email=hook-test@example.invalid",
                 "commit", "--quiet", "--allow-empty", "-m", "Fixture")
        hooks = self.install()
        worktree = self.root / "linked worktree"
        self.git("worktree", "add", "--quiet", "-b", "fixture", str(worktree))
        self.assertEqual(roborev_hooks.git(worktree, "config", "core.hooksPath"), str(hooks))
        result = subprocess.run(
            [str(self.native), "config", "get", "--local", "agent"],
            cwd=worktree, capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout.strip(), "pi")

    def test_original_symlink_target_is_not_modified(self):
        target = self.root / "shared-post-commit"
        target.write_text("#!/bin/sh\nexit 0\n")
        target.chmod(0o755)
        (self.repo / ".git/hooks/post-commit").symlink_to(target)
        hooks = self.install()
        self.assertFalse((hooks / "post-commit").is_symlink())
        self.assertEqual(target.read_text(), "#!/bin/sh\nexit 0\n")

    def test_missing_scoped_launcher_does_not_fall_back(self):
        hooks = self.install()
        self.launcher.unlink()
        fake_global = self.launcher.parent / "roborev"
        fake_global.write_text('#!/bin/sh\ntouch "' + str(self.log) + '"\n')
        fake_global.chmod(0o755)
        result = subprocess.run(
            [str(hooks / "post-commit")], cwd=self.repo, capture_output=True, text=True,
            env={**os.environ, "PATH": str(self.launcher.parent) + ":/usr/bin:/bin"},
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("review not queued", result.stderr)
        self.assertFalse(self.log.exists())

    def test_launcher_errors_are_visible(self):
        hooks = self.install()
        self.launcher.write_text("#!/bin/sh\necho 'ERROR: private profile missing' >&2\nexit 1\n")
        result = subprocess.run([str(hooks / "post-commit")], cwd=self.repo, capture_output=True, text=True)
        self.assertIn("ERROR: private profile missing", result.stderr)

    def test_existing_config_is_not_overwritten(self):
        config = self.repo / ".roborev.toml"
        config.write_text('agent = "different"\n')
        with self.assertRaisesRegex(RuntimeError, "existing review config differs"):
            self.install()
        self.assertEqual(config.read_text(), 'agent = "different"\n')
        self.assertEqual(roborev_hooks.local_hooks_values(self.repo), [])

    def test_unsupported_existing_hooks_are_not_modified(self):
        for name, content in (
            ("post-rewrite", "#!/bin/sh\ncat\n"),
            ("post-commit", "#!/usr/bin/python3\nprint('existing')\n"),
        ):
            with self.subTest(name=name):
                path = self.repo / ".git/hooks" / name
                path.write_text(content)
                with self.assertRaises(RuntimeError):
                    self.install()
                self.assertEqual(path.read_text(), content)
                self.assertEqual(roborev_hooks.local_hooks_values(self.repo), [])
                path.unlink()

    def test_registration_failure_restores_hooks_config(self):
        old = self.root / "existing hooks"
        old.mkdir()
        self.git("config", "--local", "core.hooksPath", str(old))
        with patch.object(roborev_hooks, "run_roborev", return_value="Setup incomplete"):
            with self.assertRaisesRegex(RuntimeError, "did not confirm"):
                self.install()
        self.assertEqual(roborev_hooks.local_hooks_values(self.repo), [str(old)])
        self.assertTrue(self.install().is_dir())

    def test_policy_rejects_unapproved_automation(self):
        baseline = 'max_workers = 1\ndefault_agent = "pi"\n'
        with patch.object(local_env, "settings"), patch.object(local_env, "validate_roborev_config"):
            for extra in (
                "allow_unsafe_agents = true\n",
                'default_backup_agent = "other"\n',
                "[ci]\nenabled = true\n",
                "[advanced]\ntasks_enabled = true\n",
                '[review]\nhook_review_panel = "multi"\n',
            ):
                with self.subTest(extra=extra), patch.object(local_env, "private_read", return_value=baseline + extra):
                    with self.assertRaises(RuntimeError):
                        roborev_hooks.validate_policy()


if __name__ == "__main__":
    unittest.main()
