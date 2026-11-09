#!/usr/bin/env python3
"""Tests for upgrade.py: pins, submodule advancement, snapshots, rollback and the pipeline."""

import contextlib
from contextlib import closing
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import upgrade

GIT_ENV = {"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid"}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, text=True,
                          capture_output=True).stdout.strip()


def commit(repo, name, text, message):
    (repo / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "--quiet", "-m", message)
    return git(repo, "rev-parse", "HEAD")


class TempRoot(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        env = patch.dict(os.environ, GIT_ENV)
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.temp.cleanup)

    def upstream_and_clone(self, name="kata"):
        upstream = self.root / f"{name}-upstream"
        upstream.mkdir()
        git(upstream, "init", "--quiet", "--initial-branch=main")
        commit(upstream, "base.txt", "base\n", "base")
        clone = self.root / "checkout" / name
        clone.parent.mkdir(exist_ok=True)
        subprocess.run(["git", "clone", "--quiet", str(upstream), str(clone)], check=True)
        return upstream, clone


class TrackedPinTests(unittest.TestCase):
    def test_every_tracked_pin_mention_agrees(self):
        pins = upgrade.read_pins()
        self.assertEqual(set(pins), {"pi", "pi-subagents"})


class PinTests(TempRoot):
    def setUp(self):
        super().setUp()
        self.sources = {"pi": (("a.py", rf'^PI_VERSION = "{upgrade.SEMVER}"$'),
                               ("b.md", rf"pi-coding-agent@{upgrade.SEMVER}")),
                        "pi-subagents": (("a.py", rf'"npm:pi-subagents@{upgrade.SEMVER}"'),)}
        (self.root / "a.py").write_text('PI_VERSION = "1.4.0"\nX = "npm:pi-subagents@0.83.0"\n')
        (self.root / "b.md").write_text("npm i pi-coding-agent@1.4.0; again pi-coding-agent@1.4.0\n")
        patcher = patch.object(upgrade, "PIN_SOURCES", self.sources)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_write_pin_updates_every_mention_and_nothing_else(self):
        upgrade.write_pin("pi", "1.5.0", self.root)
        self.assertEqual(upgrade.read_pins(self.root), {"pi": "1.5.0", "pi-subagents": "0.83.0"})
        self.assertEqual((self.root / "b.md").read_text(),
                         "npm i pi-coding-agent@1.5.0; again pi-coding-agent@1.5.0\n")

    def test_partial_bump_is_reported(self):
        (self.root / "b.md").write_text("pi-coding-agent@1.5.0\n")
        with self.assertRaisesRegex(upgrade.UpgradeError, "inconsistent pi pins"):
            upgrade.read_pins(self.root)

    def test_missing_mention_is_reported(self):
        (self.root / "b.md").write_text("no pin here\n")
        with self.assertRaisesRegex(upgrade.UpgradeError, "no longer mentions"):
            upgrade.read_pins(self.root)

    def test_non_semver_version_is_rejected(self):
        with self.assertRaisesRegex(upgrade.UpgradeError, "semver"):
            upgrade.write_pin("pi", "latest; rm -rf", self.root)


class SubmoduleTests(TempRoot):
    def test_fast_forwards_without_carried_commits(self):
        upstream, clone = self.upstream_and_clone()
        new = commit(upstream, "new.txt", "new\n", "upstream change")
        result = upgrade.advance_submodule(clone)
        self.assertEqual(result["to"], new)
        self.assertEqual(result["carried"], [])
        self.assertTrue(result["published"])

    def test_replays_carried_commit_onto_upstream(self):
        upstream, clone = self.upstream_and_clone()
        carried = commit(clone, "local.txt", "patch\n", "carried patch")
        new = commit(upstream, "new.txt", "new\n", "upstream change")
        result = upgrade.advance_submodule(clone)
        self.assertEqual(result["carried"], [carried])
        self.assertEqual(git(clone, "rev-parse", "HEAD~1"), new)
        self.assertEqual((clone / "local.txt").read_text(), "patch\n")
        self.assertFalse(result["published"])

    def test_drops_carried_commit_that_upstream_merged(self):
        upstream, clone = self.upstream_and_clone()
        commit(clone, "local.txt", "patch\n", "carried patch")
        new = commit(upstream, "local.txt", "patch\n", "upstream took the patch")
        result = upgrade.advance_submodule(clone)
        self.assertEqual(result["to"], new)
        self.assertEqual(result["carried"], [])

    def test_conflicting_carried_commit_restores_original(self):
        upstream, clone = self.upstream_and_clone()
        original = commit(clone, "base.txt", "local\n", "carried edit")
        commit(upstream, "base.txt", "upstream\n", "conflicting edit")
        with self.assertRaisesRegex(upgrade.UpgradeError, "conflicts"):
            upgrade.advance_submodule(clone)
        self.assertEqual(git(clone, "rev-parse", "HEAD"), original)
        self.assertEqual(git(clone, "status", "--porcelain"), "")

    def test_dirty_submodule_is_refused(self):
        _, clone = self.upstream_and_clone()
        (clone / "base.txt").write_text("edited\n")
        with self.assertRaisesRegex(upgrade.UpgradeError, "uncommitted"):
            upgrade.advance_submodule(clone)


