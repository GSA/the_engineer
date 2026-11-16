"""Ubuntu host preparation for ./engineer: OS packages, Node, Pi, Copilot CLI and shell setup.

Everything this module creates is recorded so ``undo`` can remove exactly that
and nothing else. Ubuntu packages are installed with sudo only after the user
agrees; they are never removed, because other software may need them.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import hashlib

APT_PACKAGES = (
    "git", "curl", "ca-certificates", "build-essential", "libc6-dev", "tmux", "python3",
    "python3-venv", "python3-pil", "tar", "xz-utils", "coreutils", "diffutils", "ripgrep", "fd-find",
)
NODE_VERSION = "24.11.1"
NODE_MINIMUM = (24, 11, 0)
NODE_SHA256 = "60e3b0a8500819514aca603487c254298cd776de0698d3cd08f11dba5b8289a8"
NODE_URL = f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-linux-x64.tar.xz"
PI_PACKAGE = "@earendil-works/pi-coding-agent"
COPILOT_PACKAGE = "@github/copilot"
COPILOT_VERSION = "1.0.111"
SHELL_START = "# >>> engineer >>>"
SHELL_END = "# <<< engineer <<<"
SYSTEM_CA_BUNDLE = Path("/etc/ssl/certs/ca-certificates.crt")


class NeedsRestart(RuntimeError):
    """The host must restart (for example WSL after enabling systemd) before install continues."""


def prefix(home=None):
    return Path(home or Path.home()) / ".local/engineer"


def tool_dirs(home=None):
    base = prefix(home)
    return [base / "npm/bin", base / "node/bin", Path(home or Path.home()) / ".local/bin"]


def tool_path(home=None, path=None):
    path = os.environ.get("PATH", "/usr/bin:/bin") if path is None else path
    extra = [str(directory) for directory in tool_dirs(home)]
    return os.pathsep.join([*extra, *(entry for entry in path.split(os.pathsep) if entry not in extra)])


def tool_env(home=None):
    env = dict(os.environ, PATH=tool_path(home))
    # Corporate TLS proxies: Node otherwise ignores the system trust store.
    if SYSTEM_CA_BUNDLE.is_file():
        env.setdefault("NODE_EXTRA_CA_CERTS", str(SYSTEM_CA_BUNDLE))
    return env


def missing_apt_packages(run=subprocess.run, packages=APT_PACKAGES):
    missing = []
    for package in packages:
        result = run(["dpkg-query", "-W", "-f=${Status}", package], capture_output=True, text=True)
        if result.returncode != 0 or result.stdout.strip() != "install ok installed":
            missing.append(package)
    return missing


def install_apt_packages(ask, run=subprocess.run):
    """Install missing Ubuntu packages with sudo after consent; return the packages installed."""
    missing = missing_apt_packages(run)
    if not missing:
        return []
    print("Engineer needs these Ubuntu packages: " + " ".join(missing))
    print("They are installed with sudo, so you may be asked for your Ubuntu password.")
    if not ask("Install them now?", True):
        raise RuntimeError("Ubuntu packages are required; rerun ./engineer install when you are ready")
    for command in (["sudo", "apt-get", "update"],
                    ["sudo", "apt-get", "install", "-y", "--no-install-recommends", *missing]):
        if run(command).returncode != 0:
            raise RuntimeError("installing Ubuntu packages failed; read the apt message above, then rerun")
    return missing


def node_version(run=subprocess.run, env=None):
    try:
        result = run(["node", "--version"], capture_output=True, text=True, env=env)
    except OSError:
        return None
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", result.stdout.strip()) if result.returncode == 0 else None
    return tuple(map(int, match.groups())) if match else None


def download(url, destination):
    with urllib.request.urlopen(url, timeout=300) as response, open(destination, "wb") as stream:
        shutil.copyfileobj(response, stream)


def install_node(home=None, run=subprocess.run, fetch=download):
    """Use a suitable Node already on PATH, else install the pinned release; return whether installed."""
    version = node_version(run, tool_env(home))
    if version is not None and version >= NODE_MINIMUM:
        return False
    target = prefix(home) / "node"
    print(f"Installing Node.js {NODE_VERSION} for Engineer only (in {target})...")
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / "node.tar.xz"
        fetch(NODE_URL, archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != NODE_SHA256:
            raise RuntimeError("the Node.js download did not match its expected checksum; nothing was installed")
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True)
        with tarfile.open(archive) as bundle:
            members = []
            for member in bundle.getmembers():
                parts = Path(member.name).parts[1:]
                if not parts:
                    continue
                member.name = str(Path(*parts))
                members.append(member)
            bundle.extractall(target, members=members, filter="tar")
    return True


def npm_package_version(binary, run=subprocess.run, env=None):
    if not binary.exists():
        return None
    result = run([str(binary), "--version"], capture_output=True, text=True, env=env)
    if result.returncode != 0:
        return None
    match = re.search(r"\d+\.\d+\.\d+", result.stdout)
    return match.group(0) if match else None


def install_npm_package(package, version, binary_name, home=None, run=subprocess.run):
    """Install a pinned npm CLI into Engineer's own prefix; return whether it changed."""
    env = tool_env(home)
    binary = prefix(home) / "npm/bin" / binary_name
    if npm_package_version(binary, run, env) == version:
        return False
    print(f"Installing {package} {version} for Engineer only...")
    result = run(["npm", "install", "--global", "--no-fund", "--no-audit",
                  "--prefix", str(prefix(home) / "npm"), f"{package}@{version}"], env=env)
    if result.returncode != 0:
        raise RuntimeError(f"installing {package} failed; read the npm message above, then rerun")
    return True


