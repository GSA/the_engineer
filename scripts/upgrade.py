#!/usr/bin/env python3
"""Upgrade pinned components behind a compatibility gate with automatic rollback.

  status    compare pinned versions with upstream (read-only)
  snapshot  save binaries, databases, private configs and pins under .local/upgrade/
  apply     prepare a candidate worktree (.local/upgrade/tree), move its submodules to
            upstream (rebasing carried commits) and bump its Pi pins
  verify    build the candidate tree and run its unit suites and isolated smoke test
  cutover   stop services, move the live checkout and binaries to the verified
            candidate, install Pi and extensions, restart, gate on `local_env.py accept`
  rollback  restore a snapshot, restart services and gate again
  drill     snapshot then roll back to it, proving rollback works on this host
  discard   remove the candidate worktree
  run       snapshot -> apply -> verify -> cutover; cutover rolls back on failure

The live checkout, pins and binaries stay untouched until cutover stops the
services, so running agents and reviews keep working during apply and verify.

Nothing is committed or pushed; review `git status` and commit the result.
"""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import local_env  # noqa: E402

ROOT = local_env.RUNTIME_ROOT
STATE = local_env.STATE
UPGRADE_DIR = ROOT / ".local/upgrade"
KEEP_SNAPSHOTS = 3
SMOKE_PORT_OFFSET = "3000"
SUBMODULES = ("agentsview", "forge", "kata", "roborev", "superpowers")
# Start order; stop runs in reverse so Forge never outlives Kata/roborev.
SERVICES = ("kata", "roborev", "agentsview", "forge")
UNITS = {"kata": local_env.KATA_UNIT, "roborev": local_env.ROBOREV_UNIT,
         "agentsview": local_env.AGENTSVIEW_UNIT, "forge": local_env.FORGE_UNIT}
SERVICE_SOURCES = {"kata": "kata", "roborev": "roborev", "agentsview": "agentsview", "forge": "forge"}
DATABASES = ("kata/kata.db", "roborev/reviews.db", "roborev/reviews.search.db",
             "agentsview/sessions.db", "forge/forge.db")
CONFIGS = ("environment.json", "usai.json", "pi/settings.json", "pi/models.json",
           "pi/mcp.json", "roborev/config.toml", "forge/config.toml", "kata/config.toml")
PI_PACKAGE = "@earendil-works/pi-coding-agent"
PI_SUBAGENTS_PACKAGE = "pi-subagents"
SEMVER = r"([0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.]+)?)"
# Every tracked mention of a pin; read_pins() requires all of them to agree.
PIN_SOURCES = {
    "pi": (
        ("scripts/local_env.py", rf'^PI_VERSION = "{SEMVER}"$'),
        ("dist/install.py", rf'^PI_VERSION = "{SEMVER}"$'),
        ("context/tools.md", rf'PI_VERSION = "{SEMVER}"'),
        ("README.md", rf"Pi `{SEMVER}`"),
        ("README.md", rf"pi-coding-agent@{SEMVER}"),
        ("dist/README.md", rf"\*\*Pi {SEMVER}\*\*"),
        ("dist/README.md", rf"pi-coding-agent@{SEMVER}"),
        ("dist/container/run-acceptance.sh", rf"pi-coding-agent@{SEMVER}"),
    ),
    "pi-subagents": (
        ("scripts/local_env.py", rf'"npm:pi-subagents@{SEMVER}"'),
    ),
}


class UpgradeError(RuntimeError):
    def __init__(self, message, output=""):
        super().__init__(message)
        self.output = output


def log(message):
    print(f"[upgrade] {message}", flush=True)


