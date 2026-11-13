"""Initialize the Engineer platform in another Git repository.

Holds the protected-branch push guard (a marker-delimited block in the repo's
``pre-push`` hook) and the ``init-repo`` step runner used by ``local_env.py``.
Standard library only; every outside effect (Forge, roborev, Kata) is injected
through ``InitServices`` so the runner is testable with fakes.
"""

from dataclasses import dataclass
from pathlib import Path
import os
import re
import subprocess
import tomllib
from typing import Callable

GUARD_START = "# >>> engineer protected-branch guard >>>"
GUARD_END = "# <<< engineer protected-branch guard <<<"
# Must never contain the word that roborev's installer treats as "already installed".
GUARD_BLOCK = f"""{GUARD_START}
# Blocks pushes to main/master (push, force push, deletion) unless a human
# answers on the controlling terminal. Agent tool subprocesses have no terminal.
# Bypassable with `git push --no-verify`; GitHub branch protection is the backstop.
_eg_input=$(cat)
while read -r _eg_local_ref _eg_local_sha _eg_remote_ref _eg_remote_sha; do
    case "$_eg_remote_ref" in
        refs/heads/main|refs/heads/master) ;;
        *) continue ;;
    esac
    _eg_branch=${{_eg_remote_ref#refs/heads/}}
    if ( exec </dev/tty ) 2>/dev/null; then
        printf 'Push to protected branch %s? Type yes: ' "$_eg_branch" >/dev/tty
        _eg_answer=
        read -r _eg_answer </dev/tty
        if [ "$_eg_answer" = yes ]; then
            continue
        fi
    fi
    echo "Blocked: push to protected branch '$_eg_branch'. Push a feature branch and open a pull request;" >&2
    echo "only a person at a terminal can confirm a push to $_eg_branch." >&2
    exit 1
done <<_EG_INPUT_
$_eg_input
_EG_INPUT_
if [ -n "$_eg_input" ]; then
    exec 0<<_EG_INPUT_
$_eg_input
_EG_INPUT_
fi
unset _eg_input _eg_local_ref _eg_local_sha _eg_remote_ref _eg_remote_sha _eg_branch _eg_answer
{GUARD_END}
"""
SHELLS = {"sh", "bash", "zsh", "ksh", "dash"}
DEFAULT_SHEBANG = "#!/bin/sh\n"
TEMPLATE_ROBOREV_TOML = Path(__file__).resolve().parent / "templates/roborev.toml"
ROBOREV_HOOKS = ("post-commit", "post-rewrite", "pre-push")


class ServiceUnavailable(RuntimeError):
    """A needed local service (Forge, Kata) is not reachable; the step degrades to a warning."""


def git_output(repo, *args, strip=True):
    result = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip() if strip else result.stdout


def hook_path(repo, name="pre-push"):
    """A hook git runs for this repo; the hooks directory is shared by every linked worktree."""
    hooks = git_output(repo, "rev-parse", "--path-format=absolute", "--git-path", "hooks")
    return Path(hooks) / name


def is_shell_hook(content):
    words = content.split("\n", 1)[0].strip()
    if not words.startswith("#!"):
        return False
    words = words[2:].split()
    if words and os.path.basename(words[0]) == "env":
        words = words[1:]
    return bool(words) and os.path.basename(words[0]) in SHELLS


def without_guard(content):
    """Return (content with every guard block removed, whether one was found)."""
    kept, found, inside = [], False, False
    for line in content.splitlines(keepends=True):
        text = line.strip()
        if not inside and text == GUARD_START:
            inside = found = True
        elif inside and text == GUARD_END:
            inside = False
        elif not inside:
            kept.append(line)
    if inside:
        raise RuntimeError(f"unterminated guard block (missing {GUARD_END!r}); fix the hook by hand")
    return "".join(kept), found


def write_hook(path, content):
    target = path.resolve() if path.is_symlink() else path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    target.chmod(0o755)


