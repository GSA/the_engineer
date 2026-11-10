import os
from pathlib import Path
import pty
import subprocess
import tempfile
import unittest

import repo_init

ROBOREV_BINARY = next((path for path in (
    Path(__file__).resolve().parent.parent / "roborev/bin/roborev",
    Path(os.environ.get("KENN_KOPY_RUNTIME_ROOT", Path.home() / "kenn-kopy")) / "roborev/bin/roborev",
    Path.home() / "kenn-kopy/roborev/bin/roborev") if path.is_file()), Path("/nonexistent/roborev"))
GIT = ("git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid")


def git(cwd, *args, check=True):
    return subprocess.run([*GIT, *args], cwd=cwd, text=True, capture_output=True, check=check,
                          start_new_session=True)


class TempRepoCase(unittest.TestCase):
    """A real repository with a local bare remote; pushes run without a controlling terminal."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="repo-init-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.remote = self.root / "remote.git"
        self.repo = self.root / "repo"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.remote)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "first")
        git(self.repo, "remote", "add", "origin", str(self.remote))

    def hook(self):
        return self.repo / ".git/hooks/pre-push"

    def push(self, *args, cwd=None):
        return git(cwd or self.repo, "push", "-q", *args, check=False)

    def remote_branches(self):
        output = subprocess.run(["git", "-C", str(self.remote), "for-each-ref", "--format=%(refname:short)"],
                                text=True, capture_output=True, check=True).stdout
        return set(output.split())


class GuardInstallTests(TempRepoCase):
    def test_install_writes_executable_marked_block_without_the_forbidden_word(self):
        self.assertEqual(repo_init.install_guard(self.repo), "installed")
        content = self.hook().read_text()
        self.assertTrue(content.startswith("#!/bin/sh\n" + repo_init.GUARD_START))
        self.assertIn(repo_init.GUARD_END, content)
        self.assertNotIn("roborev", content.lower())
        self.assertTrue(os.access(self.hook(), os.X_OK))
        self.assertTrue(repo_init.is_installed(self.repo))
        self.assertTrue(subprocess.run(["sh", "-n", str(self.hook())]).returncode == 0)

    def test_second_install_is_a_byte_identical_noop(self):
        repo_init.install_guard(self.repo)
        before = self.hook().read_bytes()
        mtime = self.hook().stat().st_mtime_ns
        self.assertEqual(repo_init.install_guard(self.repo), "unchanged")
        self.assertEqual(self.hook().read_bytes(), before)
        self.assertEqual(self.hook().stat().st_mtime_ns, mtime)

    def test_stale_block_is_replaced_once_and_surrounding_hook_is_kept(self):
        self.hook().write_text(
            f"#!/bin/sh\necho before\n{repo_init.GUARD_START}\nold stale text\n{repo_init.GUARD_END}\necho after\n")
        self.hook().chmod(0o755)
        self.assertEqual(repo_init.install_guard(self.repo), "updated")
        content = self.hook().read_text()
        self.assertEqual(content.count(repo_init.GUARD_START), 1)
        self.assertNotIn("old stale text", content)
        self.assertLess(content.index(repo_init.GUARD_END), content.index("echo before"))
        self.assertIn("echo after", content)

    def test_existing_shell_hook_is_preserved_after_the_guard(self):
        self.hook().write_text("#!/usr/bin/env bash\necho custom\n")
        self.hook().chmod(0o755)
        repo_init.install_guard(self.repo)
        lines = self.hook().read_text().splitlines()
        self.assertEqual(lines[0], "#!/usr/bin/env bash")
        self.assertEqual(lines[-1], "echo custom")

    def test_non_shell_hook_is_refused_and_left_untouched(self):
        self.hook().write_text("#!/usr/bin/env python3\nprint('hi')\n")
        before = self.hook().read_bytes()
        with self.assertRaisesRegex(RuntimeError, "not a POSIX shell hook"):
            repo_init.install_guard(self.repo)
        self.assertEqual(self.hook().read_bytes(), before)

    def test_unterminated_block_is_refused(self):
        self.hook().write_text(f"#!/bin/sh\n{repo_init.GUARD_START}\nexit 1\n")
        with self.assertRaisesRegex(RuntimeError, "unterminated"):
            repo_init.install_guard(self.repo)

    def test_remove_deletes_a_guard_only_hook_and_keeps_other_content(self):
        repo_init.install_guard(self.repo)
        self.assertEqual(repo_init.remove_guard(self.repo), "removed")
        self.assertFalse(self.hook().exists())
        self.assertFalse(repo_init.is_installed(self.repo))
        self.assertEqual(repo_init.remove_guard(self.repo), "absent")
        self.hook().write_text("#!/bin/sh\necho custom\n")
        repo_init.install_guard(self.repo)
        repo_init.remove_guard(self.repo)
        self.assertEqual(self.hook().read_text(), "#!/bin/sh\necho custom\n")

    def test_is_installed_requires_the_guard_first_and_executable(self):
        repo_init.install_guard(self.repo)
        self.hook().chmod(0o644)
        self.assertFalse(repo_init.is_installed(self.repo))
        self.hook().chmod(0o755)
        text = self.hook().read_text().replace("#!/bin/sh\n", "#!/bin/sh\necho first\n", 1)
        self.hook().write_text(text)
        self.assertFalse(repo_init.is_installed(self.repo))
        repo_init.install_guard(self.repo)
        self.assertTrue(repo_init.is_installed(self.repo))


class GuardPushTests(TempRepoCase):
    def setUp(self):
        super().setUp()
        repo_init.install_guard(self.repo)
        git(self.repo, "branch", "feature")

    def test_feature_branch_push_succeeds(self):
        result = self.push("origin", "feature")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("feature", self.remote_branches())

    def test_main_and_master_pushes_are_blocked_without_a_terminal(self):
        for target in ("main", "master"):
            with self.subTest(target=target):
                result = self.push("origin", f"HEAD:refs/heads/{target}")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"protected branch '{target}'", result.stderr)
                self.assertNotIn(target, self.remote_branches())

    def test_force_push_and_deletion_of_main_are_blocked(self):
        git(self.repo, "-c", "core.hooksPath=/dev/null", "push", "-q", "origin", "HEAD:refs/heads/main")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "second")
        for args in (("--force", "origin", "HEAD:main"), ("origin", ":main"), ("origin", "--delete", "main")):
            with self.subTest(args=args):
                result = self.push(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("protected branch 'main'", result.stderr)
                self.assertIn("main", self.remote_branches())

    def test_mixed_push_is_blocked_as_a_whole(self):
        result = self.push("origin", "feature", "HEAD:main")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.remote_branches(), set())

    def test_linked_worktree_shares_the_guard(self):
        worktree = self.root / "linked"
        git(self.repo, "worktree", "add", "-q", str(worktree), "-b", "linked-branch")
        self.assertTrue(repo_init.is_installed(worktree))
        self.assertEqual(self.push("origin", "linked-branch", cwd=worktree).returncode, 0)
        result = self.push("origin", "HEAD:main", cwd=worktree)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("protected branch 'main'", result.stderr)

    def test_environment_cannot_override_the_guard(self):
        for name in ("ENGINEER_ALLOW_PROTECTED_PUSH", "ALLOW_PROTECTED_PUSH", "FORCE", "CI"):
            self.assertNotIn(name, repo_init.GUARD_BLOCK)
        result = subprocess.run([*GIT, "push", "-q", "origin", "HEAD:main"], cwd=self.repo, text=True,
                                capture_output=True, start_new_session=True,
                                env={**os.environ, "ENGINEER_ALLOW_PROTECTED_PUSH": "1", "CI": "1"})
        self.assertNotEqual(result.returncode, 0)

    def push_with_terminal(self, answer):
        """Run git push main under a pseudo-terminal so /dev/tty is openable, typing `answer`."""
        pid, descriptor = pty.fork()
        if pid == 0:
            os.chdir(self.repo)
            os.execvp("git", [*GIT, "push", "-q", "origin", "HEAD:main"])
        output = b""
        os.write(descriptor, answer.encode() + b"\n")
        while True:
            try:
                chunk = os.read(descriptor, 4096)
            except OSError:
                break
            if not chunk:
                break
            output += chunk
        _, status = os.waitpid(pid, 0)
        return os.waitstatus_to_exitcode(status), output.decode(errors="replace")

    def test_a_person_at_a_terminal_must_type_yes(self):
        status, output = self.push_with_terminal("no")
        self.assertNotEqual(status, 0, output)
        self.assertIn("Push to protected branch main? Type yes:", output)
        self.assertNotIn("main", self.remote_branches())
        status, output = self.push_with_terminal("yes")
        self.assertEqual(status, 0, output)
        self.assertIn("main", self.remote_branches())


class GuardAndOtherSnippetsTests(TempRepoCase):
    """The guard re-feeds git's stdin so a later snippet (e.g. the review flush) still sees it."""

    def test_stdin_is_still_available_after_the_guard(self):
        capture = self.root / "stdin.txt"
        self.hook().write_text(f"#!/bin/sh\ncat > {capture}\n")
        self.hook().chmod(0o755)
        repo_init.install_guard(self.repo)
        git(self.repo, "branch", "feature")
        self.assertEqual(self.push("origin", "feature").returncode, 0)
        self.assertIn("refs/heads/feature", capture.read_text())

    @unittest.skipUnless(ROBOREV_BINARY.is_file(), "built roborev binary not available")
    def test_real_roborev_hook_composes_in_either_order(self):
        stdin_log = self.root / "flush-stdin.txt"
        stub = self.root / "roborev-stub"
        stub.write_text(f'#!/bin/sh\nif [ "$1" = post-commit ]; then cat >> {stdin_log}; fi\nexit 0\n')
        stub.chmod(0o755)
        home, data = self.root / "home", self.root / "data"
        home.mkdir()
        data.mkdir()
        env = {**os.environ, "HOME": str(home), "ROBOREV_DATA_DIR": str(data)}

        def roborev_init(repo):
            # --binary bakes the stub into the hooks so the push cannot reach a daemon.
            subprocess.run([str(ROBOREV_BINARY), "init", "--no-daemon", "--binary", str(stub)],
                           cwd=repo, env=env, check=False, capture_output=True, timeout=60)

        for order in ("roborev-then-guard", "guard-then-roborev", "guard-twice-after-roborev"):
            with self.subTest(order=order):
                repo = self.root / order
                subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
                git(repo, "commit", "-q", "--allow-empty", "-m", "first")
                remote = self.root / f"{order}.git"
                subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
                git(repo, "remote", "add", "origin", str(remote))
                git(repo, "branch", "feature")
                hook = repo / ".git/hooks/pre-push"
                if order == "guard-then-roborev":
                    repo_init.install_guard(repo)
                    roborev_init(repo)
                else:
                    roborev_init(repo)
                    repo_init.install_guard(repo)
                    if order == "guard-twice-after-roborev":
                        before = hook.read_bytes()
                        self.assertEqual(repo_init.install_guard(repo), "unchanged")
                        roborev_init(repo)
                        self.assertEqual(hook.read_bytes(), before)
                # The real roborev snippet is in the file, and the file is valid shell.
                self.assertIn("roborev pre-push hook", hook.read_text())
                self.assertEqual(subprocess.run(["sh", "-n", str(hook)]).returncode, 0)
                # Whichever snippet runs first, the guard still sees git's stdin and blocks main.
                early = git(repo, "push", "-q", "origin", "HEAD:main", check=False)
                self.assertNotEqual(early.returncode, 0)
                self.assertIn("protected branch 'main'", early.stderr)
                # init-repo's last word is the guard; it ends up first whatever the order.
                repo_init.install_guard(repo)
                self.assertTrue(repo_init.is_installed(repo))
                self.assertEqual(hook.read_text().count(repo_init.GUARD_START), 1)
                stdin_log.write_text("")
                feature = git(repo, "push", "-q", "origin", "feature", check=False)
                self.assertEqual(feature.returncode, 0, feature.stderr)
                self.assertIn("refs/heads/feature", stdin_log.read_text())
                blocked = git(repo, "push", "-q", "origin", "HEAD:main", check=False)
                self.assertNotEqual(blocked.returncode, 0)
                self.assertIn("protected branch 'main'", blocked.stderr)
                self.assertNotIn("main", subprocess.run(
                    ["git", "-C", str(remote), "for-each-ref", "--format=%(refname:short)"],
                    text=True, capture_output=True, check=True).stdout.split())
                # The remaining hooks still carry the review commands.
                for name in ("post-commit", "post-rewrite"):
                    self.assertIn("roborev", (repo / ".git/hooks" / name).read_text())