class LiveRollbackTests(TempRoot):
    """Snapshot a fake environment, simulate an upgrade, then roll it back."""

    def setUp(self):
        super().setUp()
        self.upstream, self.repo = self.upstream_and_clone("kata")
        checkout = self.repo.parent
        self.state = checkout / ".local/environment"
        (self.state / "kata").mkdir(parents=True, mode=0o700)
        self.state.chmod(0o700)
        env_path = self.state / "environment.json"
        env_path.write_text(json.dumps({"pi_executable": "/fake/pi", "forge_binary":
                                        str(checkout / ".local/forge-local-kata/kenn-forge")}))
        env_path.chmod(0o600)
        self.config = self.state / "kata/config.toml"
        self.config.write_text("listen = 'old'\n")
        self.db = self.state / "kata/kata.db"
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("create table issues (title text)")
            db.execute("insert into issues values ('before')")
        self.binary = self.repo / "kata"
        self.binary.write_text("old binary\n")
        (checkout / "pins.txt").write_text('PI = "1.4.0"\n')
        self.calls = []
        self.pi = {"version": "1.4.0"}
        for name, value in {
            "ROOT": checkout, "STATE": self.state, "UPGRADE_DIR": checkout / ".local/upgrade",
            "SUBMODULES": ("kata",), "DATABASES": ("kata/kata.db",), "CONFIGS": ("kata/config.toml",),
            "PIN_SOURCES": {"pi": (("pins.txt", rf'PI = "{upgrade.SEMVER}"'),)},
            "binaries": lambda config: [self.binary],
            "pi_version": lambda executable: self.pi["version"],
            "systemctl": lambda action, unit: self.calls.append((action, unit)),
            "install_pi": lambda version, executable: self.calls.append(("install_pi", version)),
            "sh": lambda command, **kw: self.calls.append(("sh", command[-1])) or "",
            "gate": lambda timeout=180: self.calls.append(("gate",)),
        }.items():
            patcher = patch.object(upgrade, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def simulate_upgrade(self):
        commit(self.upstream, "new.txt", "new\n", "upstream change")
        upgrade.advance_submodule(self.repo)
        upgrade.write_pin("pi", "1.5.0")
        self.pi["version"] = "1.5.0"
        self.binary.write_text("new binary\n")
        self.config.write_text("listen = 'new'\n")
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("pragma journal_mode=wal")
            db.execute("create table migrated (x)")
            db.execute("insert into issues values ('after')")

    def snapshot(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return upgrade.snapshot("test")

    def rollback(self, manifest, services):
        with contextlib.redirect_stdout(io.StringIO()):
            upgrade.rollback(manifest, services=services)

    def rows(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            tables = {row[0] for row in db.execute("select name from sqlite_master")}
            return tables, [row[0] for row in db.execute("select title from issues")]

    def test_live_rollback_restores_everything_and_keeps_the_failed_state(self):
        original = git(self.repo, "rev-parse", "HEAD")
        manifest = self.snapshot()
        self.simulate_upgrade()
        self.rollback(manifest, services=True)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), original)
        self.assertEqual(upgrade.read_pins(), {"pi": "1.4.0"})
        self.assertEqual(self.binary.read_text(), "old binary\n")
        self.assertEqual(self.config.read_text(), "listen = 'old'\n")
        self.assertEqual(self.rows(), ({"issues"}, ["before"]))
        self.assertFalse(Path(f"{self.db}-wal").exists())
        kept = next((upgrade.UPGRADE_DIR / "snapshots" / manifest["id"]).glob("pre-rollback-*"))
        with closing(sqlite3.connect(kept / self.db.relative_to("/"))) as db, db:
            self.assertEqual([r[0] for r in db.execute("select title from issues")], ["before", "after"])
        units = [upgrade.UNITS[name] for name in upgrade.SERVICES]
        self.assertEqual(self.calls, [
            *(("stop", unit) for unit in reversed(units)),
            ("install_pi", "1.4.0"), ("sh", "install-pi-extensions"),
            *(("start", unit) for unit in units), ("gate",),
        ])

    def test_sources_only_rollback_leaves_services_and_data_alone(self):
        manifest = self.snapshot()
        self.simulate_upgrade()
        self.rollback(manifest, services=False)
        self.assertEqual(self.binary.read_text(), "old binary\n")
        self.assertEqual(upgrade.read_pins(), {"pi": "1.4.0"})
        self.assertEqual(self.rows()[1], ["before", "after"])
        self.assertEqual(self.config.read_text(), "listen = 'new'\n")
        self.assertEqual(self.calls, [])

    def test_snapshots_are_pruned_and_latest_is_default(self):
        ids = [self.snapshot()["id"] for _ in range(upgrade.KEEP_SNAPSHOTS + 2)]
        self.assertEqual([m["id"] for m in upgrade.snapshots()], ids[-upgrade.KEEP_SNAPSHOTS:])
        self.assertEqual(upgrade.load_snapshot()["id"], ids[-1])
        with self.assertRaisesRegex(upgrade.UpgradeError, "unknown snapshot"):
            upgrade.load_snapshot("missing")


class PipelineTests(unittest.TestCase):
    def run_pipeline(self, failing=None):
        steps = MagicMock()
        steps.snapshot.return_value = {"id": "snap"}
        if failing:
            getattr(steps, failing).side_effect = upgrade.UpgradeError(f"{failing} broke")
        with patch.multiple(upgrade, snapshot=steps.snapshot, apply=steps.apply, verify=steps.verify,
                            cutover=steps.cutover, rollback=steps.rollback), \
                contextlib.redirect_stdout(io.StringIO()):
            if failing:
                with self.assertRaisesRegex(upgrade.UpgradeError, f"{failing} broke"):
                    upgrade.run()
            else:
                upgrade.run()
        return steps

    def test_success_does_not_roll_back(self):
        self.assertFalse(self.run_pipeline().rollback.called)

    def test_failure_before_cutover_restores_sources_only(self):
        for step in ("apply", "verify"):
            with self.subTest(step=step):
                steps = self.run_pipeline(step)
                steps.rollback.assert_called_once_with({"id": "snap"}, services=False, gate_timeout=180)
                self.assertFalse(steps.cutover.called)

    def test_failed_cutover_rolls_back_live_services(self):
        steps = self.run_pipeline("cutover")
        steps.rollback.assert_called_once_with({"id": "snap"}, services=True, gate_timeout=180)


class GateTests(unittest.TestCase):
    def test_gate_rejects_a_service_running_another_revision(self):
        status = {f"{name}_service": {"version": "v1.0.0-1-gaaaaaaa"} for name in upgrade.SERVICES}
        with patch.object(upgrade, "sh", side_effect=lambda command, **kw:
                          json.dumps(status) if command[-1] == "status" else ""), \
                patch.object(upgrade, "git", return_value="bbbbbbbbbb"), \
                self.assertRaisesRegex(upgrade.UpgradeError, "expected bbbbbbbbb"):
            upgrade.gate(timeout=0)

    def test_gate_reports_failed_acceptance(self):
        def sh(command, **kw):
            raise upgrade.UpgradeError("accept exited 1")
        with patch.object(upgrade, "sh", side_effect=sh), \
                self.assertRaisesRegex(upgrade.UpgradeError, "accept exited 1"):
            upgrade.gate(timeout=0)


class InstallPiTests(unittest.TestCase):
    def test_global_and_local_npm_prefixes(self):
        for executable, expected in (
            ("/n/v26/lib/node_modules/@earendil-works/pi-coding-agent/dist/cli.js",
             ["install", "--global", "--prefix", "/n/v26"]),
            ("/h/.local/engi-pi/node_modules/@earendil-works/pi-coding-agent/dist/cli.js",
             ["install", "--prefix", "/h/.local/engi-pi"]),
        ):
            with self.subTest(executable=executable), patch.object(upgrade, "sh") as sh:
                upgrade.install_pi("1.5.0", executable)
                command = [str(part) for part in sh.call_args.args[0]]
                self.assertEqual(command[1:1 + len(expected)], expected)
                self.assertEqual(command[-1], "@earendil-works/pi-coding-agent@1.5.0")

    def test_candidate_pi_is_isolated_and_version_checked(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(upgrade, "UPGRADE_DIR", Path(tmp)), \
                patch.object(upgrade, "sh") as sh, \
                patch.object(upgrade, "pi_version", return_value="1.5.0"):
            bin_dir = upgrade.candidate_pi("1.5.0")
            self.assertEqual(bin_dir, Path(tmp) / "pi-1.5.0/node_modules/.bin")
            command = [str(part) for part in sh.call_args.args[0]]
            self.assertNotIn("--global", command)
            self.assertEqual(command[-1], "@earendil-works/pi-coding-agent@1.5.0")
            bin_dir.mkdir(parents=True)
            (bin_dir / "pi").touch()
            sh.reset_mock()
            upgrade.candidate_pi("1.5.0")
            sh.assert_not_called()
            with self.assertRaisesRegex(upgrade.UpgradeError, "not 1.6.0"):
                upgrade.candidate_pi("1.6.0")

    def test_unknown_layout_is_refused(self):
        with self.assertRaisesRegex(upgrade.UpgradeError, "npm prefix"):
            upgrade.install_pi("1.5.0", "/usr/bin/pi")


if __name__ == "__main__":
    unittest.main()
