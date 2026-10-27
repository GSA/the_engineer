#!/usr/bin/env python3
"""Install the local engineering platform without copying private runtime state."""

import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import ssl
import stat
import subprocess
import sys
import tempfile
import tomllib
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent.parent
PI_VERSION = "1.0.3"
PROJECTS = ("forge", "kata", "roborev", "agentsview", "superpowers")
MANAGED_SERVICES = ("kata", "agentsview", "roborev", "forge")
KATA_DAEMON_NAME = "local"
KATA_DAEMON_URL = "http://127.0.0.1:17777"
REQUIRED_FILES = (
    ".gitmodules", "scripts/bootstrap-sources.sh", "scripts/bootstrap-toolchains.sh",
    "scripts/build.sh", "scripts/local_env.py",
)
TOOLS = {
    "bash": "bash",
    "git": "git",
    "curl": "curl",
    "tar": "tar",
    "sha256sum": "coreutils",
    "install": "coreutils",
    "diff": "diffutils",
    "make": "build-essential",
    "cc": "build-essential libc6-dev",
    "node": "Node.js >=24.11.0 (use an approved installation method)",
    "npm": "npm compatible with your Node.js installation",
    "tmux": "tmux",
    "pi": f"Pi {PI_VERSION}: npm install --prefix \"$HOME/.local/engi-pi\" "
          f"@earendil-works/pi-coding-agent@{PI_VERSION}; "
          "then add $HOME/.local/engi-pi/node_modules/.bin to PATH",
}


def capture(command, *, cwd=None, timeout=30):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{command[0]} failed (exit {result.returncode}): {result.stderr.strip()}")
    return result.stdout.strip()


def run(command, *, cwd):
    subprocess.run(command, cwd=cwd, check=True)


def check_c_toolchain():
    with tempfile.TemporaryDirectory(prefix="engi-c-preflight-") as directory:
        source = Path(directory) / "probe.c"
        source.write_text(
            "#include <stdlib.h>\n#include <stdio.h>\n#include <pthread.h>\n"
            "#include <dlfcn.h>\n#include <math.h>\nint main(void) { return 0; }\n"
        )
        capture(["cc", str(source), "-o", str(Path(directory) / "probe"),
                 "-pthread", "-ldl", "-lm"])


def prerequisites(corpus):
    errors = []
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        errors.append("This release supports Linux x86_64 only (Ubuntu/WSL).")
    missing = {tool for tool in TOOLS if shutil.which(tool) is None}
    errors.extend(f"Missing {tool}; install: {TOOLS[tool]}" for tool in TOOLS if tool in missing)
    if sys.version_info < (3, 11):
        errors.append("Python 3.11+ is required; use Ubuntu 24.04+ or an approved newer Python.")
    if "node" not in missing:
        try:
            version = capture(["node", "--version"])
            match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", version)
            if not match or tuple(map(int, match.groups())) < (24, 11, 0):
                errors.append(f"Node.js >=24.11.0 is required; found {version}.")
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
            errors.append(f"Cannot run Node.js: {error}")
    if "pi" not in missing:
        try:
            version = capture(["pi", "--version"])
            if version != PI_VERSION:
                errors.append(f"Pi {PI_VERSION} is required; found {version}. {TOOLS['pi']}")
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
            errors.append(f"Cannot run Pi: {error}")
    if "cc" not in missing:
        try:
            check_c_toolchain()
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
            errors.append(f"C headers/linker unavailable; install build-essential libc6-dev: {error}")
    certificates = ssl.get_default_verify_paths()
    if not certificates.cafile and not certificates.capath:
        errors.append("No system TLS trust store found; install ca-certificates.")
    server = corpus / "tools/context-mcp/.venv/bin/qualified-context-mcp"
    reader = corpus / "tools/context-index/context_index.py"
    for path in (server, reader):
        if not path.is_file() or not os.access(path, os.R_OK):
            errors.append(f"Missing readable Librarian prerequisite: {path}")
    if server.is_file():
        if not os.access(server, os.X_OK):
            errors.append(f"Librarian server is not executable: {server}")
        else:
            try:
                capture([str(server), "--help"])
            except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
                errors.append(f"Librarian runtime/dependencies unavailable: {error}")
    return errors