def ensure_fd(home=None):
    """Ubuntu names fd 'fdfind'; give it the standard name. Return whether a link was created."""
    home = Path(home or Path.home())
    if shutil.which("fd", path=tool_path(home)):
        return False
    fdfind = shutil.which("fdfind")
    if fdfind is None:
        return False
    link = home / ".local/bin/fd"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(fdfind)
    return True


def systemd_user_available(run=subprocess.run):
    try:
        return run(["systemctl", "--user", "show-environment"], capture_output=True).returncode == 0
    except OSError:
        return False


def is_wsl(version_file=Path("/proc/version")):
    try:
        return "microsoft" in version_file.read_text().lower()
    except OSError:
        return False


def wsl_conf_with_systemd(text):
    """Return /etc/wsl.conf text with [boot] systemd=true, preserving everything else."""
    lines = text.splitlines()
    section = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if section == "boot":
                lines.insert(index, "systemd=true")
                return "\n".join(lines) + "\n"
            section = stripped[1:-1].strip().lower()
        elif section == "boot" and re.match(r"systemd\s*=", stripped):
            lines[index] = "systemd=true"
            return "\n".join(lines) + "\n"
    if section == "boot":
        return "\n".join([*lines, "systemd=true"]) + "\n"
    prefix_text = "\n".join(lines) + ("\n\n" if lines else "")
    return prefix_text + "[boot]\nsystemd=true\n"


def ensure_systemd(ask, run=subprocess.run, wsl_conf=Path("/etc/wsl.conf")):
    """Engineer runs its services with systemd; on WSL offer to turn it on."""
    if systemd_user_available(run):
        return
    if not is_wsl():
        raise RuntimeError("this Ubuntu session has no systemd user services; log in to a desktop or SSH "
                           "session (not a container), then rerun ./engineer install")
    print("Engineer runs its services with systemd, which is turned off in this WSL Ubuntu.")
    if not ask("Turn systemd on now (uses sudo to edit /etc/wsl.conf)?", True):
        raise RuntimeError("systemd is required; rerun ./engineer install when you are ready")
    current = wsl_conf.read_text() if wsl_conf.exists() else ""
    with tempfile.NamedTemporaryFile("w", delete=False) as stream:
        stream.write(wsl_conf_with_systemd(current))
    try:
        if wsl_conf.exists():
            run(["sudo", "cp", str(wsl_conf), f"{wsl_conf}.engineer-backup"], check=True)
        run(["sudo", "install", "-m", "644", stream.name, str(wsl_conf)], check=True)
    finally:
        os.unlink(stream.name)
    raise NeedsRestart(
        "systemd is now turned on. Restart Ubuntu: in Windows PowerShell run  wsl --shutdown  "
        "then open Ubuntu again and rerun ./engineer install")


def shell_block(checkout, *, pi=False, copilot=False):
    engineer = str(Path(checkout) / "engineer")
    lines = [
        SHELL_START,
        "# Added by Engineer; ./engineer uninstall removes this block.",
        'case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$PATH:$HOME/.local/bin" ;; esac',
        f"alias engineer={json.dumps(engineer)}",
    ]
    if pi:
        lines.append(f'pi() {{ {json.dumps(engineer)} pi "$@"; }}')
    if copilot:
        lines.append(f'copilot() {{ {json.dumps(engineer)} copilot "$@"; }}')
    return "\n".join([*lines, SHELL_END]) + "\n"


def without_shell_block(text):
    pattern = re.compile(rf"(?ms)^{re.escape(SHELL_START)}\n.*?^{re.escape(SHELL_END)}\n?")
    return pattern.sub("", text)


def write_shell_block(block, home=None):
    rc = Path(home or Path.home()) / ".bashrc"
    text = rc.read_text() if rc.exists() else ""
    rest = without_shell_block(text)
    separator = "" if not rest or rest.endswith("\n") else "\n"
    rc.write_text(rest + separator + block)


def remove_shell_block(home=None):
    rc = Path(home or Path.home()) / ".bashrc"
    if rc.exists():
        rc.write_text(without_shell_block(rc.read_text()))


def prepare(ask, *, want_copilot, record, pi_version, home=None, run=subprocess.run, fetch=download):
    """Install host prerequisites; add what was created to ``record``."""
    # Own the shared tool prefix only when this install creates it, so uninstalling a
    # second checkout never deletes tools another install is using.
    if not prefix(home).exists():
        record["prefix"] = True
    installed = install_apt_packages(ask, run)
    record["apt_installed"] = sorted(set(record.get("apt_installed", [])) | set(installed))
    ensure_systemd(ask, run)
    if install_node(home, run, fetch):
        record["node"] = True
    install_npm_package(PI_PACKAGE, pi_version, "pi", home, run)
    if want_copilot:
        install_npm_package(COPILOT_PACKAGE, COPILOT_VERSION, "copilot", home, run)
    if ensure_fd(home):
        record["fd_link"] = True
    return record


def undo(record, home=None):
    """Remove only what ``prepare`` and the shell block created; return what was removed."""
    home = Path(home or Path.home())
    removed = []
    rc = home / ".bashrc"
    if rc.exists() and SHELL_START in rc.read_text():
        remove_shell_block(home)
        removed.append(f"Engineer lines in {rc}")
    link = home / ".local/bin/fd"
    if record.get("fd_link") and link.is_symlink() and Path(os.readlink(link)).name == "fdfind":
        link.unlink()
        removed.append(str(link))
    if record.get("prefix") and prefix(home).exists():
        shutil.rmtree(prefix(home))
        removed.append(f"{prefix(home)} (Engineer's Node.js, Pi and Copilot CLI)")
    return removed
