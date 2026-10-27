#!/usr/bin/env python3
"""Tests for sync-helix-gsa.py against real local git repositories.

No network and no gh: Helix and GSA are local bare repos, so every assertion
exercises real git behavior rather than a mock of it.
"""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parent / "sync-helix-gsa.py"
spec = importlib.util.spec_from_file_location("sync_helix_gsa", MODULE_PATH)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def run(args, cwd=None):
    completed = subprocess.run(
        args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    if completed.returncode != 0:
        raise AssertionError(f"{' '.join(args)} failed:\n{completed.stdout}")
    return completed.stdout


class ParseSpecTests(unittest.TestCase):
    def test_bare_name_uses_source_org(self):
        self.assertEqual(sync.parse_spec("repo", "ORG", ""), ("ORG", "repo", "repo"))

    def test_qualified_name(self):
        self.assertEqual(sync.parse_spec("A/b", "ORG", ""), ("A", "b", "b"))

    def test_explicit_destination_and_prefix(self):
        self.assertEqual(sync.parse_spec("A/b=c", "ORG", "p-"), ("A", "b", "p-c"))

    def test_strips_dot_git(self):
        self.assertEqual(sync.parse_spec("A/b.git", "", ""), ("A", "b", "b"))

    def test_bare_name_without_org_is_rejected(self):
        with self.assertRaises(ValueError):
            sync.parse_spec("repo", "", "")

    def test_too_many_segments_rejected(self):
        with self.assertRaises(ValueError):
            sync.parse_spec("a/b/c", "", "")


class ClassifyTests(unittest.TestCase):
    def test_states(self):
        self.assertEqual(sync.classify(0, 0, True, True), sync.IN_SYNC)
        self.assertEqual(sync.classify(0, 0, True, False), sync.NEW_ON_HELIX)
        self.assertEqual(sync.classify(0, 0, False, True), sync.ONLY_ON_GSA)
        self.assertEqual(sync.classify(0, 3, True, True), sync.GSA_BEHIND)
        self.assertEqual(sync.classify(2, 0, True, True), sync.GSA_AHEAD)
        self.assertEqual(sync.classify(2, 3, True, True), sync.DIVERGED)

    def test_diverged_is_never_forwardable(self):
        self.assertNotIn(sync.DIVERGED, sync.FORWARDABLE)
        self.assertNotIn(sync.GSA_AHEAD, sync.FORWARDABLE)
        self.assertNotIn(sync.ONLY_ON_GSA, sync.FORWARDABLE)


class ReadReposFileTests(unittest.TestCase):
    def test_comments_and_blanks_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "repos.txt"
            path.write_text("# note\n\nA/one\nA/two=dos  # trailing\n", encoding="utf-8")
            self.assertEqual(sync.read_repos_file(path), ["A/one", "A/two=dos"])

    def test_missing_file_raises(self):
        with self.assertRaises(ValueError):
            sync.read_repos_file("/nonexistent/repos.txt")


class SyncIntegrationTests(unittest.TestCase):
    """End-to-end runs against local bare repos standing in for both hosts."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sync-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.helix = self.root / "helix.git"
        self.gsa = self.root / "gsa.git"
        self.into = self.root / "clones"

        run(["git", "init", "-q", "--bare", str(self.helix)])
        self.seed = self.root / "seed"
        run(["git", "init", "-q", str(self.seed)])
        self.git_seed(["config", "user.email", "t@example.invalid"])
        self.git_seed(["config", "user.name", "Test"])
        (self.seed / "f").write_text("base\n", encoding="utf-8")
        self.git_seed(["add", "."])
        self.git_seed(["commit", "-qm", "base"])
        self.git_seed(["branch", "-M", "master"])
        self.git_seed(["push", "-q", str(self.helix), "master"])
        # GSA starts as a mirror of Helix, matching the real starting state.
        run(["git", "clone", "-q", "--mirror", str(self.helix), str(self.gsa)])

    def git_seed(self, args):
        return run(["git", *args], cwd=self.seed)

    def git_helix(self, args):
        return run(["git", f"--git-dir={self.helix}", *args])

    def git_gsa(self, args):
        return run(["git", f"--git-dir={self.gsa}", *args])

    def commit_on_helix(self, message, branch="master", new_file=None):
        self.git_seed(["checkout", "-q", branch])
        target = self.seed / (new_file or "f")
        target.write_text(target.read_text() + message + "\n" if target.exists() else message, encoding="utf-8")
        self.git_seed(["add", "."])
        self.git_seed(["commit", "-qm", message])
        self.git_seed(["push", "-q", str(self.helix), branch])

    def make_repo(self, path=None):
        """A Repo whose two remotes are the local bare repos."""

        class StubConfig:
            source_host = "helix.invalid"
            source_org = "ORG"
            dest_host = "github.invalid"
            dest_org = "GSA"
            dest_prefix = ""
            protocol = "https"
            into = self.into

        repo = sync.Repo(path or (self.into / "app"), "ORG", "app", "app", StubConfig())
        repo.helix_url = str(self.helix)
        repo.gsa_url = str(self.gsa)
        return repo

    def clone_and_wire(self):
        """Clone from the stand-in GSA and add the stand-in Helix remote."""
        path = self.into / "app"
        path.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "-q", "--origin", "origin", str(self.gsa), str(path)])
        run(["git", "config", "user.email", "t@example.invalid"], cwd=path)
        run(["git", "config", "user.name", "Test"], cwd=path)
        run(["git", "remote", "add", "helix", str(self.helix)], cwd=path)
        return path

    def repo_object(self, path):
        repo = self.make_repo(path)
        repo.configure_helix_refspecs()
        return repo

    # -- the behaviors that matter ------------------------------------

    def test_pull_fast_forwards_gsa_from_helix(self):
        path = self.clone_and_wire()
        repo = self.repo_object(path)
        self.commit_on_helix("helix change")
        self.assertIsNone(repo.fetch("helix"))
        self.assertIsNone(repo.fetch("origin"))

        rows = {r["branch"]: r for r in repo.compare()}
        self.assertEqual(rows["master"]["state"], sync.GSA_BEHIND)
        self.assertEqual(rows["master"]["gsa_behind"], 1)

        pushed, error = repo.forward_to_gsa(repo.compare())
        self.assertIsNone(error)
        self.assertEqual(pushed, ["master"])

        helix_tip = self.git_helix(["rev-parse", "master"]).strip()
        gsa_tip = self.git_gsa(["rev-parse", "master"]).strip()
        self.assertEqual(helix_tip, gsa_tip)

    def test_pull_creates_branch_that_is_new_on_helix(self):
        path = self.clone_and_wire()
        repo = self.repo_object(path)
        self.git_seed(["checkout", "-q", "-b", "release/1.0"])
        (self.seed / "r").write_text("r\n", encoding="utf-8")
        self.git_seed(["add", "."])
        self.git_seed(["commit", "-qm", "release"])
        self.git_seed(["push", "-q", str(self.helix), "release/1.0"])

        repo.fetch("helix")
        repo.fetch("origin")
        rows = {r["branch"]: r for r in repo.compare()}
        self.assertEqual(rows["release/1.0"]["state"], sync.NEW_ON_HELIX)

        pushed, error = repo.forward_to_gsa(repo.compare())
        self.assertIsNone(error)
        self.assertIn("release/1.0", pushed)
        self.assertIn(
            "refs/heads/release/1.0",
            self.git_gsa(["for-each-ref", "--format=%(refname)", "refs/heads"]),
        )

    def test_divergence_is_reported_and_never_pushed(self):
        path = self.clone_and_wire()
        repo = self.repo_object(path)
        # Both sides move master independently.
        self.commit_on_helix("helix side")
        run(["git", "fetch", "-q", "origin"], cwd=path)
        run(["git", "checkout", "-q", "master"], cwd=path)
        (path / "gsa-only").write_text("g\n", encoding="utf-8")
        run(["git", "add", "."], cwd=path)
        run(["git", "commit", "-qm", "gsa side"], cwd=path)
        run(["git", "push", "-q", "origin", "master"], cwd=path)

        repo.fetch("helix")
        repo.fetch("origin")
        rows = {r["branch"]: r for r in repo.compare()}
        self.assertEqual(rows["master"]["state"], sync.DIVERGED)
        self.assertEqual(rows["master"]["gsa_ahead"], 1)
        self.assertEqual(rows["master"]["gsa_behind"], 1)

        before = self.git_gsa(["rev-parse", "master"]).strip()
        pushed, error = repo.forward_to_gsa(repo.compare())
        self.assertEqual(pushed, [])
        self.assertIsNone(error)
        self.assertEqual(self.git_gsa(["rev-parse", "master"]).strip(), before)

    def test_gsa_only_branch_is_never_deleted(self):
        path = self.clone_and_wire()
        repo = self.repo_object(path)
        run(["git", "checkout", "-q", "-b", "feat/local"], cwd=path)
        (path / "x").write_text("x\n", encoding="utf-8")
        run(["git", "add", "."], cwd=path)
        run(["git", "commit", "-qm", "feature"], cwd=path)
        run(["git", "push", "-q", "origin", "feat/local"], cwd=path)

        self.commit_on_helix("helix change")
        repo.fetch("helix")
        repo.fetch("origin")
        rows = {r["branch"]: r for r in repo.compare()}
        self.assertEqual(rows["feat/local"]["state"], sync.ONLY_ON_GSA)

        repo.forward_to_gsa(repo.compare())
        self.assertIn(
            "refs/heads/feat/local",
            self.git_gsa(["for-each-ref", "--format=%(refname)", "refs/heads"]),
        )

    def test_dirty_worktree_and_checked_out_branch_survive_pull(self):
        path = self.clone_and_wire()
        repo = self.repo_object(path)
        run(["git", "checkout", "-q", "-b", "my/wip"], cwd=path)
        (path / "uncommitted.txt").write_text("scratch\n", encoding="utf-8")
        self.commit_on_helix("helix change")

        repo.fetch("helix")
        repo.fetch("origin")
        repo.forward_to_gsa(repo.compare())

        branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path).strip()
        self.assertEqual(branch, "my/wip")
        self.assertTrue((path / "uncommitted.txt").exists())
        dirty = run(["git", "status", "--porcelain"], cwd=path)
        self.assertIn("uncommitted.txt", dirty)

    def test_push_branch_sends_local_work_to_helix(self):
        path = self.clone_and_wire()
        repo = self.repo_object(path)
        run(["git", "checkout", "-q", "-b", "feat/upstream"], cwd=path)
        (path / "newfile").write_text("content\n", encoding="utf-8")
        run(["git", "add", "."], cwd=path)
        run(["git", "commit", "-qm", "work for upstream"], cwd=path)

        self.assertIsNone(repo.push_branch("feat/upstream", "helix"))
        self.assertIn(
            "refs/heads/feat/upstream",
            self.git_helix(["for-each-ref", "--format=%(refname)", "refs/heads"]),
        )

    def test_push_branch_rejects_unknown_branch(self):
        path = self.clone_and_wire()
        repo = self.repo_object(path)
        error = repo.push_branch("no/such-branch", "helix")
        self.assertIsNotNone(error)
        self.assertIn("no local branch", error)

    def test_rewritten_helix_history_is_refused_not_forced(self):
        path = self.clone_and_wire()
        repo = self.repo_object(path)
        self.commit_on_helix("first")
        repo.fetch("helix")
        repo.fetch("origin")
        repo.forward_to_gsa(repo.compare())
        synced = self.git_gsa(["rev-parse", "master"]).strip()

        # Helix rewrites master: GSA's tip is no longer an ancestor.
        self.git_seed(["reset", "-q", "--hard", "HEAD~1"])
        (self.seed / "f").write_text("rewritten\n", encoding="utf-8")
        self.git_seed(["add", "."])
        self.git_seed(["commit", "-qm", "rewritten"])
        self.git_seed(["push", "-qf", str(self.helix), "master"])

        repo.fetch("helix")
        repo.fetch("origin")
        rows = {r["branch"]: r for r in repo.compare()}
        self.assertEqual(rows["master"]["state"], sync.DIVERGED)
        pushed, _ = repo.forward_to_gsa(repo.compare())
        self.assertEqual(pushed, [])
        self.assertEqual(self.git_gsa(["rev-parse", "master"]).strip(), synced)

    def test_helix_tags_land_outside_refs_tags(self):
        path = self.clone_and_wire()
        repo = self.repo_object(path)
        self.git_seed(["tag", "v1.0"])
        self.git_seed(["push", "-q", str(self.helix), "v1.0"])
        repo.fetch("helix")

        local_tags = run(
            ["git", "for-each-ref", "--format=%(refname)", "refs/tags"], cwd=path
        )
        self.assertNotIn("refs/tags/v1.0", local_tags)
        namespaced = run(
            ["git", "for-each-ref", "--format=%(refname)", sync.HELIX_TAG_NS], cwd=path
        )
        self.assertIn(f"{sync.HELIX_TAG_NS}/v1.0", namespaced)

        tag_rows = {r["tag"]: r for r in repo.compare_tags()}
        self.assertEqual(tag_rows["v1.0"]["state"], sync.NEW_ON_HELIX)
        pushed, error = repo.forward_tags_to_gsa(repo.compare_tags())
        self.assertIsNone(error)
        self.assertEqual(pushed, ["v1.0"])
        self.assertIn(
            "refs/tags/v1.0",
            self.git_gsa(["for-each-ref", "--format=%(refname)", "refs/tags"]),
        )

    def test_ensure_refuses_clone_with_wrong_origin(self):
        path = self.into / "app"
        path.parent.mkdir(parents=True, exist_ok=True)
        other = self.root / "other.git"
        run(["git", "init", "-q", "--bare", str(other)])
        run(["git", "clone", "-q", "--origin", "origin", str(other), str(path)])

        repo = self.make_repo(path)
        problems = repo.ensure()
        self.assertTrue(problems)
        self.assertIn("origin is", problems[0])

    def test_ensure_refuses_wrong_helix_remote(self):
        path = self.clone_and_wire()
        run(["git", "remote", "set-url", "helix", "https://wrong.invalid/x/y.git"], cwd=path)
        repo = self.make_repo(path)

        problems = repo.ensure()
        self.assertTrue(any("remote 'helix' is" in p for p in problems))

    def test_ensure_adds_missing_helix_remote_and_refspecs(self):
        path = self.into / "app"
        path.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "-q", "--origin", "origin", str(self.gsa), str(path)])
        repo = self.make_repo(path)

        self.assertEqual(repo.ensure(), [])
        self.assertEqual(repo.remote_url("helix"), str(self.helix))
        refspecs = run(
            ["git", "config", "--get-all", "remote.helix.fetch"], cwd=path
        )
        self.assertIn("+refs/heads/*:refs/remotes/helix/*", refspecs)
        self.assertIn(f"+refs/tags/*:{sync.HELIX_TAG_NS}/*", refspecs)

    def test_ensure_clones_when_missing(self):
        repo = self.make_repo()
        self.assertEqual(repo.ensure(), [])
        self.assertTrue((self.into / "app" / ".git").is_dir())
        self.assertEqual(repo.remote_url("origin"), str(self.gsa))
        self.assertEqual(repo.remote_url("helix"), str(self.helix))


    def test_push_batching_preserves_slashed_branch_names(self):
        path = self.clone_and_wire()
        repo = self.repo_object(path)
        self.addCleanup(setattr, sync, "PUSH_BATCH", sync.PUSH_BATCH)
        sync.PUSH_BATCH = 2
        for index in range(5):
            name = f"team/feature-{index}"
            self.git_seed(["checkout", "-q", "-b", name, "master"])
            (self.seed / f"file{index}").write_text("x\n", encoding="utf-8")
            self.git_seed(["add", "."])
            self.git_seed(["commit", "-qm", name])
            self.git_seed(["push", "-q", str(self.helix), name])

        repo.fetch("helix")
        repo.fetch("origin")
        pushed, error = repo.forward_to_gsa(repo.compare())
        self.assertIsNone(error)
        refs = self.git_gsa(["for-each-ref", "--format=%(refname)", "refs/heads"])
        for index in range(5):
            self.assertIn(f"team/feature-{index}", pushed)
            self.assertIn(f"refs/heads/team/feature-{index}", refs)


class CommandLineTests(unittest.TestCase):
    """Drive main() end to end. insteadOf rules rewrite the public URLs to
    local bare repositories, so the real code paths run with no network."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sync-cli-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.into = self.root / "clones"
        self.helix = self.root / "helix.git"
        self.gsa = self.root / "gsa.git"

        run(["git", "init", "-q", "--bare", str(self.helix)])
        self.seed = self.root / "seed"
        run(["git", "init", "-q", str(self.seed)])
        run(["git", "config", "user.email", "t@example.invalid"], cwd=self.seed)
        run(["git", "config", "user.name", "Test"], cwd=self.seed)
        (self.seed / "f").write_text("base\n", encoding="utf-8")
        run(["git", "add", "."], cwd=self.seed)
        run(["git", "commit", "-qm", "base"], cwd=self.seed)
        run(["git", "branch", "-M", "master"], cwd=self.seed)
        run(["git", "push", "-q", str(self.helix), "master"], cwd=self.seed)
        run(["git", "clone", "-q", "--mirror", str(self.helix), str(self.gsa)])

        (self.home / ".gitconfig").write_text(
            f'[url "{self.helix}"]\n'
            "\tinsteadOf = https://helix.invalid/ORG/app.git\n"
            f'[url "{self.gsa}"]\n'
            "\tinsteadOf = https://github.invalid/GSA/app.git\n",
            encoding="utf-8",
        )
        self.previous_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        self.addCleanup(self.restore_home)

    def restore_home(self):
        if self.previous_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.previous_home

    def git_in(self, path, args):
        return run(["git", *args], cwd=path)

    def invoke_streams(self, *extra):
        args = [
            extra[0],
            "--into",
            str(self.into),
            "--source-host",
            "helix.invalid",
            "--source-org",
            "ORG",
            "--dest-host",
            "github.invalid",
            "--dest-org",
            "GSA",
            "app",
            *extra[1:],
        ]
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = sync.main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def invoke(self, *extra):
        code, stdout, stderr = self.invoke_streams(*extra)
        return code, stdout + stderr

    def helix_tip(self, branch="master"):
        return run(["git", f"--git-dir={self.helix}", "rev-parse", branch]).strip()

    def gsa_tip(self, branch="master"):
        return run(["git", f"--git-dir={self.gsa}", "rev-parse", branch]).strip()

    def commit_upstream(self, message):
        existing = (self.seed / "f").read_text(encoding="utf-8")
        (self.seed / "f").write_text(existing + message + "\n", encoding="utf-8")
        run(["git", "commit", "-qam", message], cwd=self.seed)
        run(["git", "push", "-q", str(self.helix), "master"], cwd=self.seed)

    def test_status_clones_and_reports_clean(self):
        code, output = self.invoke("status")
        self.assertEqual(code, 0, output)
        self.assertIn("OK    app", output)
        self.assertTrue((self.into / "app" / ".git").is_dir())

    def test_pull_advances_gsa_then_reruns_clean(self):
        self.invoke("status")
        self.commit_upstream("upstream change")

        code, output = self.invoke("pull")
        self.assertEqual(code, 0, output)
        self.assertIn("SYNCD app", output)
        self.assertEqual(self.helix_tip(), self.gsa_tip())

        # A second pull with nothing new must not claim it synced anything.
        code, output = self.invoke("pull")
        self.assertEqual(code, 0, output)
        self.assertIn("nothing to fast-forward", output)
        self.assertNotIn("SYNCD", output)

    def test_pull_exits_nonzero_on_divergence_and_pushes_nothing(self):
        self.invoke("status")
        path = self.into / "app"
        self.git_in(path, ["config", "user.email", "t@example.invalid"])
        self.git_in(path, ["config", "user.name", "Test"])
        self.commit_upstream("helix side")
        (path / "gsa-only").write_text("g\n", encoding="utf-8")
        self.git_in(path, ["add", "."])
        self.git_in(path, ["commit", "-qm", "gsa side"])
        self.git_in(path, ["push", "-q", "origin", "master"])

        before = self.gsa_tip()
        code, output = self.invoke("pull")
        self.assertEqual(code, 1, output)
        self.assertIn("DIVER app", output)
        self.assertIn("DIVERGED", output)
        self.assertEqual(before, self.gsa_tip())

    def test_dry_run_changes_nothing(self):
        self.invoke("status")
        self.commit_upstream("upstream change")
        before = self.gsa_tip()

        code, output = self.invoke("pull", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn("would push", output)
        self.assertEqual(before, self.gsa_tip())

    def test_push_sends_local_branch_upstream(self):
        self.invoke("status")
        path = self.into / "app"
        self.git_in(path, ["config", "user.email", "t@example.invalid"])
        self.git_in(path, ["config", "user.name", "Test"])
        self.git_in(path, ["checkout", "-q", "-b", "feat/x"])
        (path / "new").write_text("n\n", encoding="utf-8")
        self.git_in(path, ["add", "."])
        self.git_in(path, ["commit", "-qm", "feature"])

        code, output = self.invoke("push", "--branch", "feat/x")
        self.assertEqual(code, 0, output)
        refs = run(
            [
                "git",
                f"--git-dir={self.helix}",
                "for-each-ref",
                "--format=%(refname)",
                "refs/heads",
            ]
        )
        self.assertIn("refs/heads/feat/x", refs)

    def test_pull_request_uses_advertised_main_branch(self):
        run(["git", "branch", "-M", "main"], cwd=self.seed)
        run(["git", "push", "-q", str(self.helix), "main"], cwd=self.seed)
        run(["git", f"--git-dir={self.helix}", "symbolic-ref", "HEAD", "refs/heads/main"])
        path = self.root / "pr-worktree"
        path.mkdir()
        run(["git", "init", "-q"], cwd=path)
        run(["git", "remote", "add", "helix", str(self.helix)], cwd=path)
        class StubConfig:
            protocol = "https"
            source_host = "helix.invalid"
            source_org = "ORG"
            dest_host = "github.invalid"
            dest_org = "GSA"
            dest_prefix = ""
            into = self.into

        repo = sync.Repo(path, "ORG", "app", "app", StubConfig())
        messages = []
        with patch.object(sync, "log", side_effect=messages.append):
            error = sync.open_pull_request(repo, "feat/example", "", "", "", True)
        self.assertIsNone(error)
        self.assertTrue(any("feat/example -> main" in message for message in messages))

    def test_pull_request_requires_an_advertised_default_branch(self):
        class StubConfig:
            protocol = "https"
            source_host = "helix.invalid"
            source_org = "ORG"
            dest_host = "github.invalid"
            dest_org = "GSA"
            dest_prefix = ""
            into = self.into

        repo = sync.Repo(self.root, "ORG", "app", "app", StubConfig())
        with patch.object(sync, "git", return_value=(0, "abc123\\tHEAD")):
            error = sync.open_pull_request(repo, "feat/example", "", "", "", True)
        self.assertIn("cannot determine Helix default branch", error)
        self.assertIn("pass --base explicitly", error)

    def test_json_output_is_parseable(self):
        code, stdout, stderr = self.invoke_streams("status", "--json")
        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload[0]["repo"], "app")
        self.assertEqual(payload[0]["problems"], [])
        self.assertIn("Summary", stderr)

    def test_json_output_remains_parseable_on_divergence(self):
        self.invoke("status")
        path = self.into / "app"
        self.git_in(path, ["config", "user.email", "t@example.invalid"])
        self.git_in(path, ["config", "user.name", "Test"])
        self.commit_upstream("helix side")
        (path / "gsa-only").write_text("g\\n", encoding="utf-8")
        self.git_in(path, ["add", "."])
        self.git_in(path, ["commit", "-qm", "gsa side"])
        self.git_in(path, ["push", "-q", "origin", "master"])

        code, stdout, stderr = self.invoke_streams("pull", "--json")
        self.assertEqual(code, 1)
        payload = json.loads(stdout)
        self.assertTrue(payload[0]["needs_attention"])
        self.assertIn("diverged and were left untouched", stderr)

    def test_push_json_output_is_standalone(self):
        self.invoke("status")
        path = self.into / "app"
        self.git_in(path, ["config", "user.email", "t@example.invalid"])
        self.git_in(path, ["config", "user.name", "Test"])
        self.git_in(path, ["checkout", "-q", "-b", "feat/json"])
        (path / "new").write_text("content\\n", encoding="utf-8")
        self.git_in(path, ["add", "."])
        self.git_in(path, ["commit", "-qm", "feature"])

        code, stdout, stderr = self.invoke_streams("push", "--branch", "feat/json", "--json")
        self.assertEqual(code, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload[0]["pushed"], ["feat/json"])

    def test_unfetched_helix_is_a_failure_not_a_clean_run(self):
        # A clone whose Helix side was never fetched must never be reported as
        # in sync: that silent no-op is the failure mode of the old script.
        code, output = self.invoke("status", "--no-fetch", "--skip-preflight")
        self.assertEqual(code, 1, output)
        self.assertIn("no Helix refs", output)
        self.assertIn("FAIL  app", output)


class LockTests(unittest.TestCase):
    def test_second_lock_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            into = Path(directory) / "clones"
            first = sync.lock(into)
            self.addCleanup(first.close)
            with self.assertRaises(SystemExit) as caught:
                sync.lock(into)
            self.assertEqual(caught.exception.code, 2)


class PreflightTests(unittest.TestCase):
    def make_repo(self, url):
        class StubConfig:
            source_host = "helix.invalid"
            source_org = "ORG"
            dest_host = "github.invalid"
            dest_org = "GSA"
            dest_prefix = ""
            protocol = "https"
            into = Path("/tmp")

        repo = sync.Repo(Path("/tmp/unused"), "ORG", "app", "app", StubConfig())
        repo.helix_url = url
        return repo

    def test_unresolvable_host_reports_vpn(self):
        repo = self.make_repo("https://helix.invalid/ORG/app.git")
        problem = sync.preflight_helix(repo, timeout=20)
        self.assertIsNotNone(problem)
        self.assertIn("VPN", problem)

    def test_reachable_local_repo_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            bare = Path(directory) / "r.git"
            run(["git", "init", "-q", "--bare", str(bare)])
            repo = self.make_repo(str(bare))
            self.assertIsNone(sync.preflight_helix(repo, timeout=20))

    def test_timeout_is_bounded_and_explained(self):
        # A hanging probe must return a message, not block an unattended run.
        repo = self.make_repo("https://10.255.255.1/ORG/app.git")
        problem = sync.preflight_helix(repo, timeout=2)
        self.assertIsNotNone(problem)


if __name__ == "__main__":
    unittest.main()