def validate_source(source):
    if source.startswith("-") or any(char in source for char in "\n\r\x00"):
        raise RuntimeError("Invalid source repository path/URL.")
    if re.match(r"[^/]*:[^/]*@", source) and "://" not in source:
        raise RuntimeError("Do not embed credentials in repository URLs; use approved Git authentication.")
    url = urlsplit(source)
    if url.scheme in ("https", "http", "ssh"):
        if url.password or url.query or url.fragment or (
                url.scheme in ("http", "https") and url.username):
            raise RuntimeError("Do not embed credentials in repository URLs; use approved Git authentication.")
        if url.scheme == "http":
            raise RuntimeError("Use HTTPS or SSH for repository downloads.")
    elif "://" in source:
        raise RuntimeError("Use HTTPS, SSH or a local Git repository for the source.")


def validate_checkout(checkout, revision):
    if any(not (checkout / path).is_file() for path in REQUIRED_FILES):
        raise RuntimeError(f"Not an engineering platform checkout: {checkout}; refusing to overwrite it.")
    top = Path(capture(["git", "-C", str(checkout), "rev-parse", "--show-toplevel"])).resolve()
    if top != checkout:
        raise RuntimeError(f"Not an independent platform checkout: {checkout}")
    if revision and capture(["git", "-C", str(checkout), "rev-parse", "HEAD"]) != revision:
        raise RuntimeError("Existing checkout has another revision; select another directory or migrate manually.")


def acquire_checkout(checkout, source, revision):
    if revision and not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise RuntimeError("--revision must be a full, lowercase 40-character Git commit SHA.")
    if source:
        validate_source(source)
    if not checkout.exists():
        if not source or not revision:
            raise RuntimeError("A new checkout requires both --source and --revision; no repository URL is assumed.")
        checkout.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--template=", "--no-checkout", "--", source, str(checkout)],
            cwd=checkout.parent)
        run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(checkout),
             "checkout", "--detach", revision], cwd=checkout.parent)
    validate_checkout(checkout, revision)
    return checkout


def check_submodules(checkout):
    for project in PROJECTS:
        path = checkout / project
        if not (path / ".git").exists():
            continue
        changed = capture(["git", "-C", str(path), "status", "--porcelain", "--ignore-submodules=none"])
        if changed:
            raise RuntimeError(f"{project} has local changes; preserve them before installing/updating.")


def _check_native_kata_directory(path):
    if path.is_symlink():
        raise RuntimeError(f"Native Kata path is a symlink; resolve it explicitly: {path}")
    if path.exists() and not path.is_dir():
        raise RuntimeError(f"Native Kata path is not a directory: {path}")