def install_guard(repo):
    """Place the guard right after the shebang; return installed, updated or unchanged."""
    path = hook_path(repo)
    existing = path.read_text(errors="replace") if path.exists() else None
    if existing is None or not existing.strip():
        content, found = DEFAULT_SHEBANG, False
    else:
        if not is_shell_hook(existing):
            raise RuntimeError(f"{path} is not a POSIX shell hook; add the guard by hand or replace the hook")
        content, found = without_guard(existing)
    head, _, rest = content.partition("\n")
    updated = f"{head}\n{GUARD_BLOCK}{rest}"
    if updated == existing:
        if os.access(path, os.X_OK):
            return "unchanged"
        # Git ignores a non-executable hook, so matching text alone is not enforcement.
        write_hook(path, updated)
        return "updated"
    write_hook(path, updated)
    return "updated" if found else "installed"


def remove_guard(repo):
    """Remove the guard block, deleting the hook when nothing else remains."""
    path = hook_path(repo)
    if not path.exists():
        return "absent"
    remaining, found = without_guard(path.read_text(errors="replace"))
    if not found:
        return "absent"
    if all(not line.strip() or line.startswith("#!") for line in remaining.splitlines()):
        path.unlink()
    else:
        write_hook(path, remaining)
    return "removed"


def is_installed(repo):
    """True when the current guard text is first in an executable pre-push hook."""
    path = hook_path(repo)
    try:
        return (os.access(path, os.X_OK)
                and path.read_text(errors="replace").partition("\n")[2].startswith(GUARD_BLOCK))
    except OSError:
        return False


@dataclass
class InitServices:
    """Outside effects of init-repo; local_env.py supplies the real ones."""
    command: str                                  # local_env.py invocation shown in manual steps
    register: Callable[[Path], tuple]             # -> (status, message); may raise ServiceUnavailable
    roborev_init: Callable[[Path], None]
    kata_init: Callable[[Path, str], None]        # may raise ServiceUnavailable
    kata_mapping: Callable[[str], tuple]          # -> (Forge mapping status or "", mapped repo_path or "")
    verify: Callable[[Path], None]
    roborev_template: Path = TEMPLATE_ROBOREV_TOML


def kata_project_name(repo, default):
    try:
        return tomllib.loads((repo / ".kata.toml").read_text())["project"]["name"]
    except (OSError, KeyError, ValueError):
        return default


def changed_files(repo, names):
    # Keep the leading status column: " M file" must not lose its first name character.
    status = git_output(repo, "status", "--porcelain", "--", *names, strip=False)
    return [line[3:] for line in status.splitlines()]


def init_repo(path, services, *, project=None, skip_kata=False, remove_guard_only=False, out=print):
    """Run each init step, one OK/SKIP/WARN/ERROR line apiece; return the exit status."""
    statuses = []

    def report(status, step, message):
        out(f"{status:<5} {step}: {message}")
        statuses.append(status)

    repo = Path(path).expanduser().resolve()
    try:
        if not repo.is_dir():
            raise RuntimeError(f"not a directory: {repo}")
        if git_output(repo, "rev-parse", "--is-bare-repository") == "true":
            raise RuntimeError(f"bare repository; init-repo needs a working checkout: {repo}")
        if Path(git_output(repo, "rev-parse", "--show-toplevel")).resolve() != repo:
            raise RuntimeError(f"not the root of a Git checkout: {repo}")
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        report("ERROR", "repository", str(error))
        return 1
    report("OK", "repository", str(repo))

    if remove_guard_only:
        try:
            result = remove_guard(repo)
        except (RuntimeError, OSError) as error:
            report("ERROR", "guard", str(error))
            return 1
        report("OK" if result == "removed" else "SKIP", "guard",
               "protected-branch guard removed" if result == "removed" else "no guard installed")
        return 0

    manual_register = f"{services.command} register {repo}"
    try:
        status, message = services.register(repo)
        report(status, "forge", message)
    except ServiceUnavailable as error:
        report("WARN", "forge", f"{error}; start Forge, then run: {manual_register}")
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        report("ERROR", "forge", str(error))

    try:
        present = all(roborev_hook_present(repo, name) for name in ROBOREV_HOOKS)
        services.roborev_init(repo)
        report("SKIP" if present else "OK", "roborev-hooks",
               f"{', '.join(ROBOREV_HOOKS)} hooks " + ("already installed" if present else "installed"))
        config = repo / ".roborev.toml"
        if config.exists():
            report("SKIP", "roborev-config", ".roborev.toml already exists; left unchanged")
        else:
            config.write_text(services.roborev_template.read_text())
            report("OK", "roborev-config", "wrote .roborev.toml from the Engineer template")
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        report("ERROR", "roborev", str(error))

    name = project or repo.name
    if skip_kata:
        report("SKIP", "kata", "--skip-kata")
    else:
        if (repo / ".kata.toml").exists():
            report("SKIP", "kata", ".kata.toml already exists; left unchanged")
        else:
            try:
                services.kata_init(repo, name)
                report("OK", "kata", f"created .kata.toml for project {name!r}; it is a committed file, "
                       "so land it through a feature branch and pull request")
            except ServiceUnavailable as error:
                report("WARN", "kata", f"{error}; start Kata, then run: kata init --project {name} (in {repo})")
            except (RuntimeError, OSError, subprocess.SubprocessError) as error:
                report("ERROR", "kata", str(error))
        report_kata_mapping(report, services, kata_project_name(repo, name), repo)

    try:
        result = install_guard(repo)
        report("SKIP" if result == "unchanged" else "OK", "guard",
               f"protected-branch guard {'already installed' if result == 'unchanged' else result} "
               f"in {hook_path(repo)}")
    except (RuntimeError, OSError) as error:
        report("ERROR", "guard", str(error))

    try:
        services.verify(repo)
        report("OK", "verify", "accept --repo checks passed")
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        report("WARN", "verify", str(error))

    print_next_steps(repo, services, out)
    return 1 if "ERROR" in statuses else 0