def sh(command, *, cwd=None, env=None, capture=False, timeout=None):
    """Run a command, raising UpgradeError on failure. Tests replace this."""
    command = [str(part) for part in command]
    if not capture:
        log("$ " + " ".join(command))
    result = subprocess.run(command, cwd=cwd, env=env, text=True, timeout=timeout,
                            capture_output=capture)
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip().splitlines()[-1:] if capture else []
        raise UpgradeError(f"{' '.join(command[:6])} exited {result.returncode}"
                           + (f": {detail[0]}" if detail else ""),
                           output=f"{result.stdout or ''}{result.stderr or ''}")
    return result.stdout if capture else ""


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True)
    if result.returncode:
        raise UpgradeError(f"git -C {repo} {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def systemctl(action, unit):
    sh(["systemctl", "--user", action, unit], timeout=120)


# ---------------------------------------------------------------- pins

def read_pins(root=None):
    """Return {pin: version}, failing when any tracked mention disagrees or is missing."""
    root = ROOT if root is None else root
    pins = {}
    for name, sources in PIN_SOURCES.items():
        found = {}
        for relative, pattern in sources:
            matches = re.findall(pattern, (root / relative).read_text(), re.M)
            if not matches:
                raise UpgradeError(f"{relative} no longer mentions the {name} pin ({pattern})")
            for version in matches:
                found.setdefault(version, []).append(relative)
        if len(found) != 1:
            raise UpgradeError(f"inconsistent {name} pins: {found}")
        pins[name] = next(iter(found))
    return pins


def write_pin(name, version, root=None):
    root = ROOT if root is None else root
    if not re.fullmatch(SEMVER, version):
        raise UpgradeError(f"{name} version must be semver: {version!r}")
    for relative in sorted({relative for relative, _ in PIN_SOURCES[name]}):
        path = root / relative
        text = path.read_text()
        for source, pattern in PIN_SOURCES[name]:
            if source == relative:
                text = re.sub(pattern, lambda m: m.group(0).replace(m.group(1), version), text,
                              flags=re.M)
        path.write_text(text)


def npm_latest(package):
    return sh(["npm", "view", package, "version"], capture=True, timeout=60).strip()


# ---------------------------------------------------------------- submodules

def upstream_ref(repo):
    try:
        return git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    except UpgradeError:
        return "origin/main"


def carried_commits(repo, target):
    """Local commits on HEAD that upstream does not already contain (oldest first)."""
    listed = git(repo, "rev-list", "--reverse", "--right-only", "--cherry-pick", "--no-merges",
                 f"{target}...HEAD")
    merges = git(repo, "rev-list", "--merges", f"{target}..HEAD")
    if merges:
        raise UpgradeError(f"{repo.name} carries merge commits; rebase them by hand")
    return listed.split()


def require_clean(repo):
    if git(repo, "status", "--porcelain", "--untracked-files=no"):
        raise UpgradeError(f"{repo} has uncommitted changes; preserve them first")


def advance_submodule(repo, *, fetch=True):
    """Move a submodule to its upstream branch, replaying carried commits on top."""
    require_clean(repo)
    original = git(repo, "rev-parse", "HEAD")
    if fetch:
        git(repo, "fetch", "--quiet", "origin")
    ref = upstream_ref(repo)
    target = git(repo, "rev-parse", f"{ref}^{{commit}}")
    carried = carried_commits(repo, target)
    git(repo, "checkout", "--quiet", "--detach", target)
    for commit in carried:
        result = subprocess.run(["git", "-C", str(repo), "cherry-pick", commit],
                                text=True, capture_output=True)
        if result.returncode:
            subprocess.run(["git", "-C", str(repo), "cherry-pick", "--abort"], capture_output=True)
            git(repo, "checkout", "--quiet", "--detach", original)
            raise UpgradeError(f"{repo.name}: carried commit {commit[:9]} conflicts with {ref}; "
                               f"restored {original[:9]}. Rebase it by hand.")
    head = git(repo, "rev-parse", "HEAD")
    return {"from": original, "to": head, "upstream": target, "carried": carried,
            "published": not carried or bool(git(repo, "branch", "-r", "--contains", head))}


def restore_submodule(repo, sha):
    if git(repo, "rev-parse", "HEAD") != sha:
        require_clean(repo)
        git(repo, "checkout", "--quiet", "--detach", sha)
    stage_gitlink(repo.name)


def stage_gitlink(name, root=None):
    """Stage (never commit) a submodule's gitlink so `git submodule status` and accept agree."""
    git(ROOT if root is None else root, "add", "--", name)


# ---------------------------------------------------------------- candidate tree

def tree():
    return UPGRADE_DIR / "tree"


def candidate_marker():
    return UPGRADE_DIR / "candidate.json"


def remove_tree():
    candidate_marker().unlink(missing_ok=True)
    shutil.rmtree(tree(), ignore_errors=True)
    for repo in (ROOT, *(ROOT / name for name in SUBMODULES)):
        git(repo, "worktree", "prune")


def prepare_tree():
    """Check out the live revisions as a separate worktree with shared tools and caches."""
    remove_tree()
    path = tree()
    path.parent.mkdir(parents=True, exist_ok=True)
    git(ROOT, "worktree", "add", "--quiet", "--detach", str(path), "HEAD")
    for name in SUBMODULES:
        (path / name).mkdir(exist_ok=True)
        git(ROOT / name, "worktree", "add", "--quiet", "--detach", str(path / name),
            git(ROOT / name, "rev-parse", "HEAD"))
    (path / ".local").mkdir()
    for name in ("tools", "cache"):
        if (ROOT / ".local" / name).is_dir():
            (path / ".local" / name).symlink_to(ROOT / ".local" / name)
    return path


def tree_heads():
    return {name: git(tree() / name, "rev-parse", "HEAD") for name in SUBMODULES}


def shipped(config):
    """Live paths of the binaries a build produces."""
    return [ROOT / "kata/kata", ROOT / "roborev/bin/roborev", ROOT / "agentsview/agentsview",
            forge_binary(config)]


def in_tree(path):
    try:
        return tree() / Path(path).relative_to(ROOT)
    except ValueError:
        raise UpgradeError(f"{path} is outside {ROOT}; the candidate tree cannot build it") from None


def load_candidate():
    """Return the verified candidate, refusing one whose tree changed after verify."""
    try:
        candidate = json.loads(candidate_marker().read_text())
    except FileNotFoundError:
        raise UpgradeError("no verified candidate; run `upgrade.py apply` and `verify` first") from None
    if candidate["submodules"] != tree_heads() or candidate["pins"] != read_pins(tree()):
        raise UpgradeError("candidate tree changed since verify; run `upgrade.py verify` again")
    return candidate


# ---------------------------------------------------------------- snapshots

def environment_config():
    return json.loads(local_env.private_read(STATE / "environment.json"))


def forge_binary(config):
    return Path(config["forge_binary"])


def binaries(config):
    forge = forge_binary(config)
    return [path for path in shipped(config) if path.is_file()]


def pi_version(executable):
    return sh([executable, "--version"], env=local_env.base_environment(), capture=True,
              timeout=30).strip()


def backup_database(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.upgrade-backup")
    temporary.unlink(missing_ok=True)
    with closing(sqlite3.connect(source, timeout=60)) as src, closing(sqlite3.connect(temporary)) as dst:
        src.backup(dst)
    os.chmod(temporary, source.stat().st_mode & 0o777)
    os.replace(temporary, target)


def capture_state(directory, manifest):
    """Copy the live databases and configs into a snapshot directory."""
    manifest["databases"], manifest["configs"] = [], []
    for relative in DATABASES:
        path = STATE / relative
        if path.is_file():
            backup_database(path, stored(directory, path))
            manifest["databases"].append(str(path))
    for relative in CONFIGS:
        if (STATE / relative).is_file():
            stored(directory, STATE / relative).parent.mkdir(parents=True, exist_ok=True)
            replace_file(STATE / relative, stored(directory, STATE / relative))
            manifest["configs"].append(str(STATE / relative))


def write_manifest(directory, manifest):
    temporary = directory / ".manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    os.replace(temporary, directory / "manifest.json")


def stored(snapshot_dir, path):
    return snapshot_dir / "files" / path.relative_to("/")


def snapshot(label="manual"):
    config = environment_config()
    created = datetime.now(timezone.utc)
    snapshot_id = created.strftime("%Y%m%dT%H%M%S%fZ")
    directory = UPGRADE_DIR / "snapshots" / snapshot_id
    directory.mkdir(mode=0o700, parents=True)
    manifest = {
        "id": snapshot_id, "label": label, "created_at": created.isoformat(),
        "submodules": {name: git(ROOT / name, "rev-parse", "HEAD") for name in SUBMODULES},
        "pins": read_pins(),
        "pi": {"executable": config["pi_executable"], "version": pi_version(config["pi_executable"])},
        "binaries": [], "databases": [], "configs": [],
    }
    for path in binaries(config):
        stored(directory, path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, stored(directory, path))
        manifest["binaries"].append(str(path))
    capture_state(directory, manifest)
    # The manifest is written last so an interrupted snapshot is never selected.
    write_manifest(directory, manifest)
    prune_snapshots(keep={snapshot_id})
    log(f"snapshot {snapshot_id}: {len(manifest['binaries'])} binaries, "
        f"{len(manifest['databases'])} databases, {len(manifest['configs'])} configs")
    return manifest


def snapshots():
    root = UPGRADE_DIR / "snapshots"
    found = sorted(path for path in root.glob("*/manifest.json")) if root.is_dir() else []
    return [json.loads(path.read_text()) for path in found]


def load_snapshot(snapshot_id=None):
    available = snapshots()
    if not available:
        raise UpgradeError("no snapshot exists; run `upgrade.py snapshot` first")
    if snapshot_id is None:
        return available[-1]
    for manifest in available:
        if manifest["id"] == snapshot_id:
            return manifest
    raise UpgradeError(f"unknown snapshot {snapshot_id}")


def prune_snapshots(keep=()):
    root = UPGRADE_DIR / "snapshots"
    entries = sorted(path for path in root.iterdir() if path.is_dir())
    for path in entries[:-KEEP_SNAPSHOTS]:
        if path.name not in keep:
            shutil.rmtree(path)


def replace_file(source, target):
    temporary = target.with_name(f".{target.name}.upgrade-restore")
    shutil.copy2(source, temporary)
    os.replace(temporary, target)


# ---------------------------------------------------------------- live operations

def local_env_command(*args):
    return [sys.executable, str(ROOT / "scripts/local_env.py"), *args]


def setup_command(config):
    command = local_env_command("setup", "--corpus", config["corpus"],
                                "--forge-binary", config["forge_binary"])
    for key in ("librarian_executable", "librarian_reader", "librarian_root", "librarian_selection"):
        if config.get(key):
            command += [f"--{key.replace('_', '-')}", config[key]]
    return command


def install_pi(version, executable):
    """Install Pi in the same npm prefix as the configured executable."""
    parts = Path(executable).parts
    if "node_modules" not in parts:
        raise UpgradeError(f"cannot locate the npm prefix of {executable}; install Pi {version} by hand")
    index = parts.index("node_modules")
    if parts[index - 1] == "lib":
        prefix, scope = Path(*parts[:index - 1]), ["--global"]
    else:
        prefix, scope = Path(*parts[:index]), []
    npm = prefix / "bin/npm" if (prefix / "bin/npm").is_file() else "npm"
    env = {**os.environ, "PATH": f"{prefix / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"}
    sh([npm, "install", *scope, "--prefix", prefix, "--no-fund", "--no-audit",
        f"{PI_PACKAGE}@{version}"], env=env, timeout=600)


def candidate_pi(version):
    """Return a PATH directory holding Pi `version`, isolated from the live install."""
    prefix = tree() / f".local/pi-{version}"
    bin_dir = prefix / "node_modules/.bin"
    if not (bin_dir / "pi").exists():
        sh(["npm", "install", "--prefix", prefix, "--no-fund", "--no-audit", "--no-save",
            f"{PI_PACKAGE}@{version}"], timeout=600)
    reported = pi_version(bin_dir / "pi")
    if reported != version:
        raise UpgradeError(f"candidate Pi at {bin_dir} reports {reported!r}, not {version}")
    return bin_dir


def running_versions():
    status = json.loads(sh(local_env_command("status"), capture=True, timeout=60))
    return {name: (status.get(f"{name}_service") or {}).get("version", "") for name in SERVICES}


def gate(timeout=180, interval=5):
    """Wait until acceptance passes and every service runs its checked-out source revision."""
    deadline = time.monotonic() + timeout
    while True:
        problems = []
        try:
            sh(local_env_command("accept"), capture=True, timeout=300)
        except UpgradeError as error:
            failed = [line.strip() for line in error.output.splitlines() if line.startswith("FAIL")]
            problems.append(f"accept: {'; '.join(failed) or error}")
        else:
            versions = running_versions()
            for name, source in SERVICE_SOURCES.items():
                head = git(ROOT / source, "rev-parse", "HEAD")
                if head[:7] not in versions[name]:
                    problems.append(f"{name} runs {versions[name] or 'nothing'}, expected {head[:9]}")
        if not problems:
            log("gate passed: acceptance green and services run the checked-out revisions")
            return
        if time.monotonic() >= deadline:
            raise UpgradeError("gate failed: " + "; ".join(problems))
        time.sleep(interval)


def restart_services():
    for name in SERVICES:
        systemctl("restart", UNITS[name])


def cutover(manifest, gate_timeout=180):
    """Switch live services to the checked-out candidate, rolling back to `manifest` on failure.

    Services stop first and the snapshot's databases and configs are refreshed
    while quiescent, so a rollback loses no writes made since the snapshot.
    """
    directory = UPGRADE_DIR / "snapshots" / manifest["id"]
    candidate = load_candidate()
    try:
        for name in reversed(SERVICES):
            systemctl("stop", UNITS[name])
        capture_state(directory, manifest)
        manifest["state_captured_at"] = datetime.now(timezone.utc).isoformat()
        write_manifest(directory, manifest)
        log(f"snapshot {manifest['id']}: refreshed {len(manifest['databases'])} databases "
            f"and {len(manifest['configs'])} configs with services stopped")
        for name, sha in candidate["submodules"].items():
            restore_submodule(ROOT / name, sha)
        for name, version in candidate["pins"].items():
            write_pin(name, version)
        for path in map(Path, candidate["binaries"]):
            replace_file(in_tree(path), path)
        # Binaries the candidate no longer ships (rollback restores them).
        for path in set(manifest["binaries"]) - set(candidate["binaries"]):
            Path(path).unlink(missing_ok=True)
        config = environment_config()
        if pi_version(config["pi_executable"]) != candidate["pins"]["pi"]:
            install_pi(candidate["pins"]["pi"], config["pi_executable"])
        sh(setup_command(config), timeout=300)
        sh(local_env_command("install-pi-extensions"), timeout=600)
        restart_services()
        gate(gate_timeout)
    except BaseException as error:
        log(f"cutover FAILED: {error}")
        rollback(manifest, gate_timeout=gate_timeout)
        raise
    remove_tree()


def rollback(manifest, *, gate_timeout=180):
    """Restore a snapshot's sources, pins, binaries, Pi, data and configs, then gate."""
    directory = UPGRADE_DIR / "snapshots" / manifest["id"]
    log(f"rolling back to snapshot {manifest['id']}")
    for name in reversed(SERVICES):
        systemctl("stop", UNITS[name])
    keep = directory / f"pre-rollback-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    for path in map(Path, manifest["databases"] + manifest["configs"]):
        for current in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
            if current.is_file():
                (keep / current.relative_to("/")).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(current, keep / current.relative_to("/"))
    log(f"current databases and configs kept in {keep}")
    for path in map(Path, manifest["databases"]):
        for sidecar in (Path(f"{path}-wal"), Path(f"{path}-shm")):
            sidecar.unlink(missing_ok=True)
        replace_file(stored(directory, path), path)
    for path in map(Path, manifest["configs"]):
        replace_file(stored(directory, path), path)
    for path in map(Path, manifest["binaries"]):
        replace_file(stored(directory, path), path)
    for name, sha in manifest["submodules"].items():
        restore_submodule(ROOT / name, sha)
    # Rewritten unconditionally: an interrupted bump may have left mentions disagreeing.
    for name, version in manifest["pins"].items():
        write_pin(name, version)
    executable = manifest["pi"]["executable"]
    if pi_version(executable) != manifest["pi"]["version"]:
        install_pi(manifest["pi"]["version"], executable)
    sh(local_env_command("install-pi-extensions"), timeout=600)
    for name in SERVICES:
        systemctl("start", UNITS[name])
    gate(gate_timeout)
    if read_pins() != manifest["pins"]:
        raise UpgradeError(f"pins after rollback are {read_pins()}, expected {manifest['pins']}")
    log(f"rollback to {manifest['id']} complete")


# ---------------------------------------------------------------- pipeline

def status():
    pins = read_pins()
    rows = []
    for name in SUBMODULES:
        repo = ROOT / name
        git(repo, "fetch", "--quiet", "origin")
        ref = upstream_ref(repo)
        behind = git(repo, "rev-list", "--count", f"HEAD..{ref}")
        carried = carried_commits(repo, ref)
        rows.append((name, git(repo, "describe", "--tags", "--always", "HEAD"),
                     f"{behind} behind {ref}" + (f", {len(carried)} carried" if carried else "")))
    rows.append(("pi", pins["pi"], f"latest {npm_latest(PI_PACKAGE)}"))
    rows.append(("pi-subagents", pins["pi-subagents"], f"latest {npm_latest(PI_SUBAGENTS_PACKAGE)}"))
    for row in rows:
        print(f"{row[0]:<14} {row[1]:<34} {row[2]}")
    return rows


def apply(components=SUBMODULES, pi="latest", pi_subagents="latest"):
    """Prepare the candidate tree; the live checkout is not modified."""
    require_clean(ROOT)
    for name in SUBMODULES:
        require_clean(ROOT / name)
    path = prepare_tree()
    changes = {}
    for name in components:
        changes[name] = advance_submodule(path / name)
        stage_gitlink(name, path)
        result = changes[name]
        log(f"{name}: {result['from'][:9]} -> {result['to'][:9]}"
            + (f" ({len(result['carried'])} carried commits replayed)" if result["carried"] else ""))
        if not result["published"]:
            log(f"WARNING {name} {result['to'][:9]} exists only locally; publish it to an approved "
                f"remote (e.g. git -C {name} push fork {result['to']}:refs/heads/<branch>) "
                "before committing the gitlink")
    current = read_pins(path)
    for name, package, requested in (("pi", PI_PACKAGE, pi),
                                     ("pi-subagents", PI_SUBAGENTS_PACKAGE, pi_subagents)):
        if requested == "keep":
            continue
        version = npm_latest(package) if requested == "latest" else requested
        if version != current[name]:
            write_pin(name, version, path)
            changes[name] = {"from": current[name], "to": version}
            log(f"{name}: {current[name]} -> {version}")
    log(f"candidate tree ready in {path}")
    return changes


def verify(*, build=True, smoke=True):
    """Build and test the candidate tree; live services and binaries are never touched."""
    path = tree()
    if not (path / ".git").exists():
        raise UpgradeError("no candidate tree; run `upgrade.py apply` first")
    # A stale marker must never authorize a candidate whose latest verify failed.
    candidate_marker().unlink(missing_ok=True)
    config = environment_config()
    if build:
        sh(["bash", "scripts/build.sh", "roborev", "kata", "agentsview", "forge"],
           cwd=path, timeout=3600)
    check_candidate(config, smoke)
    marker = {"submodules": tree_heads(), "pins": read_pins(path),
              "binaries": [str(binary) for binary in shipped(config)]}
    temporary = candidate_marker().with_name(".candidate.json.tmp")
    temporary.write_text(json.dumps(marker, indent=2) + "\n")
    os.replace(temporary, candidate_marker())
    log("verify passed")


def check_candidate(config, smoke):
    path = tree()
    for name, binary in zip(SERVICE_SOURCES, shipped(config)):
        candidate = in_tree(binary)
        head = git(path / SERVICE_SOURCES[name], "rev-parse", "HEAD")
        reported = sh([candidate, "version"], capture=True, timeout=30)
        if head[:7] not in reported:
            raise UpgradeError(f"{candidate} reports {reported.strip()!r}, not source {head[:9]}")
    # Suites and smoke resolve `pi` from PATH, so they exercise the pinned candidate.
    pi_dir = candidate_pi(read_pins(path)["pi"])
    env = {**os.environ, "PATH": f"{pi_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
    python = [sys.executable, "-m", "unittest", "discover", "-p", "test_*.py"]
    sh([*python, "-s", "scripts"], cwd=path, env=env, timeout=1800)
    sh([*python, "-s", "dist"], cwd=path, env=env, timeout=1800)
    bun = path / ".local/tools/bun-1.4.4/node_modules/@oven/bun-linux-x64/bin/bun"
    tests = sorted(path.glob("scripts/*.test.mjs")) + sorted(path.glob("scripts/pi-extensions/*.test.mjs"))
    sh([bun, "test", *tests], cwd=path, env=env, timeout=900)
    if smoke:
        sh([sys.executable, "scripts/smoke.py", "--forge-binary", in_tree(forge_binary(config))],
           cwd=path, env={**env, "KENN_KOPY_PORT_OFFSET": SMOKE_PORT_OFFSET}, timeout=600)


def run(components=SUBMODULES, pi="latest", pi_subagents="latest", gate_timeout=180):
    manifest = snapshot("pre-upgrade")
    try:
        changes = apply(components, pi, pi_subagents)
        verify()
    except BaseException as error:
        log(f"FAILED before cutover; live services untouched, candidate kept in {tree()}: {error}")
        raise
    cutover(manifest, gate_timeout)
    log(f"upgrade complete; snapshot {manifest['id']} remains available for `rollback`")
    return changes


def drill(gate_timeout=180):
    """Rehearse a live rollback onto the current versions; services stop first so no write is lost."""
    for name in reversed(SERVICES):
        systemctl("stop", UNITS[name])
    try:
        manifest = snapshot("rollback-drill")
    except BaseException:
        for name in SERVICES:
            systemctl("start", UNITS[name])
        raise
    rollback(manifest, gate_timeout=gate_timeout)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("snapshot")
    commands.add_parser("snapshots", help="list available snapshots")
    commands.add_parser("discard", help="remove the candidate worktree")
    for name in ("apply", "run"):
        sub = commands.add_parser(name)
        sub.add_argument("--only", default=",".join(SUBMODULES),
                         help="comma-separated submodules to advance (default: all)")
        sub.add_argument("--pi", default="latest", help="Pi version, 'latest' or 'keep'")
        sub.add_argument("--pi-subagents", default="latest",
                         help="pi-subagents version, 'latest' or 'keep'")
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--no-build", action="store_true")
    verify_parser.add_argument("--no-smoke", action="store_true")
    for name in ("cutover", "rollback", "drill", "run"):
        sub = commands.choices.get(name) or commands.add_parser(name)
        sub.add_argument("--gate-timeout", type=int, default=180)
    for name in ("cutover", "rollback"):
        commands.choices[name].add_argument("snapshot", nargs="?",
                                            help="snapshot ID to roll back to (default: latest)")
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            status()
        elif args.command == "snapshot":
            snapshot()
        elif args.command == "snapshots":
            for manifest in snapshots():
                print(f"{manifest['id']}  {manifest['label']:<16} pi {manifest['pins']['pi']}  "
                      + " ".join(f"{k}={v[:9]}" for k, v in manifest["submodules"].items()))
        elif args.command in ("apply", "run"):
            components = tuple(name for name in args.only.split(",") if name)
            unknown = set(components) - set(SUBMODULES)
            if unknown:
                parser.error(f"unknown submodules: {', '.join(sorted(unknown))}")
            if args.command == "apply":
                apply(components, args.pi, args.pi_subagents)
            else:
                run(components, args.pi, args.pi_subagents, args.gate_timeout)
        elif args.command == "verify":
            verify(build=not args.no_build, smoke=not args.no_smoke)
        elif args.command == "cutover":
            cutover(load_snapshot(args.snapshot), args.gate_timeout)
        elif args.command == "rollback":
            rollback(load_snapshot(args.snapshot), gate_timeout=args.gate_timeout)
        elif args.command == "drill":
            drill(args.gate_timeout)
        elif args.command == "discard":
            remove_tree()
    except UpgradeError as error:
        print(f"upgrade: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