def _loopback_daemon_identity(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError:
        return None
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or port is None
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/")):
        return None
    return parsed.scheme, parsed.hostname, port


def _write_native_kata_config(path, contents, mode):
    fd, temporary = tempfile.mkstemp(prefix=".config.toml.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink():
            raise RuntimeError(f"Native Kata config became a symlink; refusing to replace it: {path}")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def provision_native_kata_client(checkout, home=None):
    checkout = Path(checkout).resolve()
    home = Path(home or Path.home()).expanduser().resolve()
    binary = checkout / "kata/kata"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"Build did not produce an executable Kata binary: {binary}")
    binary = binary.resolve(strict=True)

    local_dir = home / ".local"
    bin_dir = local_dir / "bin"
    kata_dir = home / ".kata"
    link = bin_dir / "kata"
    config_path = kata_dir / "config.toml"
    for directory in (home, local_dir, bin_dir, kata_dir):
        _check_native_kata_directory(directory)

    if link.is_symlink():
        try:
            if link.resolve(strict=True) != binary:
                raise RuntimeError(f"A different Kata binary already owns {link}; resolve it explicitly.")
        except FileNotFoundError as error:
            raise RuntimeError(f"A broken Kata symlink already exists at {link}; resolve it explicitly.") from error
    elif link.exists():
        raise RuntimeError(f"A different Kata binary already exists at {link}; resolve it explicitly.")

    config_exists = config_path.exists() or config_path.is_symlink()
    if config_path.is_symlink():
        raise RuntimeError(f"Native Kata config is a symlink; resolve it explicitly: {config_path}")
    if config_exists and not config_path.is_file():
        raise RuntimeError(f"Native Kata config is not a regular file: {config_path}")
    if config_exists:
        try:
            config_text = config_path.read_text(encoding="utf-8")
            config = tomllib.loads(config_text)
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
            raise RuntimeError(f"Cannot safely read native Kata config {config_path}: {error}") from error
    else:
        config_text = ""
        config = {}
    original_config_text = config_text

    entries = config.get("daemon", [])
    if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
        raise RuntimeError(f"Native Kata config has an invalid daemon catalog: {config_path}")
    expected_identity = _loopback_daemon_identity(KATA_DAEMON_URL)
    if expected_identity is None:
        raise RuntimeError(f"Installer Kata endpoint must be a loopback URL: {KATA_DAEMON_URL}")

    active_present = "active_daemon" in config
    active_name = config.get("active_daemon")
    if active_present and not isinstance(active_name, str):
        raise RuntimeError(f"Native Kata config has an invalid active_daemon: {config_path}")
    already_configured = False
    if active_name and active_name.strip():
        selected = [entry for entry in entries if entry.get("name") == active_name]
        if (len(selected) == 1 and not selected[0].get("local", False)
                and _loopback_daemon_identity(selected[0].get("url")) == expected_identity):
            selected_name = active_name
            add_entry = False
            already_configured = True
        else:
            raise RuntimeError(
                f"Native Kata config selects a different or ambiguous active Kata daemon "
                f"({active_name!r}); resolve it explicitly: {config_path}"
            )

    if not already_configured:
        matching = [
            entry for entry in entries
            if _loopback_daemon_identity(entry.get("url")) == expected_identity
        ]
        if len(matching) > 1 or any(entry.get("local", False) for entry in matching):
            raise RuntimeError(f"Native Kata config has conflicting loopback daemon identities: {config_path}")
        if matching:
            selected_name = matching[0].get("name")
            if not isinstance(selected_name, str) or not selected_name.strip():
                raise RuntimeError(f"Native Kata config has an unnamed loopback daemon: {config_path}")
            add_entry = False
        else:
            if any(entry.get("name") == KATA_DAEMON_NAME for entry in entries):
                raise RuntimeError(
                    f"Native Kata daemon name {KATA_DAEMON_NAME!r} is already in use: {config_path}"
                )
            selected_name = KATA_DAEMON_NAME
            add_entry = True

        if active_present:
            empty_active = re.compile(
                r"""(?m)^([ \t]*active_daemon[ \t]*=[ \t]*)(?:""|'')([ \t]*(?:#.*)?)$"""
            )
            config_text, replaced = empty_active.subn(
                lambda match: f"{match.group(1)}{json.dumps(selected_name)}{match.group(2)}",
                config_text,
                count=1,
            )
            if not replaced:
                raise RuntimeError(
                    f"Cannot safely select a daemon from empty active_daemon in {config_path}; "
                    "resolve it explicitly."
                )
        else:
            config_text = f"active_daemon = {json.dumps(selected_name)}\n\n{config_text}"
        if add_entry:
            separator = "" if not config_text else ("" if config_text.endswith("\n\n") else "\n")
            config_text += (
                f"{separator}[[daemon]]\n"
                f"name = {json.dumps(selected_name)}\n"
                f"url = {json.dumps(KATA_DAEMON_URL)}\n"
            )

    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    local_dir.mkdir(mode=0o755, exist_ok=True)
    bin_dir.mkdir(mode=0o755, exist_ok=True)
    kata_dir.mkdir(mode=0o700, exist_ok=True)
    if not link.is_symlink() and not link.exists():
        link.symlink_to(binary)
    if not already_configured and config_text != original_config_text:
        mode = stat.S_IMODE(config_path.stat().st_mode) if config_exists else 0o600
        _write_native_kata_config(config_path, config_text, mode)
    print(f"Native Kata CLI: {link}")
    print(f"Native Kata client config: {config_path}")


def service_choice(choice):
    if choice != "ask":
        return choice
    if not sys.stdin.isatty():
        print("Noninteractive input: services remain manual; use --services user for explicit opt-in.")
        return "manual"
    answer = input(
        f"Enable AND start all {len(MANAGED_SERVICES)} Ubuntu user services now? [y/N] "
    ).strip().lower()
    if answer in ("y", "yes"):
        return "user"
    if answer in ("", "n", "no"):
        return "manual"
    raise RuntimeError("Answer yes or no for service registration; no services were changed.")


def check_user_services(checkout):
    for tool in ("systemctl", "systemd-analyze"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"{tool} is required for user services; use --services manual instead.")
    capture(["systemctl", "--user", "show-environment"])
    for project in MANAGED_SERVICES:
        unit = f"kenn-kopy-{project}.service"
        listed = capture(["systemctl", "--user", "list-unit-files", "--no-legend", "--no-pager", unit])
        if not listed:
            continue
        fragment = capture(["systemctl", "--user", "show", unit, "--property=FragmentPath", "--value"])
        expected = checkout / ".local/environment/systemd" / unit
        if not fragment or Path(fragment).resolve() != expected:
            raise RuntimeError(f"{unit} belongs to another installation; use manual services or migrate it explicitly.")


def load_environment(checkout):
    spec = importlib.util.spec_from_file_location("engi_install_environment",
                                               checkout / "scripts/local_env.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def install(checkout, corpus, forge_build, choice):
    environment = load_environment(checkout)
    if environment.PI_VERSION != PI_VERSION:
        raise RuntimeError("Installer/runtime Pi pins differ; use dist from the selected platform revision.")
    if set(environment.SERVICE_PORTS) != set(MANAGED_SERVICES):
        raise RuntimeError("Installer/runtime services differ; use dist from the selected platform revision.")
    environment.check_ports()
    check_submodules(checkout)
    print("\nInitializing repositories at the platform's exact gitlink revisions...")
    run(["bash", "scripts/bootstrap-sources.sh"], cwd=checkout)
    print("\nInstalling workspace-local Go/Bun/GitHub CLI toolchains...")
    run(["bash", "scripts/bootstrap-toolchains.sh"], cwd=checkout)
    print("\nBuilding services (normal Forge remains the default; no automatic fallback)...")
    forge_target = "forge" if forge_build == "normal" else "forge-local-kata"
    run(["bash", "scripts/build.sh", "roborev", "kata", "agentsview", forge_target], cwd=checkout)
    forge = checkout / ("forge/kenn-forge" if forge_build == "normal"
                        else ".local/forge-local-kata/kenn-forge")
    for binary in (forge, checkout / "roborev/bin/roborev",
                   checkout / "kata/kata", checkout / "agentsview/agentsview"):
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise RuntimeError(f"Build did not produce an executable: {binary}")
    provision_native_kata_client(checkout)
    command = [sys.executable, str(checkout / "scripts/local_env.py")]
    print("\nCreating missing private configuration; existing settings are preserved...")
    run([*command, "setup", "--corpus", str(corpus), "--forge-binary", str(forge)], cwd=checkout)
    run([*command, "configure-private-pi-tracking"], cwd=checkout)
    run([*command, "install-pi-review-extension"], cwd=checkout)
    run([sys.executable, str(checkout / "scripts/pi-local.py"), "mcp", "list"], cwd=checkout)
    node = Path(shutil.which("node")).resolve()
    instructions(checkout, node)
    if choice == "user":
        print("\nEnabling and starting explicitly selected user services...")
        for name in MANAGED_SERVICES:
            run([*command, f"install-{name}-service"], cwd=checkout)
        print("User services are enabled and responsive. They start with your user manager/login.")
        print("Boot without login requires administrator-approved lingering; it was NOT enabled here.")
    else:
        print("\nInstallation configured for manual startup; no services were started or registered.")


def manual_kata_command(checkout):
    env = Path("/usr/bin/env")
    if not env.is_file() or not os.access(env, os.X_OK):
        raise RuntimeError("Missing /usr/bin/env required to isolate the Kata process environment.")
    environment = {
        "HOME": str(Path.home()),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "KATA_HOME": str(checkout / ".local/environment/kata"),
        "KATA_DSN": str(checkout / ".local/environment/kata/kata.db"),
        "KATA_DB": "",
        "KATA_TELEMETRY_ENABLED": "0",
    }
    return [
        str(env), "-i",
        *(f"{key}={value}" for key, value in environment.items()),
        str(checkout / "kata/kata"), "daemon", "start", "--foreground",
        "--no-auto-token", "--listen", "127.0.0.1:17777",
    ]


def instructions(checkout, node):
    command = [sys.executable, str(checkout / "scripts/local_env.py")]
    print(f"\nNative Kata CLI: {Path.home() / '.local/bin/kata'}")
    print("  The installer does not edit shell startup files; add ~/.local/bin to PATH if needed.")
    print("\nManual startup (all dashboards in the foreground; Ctrl+C stops owned processes):")
    print("  " + shlex.join([*command, "run"]))
    print("Or run each service in a separate terminal:")
    for name in MANAGED_SERVICES:
        args = (manual_kata_command(checkout) if name == "kata"
                else [*command, f"{name}-run"])
        if name in ("roborev", "forge"):
            args.extend(["--node-executable", str(node)])
        print("  " + shlex.join(args))
    print("Stop a supervisor from another terminal:")
    print("  " + shlex.join([*command, "stop"]))
    print("Independent user services are NOT stopped by that command. For each installed unit:")
    for name in MANAGED_SERVICES:
        print(f"  systemctl --user stop kenn-kopy-{name}.service")
    print(f"\nNative Kata client selects {KATA_DAEMON_URL} by default.")
    print("\nDashboards: Forge http://127.0.0.1:18091/ | Kata http://127.0.0.1:17777/kata")
    print("roborev http://127.0.0.1:17374/reviews | AgentsView http://127.0.0.1:18080/")
    print("\nAgents are not model-ready until you configure your approved USAi endpoint/model and key.")
    print("  " + shlex.join([*command, "configure-provider",
                             "--base-url", "APPROVED_URL", "--model", "APPROVED_MODEL",
                             "--api", "openai-completions"]))
    print("Use a private-only key prompt (set-key also links existing global USAi credentials):")
    print("  " + shlex.join([*command, "set-key", "--private-only"]))
    print("Git authentication, repository/Kata bindings and active engineering policy are separate onboarding.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=ROOT, help="existing checkout or new clone destination")
    parser.add_argument("--source", help="approved platform Git URL/path; required for a new clone")
    parser.add_argument("--revision", help="exact platform commit for a new clone (never an implicit latest)")
    parser.add_argument("--corpus", type=Path, required=True, help="existing approved local Librarian checkout")
    parser.add_argument("--check", action="store_true", help="check prerequisites; no downloads/config/service changes")
    parser.add_argument("--services", choices=("ask", "manual", "user"), default="ask")
    parser.add_argument("--forge-build", choices=("normal", "local-kata"), default="normal",
                        help="explicitly select the temporary local-Kata workaround if normal downloads are blocked")
    args = parser.parse_args(argv)
    checkout = args.checkout.expanduser().resolve()
    corpus = args.corpus.expanduser().resolve()
    try:
        errors = prerequisites(corpus)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            print("Install the missing prerequisites, then rerun. No packages or services were changed.",
                  file=sys.stderr)
            return 1
        print("Host tools, C headers/linker and Librarian executable prerequisites passed.")
        if args.check:
            print("Check only: source downloads, builds, configuration and services were not changed.")
            return 0
        choice = service_choice(args.services)
        if choice == "user":
            check_user_services(checkout)
        acquire_checkout(checkout, args.source, args.revision)
        local = checkout / ".local"
        os.umask(0o077)
        local.mkdir(mode=0o700, exist_ok=True)
        info = local.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise RuntimeError("Expected an owned .local directory, not a symlink or shared writable path.")
        fd = os.open(local / "installer.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "rb") as lock:
            info = os.fstat(lock.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise RuntimeError("Expected an owned private regular installer.lock file (0600).")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError("Another installer is using this checkout; wait for it to finish.") from error
            install(checkout, corpus, args.forge_build, choice)
        return 0
    except (OSError, RuntimeError, ValueError, EOFError, subprocess.SubprocessError) as error:
        print(f"ERROR: Installation stopped: {error}", file=sys.stderr)
        print("Completed files/settings are retained. If service registration partially succeeded, "
              "earlier units may still be running; use the printed per-unit stop commands.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