def roborev_hook_present(repo, name):
    path = hook_path(repo, name)
    return path.exists() and "roborev" in path.read_text(errors="replace").lower()


def origin_repo_path(repo):
    """owner/name of the checkout's origin remote, lowercased, or "" when it is not a GitHub-style URL."""
    try:
        url = git_output(repo, "remote", "get-url", "origin")
    except RuntimeError:
        return ""
    match = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?/?$", url)
    return match.group(1).lower() if match else ""


def report_kata_mapping(report, services, project, repo):
    try:
        status, mapped_repo = services.kata_mapping(project)
    except ServiceUnavailable as error:
        report("WARN", "kata-mapping", f"{error}; check later with: {services.command} verify-handoff WORKSPACE")
        return
    except (RuntimeError, OSError) as error:
        report("ERROR", "kata-mapping", str(error))
        return
    if status == "mapped":
        here = origin_repo_path(repo)
        if mapped_repo and here and mapped_repo.lower() != here:
            report("WARN", "kata-mapping",
                   f"Forge maps Kata project {project!r} to {mapped_repo}, not this repository ({here}); Kata "
                   "workspaces will open there. Fix: change the mapping in Forge Settings > Kata project "
                   "mappings, or choose another project name with --project")
        else:
            report("OK", "kata-mapping", f"Forge maps Kata project {project!r} to this repository"
                   if mapped_repo else f"Forge maps Kata project {project!r}")
    elif status:
        report("WARN", "kata-mapping",
               f"Forge reports Kata project {project!r} as {status}; Forge maps it automatically from a registered "
               "GitHub-backed checkout whose committed .kata.toml names the project. Fix: add a GitHub 'origin' "
               f"remote to {repo}, or map it by hand in Forge Settings > Kata project mappings")
    else:
        report("WARN", "kata-mapping",
               f"the Kata daemon does not list project {project!r} yet; run `kata init --project {project}` "
               f"in {repo}, then re-run init-repo")


def print_next_steps(repo, services, out):
    out("")
    out("Next steps:")
    pending = changed_files(repo, (".kata.toml", ".roborev.toml", ".gitignore"))
    if pending:
        out(f"  1. Commit {', '.join(pending)} on a feature branch and open a pull request (never push main).")
    else:
        out("  1. Land any further repository changes through a feature branch and pull request (never push main).")
    out(f"  2. Verify: {services.command} accept --repo {repo}")
    out("  3. Owner: enable GitHub branch protection on main; the local guard is a speed bump "
        "(`git push --no-verify` bypasses it). See README: Initialize the platform in another repository.")
    out(f"  4. Remove the local guard with: {services.command} init-repo {repo} --remove-guard")
