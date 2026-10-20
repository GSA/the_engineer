#!/usr/bin/python3
"""Install machine-local automatic reviews without replacing original Git hooks."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

import local_env


HOOKS = ("post-commit", "post-rewrite", "pre-push")
GUIDELINES = {
    "platform": (
        "Check concrete regressions in local setup, service ownership, hook routing, "
        "secret handling and reproducibility. Preserve loopback-only services, private "
        "profiles, USAi routing and human approval for publication. Do not confuse "
        "configuration or a successful command with verified end-to-end behavior."
    ),
    "application": (
        "Check changed application behavior, API/data contracts and directly affected "
        "tests. Preserve existing business rules unless the change explicitly revises "
        "them. Use confirmed requirements; do not invent Jira acceptance criteria or "
        "infer operational readiness from repository content."
    ),
    "corpus": (
        "Review tooling regressions and demonstrable documentation defects, including "
        "broken references, lost provenance and dropped qualifications. Follow AGENTS.md "
        "and applicable task guides. Reporting, extraction and indexing are not source "
        "verification or ORR acceptance. Preserve authoritative stores, source wording "
        "and unrelated local work; do not propose invented operational conclusions."
    ),
}


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
    ).stdout.strip()


def run_roborev(repo, *args):
    command, environment = local_env.roborev_launch(list(args))
    return subprocess.run(
        command, cwd=repo, env=environment, check=True, capture_output=True, text=True,
    ).stdout


def review_config(profile):
    guidance = (
        "Report actionable defects introduced by the change with file/line evidence. "
        "Avoid speculative findings, stylistic preferences and unrelated pre-existing "
        "issues. Review only: do not edit files, run fixes, publish or mutate MCP stores. "
        + GUIDELINES[profile]
    )
    return (
        'agent = "pi"\nreview_reasoning = "standard"\n'
        'post_commit_review = "commit"\npost_commit_batch_size = 1\n'
        'exclude_patterns = [".local/**", ".roborev/**", "node_modules/**", '
        '"**/node_modules/**", ".venv/**", "**/.venv/**"]\n'
        f"review_guidelines = {json.dumps(guidance)}\n"
        '\n[auto_design_review]\nenabled = false\n'
    )


def local_hooks_values(repo):
    result = subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "--get-all", "core.hooksPath"],
        capture_output=True, text=True,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip())
    return result.stdout.splitlines()


def restore_hooks_values(repo, values):
    if local_hooks_values(repo):
        git(repo, "config", "--local", "--unset-all", "core.hooksPath")
    for value in values:
        git(repo, "config", "--local", "--add", "core.hooksPath", value)


def validate_policy():
    local_env.settings()
    local_env.validate_roborev_config()
    cfg = tomllib.loads(local_env.private_read(local_env.STATE / "roborev/config.toml"))
    if cfg.get("max_workers") != 1 or cfg.get("default_agent") != "pi":
        raise RuntimeError("automatic reviews require the existing one-worker Pi policy")
    if (cfg.get("allow_unsafe_agents", False)
            or cfg.get("ci", {}).get("enabled", False)
            or cfg.get("advanced", {}).get("tasks_enabled", False)
            or cfg.get("review", {}).get("hook_review_panel")
            or cfg.get("default_backup_agent")
            or cfg.get("default_backup_model")):
        raise RuntimeError("unsafe agents, CI polling, background tasks, panels and fallbacks must stay off")


def copy_original_hooks(source, destination):
    # Native remap consumes stdin; never prepend it to an existing rewrite hook.
    if (source / "post-rewrite").exists():
        raise RuntimeError(f"existing post-rewrite hook needs an explicit stdin-preserving migration: {source}")
    if destination.parent.parent != local_env.STATE / "roborev/hooks":
        raise RuntimeError(f"staged hooks must stay within the private installation state: {destination}")
    local_env.private_dir(destination.parent)
    if destination.exists():
        if destination.is_symlink() or destination.name != "hooks":
            raise RuntimeError(f"refusing to replace an unexpected staged hooks path: {destination}")
        shutil.rmtree(destination)
    if source.is_dir():
        shutil.copytree(source, destination, symlinks=True)
        # Native installation follows hook symlinks; materialize only its targets.
        for name in HOOKS:
            path = destination / name
            if path.is_symlink():
                path.unlink()
                shutil.copy2(source / name, path)
    else:
        destination.mkdir(mode=0o700)


def install(repo, profile):
    repo = repo.expanduser().resolve(strict=True)
    if Path(git(repo, "rev-parse", "--show-toplevel")) != repo or not (repo / ".git").is_dir():
        raise RuntimeError(f"select a main repository root, not a subdirectory/worktree: {repo}")
    launcher = local_env.ROOT / "scripts/roborev-local.py"
    config_path = repo / ".roborev.toml"
    config_text = review_config(profile)
    if config_path.is_symlink():
        raise RuntimeError(f"refusing a symlinked review config: {config_path}")
    if config_path.exists() and config_path.read_text() != config_text:
        raise RuntimeError(f"existing review config differs; inspect it before installation: {config_path}")

    identifier = hashlib.sha256(os.fsencode(repo)).hexdigest()[:16]
    base = local_env.STATE / "roborev/hooks" / identifier
    hooks = base / "hooks"
    manifest = base / "installation.json"
    current = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-path", "hooks"))
    old_values = local_hooks_values(repo)
    if manifest.exists():
        saved = json.loads(local_env.private_read(manifest))
        original_restored = (
            str(current) == saved["previous_hooks"]
            and old_values == saved["previous_local_hooks_values"]
        )
        if (saved["repo"] != str(repo) or saved["profile"] != profile
                or (current != hooks and not original_restored)):
            raise RuntimeError(f"saved hook installation differs from current repository configuration: {repo}")
        if current != hooks:
            copy_original_hooks(current, hooks)
    else:
        if base.exists():
            raise RuntimeError(f"incomplete hook installation requires inspection: {base}")
        copy_original_hooks(current, hooks)
        local_env.json_write(manifest, {
            "repo": str(repo), "profile": profile,
            "previous_hooks": str(current), "previous_local_hooks_values": old_values,
        })

    if not config_path.exists():
        local_env.private_write(config_path, config_text)
    exclude = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-path", "info/exclude"))
    existing = exclude.read_text() if exclude.exists() else ""
    additions = [p for p in ("/.roborev.toml", "/.roborev/") if p not in existing.splitlines()]
    if additions:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a") as stream:
            stream.write(("\n" if existing and not existing.endswith("\n") else "") + "\n".join(additions) + "\n")

    run_roborev(repo, "config", "validate", "--local")
    try:
        git(repo, "config", "--local", "--replace-all", "core.hooksPath", str(hooks))
        output = run_roborev(repo, "init", "--no-daemon", "--binary", str(launcher))
        if "Repo registered with running daemon" not in output:
            raise RuntimeError(f"roborev did not confirm repository registration:\n{output}")
        for name in HOOKS:
            path = hooks / name
            text = path.read_text()
            if f'ROBOREV="{launcher}"' not in text or not os.access(path, os.X_OK):
                raise RuntimeError(f"hook does not select the scoped executable: {path}")
            text = text.replace(
                "ROBOREV=$(command -v roborev 2>/dev/null)",
                "printf '%s\\n' 'ERROR: scoped roborev launcher missing; review not queued.' >&2\n"
                "    ROBOREV=''",
            )
            for call in ('"$ROBOREV" post-commit', '"$ROBOREV" remap --quiet',
                         '"$ROBOREV" post-commit --flush-push'):
                text = text.replace(call + " 2>/dev/null", call)
            if "command -v roborev" in text:
                raise RuntimeError(f"unexpected global executable fallback: {path}")
            path.write_text(text)
            if text.startswith("#!/bin/sh\n"):
                subprocess.run(["/bin/sh", "-n", str(path)], check=True)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        restore_hooks_values(repo, old_values)
        raise
    print(f"Enabled scoped automatic reviews: {repo}")
    return hooks


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=GUIDELINES, required=True)
    parser.add_argument("repositories", type=Path, nargs="+")
    args = parser.parse_args()
    validate_policy()
    for repo in args.repositories:
        install(repo, args.profile)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr)
        sys.exit(1)