class InitRepoStepTests(TempRepoCase):
    def services(self, **overrides):
        calls = []
        template = self.root / "roborev-template.toml"
        template.write_text('agent = "pi"\n')

        def roborev_init(repo):
            calls.append("roborev")
            for name in repo_init.ROBOREV_HOOKS:
                path = repo_init.hook_path(repo, name)
                if not path.exists():
                    path.write_text("#!/bin/sh\n# roborev hook\n")
                    path.chmod(0o755)

        def kata_init(repo, project):
            calls.append(("kata", project))
            (repo / ".kata.toml").write_text(f'version = 1\n\n[project]\nname = "{project}"\n')

        values = dict(command="local_env.py", register=lambda repo: ("OK", "registered with Forge"),
                      roborev_init=roborev_init, kata_init=kata_init, kata_mapping=lambda project: "mapped",
                      verify=lambda repo: None, roborev_template=template)
        values.update(overrides)
        services = repo_init.InitServices(**values)
        services.calls = calls
        return services

    def run_init(self, services, path=None, **options):
        output = []
        status = repo_init.init_repo(path or self.repo, services, out=output.append, **options)
        return status, "\n".join(output)

    def test_first_run_does_every_step_and_second_run_skips_them(self):
        services = self.services()
        status, output = self.run_init(services)
        self.assertEqual(status, 0, output)
        for expected in ("OK    repository", "OK    forge", "OK    roborev-hooks", "OK    roborev-config",
                         "OK    kata:", "OK    guard", "OK    verify", "Next steps:"):
            self.assertIn(expected, output)
        self.assertIn("feature branch and pull request", output)
        self.assertIn('name = "repo"', (self.repo / ".kata.toml").read_text())
        self.assertEqual((self.repo / ".roborev.toml").read_text(), 'agent = "pi"\n')
        self.assertTrue(repo_init.is_installed(self.repo))
        snapshot = {path: path.read_bytes() for path in self.repo.rglob("*")
                    if path.is_file() and ".git/objects" not in str(path)}
        status, output = self.run_init(self.services(register=lambda repo: ("SKIP", "already registered")))
        self.assertEqual(status, 0, output)
        for expected in ("SKIP  forge", "SKIP  roborev-hooks", "SKIP  roborev-config", "SKIP  kata:",
                         "SKIP  guard"):
            self.assertIn(expected, output)
        self.assertEqual(snapshot, {path: path.read_bytes() for path in snapshot})

    def test_existing_files_are_never_overwritten(self):
        (self.repo / ".roborev.toml").write_text("mine = true\n")
        (self.repo / ".kata.toml").write_text('version = 1\n\n[project]\nname = "custom"\n')
        services = self.services()
        status, _ = self.run_init(services, project="ignored")
        self.assertEqual(status, 0)
        self.assertEqual((self.repo / ".roborev.toml").read_text(), "mine = true\n")
        self.assertIn('"custom"', (self.repo / ".kata.toml").read_text())
        self.assertNotIn(("kata", "ignored"), services.calls)

    def test_project_option_and_skip_kata(self):
        services = self.services()
        self.run_init(services, project="the_thing")
        self.assertIn(("kata", "the_thing"), services.calls)
        other = self.root / "skip"
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        services = self.services()
        status, output = self.run_init(services, path=other, skip_kata=True)
        self.assertEqual(status, 0, output)
        self.assertIn("SKIP  kata: --skip-kata", output)
        self.assertFalse((other / ".kata.toml").exists())
        self.assertFalse(any(isinstance(call, tuple) for call in services.calls))

    def test_unreachable_services_warn_with_the_manual_command_and_continue(self):
        def forge_down(repo):
            raise repo_init.ServiceUnavailable("Forge is not answering")

        def kata_down(repo, project):
            raise repo_init.ServiceUnavailable("Kata daemon is not reachable")

        status, output = self.run_init(self.services(register=forge_down, kata_init=kata_down))
        self.assertEqual(status, 0, output)
        self.assertIn(f"WARN  forge: Forge is not answering; start Forge, then run: local_env.py register "
                      f"{self.repo.resolve()}", output)
        self.assertIn("WARN  kata: Kata daemon is not reachable; start Kata, then run: kata init --project repo",
                      output)
        self.assertIn("OK    guard", output)

    def test_unmapped_kata_project_prints_the_manual_step(self):
        status, output = self.run_init(self.services(kata_mapping=lambda project: "unmapped"))
        self.assertEqual(status, 0, output)
        self.assertIn("WARN  kata-mapping", output)
        self.assertIn("Kata project mappings", output)

    def test_error_in_a_step_sets_nonzero_exit_but_later_steps_still_run(self):
        def broken(repo):
            raise RuntimeError("roborev exploded")

        status, output = self.run_init(self.services(roborev_init=broken))
        self.assertEqual(status, 1)
        self.assertIn("ERROR roborev: roborev exploded", output)
        self.assertIn("OK    guard", output)

    def test_non_shell_pre_push_hook_is_an_error(self):
        self.hook().write_text("#!/usr/bin/env python3\n")
        status, output = self.run_init(self.services())
        self.assertEqual(status, 1)
        self.assertIn("ERROR guard", output)
        self.assertEqual(self.hook().read_text(), "#!/usr/bin/env python3\n")

    def test_invalid_paths_are_errors(self):
        bare_status, bare = self.run_init(self.services(), path=self.remote)
        self.assertEqual(bare_status, 1)
        self.assertIn("bare repository", bare)
        plain = self.root / "plain"
        plain.mkdir()
        self.assertEqual(self.run_init(self.services(), path=plain)[0], 1)
        self.assertEqual(self.run_init(self.services(), path=self.root / "missing")[0], 1)
        self.assertEqual(self.run_init(self.services(), path=self.repo / ".git")[0], 1)

    def test_remove_guard_option_only_removes_the_guard(self):
        self.run_init(self.services())
        services = self.services()
        status, output = self.run_init(services, remove_guard_only=True)
        self.assertEqual(status, 0, output)
        self.assertIn("OK    guard: protected-branch guard removed", output)
        self.assertFalse(repo_init.is_installed(self.repo))
        self.assertEqual(services.calls, [])
        self.assertIn("SKIP  guard: no guard installed", self.run_init(services, remove_guard_only=True)[1])


if __name__ == "__main__":
    unittest.main()
