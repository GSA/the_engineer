import json
from pathlib import Path
import sqlite3
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import backup_workspace


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="backup-test-")
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        self.source = self.parent / "workspace"
        self.source.mkdir()
        self.run_git("init", "-q")
        self.run_git("config", "user.name", "Backup Fixture")
        self.run_git("config", "user.email", "backup@example.invalid")
        (self.source / ".gitignore").write_text(".local/\nnode_modules/\n")
        (self.source / "source.txt").write_text("committed source\n")
        self.run_git("add", ".")
        self.run_git("commit", "-qm", "fixture")
        self.destination = self.parent / "OneDrive" / "EngiPlatformBackups"
        self.destination.parent.mkdir()

    def run_git(self, *arguments):
        return subprocess.run(
            ["git", "-C", str(self.source), *arguments],
            check=True, capture_output=True, text=True,
        )

    def write(self, name, contents):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        return path

    def unpack(self, result):
        restore = self.parent / "restored"
        backup_workspace.extract_snapshot(Path(result["archive"]), restore)
        return restore / "workspace", json.loads((restore / "backup-manifest.json").read_text())

    def test_copy_preserves_history_dirty_and_sensitive_state_without_dependencies(self):
        self.write("source.txt", "uncommitted source\n")
        self.write("new.txt", "untracked source\n")
        self.write(".local/environment/sensitive-document.txt", "synthetic sensitive asset\n")
        self.write(".local/environment/secrets/usai-api-key", "synthetic-key-not-a-credential\n")
        (self.source / ".local/environment/secrets").chmod(0o700)
        (self.source / ".local/environment/secrets/usai-api-key").chmod(0o600)
        self.write("node_modules/large.bin", "reinstallable")
        self.write(".local/cache/generated", "reinstallable")
        self.write(".local/tools/generated", "reinstallable")
        self.write(".local/environment/pi/npm/package-lock.json", "{}")
        self.write(".local/environment/pi/npm/node_modules/large.bin", "reinstallable")
        self.write("internal/web/dist/stub.html", "tracked stub")
        self.run_git("add", "internal/web/dist/stub.html")
        self.run_git("commit", "-qm", "tracked stub")
        self.write("internal/web/dist/bundle.js", "rebuildable")
        (self.source / "source-link").symlink_to("source.txt")
        result = backup_workspace.create_backup(self.source, self.destination)
        restored, manifest = self.unpack(result)
        self.assertTrue(result["local_restore_verified"])
        self.assertFalse(result["cloud_sync_verified"])
        self.assertEqual((restored / "source.txt").read_text(), "uncommitted source\n")
        self.assertTrue((restored / ".git/objects").is_dir())
        self.assertTrue((restored / ".local/environment/secrets/usai-api-key").is_file())
        self.assertEqual((restored / ".local/environment/secrets").stat().st_mode & 0o777, 0o700)
        self.assertEqual((restored / ".local/environment/secrets/usai-api-key").stat().st_mode & 0o777, 0o600)
        self.assertTrue((restored / "internal/web/dist/stub.html").is_file())
        self.assertTrue((restored / ".local/environment/pi/npm/package-lock.json").is_file())
        self.assertFalse((restored / "node_modules").exists())
        self.assertFalse((restored / ".local/cache").exists())
        self.assertFalse((restored / "internal/web/dist/bundle.js").exists())
        self.assertEqual(
            backup_workspace.digest(Path(result["archive"])), result["sha256"],
        )
        self.assertIn("new.txt", manifest["files"])

    def test_online_sqlite_snapshot_includes_uncheckpointed_wal_rows(self):
        database = self.source / ".local/environment/kata/kata.db"
        database.parent.mkdir(parents=True)
        with closing(sqlite3.connect(database)) as writer:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("PRAGMA wal_autocheckpoint=0")
            writer.execute("CREATE TABLE tasks (title TEXT)")
            writer.execute("INSERT INTO tasks VALUES ('durable task')")
            writer.commit()
            self.assertTrue(Path(str(database) + "-wal").is_file())
            result = backup_workspace.create_backup(self.source, self.destination)
        restored, manifest = self.unpack(result)
        saved = restored / database.relative_to(self.source)
        with closing(sqlite3.connect(saved)) as reader:
            self.assertEqual(reader.execute("SELECT title FROM tasks").fetchall(), [("durable task",)])
        self.assertEqual(result["sqlite_snapshots"], 1)
        self.assertFalse(Path(str(saved) + "-wal").exists())
        self.assertEqual(manifest["databases"], [database.relative_to(self.source).as_posix()])

    def test_submodule_source_and_history_restore_without_network(self):
        upstream = self.parent / "upstream"
        subprocess.run(["git", "init", "-q", str(upstream)], check=True)
        subprocess.run(["git", "-C", str(upstream), "config", "user.name", "Fixture"], check=True)
        subprocess.run(["git", "-C", str(upstream), "config", "user.email", "fixture@example.invalid"], check=True)
        (upstream / "asset").write_text("upstream source")
        subprocess.run(["git", "-C", str(upstream), "add", "."], check=True)
        subprocess.run(["git", "-C", str(upstream), "commit", "-qm", "upstream"], check=True)
        self.run_git("-c", "protocol.file.allow=always", "submodule", "add", str(upstream), "component")
        self.run_git("commit", "-qm", "add component")
        result = backup_workspace.create_backup(self.source, self.destination)
        restored, manifest = self.unpack(result)
        self.assertTrue((restored / ".git/modules/component/objects").is_dir())
        self.assertEqual((restored / "component/asset").read_text(), "upstream source")
        self.assertIn("component", manifest["submodules"])

    def test_external_symlink_aborts_before_host_copy(self):
        (self.source / "external").symlink_to(self.parent / "outside")
        with self.assertRaisesRegex(RuntimeError, "scope decision"):
            backup_workspace.create_backup(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_destination_inside_workspace_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            backup_workspace.create_backup(self.source, self.source / "backups")

    def test_runtime_socket_is_recorded_as_nonrestorable_not_copied(self):
        path = self.source / ".local/environment/runtime/daemon.sock"
        path.parent.mkdir(parents=True)
        with socket.socket(socket.AF_UNIX) as daemon:
            daemon.bind(str(path))
            result = backup_workspace.create_backup(self.source, self.destination)
        restored, manifest = self.unpack(result)
        self.assertFalse((restored / path.relative_to(self.source)).exists())
        self.assertIn(
            {"path": path.relative_to(self.source).as_posix(), "reason": "regenerated runtime socket"},
            manifest["omitted"],
        )

    def test_failed_restore_check_never_publishes_archive(self):
        with patch.object(backup_workspace, "verify_restore", side_effect=RuntimeError("failed restore")):
            with self.assertRaisesRegex(RuntimeError, "failed restore"):
                backup_workspace.create_backup(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_failed_host_checksum_removes_only_the_new_copy(self):
        real_digest = backup_workspace.digest

        def digest(path):
            if path.parent == self.destination:
                return "incorrect"
            return real_digest(path)

        with patch.object(backup_workspace, "digest", side_effect=digest):
            with self.assertRaisesRegex(RuntimeError, "Host archive checksum"):
                backup_workspace.create_backup(self.source, self.destination)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_repeated_backups_do_not_overwrite_prior_archive(self):
        first = backup_workspace.create_backup(self.source, self.destination)
        second = backup_workspace.create_backup(self.source, self.destination)
        self.assertNotEqual(first["archive"], second["archive"])
        self.assertTrue(Path(first["archive"]).is_file())
        self.assertTrue(Path(second["archive"]).is_file())


if __name__ == "__main__":
    unittest.main()
from contextlib import closing
