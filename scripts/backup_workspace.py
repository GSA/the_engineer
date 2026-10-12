#!/usr/bin/env python3
"""Create and restore-check a private workspace archive before copying it to OneDrive."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import tarfile
import tempfile
import time
import uuid


ROOT = Path(__file__).resolve().parent.parent
DEPENDENCY_NAMES = {
    "node_modules", "__pycache__", ".venv", ".npm", ".cache",
    ".gocache", ".gomodcache", ".gopath", "dist",
}
GENERATED_PATHS = (
    ".local/cache", ".local/downloads", ".local/tools", ".local/builds",
    ".local/include", ".local/forge-local-kata/kenn-forge",
    ".local/forge-local-kata/kenn-forge-github-app", ".local/environment/tmp",
    ".local/environment/pi/tmp", "agentsview/agentsview",
    "agentsview/.sqlite-include", "agentsview/frontend/src/lib/paraglide",
    "agentsview/frontend/project.inlang/cache", "kata/kata", "roborev/bin",
    "forge/kenn-forge",
)


def git(root, *arguments):
    environment = os.environ.copy()
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null")
    result = subprocess.run(
        ["git", "-C", str(root), *arguments], env=environment,
        capture_output=True, check=True, timeout=120,
    )
    return result.stdout


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def excluded(relative, tracked, tracked_parents, source):
    name = relative.as_posix()
    if ".git" in relative.parts or name in tracked or name in tracked_parents:
        return False
    return (
        bool(DEPENDENCY_NAMES.intersection(relative.parts))
        or ((source / relative).is_dir() and (source / relative / "pyvenv.cfg").is_file())
        or any(name == prefix or name.startswith(prefix + "/") for prefix in GENERATED_PATHS)
    )


def is_database(path):
    if not path.is_file() or path.is_symlink():
        return False
    with path.open("rb") as stream:
        return stream.read(16) == b"SQLite format 3\0"


def snapshot_database(source, destination):
    started = time.monotonic()

    def progress(status, remaining, total):
        if time.monotonic() - started > 120:
            raise TimeoutError("SQLite snapshot exceeded 120 seconds")

    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as reader:
        with closing(sqlite3.connect(destination)) as writer:
            reader.backup(writer, pages=256, progress=progress)
            if writer.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise RuntimeError(f"SQLite integrity check failed: {source.name}")
            writer.execute("PRAGMA journal_mode=DELETE")
    shutil.copystat(source, destination)


def snapshot_files(source, target, tracked, sqlite_paths=None):
    parents = {parent.as_posix() for name in tracked for parent in Path(name).parents}
    inventory = {}
    omissions = []
    databases = []

    def copy(relative):
        path = source / relative
        destination = target / relative
        if excluded(relative, tracked, parents, source):
            omissions.append({"path": relative.as_posix(), "reason": "reinstallable/generated"})
            return
        info = path.lstat()
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISLNK(info.st_mode):
            link = os.readlink(path)
            resolved = (path.parent / link).resolve()
            if os.path.isabs(link) or not resolved.is_relative_to(source):
                raise RuntimeError(f"External symlink requires a scope decision: {relative}")
            destination.symlink_to(link)
            inventory[relative.as_posix()] = {"kind": "symlink", "target": link}
        elif stat.S_ISDIR(info.st_mode):
            destination.mkdir(mode=0o700)
            for child in sorted(path.iterdir()):
                copy(child.relative_to(source))
            shutil.copystat(path, destination)
            inventory[relative.as_posix()] = {"kind": "directory", "mode": mode}
        elif stat.S_ISREG(info.st_mode):
            for suffix in ("-wal", "-shm", "-journal"):
                if not path.name.endswith(suffix):
                    continue
                base = path.with_name(path.name[:-len(suffix)])
                if ((sqlite_paths is None or base.relative_to(source).as_posix() in sqlite_paths)
                        and is_database(base)):
                    omissions.append({"path": relative.as_posix(), "reason": "SQLite snapshot sidecar"})
                    return
            if (sqlite_paths is None or relative.as_posix() in sqlite_paths) and is_database(path):
                snapshot_database(path, destination)
                databases.append(relative.as_posix())
            else:
                shutil.copy2(path, destination)
                after = path.stat()
                if (info.st_size, info.st_mtime_ns, info.st_ino) != (
                        after.st_size, after.st_mtime_ns, after.st_ino):
                    raise RuntimeError(f"File changed during snapshot; retry: {relative}")
            inventory[relative.as_posix()] = {
                "kind": "file", "mode": mode, "bytes": destination.stat().st_size,
                "sha256": digest(destination),
            }
        elif stat.S_ISSOCK(info.st_mode):
            omissions.append({"path": relative.as_posix(), "reason": "regenerated runtime socket"})
        else:
            raise RuntimeError(f"Special file requires a scope decision: {relative}")

    target.mkdir(mode=0o700)
    for child in sorted(source.iterdir()):
        copy(child.relative_to(source))
    return inventory, omissions, databases


def extract_snapshot(archive, destination):
    def preserve_modes(member, path):
        filtered = tarfile.data_filter(member, path)
        return filtered.replace(mode=member.mode)

    with tarfile.open(archive, "r:gz") as saved:
        saved.extractall(destination, filter=preserve_modes)


def verify_restore(root, manifest):
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*")}
    if actual != set(manifest["files"]):
        raise RuntimeError("Restored file inventory differs from the snapshot")
    for name, expected in manifest["files"].items():
        path = root / name
        if expected["kind"] == "symlink":
            if not path.is_symlink() or os.readlink(path) != expected["target"]:
                raise RuntimeError(f"Restored symlink mismatch: {name}")
        elif expected["kind"] == "directory":
            if path.is_symlink() or not path.is_dir():
                raise RuntimeError(f"Restored directory mismatch: {name}")
        elif path.is_symlink() or not path.is_file() or digest(path) != expected["sha256"]:
            raise RuntimeError(f"Restored content mismatch: {name}")
        if "mode" in expected and stat.S_IMODE(path.stat().st_mode) != expected["mode"]:
            raise RuntimeError(f"Restored permission mismatch: {name}")
    if git(root, "rev-parse", "HEAD").decode().strip() != manifest["commit"]:
        raise RuntimeError("Restored Git HEAD differs from the snapshot")
    git(root, "fsck", "--no-reflogs", "--connectivity-only")
    if git(root, "status", "--porcelain", "--untracked-files=no").decode() != manifest["git_tracked_status"]:
        raise RuntimeError("Restored tracked Git worktree status differs from the snapshot")
    for line in manifest["submodules"].splitlines():
        path = line.split()[1]
        git(root / path, "fsck", "--no-reflogs", "--connectivity-only")
    if git(root, "submodule", "status", "--recursive").decode() != manifest["submodules"]:
        raise RuntimeError("Restored submodule revisions differ from the snapshot")
    for name in manifest["databases"]:
        with closing(sqlite3.connect((root / name).as_uri() + "?mode=ro", uri=True)) as database:
            if database.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise RuntimeError(f"Restored SQLite integrity check failed: {name}")


def create_backup(source, destination, *, staging_dir=None, sqlite_paths=None):
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if destination.is_relative_to(source):
        raise ValueError("Backup destination must be outside the workspace")
    if not destination.parent.is_dir():
        raise ValueError("Backup destination's parent must already exist")
    if not (source / ".git").is_dir():
        raise ValueError("Backup requires a standalone Git checkout with a local .git directory")
    if staging_dir is not None:
        staging_dir = staging_dir.resolve(strict=True)
        if not staging_dir.is_dir() or staging_dir.is_relative_to(source):
            raise ValueError("Staging directory must be an existing directory outside the workspace")
    if sqlite_paths is not None:
        sqlite_paths = set(sqlite_paths)
        for name in sqlite_paths:
            path = Path(name)
            if path.is_absolute() or ".." in path.parts or (source / path).is_symlink():
                raise ValueError("SQLite snapshot paths must be relative workspace files without symlinks")
            if not is_database(source / path):
                raise ValueError(f"SQLite snapshot path is not an existing database: {name}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    label = "engi-platform" if source == ROOT else source.name
    name = f"{label}-{stamp}-{uuid.uuid4().hex[:8]}.tar.gz"
    tracked = set(git(source, "ls-files", "--recurse-submodules", "-z").decode().split("\0")) - {""}
    manifest = {
        "format": 1, "created_at": stamp, "workspace": source.name,
        "commit": git(source, "rev-parse", "HEAD").decode().strip(),
        "git_status": git(source, "status", "--porcelain").decode(),
        "git_tracked_status": git(source, "status", "--porcelain", "--untracked-files=no").decode(),
        "submodules": git(source, "submodule", "status", "--recursive").decode(),
        "scope": "Entire workspace including sensitive private state; external assets not followed",
        "sqlite_consistency": "Individually consistent online snapshots, not a cross-service transaction",
        "sqlite_snapshot_paths": "all" if sqlite_paths is None else sorted(sqlite_paths),
    }
    with tempfile.TemporaryDirectory(prefix="engi-backup-", dir=staging_dir) as temporary:
        stage = Path(temporary)
        snapshot = stage / source.name
        files, omissions, databases = snapshot_files(source, snapshot, tracked, sqlite_paths)
        manifest.update(files=files, omitted=omissions, databases=databases)
        if (git(source, "rev-parse", "HEAD").decode().strip() != manifest["commit"]
                or git(source, "status", "--porcelain").decode() != manifest["git_status"]
                or git(source, "submodule", "status", "--recursive").decode() != manifest["submodules"]):
            raise RuntimeError("Git state changed during snapshot; retry")
        metadata = stage / "backup-manifest.json"
        metadata.write_text(json.dumps(manifest, indent=2) + "\n")
        archive = stage / name
        with tarfile.open(archive, "w:gz", compresslevel=1) as output:
            output.add(snapshot, arcname=source.name)
            output.add(metadata, arcname=metadata.name)
        restore = stage / "restore"
        restore.mkdir(mode=0o700)
        extract_snapshot(archive, restore)
        restored_manifest = json.loads((restore / metadata.name).read_text())
        if restored_manifest != manifest:
            raise RuntimeError("Restored manifest differs from the snapshot")
        verify_restore(restore / source.name, restored_manifest)
        checksum = digest(archive)
        destination.mkdir(mode=0o700, exist_ok=True)
        uploaded = destination / name
        checksum_path = destination / (name + ".sha256")
        created = []
        try:
            with uploaded.open("xb") as output:
                created.append(uploaded)
                with archive.open("rb") as stream:
                    shutil.copyfileobj(stream, output)
                output.flush()
                os.fsync(output.fileno())
            if digest(uploaded) != checksum:
                raise RuntimeError("Host archive checksum differs from the verified local archive")
            with checksum_path.open("x") as output:
                created.append(checksum_path)
                output.write(f"{checksum}  {name}\n")
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            for path in reversed(created):
                path.unlink()
            raise
        return {
            "archive": str(uploaded), "bytes": uploaded.stat().st_size,
            "sha256": checksum, "commit": manifest["commit"],
            "files": len(files), "sqlite_snapshots": len(databases),
            "omitted_paths": len(omissions), "local_restore_verified": True,
            "cloud_sync_verified": False,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="Explicit approved backup directory outside the checkout")
    parser.add_argument("--source", type=Path, default=ROOT, help="Workspace to copy (default: this platform)")
    parser.add_argument("--staging-dir", type=Path, help="Existing private directory on a disk with room for staging")
    parser.add_argument(
        "--sqlite-snapshot", action="append", dest="sqlite_paths",
        help="Snapshot only these relative live database paths; preserve other SQLite artifacts byte-for-byte",
    )
    arguments = parser.parse_args()
    os.umask(0o077)
    try:
        print(json.dumps(create_backup(
            arguments.source, arguments.destination,
            staging_dir=arguments.staging_dir, sqlite_paths=arguments.sqlite_paths,
        ), indent=2))
    except (OSError, ValueError, RuntimeError, sqlite3.Error, subprocess.SubprocessError, tarfile.TarError) as error:
        parser.exit(1, f"ERROR: {error}\n")
