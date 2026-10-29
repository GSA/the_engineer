#!/usr/bin/env python3
"""Manage the persistent, workspace-local engineering environment."""

import argparse
from datetime import datetime, timezone
import fcntl
import getpass
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".local/environment"
GLOBAL_PI = Path.home() / ".pi/agent"
PI_VERSION = "1.4.0"
PI_REVIEW_EXTENSION = "npm:@nqbao/pi-json-schema@0.1.1"
PI_SUBAGENTS_EXTENSION = "npm:pi-subagents@0.83.0"
PI_EXTENSIONS = (PI_REVIEW_EXTENSION, PI_SUBAGENTS_EXTENSION)
PI_SUBAGENT_DESCRIPTIONS = {
    "delegate": (
        'Project-context-inheriting delegation subagent (USAi: omit model or pass model:"inherit" '
        'to use the active usai/* session model; omit model on action:"resume").'
    ),
    "oracle": (
        'Deep read-only architectural and debugging analysis subagent (USAi: omit model or pass model:"inherit" '
        'to use the active usai/* session model; omit model on action:"resume").'
    ),
    "reviewer": (
        'Independent read-only spec and code review subagent for Superpowers tasks (USAi: omit model or pass '
        'model:"inherit"; omit model on action:"resume"; use native roborev CLI for commit/branch roborev reviews).'
    ),
    "scout": (
        'Fast read-only codebase reconnaissance subagent (USAi: omit model or pass model:"inherit" '
        'to use the active usai/* session model; omit model on action:"resume").'
    ),
    "worker": (
        'General implementation and code-editing subagent (USAi: omit model or pass model:"inherit" '
        'to use the active usai/* session model; omit model on action:"resume").'
    ),
}
GH_VERSION = "2.102.0"
GH_BINARY = ROOT / f".local/tools/gh-{GH_VERSION}/bin/gh"
PORTS = (17373, 17374, 17777, 18080, 18091)
FORGE_PORT = 18091
FORGE_MCP_PORT = 18092
AGENTSVIEW_UNIT = "kenn-kopy-agentsview.service"
ROBOREV_UNIT = "kenn-kopy-roborev.service"
FORGE_UNIT = "kenn-kopy-forge.service"
KATA_UNIT = "kenn-kopy-kata.service"

SERVICE_PORTS = {"agentsview": (18080,), "roborev": (17373, 17374),
                 "kata": (17777,), "forge": (FORGE_PORT,)}
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def private_dir(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError(f"expected an owned private directory (0700): {path}")


def private_read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "r") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise RuntimeError(f"expected an owned private regular file (0600): {path}")
        return stream.read()


def private_write(path, text, *, replace=False):
    if path.exists() or path.is_symlink():
        private_read(path)
        if not replace:
            return
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def json_write(path, value, *, replace=False):
    private_write(path, json.dumps(value, indent=2) + "\n", replace=replace)


def settings():
    private_dir(STATE)
    return json.loads(private_read(STATE / "environment.json"))


def base_environment(roborev_executable=None):
    home = STATE / "home"
    roborev_executable = roborev_binary() if roborev_executable is None else roborev_executable
    return {
        "PATH": os.pathsep.join([str(GH_BINARY.parent), str(roborev_executable.parent),
                                str(ROOT / "kata"), str(ROOT / "agentsview"), os.environ["PATH"]]),
        "HOME": str(home),
        "USER": getpass.getuser(),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_RUNTIME_DIR": str(STATE / "runtime"),
        "TMPDIR": str(STATE / "tmp"),
        "TERM": os.environ.get("TERM", "xterm-256color"),
        "LANG": "C.UTF-8",
        "TELEMETRY_ENABLED": "0",
        "ROBOREV_TELEMETRY_ENABLED": "0",
        "KATA_TELEMETRY_ENABLED": "0",
        "AGENTSVIEW_TELEMETRY_ENABLED": "0",
        "ROBOREV_DATA_DIR": str(STATE / "roborev"),
        "KATA_HOME": str(STATE / "kata"),
        "KATA_SERVER": "http://127.0.0.1:17777",
        "KENN_FORGE_HOME": str(STATE / "forge"),
        "AGENTSVIEW_DATA_DIR": str(STATE / "agentsview"),
        "AGENTSVIEW_NO_DAEMON": "1",
        "PI_CODING_AGENT_DIR": str(STATE / "pi"),
        "PI_OFFLINE": "1",
        "GH_CONFIG_DIR": str(STATE / "gh"),
        "GH_PROMPT_DISABLED": "1",
    }


def verify_pi(config, *, env=None):
    executable = config["pi_executable"]
    result = subprocess.run([executable, "--version"], env=base_environment() if env is None else env,
                            text=True, capture_output=True, check=True, timeout=15)
    if result.stdout.strip() != PI_VERSION:
        raise RuntimeError(f"expected Pi {PI_VERSION}; update the local setup deliberately")
    return executable


def default_pi_subagents_settings():
    return {
        "defaultProvider": "usai",
        "defaultModel": "inherit",
        "modelScope": {
            "enforce": True,
            "strict": True,
            "allow": ["inherit", "usai/*"],
        },
        "agentOverrides": {
            name: {
                "advertise": True,
                "description": description,
                "model": "inherit",
            }
            for name, description in PI_SUBAGENT_DESCRIPTIONS.items()
        },
    }


def merge_pi_subagents_settings(existing):
    defaults = default_pi_subagents_settings()
    if not isinstance(existing, dict):
        return defaults
    merged = {**defaults, **existing}
    scope = existing.get("modelScope")
    merged["modelScope"] = {**defaults["modelScope"], **(scope if isinstance(scope, dict) else {})}
    overrides = existing.get("agentOverrides")
    merged_overrides = {
        name: {
            **default_override,
            **(overrides.get(name) if isinstance(overrides, dict) and isinstance(overrides.get(name), dict) else {}),
        }
        for name, default_override in defaults["agentOverrides"].items()
    }
    if isinstance(overrides, dict):
        for name, value in overrides.items():
            if name not in merged_overrides and isinstance(value, dict):
                merged_overrides[name] = dict(value)
    merged["agentOverrides"] = merged_overrides
    return merged


def setup(corpus, forge_binary):
    corpus = corpus.expanduser().resolve()
    forge_binary = forge_binary.resolve()
    server = corpus / "tools/context-mcp/.venv/bin/qualified-context-mcp"
    reader = corpus / "tools/context-index/context_index.py"
    for path in (server, reader, forge_binary):
        if not path.is_file():
            raise RuntimeError(f"missing prerequisite: {path}")
    pi = shutil.which("pi")
    if pi is None:
        raise RuntimeError(f"install Pi {PI_VERSION} before setup")
    config = {"corpus": str(corpus), "forge_binary": str(forge_binary),
              "pi_executable": str(Path(pi).resolve()), "pi_version": PI_VERSION}
    private_dir(STATE)
    for name in ("home", "runtime", "tmp", "logs", "secrets", "pi", "forge",
                 "roborev", "kata", "agentsview"):
        private_dir(STATE / name)
    verify_pi(config)
    config_path = STATE / "environment.json"
    if config_path.exists() and json.loads(private_read(config_path)) != config:
        raise RuntimeError(f"setup differs from saved paths/version; inspect {config_path} first")
    json_write(config_path, config)
    wrapper = ROOT / "scripts/pi-local.py"
    disabled = "".join(f'\n[[agents]]\nkey = "{key}"\nenabled = false\n'
                       for key in ("claude", "codex", "gemini", "opencode", "aider"))
    private_write(
        STATE / "forge/config.toml",
        'host = "127.0.0.1"\nport = 18091\n'
        '[roborev]\nendpoint = "http://127.0.0.1:17373"\ninit_managed_clones = false\n'
        '[tmux]\ncommand = ["tmux", "-L", "kenn-kopy-local"]\n'
        f'[mcp]\nenabled = true\nhost = "127.0.0.1"\nport = {FORGE_MCP_PORT}\n'
        '[[agents]]\nkey = "pi"\nlabel = "Pi (USAi)"\nenabled = true\n'
        f'command = [{json.dumps(str(wrapper))}]\n' + disabled,
    )
    private_write(
        STATE / "roborev/config.toml",
        'server_addr = "127.0.0.1:17373"\nmax_workers = 1\ndefault_agent = "pi"\n'
        f'pi_cmd = {json.dumps(str(wrapper))}\n'
        '[web]\nlisten = "127.0.0.1:17374"\n',
    )
    private_write(
        STATE / "kata/config.toml",
        'listen = "127.0.0.1:17777"\nactive_daemon = "local"\n'
        '[[daemon]]\nname = "local"\nurl = "http://127.0.0.1:17777"\n',
    )
    json_write(
        STATE / "pi/settings.json",
        {
            "defaultThinkingLevel": "off",
            "packages": [str(ROOT / "superpowers")],
            "lastChangelogVersion": PI_VERSION,
            "subagents": default_pi_subagents_settings(),
        },
    )
    json_write(
        STATE / "pi/mcp.json",
        {
            "mcpServers": {
                "falcon-context": {
                    "command": str(server),
                    "args": ["--root", str(corpus), "--reader", str(reader)],
                    "exposure": "codemode",
                    "timeout": 60,
                },
                "kata": {
                    "command": str(ROOT / "kata/kata"),
                    "args": ["mcp", "serve"],
                    "cwd": str(ROOT),
                    "exposure": "direct",
                    "timeout": 30,
                    "env": {"KATA_SERVER": "http://127.0.0.1:17777"},
                },
                "kenn-forge": {
                    "type": "http",
                    "url": f"http://127.0.0.1:{FORGE_MCP_PORT}/mcp",
                    "exposure": "direct",
                    "timeout": 60,
                },
            }
        },
    )
    private_dir(STATE / "pi/extensions")
    forge_ext_src = ROOT / "scripts/pi-extensions/forge-workspace.ts"
    if forge_ext_src.is_file():
        private_write(
            STATE / "pi/extensions/forge-workspace.ts",
            forge_ext_src.read_text(),
            replace=True,
        )
    print(f"Persistent local settings/data: {STATE}")
    print(f"Private USAi key destination: {STATE / 'secrets/usai-api-key'}")
    print("Existing settings were preserved. No service or model request was started.")


def validate_key(key):
    key = key.strip()
    if not key or any(not 33 <= ord(character) <= 126 for character in key) or len(key) > 8192:
        raise RuntimeError("USAi key must be one nonempty token; its value was not logged")
    return key


def set_key(*, private_only=False):
    settings()
    private_dir(STATE / "secrets")
    if not sys.stdin.isatty():
        raise RuntimeError("run set-key in your terminal; do not pass a key as an argument or pipe")
    key = validate_key(getpass.getpass("USAi API key (hidden): "))
    path = STATE / "secrets/usai-api-key"
    if path.exists() or path.is_symlink():
        private_read(path)
    linked = 0 if private_only else link_cli_key()
    private_write(path, key + "\n", replace=True)
    print("USAi key saved privately (0600); its value was not logged.")
    if private_only:
        print("Global Pi credentials were not changed; only the private platform uses this key file.")
    else:
        print(f"Forge and {linked} existing global Pi USAi provider(s) use the same key file.")
    print("Restart existing Pi sessions after rotation; settings and sessions remain separate.")


def link_cli_key():
    command = "!" + shlex.join([sys.executable, str(ROOT / "scripts/usai-key.py")])
    auth_path = GLOBAL_PI / "auth.json"
    auth = json.loads(private_read(auth_path)) if auth_path.exists() or auth_path.is_symlink() else {}
    if not isinstance(auth, dict):
        raise RuntimeError(f"expected a global Pi auth object: {auth_path}")
    updates = []
    for name, section, provider_name in (
        ("models.json", "providers", "usai"),
        ("settings.json", "litellm", "litellm-usai"),
    ):
        path = GLOBAL_PI / name
        if not path.exists() and not path.is_symlink():
            continue
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "r") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o022):
                raise RuntimeError(f"expected an owned, non-writable-by-others Pi config: {path}")
            config = json.load(stream)
        if not isinstance(config, dict):
            raise RuntimeError(f"expected a global Pi config object: {path}")
        providers = config.get(section, {})
        if not isinstance(providers, dict):
            raise RuntimeError(f"invalid global Pi {section} configuration: {path}")
        if name == "settings.json":
            providers = providers.get("providers", {})
        if not isinstance(providers, dict):
            raise RuntimeError(f"invalid global Pi providers configuration: {path}")
        provider = providers.get(provider_name)
        if provider is None:
            continue
        if not isinstance(provider, dict):
            raise RuntimeError(f"invalid global Pi {provider_name} configuration: {path}")
        if provider_name in auth:
            raise RuntimeError(f"global Pi auth.json overrides {provider_name}; review that credential first")
        provider["apiKey"] = command
        updates.append((path, config))
    for path, config in updates:
        # Legacy global configs can be readable; replace them privately without retaining a key copy.
        os.chmod(path, 0o600, follow_symlinks=False)
        json_write(path, config, replace=True)
    return len(updates)


def validate_base_url(base_url):
    parsed = urllib.parse.urlsplit(base_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise RuntimeError("USAi base URL must be HTTPS without credentials, query or fragment")
    return base_url.rstrip("/")


def load_usai_key():
    private_dir(STATE / "secrets")
    try:
        return validate_key(private_read(STATE / "secrets/usai-api-key"))
    except UnicodeError as error:
        raise RuntimeError("USAi key file must contain a UTF-8 token; its value was not logged") from error


def list_models(base_url):
    settings()
    base_url = validate_base_url(base_url)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, file_pointer, code, message, headers, new_url):
            return None

    request = urllib.request.Request(
        base_url + "/models",
        headers={"Authorization": "Bearer " + load_usai_key(), "Accept": "application/json"},
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
            body = response.read(4 * 1024 * 1024 + 1)
            if len(body) > 4 * 1024 * 1024:
                raise RuntimeError("USAi model list exceeds the 4 MiB limit; no partial list was saved")
            payload = json.loads(body)
    except urllib.error.HTTPError as error:
        error.close()
        raise RuntimeError(
            f"USAi model list returned HTTP {error.code}; redirects are refused; response body not logged"
        ) from None
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise RuntimeError("USAi model list must contain a data array; no catalog was saved")
    ids = []
    for model in payload["data"]:
        if not isinstance(model, dict) or not isinstance(model.get("id"), str) or not model["id"].strip():
            raise RuntimeError("USAi model list has an invalid model ID; no partial catalog was saved")
        ids.append(model["id"])
    if not ids:
        raise RuntimeError("USAi returned an empty model list; no catalog was saved")
    ids = sorted(set(ids))
    json_write(STATE / "usai-models.json", {
        "base_url": base_url, "fetched_at": datetime.now(timezone.utc).isoformat(), "models": ids,
    }, replace=True)
    print(f"Saved {len(ids)} advertised model IDs to {STATE / 'usai-models.json'}")
    print("\n".join(ids))
    print("Discovery only: this does not verify a model's chat, streaming or tool-call protocol.")
    return ids


def configure_provider(base_url, model, api):
    settings()
    base_url = validate_base_url(base_url)
    if not model.strip() or any(character.isspace() for character in model):
        raise RuntimeError("supply the exact nonempty USAi model alias without whitespace")
    path = STATE / "pi/models.json"
    models = json.loads(private_read(path)) if path.exists() else {}
    providers = models.setdefault("providers", {})
    provider = providers.setdefault("usai", {})
    provider.update({"baseUrl": base_url, "api": api, "apiKey": "${USAI_API_KEY}"})
    entries = provider.setdefault("models", [])
    for required_model in (model, "gemini-4-argon"):
        if not any(entry.get("id") == required_model for entry in entries):
            entries.append({"id": required_model, "compat": {"supportsDeveloperRole": False}})
    for entry in entries:
        if isinstance(entry, dict) and entry.get("id"):
            compat = entry.get("compat")
            entry["compat"] = {**(compat if isinstance(compat, dict) else {}), "supportsDeveloperRole": False}
    json_write(path, models, replace=True)
    settings_path = STATE / "pi/settings.json"
    pi_settings = json.loads(private_read(settings_path)) if settings_path.exists() else {}
    pi_settings.update({"defaultProvider": "usai", "defaultModel": model})
    pi_settings["subagents"] = merge_pi_subagents_settings(pi_settings.get("subagents"))
    json_write(settings_path, pi_settings, replace=True)
    json_write(STATE / "usai.json", {"model": model}, replace=True)
    print("USAi provider configured without storing a key in model settings. No model call was made.")


def pi_launch(args):
    config = settings()
    executable = verify_pi(config)
    env = base_environment()
    if args and (args[0] == "mcp" or args == ["--version"] or args == ["--help"]):
        return [executable, *args], env
    for arg in args:
        if any(arg == flag or arg.startswith(flag + "=")
               for flag in ("--api-key", "--provider", "--model")):
            raise RuntimeError("the local agent uses the saved USAi model; configure-provider to change it")
    try:
        model = json.loads(private_read(STATE / "usai.json"))["model"]
        models = json.loads(private_read(STATE / "pi/models.json"))
        provider = models.get("providers", {}).get("usai", {})
        if not any(entry.get("id") == model for entry in provider.get("models", [])):
            raise RuntimeError(
                "saved USAi model is missing from pi/models.json; restore its verified model "
                "entry or explicitly configure-provider before launching; no custom-model fallback"
            )
        key = load_usai_key()
    except FileNotFoundError as error:
        raise RuntimeError("USAi is not ready: run configure-provider and set-key; no provider fallback") from error
    env["USAI_API_KEY"] = key
    return [executable, "--provider", "usai", "--model", model, *args], env


def install_pi_extensions():
    executable = verify_pi(settings())
    path = STATE / "pi/settings.json"
    private_read(path)
    for extension in PI_EXTENSIONS:
        subprocess.run(
            [executable, "install", extension],
            cwd=STATE / "home", env=base_environment(), check=True, timeout=180,
        )
        config = json.loads(private_read(path))
        if extension not in config.get("packages", []):
            raise RuntimeError(f"Pi did not save {extension} in the isolated profile")
    config = json.loads(private_read(path))
    config["subagents"] = merge_pi_subagents_settings(config.get("subagents"))
    json_write(path, config, replace=True)
    print(f"Installed {', '.join(PI_EXTENSIONS)} in the isolated Pi profile; no model request was made.")


def install_pi_review_extension():
    install_pi_extensions()


def roborev_warnings(*, proc_root=Path("/proc")):
    """Read-only diagnostics: never start or signal another daemon."""
    warnings = []
    for host, family in (("127.0.0.1", socket.AF_INET), ("::1", socket.AF_INET6)):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as probe:
                probe.settimeout(0.2)
                if probe.connect_ex((host, 7373)) == 0:
                    warnings.append(f"unexpected listener at {host}:7373; managed roborev uses 17373")
        except OSError:
            pass
    allowed = set()
    try:
        allowed.add(user_service_pid(ROBOREV_UNIT))
    except (OSError, RuntimeError, subprocess.SubprocessError):
        pass
    try:
        saved = supervisor()
    except (OSError, ValueError, KeyError, RuntimeError):
        saved = None
    if saved:
        allowed.add(saved.get("children", {}).get("roborev"))
    for entry in proc_root.glob("[0-9]*"):
        try:
            args = (entry / "cmdline").read_bytes().split(b"\0")
            if (Path(os.fsdecode(args[0])).name == "roborev"
                    and b"daemon" in args[1:] and b"run" in args[1:]
                    and int(entry.name) not in allowed):
                warnings.append(f"unmanaged roborev daemon PID {entry.name}; inspect before stopping it")
        except (OSError, ValueError):
            continue
    return warnings


def github_cli_launch(args):
    settings()
    private_dir(STATE / "gh")
    if not GH_BINARY.is_file() or not os.access(GH_BINARY, os.X_OK):
        raise RuntimeError("GitHub CLI is missing; run scripts/bootstrap-toolchains.sh")
    env = base_environment()
    env.pop("GH_PROMPT_DISABLED")
    return [str(GH_BINARY), *args], env


def terminal_launch(action, name="engi-platform"):
    if action not in ("open", "list", "stop"):
        raise RuntimeError("terminal action must be open, list or stop")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}", name):
        raise RuntimeError("session names must be 1-48 letters, digits, hyphens or underscores")
    settings()
    binary = shutil.which("tmux")
    if not binary:
        raise RuntimeError("tmux is missing; install it before using the terminal launcher")
    directory = STATE / "runtime/terminal"
    private_dir(directory.parent)
    private_dir(directory)
    endpoint = directory / "tmux.sock"
    if endpoint.exists() or endpoint.is_symlink():
        info = endpoint.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError(f"expected an owned tmux socket: {endpoint}")
    command = [
        binary, "-S", str(endpoint), "-f", str(ROOT / "scripts/terminal.tmux.conf"),
    ]
    if action == "open":
        command += ["new-session", "-A", "-s", name, "-c", str(ROOT)]
    elif action == "list":
        command += [
            "list-sessions", "-F",
            "#{session_name}: #{session_windows} windows (#{session_attached} attached)",
        ]
    else:
        command += ["kill-session", "-t", f"={name}"]
    environment = base_environment()
    # Copilot retains its existing authentication and session storage, unlike private Pi.
    home = Path.home()
    environment["HOME"] = str(home)
    for variable, default in (
        ("XDG_CONFIG_HOME", home / ".config"),
        ("XDG_DATA_HOME", home / ".local/share"),
        ("XDG_CACHE_HOME", home / ".cache"),
    ):
        environment[variable] = os.environ.get(variable, str(default))
    return command, environment


def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request("http://127.0.0.1:18091/api/v1" + path, data=data,
                                     method=method, headers={"Content-Type": "application/json"})
    with HTTP.open(request, timeout=15) as response:
        return json.load(response) if response.status != 204 else None


def register_project(path):
    path = path.expanduser().resolve()
    if not path.is_dir():
        raise RuntimeError(f"project directory does not exist: {path}")
    subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                   capture_output=True, check=True, timeout=15)
    for project in api("GET", "/projects")["projects"]:
        if Path(project["local_path"]).resolve() == path:
            print(f"Project retained: {project['display_name']} ({project['id']})", flush=True)
            return project
    project = api("POST", "/projects", {"local_path": str(path), "display_name": path.name})
    print(f"Project registered: {project['display_name']} ({project['id']})", flush=True)
    return project


def process_identity(pid):
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return fields[19]


def supervisor():
    path = STATE / "runtime/supervisor.json"
    try:
        saved = json.loads(private_read(path))
    except FileNotFoundError:
        return None
    try:
        identity = process_identity(saved["pid"])
    except FileNotFoundError:
        print(f"WARNING: supervisor PID {saved['pid']} has exited; "
              "stale supervisor metadata retained.", file=sys.stderr)
        return None
    if identity != saved["start_time"]:
        raise RuntimeError("saved supervisor PID was reused; refusing to signal it")
    return saved


def check_ports(ports=PORTS):
    for port in ports:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", port))


def agentsview_request(method, path, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    url = ("http://127.0.0.1:18080/api/ping" if path == "/ping"
           else "http://127.0.0.1:18080/api/v1" + path)
    request = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with HTTP.open(request, timeout=timeout) as response:
        return json.load(response)


def agentsview_command():
    args = [str(ROOT / "agentsview/agentsview"), "serve", "--host", "127.0.0.1",
            "--port", "18080", "--no-browser", "--no-update-check"]
    if not (STATE / "agentsview-tracking.json").exists():
        args.append("--no-sync")
    return args


def configure_tracking(copilot_dir, pi_dirs, archive_content):
    settings()
    copilot_dir = copilot_dir.expanduser().resolve()
    if not (copilot_dir / "session-state").is_dir():
        raise RuntimeError("Copilot source must contain its existing session-state directory")
    private_dir(STATE / "pi/sessions")
    pi_dirs = list(dict.fromkeys(str(path.expanduser().resolve()) for path in pi_dirs))
    if not pi_dirs or any(not Path(path).is_dir() for path in pi_dirs):
        raise RuntimeError("each Pi source must be an existing sessions directory")
    saved = agentsview_request("GET", "/settings")
    excluded = sorted(provider["id"] for provider in saved["session_providers"]
                      if provider["id"] not in ("copilot", "pi"))
    path = STATE / "agentsview/config.toml"
    # Share the application's config lock so UI settings writes cannot be lost.
    lock_fd = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, "rb") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("AgentsView config is busy; retry configure-tracking") from error
        text = private_read(path)
        config = tomllib.loads(text)
        prefix = ""
        for key, value in (("archive_content", archive_content), ("disabled_agents", excluded)):
            if key in config:
                if config[key] != value:
                    raise RuntimeError(f"existing AgentsView {key} differs; review the private config before changing it")
            else:
                prefix += f"{key} = {json.dumps(value)}\n"
        suffix = ""
        for agent, dirs in (("copilot", [str(copilot_dir)]), ("pi", pi_dirs)):
            existing = config.get("agents", {}).get(agent)
            if existing is not None:
                if existing.get("dirs") != dirs:
                    raise RuntimeError(f"existing AgentsView {agent} directories differ; review before changing them")
            else:
                suffix += f"\n[agents.{agent}]\ndirs = {json.dumps(dirs)}\n"
        updated = prefix + text + ("\n" + suffix if suffix else "")
        tomllib.loads(updated)
        private_write(path, updated, replace=True)
        json_write(STATE / "agentsview-tracking.json", {
            "copilot_dir": str(copilot_dir), "pi_dirs": pi_dirs,
            "archive_content": archive_content,
        }, replace=True)
    print("Copilot/Pi tracking configured; source files and model routing are unchanged.")
    print(f"Archive policy: {archive_content}. Restart AgentsView to enable ingestion.")


def agentsview_environment():
    env = base_environment()
    # Native Pi home overrides configured multi-directory discovery.
    env.pop("PI_CODING_AGENT_DIR")
    return env


def configure_private_pi_tracking():
    settings()
    sessions = STATE / "pi/sessions"
    private_dir(sessions)
    path = STATE / "agentsview/config.toml"
    metadata = STATE / "agentsview-tracking.json"
    expected = {"archive_content": "usage", "agents": {"pi": {"dirs": [str(sessions)]}}}
    lock_fd = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, "rb") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("AgentsView config is busy; retry configure-private-pi-tracking") from error
        config = tomllib.loads(private_read(path)) if path.exists() or path.is_symlink() else {}
        if metadata.exists() or metadata.is_symlink():
            tracking = json.loads(private_read(metadata))
            if config.get("archive_content") != tracking["archive_content"]:
                raise RuntimeError("existing AgentsView archive policy differs from tracking metadata")
            print("Existing configured AgentsView tracking preserved; no sources or archive policy changed.")
            return
        if config and config != expected:
            raise RuntimeError("existing AgentsView settings require explicit tracking configuration; not overwritten")
        private_write(path, 'archive_content = "usage"\n\n[agents.pi]\n'
                      f'dirs = {json.dumps([str(sessions)])}\n')
        json_write(metadata, {"copilot_dir": None, "pi_dirs": [str(sessions)],
                              "archive_content": "usage"})
    print("AgentsView configured offline for private Pi usage metadata only; no global sessions imported.")


def systemd_quote(value):
    value = str(value)
    if any(character in value for character in "\n\r\x00"):
        raise RuntimeError("systemd paths cannot contain line breaks or NUL")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$") + '"'


def install_agentsview_service():
    settings()
    if not (STATE / "agentsview-tracking.json").exists():
        raise RuntimeError("configure-tracking before installing the AgentsView service")
    install_user_service(
        AGENTSVIEW_UNIT, "agentsview-run", "Kenn Kopy local Copilot and Pi session tracking",
        SERVICE_PORTS["agentsview"], lambda: managed_agentsview(required=True),
    )
    json_write(STATE / "agentsview-service.json", {"unit": AGENTSVIEW_UNIT}, replace=True)
    print("AgentsView user service enabled and responsive at http://127.0.0.1:18080/")


def install_user_service(unit_name, command, description, ports, readiness, args=(),
                         executable=None, environment=(), working_directory=None,
                         require_stopped=False):
    active = subprocess.run(["systemctl", "--user", "is-active", "--quiet", unit_name],
                            timeout=15)
    if active.returncode == 0:
        if require_stopped:
            raise RuntimeError(f"finish reviews and stop {unit_name} before selecting a different binary")
        readiness()
    elif active.returncode in (3, 4):
        check_ports(ports)
    else:
        raise RuntimeError(f"cannot inspect {unit_name}")
    subprocess.run(["systemctl", "--user", "show-environment"], check=True,
                   stdout=subprocess.DEVNULL, timeout=15)
    directory = STATE / "systemd"
    private_dir(directory)
    unit = directory / unit_name
    executable = " ".join(systemd_quote(value) for value in (executable or (
        sys.executable, ROOT / "scripts/local_env.py", command, *args,
    )))
    environment_lines = "".join(f"Environment={systemd_quote(value)}\n" for value in environment)
    directory_line = ""
    if working_directory is not None:
        systemd_quote(working_directory)
        if not Path(working_directory).is_absolute():
            raise RuntimeError("systemd working directory must be absolute")
        directory_line = f"WorkingDirectory={str(working_directory).replace('%', '%%')}\n"
    text = (
        f"[Unit]\nDescription={description}\n"
        "[Service]\nType=simple\nUMask=0077\nNoNewPrivileges=true\n"
        f"{environment_lines}{directory_line}ExecStart={executable}\n"
        "Restart=on-failure\nRestartSec=5\nTimeoutStopSec=45\n"
        "[Install]\nWantedBy=default.target\n"
    )
    previous_unit = private_read(unit) if require_stopped and unit.exists() else None
    try:
        private_write(unit, text, replace=True)
        subprocess.run(["systemd-analyze", "--user", "verify", str(unit)], check=True, timeout=15)
        subprocess.run(["systemctl", "--user", "link", str(unit)], check=True, timeout=15)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, timeout=15)
        subprocess.run(["systemctl", "--user", "enable", "--now", unit_name],
                       check=True, timeout=60)
        deadline = time.monotonic() + 60
        while True:
            try:
                readiness()
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError, FileNotFoundError):
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"{unit_name} readiness timed out; inspect its user journal")
                time.sleep(0.5)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        if require_stopped:
            if previous_unit is None:
                unit.unlink(missing_ok=True)
            else:
                private_write(unit, previous_unit, replace=True)
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, timeout=15)
        raise


def user_service_pid(unit_name):
    result = subprocess.run(
        ["systemctl", "--user", "show", unit_name,
         "--property=ActiveState,MainPID"], check=True, text=True, capture_output=True, timeout=15,
    )
    properties = dict(line.split("=", 1) for line in result.stdout.splitlines())
    if properties["ActiveState"] != "active" or int(properties["MainPID"]) <= 0:
        raise RuntimeError(f"{unit_name} is not active; start it with systemctl --user")
    return int(properties["MainPID"])


def managed_agentsview(*, required=False):
    if not required and not (STATE / "agentsview-service.json").exists():
        return None
    pid = user_service_pid(AGENTSVIEW_UNIT)
    health = agentsview_request("GET", "/ping", timeout=3)
    if health.get("pid") != pid or health.get("healthy") is not True or not health.get("version"):
        raise RuntimeError("AgentsView health does not match the managed user service")
    return {"unit": AGENTSVIEW_UNIT, "pid": pid, "version": health["version"]}


def agentsview_run():
    settings()
    tracking = json.loads(private_read(STATE / "agentsview-tracking.json"))
    config = tomllib.loads(private_read(STATE / "agentsview/config.toml"))
    if config.get("archive_content") != tracking["archive_content"]:
        raise RuntimeError("AgentsView archive policy differs from the configured tracking policy")
    check_ports((18080,))
    command = agentsview_command()
    os.chdir(STATE / "home")
    os.execve(command[0], command, agentsview_environment())


def validate_roborev_config():
    config = tomllib.loads(private_read(STATE / "roborev/config.toml"))
    if (config.get("server_addr") != "127.0.0.1:17373"
            or config.get("web", {}).get("listen") != "127.0.0.1:17374"):
        raise RuntimeError("roborev must retain the documented loopback API and UI ports")


def node_environment(node_executable, *, roborev_executable=None):
    node = node_executable.expanduser().resolve()
    if not node.is_file() or not os.access(node, os.X_OK):
        raise RuntimeError(f"missing executable Node runtime for Pi agents: {node}")
    env = base_environment(roborev_executable)
    env["PATH"] = str(node.parent) + os.pathsep + env["PATH"]
    return env


def roborev_binary():
    marker = STATE / "roborev-service.json"
    if marker.exists():
        saved = json.loads(private_read(marker))
        if "binary" in saved:
            binary = Path(saved["binary"])
            if not binary.is_absolute():
                raise RuntimeError("saved roborev binary must be an absolute path")
            return binary
    return ROOT / "roborev/bin/roborev"


def roborev_command(binary=None):
    binary = roborev_binary() if binary is None else binary
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"missing executable roborev binary: {binary}")
    return [str(binary), "daemon", "run",
            "--addr", "127.0.0.1:17373", "--config", str(STATE / "roborev/config.toml")]


def install_roborev_service(binary=None):
    config = settings()
    validate_roborev_config()
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node must be on this shell's PATH before installing roborev")
    node = Path(node).resolve()
    previous_binary = roborev_binary()
    binary = previous_binary if binary is None else binary.expanduser().resolve()
    command = roborev_command(binary)
    env = node_environment(node, roborev_executable=binary)
    verify_pi(config, env=env)
    install_user_service(
        ROBOREV_UNIT, None, "Engi Platform local code review",
        SERVICE_PORTS["roborev"], lambda: managed_roborev(required=True, binary=binary),
        executable=command, environment=tuple(f"{key}={value}" for key, value in env.items()),
        working_directory=STATE / "home",
        require_stopped=binary != previous_binary,
    )
    json_write(STATE / "roborev-service.json", {"unit": ROBOREV_UNIT, "binary": str(binary)}, replace=True)
    print("roborev user service enabled and responsive at http://127.0.0.1:17374/reviews")


def managed_roborev(*, required=False, binary=None):
    if not required and not (STATE / "roborev-service.json").exists():
        return None
    pid = user_service_pid(ROBOREV_UNIT)
    if binary is not None and not os.path.samefile(f"/proc/{pid}/exe", binary):
        raise RuntimeError("running roborev executable differs from the requested binary; "
                           "finish reviews, stop the service and reinstall before restarting")
    with HTTP.open("http://127.0.0.1:17373/api/ping", timeout=3) as response:
        health = json.load(response)
    if health.get("pid") != pid or health.get("ok") is not True or not health.get("version"):
        raise RuntimeError("roborev health does not match the managed user service")
    with HTTP.open("http://127.0.0.1:17373/api/status", timeout=3) as response:
        status = json.load(response)
    if status.get("version") != health["version"]:
        raise RuntimeError("roborev database status does not match its health version")
    request = urllib.request.Request("http://127.0.0.1:17374/reviews",
                                     headers={"Accept": "text/html"})
    with HTTP.open(request, timeout=3) as response:
        if response.status != 200 or "text/html" not in response.headers.get("Content-Type", ""):
            raise RuntimeError("roborev review dashboard is not healthy")
    return {"unit": ROBOREV_UNIT, "pid": pid, "version": health["version"]}


def roborev_run(node_executable):
    config = settings()
    validate_roborev_config()
    env = node_environment(node_executable)
    verify_pi(config, env=env)
    check_ports(SERVICE_PORTS["roborev"])
    command = roborev_command()
    os.chdir(STATE / "home")
    os.execve(command[0], command, env)


def validate_forge_config():
    config = tomllib.loads(private_read(STATE / "forge/config.toml"))
    if config.get("host") != "127.0.0.1" or config.get("port") != FORGE_PORT:
        raise RuntimeError("Forge must retain the documented loopback port")
    return config


def forge_command(config):
    binary = Path(config["forge_binary"])
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"missing executable Forge binary: {binary}")
    forge_config = validate_forge_config()
    command = [str(binary), "serve", "--config", str(STATE / "forge/config.toml"),
               "--host", "127.0.0.1", "--port", str(FORGE_PORT)]
    if not forge_config.get("repos"):
        command.append("--disable-sync")
    return command


def forge_probe():
    """Report an unmanaged Forge; managed service health is checked separately."""
    try:
        with HTTP.open(f"http://127.0.0.1:{FORGE_PORT}/healthz", timeout=3) as response:
            health = json.load(response)
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError):
        return None
    if health.get("status") != "ok" or not health.get("version"):
        raise RuntimeError("something is answering the Forge port without healthy Forge identity")
    return {"managed": False, "version": health["version"],
            "revision": health.get("revision")}


def install_forge_service():
    config = settings()
    validate_forge_config()
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node must be on this shell's PATH before installing Forge")
    node = Path(node).resolve()
    verify_pi(config, env=node_environment(node))
    forge_command(config)
    private_dir(STATE / "gh")
    install_user_service(
        FORGE_UNIT, "forge-run", "Engi Platform local workspaces and coding agents",
        SERVICE_PORTS["forge"], lambda: managed_forge(required=True),
        args=("--node-executable", node),
    )
    json_write(STATE / "forge-service.json", {"unit": FORGE_UNIT}, replace=True)
    print("Forge user service enabled and responsive at http://127.0.0.1:18091/")


def managed_forge(*, required=False):
    if not required and not (STATE / "forge-service.json").exists():
        return None
    pid = user_service_pid(FORGE_UNIT)
    private_dir(STATE / "forge")
    path = STATE / "forge" / f"daemon.{pid}.json"
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "r") as stream:
        info = os.fstat(stream.fileno())
        # Native runtime metadata can be 0644 inside the private data directory.
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o022):
            raise RuntimeError(f"expected owned, non-writable-by-others Forge runtime metadata: {path}")
        runtime = json.load(stream)
    if (runtime.get("pid") != pid or runtime.get("service") != "kenn-forge"
            or runtime.get("address") != f"127.0.0.1:{FORGE_PORT}"
            or runtime.get("metadata", {}).get("data_dir") != str(STATE / "forge")
            or runtime.get("metadata", {}).get("config_path") != str(STATE / "forge/config.toml")):
        raise RuntimeError("Forge runtime identity does not match the managed user service")
    with HTTP.open(f"http://127.0.0.1:{FORGE_PORT}/healthz", timeout=3) as response:
        health = json.load(response)
    if (health.get("status") != "ok" or not health.get("version")
            or health["version"] != runtime.get("version") or not health.get("revision")):
        raise RuntimeError("Forge database health does not match its runtime identity")
    with HTTP.open(f"http://127.0.0.1:{FORGE_PORT}/", timeout=3) as response:
        if response.status != 200 or "text/html" not in response.headers.get("Content-Type", ""):
            raise RuntimeError("Forge dashboard is not healthy")
    return {"unit": FORGE_UNIT, "pid": pid, "version": health["version"],
            "revision": health["revision"]}


def forge_run(node_executable=None):
    config = settings()
    validate_forge_config()
    if node_executable is None:
        node = shutil.which("node")
        if node is None:
            raise RuntimeError("Node must be on this shell's PATH or passed with --node-executable")
        node_executable = Path(node).resolve()
    env = node_environment(node_executable)
    verify_pi(config, env=env)
    check_ports((FORGE_PORT,))
    command = forge_command(config)
    private_dir(STATE / "gh")
    os.chdir(STATE / "home")
    os.execve(command[0], command, env)


def validate_kata_config():
    config = tomllib.loads(private_read(STATE / "kata/config.toml"))
    if config.get("listen") != "127.0.0.1:17777" or config.get("web", {}).get("listen"):
        raise RuntimeError("Kata must retain the documented loopback API and shared UI port")


def kata_command():
    binary = ROOT / "kata/kata"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError("missing executable Kata binary; build it before starting the service")
    return [str(binary), "daemon", "start", "--foreground", "--no-auto-token",
            "--listen", "127.0.0.1:17777"]


def kata_environment():
    return {
        "HOME": str(Path.home()),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "KATA_HOME": str(STATE / "kata"),
        "KATA_DSN": str(STATE / "kata/kata.db"),
        "KATA_DB": "",
        "KATA_TELEMETRY_ENABLED": "0",
    }


def kata_service_command():
    env = Path("/usr/bin/env")
    if not env.is_file() or not os.access(env, os.X_OK):
        raise RuntimeError("missing /usr/bin/env required to isolate the Kata service environment")
    environment = [f"{key}={value}" for key, value in kata_environment().items()]
    return [str(env), "-i", *environment, *kata_command()]


def install_kata_service():
    settings()
    validate_kata_config()
    install_user_service(
        KATA_UNIT, None, "Engi Platform local task ledger",
        SERVICE_PORTS["kata"], lambda: managed_kata(required=True),
        executable=kata_service_command(),
    )
    json_write(STATE / "kata-service.json", {"unit": KATA_UNIT}, replace=True)
    print("Kata user service enabled and responsive at http://127.0.0.1:17777/kata")


def managed_kata(*, required=False):
    if not required and not (STATE / "kata-service.json").exists():
        return None
    pid = user_service_pid(KATA_UNIT)
    with HTTP.open("http://127.0.0.1:17777/api/v1/ping", timeout=3) as response:
        ping = json.load(response)
    if (ping.get("pid") != pid or ping.get("service") != "kata"
            or ping.get("ok") is not True or not ping.get("version")):
        raise RuntimeError("Kata health does not match the managed user service")
    with HTTP.open("http://127.0.0.1:17777/api/v1/health", timeout=3) as response:
        health = json.load(response)
    if (health.get("ok") is not True or health.get("version") != ping["version"]
            or health.get("db_path") != str(STATE / "kata/kata.db")
            or type(health.get("schema_version")) is not int or health["schema_version"] <= 0
            or not health.get("api_schema_version")):
        raise RuntimeError("Kata database health does not match its private profile")
    request = urllib.request.Request("http://127.0.0.1:17777/kata",
                                     headers={"Accept": "text/html"})
    with HTTP.open(request, timeout=3) as response:
        if response.status != 200 or "text/html" not in response.headers.get("Content-Type", ""):
            raise RuntimeError("Kata task dashboard is not healthy")
    return {"unit": KATA_UNIT, "pid": pid, "version": ping["version"],
            "schema_version": health["schema_version"],
            "api_schema_version": health["api_schema_version"]}


def managed_services():
    services = {"agentsview": managed_agentsview(), "roborev": managed_roborev(),
                "kata": managed_kata(), "forge": managed_forge()}
    return {name: service for name, service in services.items() if service is not None}


def supervised_ports(external_services):
    external_ports = {port for name in external_services for port in SERVICE_PORTS[name]}
    return tuple(port for port in PORTS if port not in external_ports)


def status():
    settings()
    external = managed_services()
    saved = supervisor()
    if saved and external:
        saved.setdefault("external_services", {}).update(external)
    forge = {"managed": True, **external["forge"]} if "forge" in external else forge_probe()
    return {"stack": "running" if saved else "stopped", "supervisor": saved,
            "agentsview_service": external.get("agentsview"),
            "roborev_service": external.get("roborev"),
            "roborev_warnings": roborev_warnings(),
            "forge_service": external.get("forge"),
            "forge": forge,
            "kata_service": external.get("kata"),
            "projects": api("GET", "/projects") if forge else None}


def serve():
    config = settings()
    verify_pi(config)
    lock_fd = os.open(STATE / "runtime/owner.lock",
                      os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    children = []
    saved_supervisor = False
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("the local environment already has an owner; use status or stop") from error
        external = managed_services()
        owned_ports = supervised_ports(external)
        check_ports(owned_ports)
        validate_roborev_config()
        validate_kata_config()
        forge = forge_command(config)
        roborev = roborev_command()
        services = [
            ("roborev", Path(roborev[0]), roborev[1:],
             "http://127.0.0.1:17373/api/status"),
            ("kata", ROOT / "kata/kata", kata_command()[1:],
             "http://127.0.0.1:17777/api/v1/health"),
            ("agentsview", ROOT / "agentsview/agentsview", agentsview_command()[1:],
             "http://127.0.0.1:18080/api/ping"),
            ("forge", Path(forge[0]), forge[1:], f"http://127.0.0.1:{FORGE_PORT}/healthz"),
        ]
        services = [service for service in services if service[0] not in external]
        for name, service in external.items():
            print(f"{name} retained under {service['unit']} (PID {service['pid']})", flush=True)
        def interrupted(signum, _frame):
            raise SystemExit(128 + signum)

        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, interrupted)
        for name, binary, args, health in services:
            if not binary.is_file():
                raise RuntimeError(f"missing {name} binary: {binary}")
            log_path = STATE / "logs" / f"{name}.log"
            private_write(log_path, "")
            env = agentsview_environment() if name == "agentsview" else base_environment()
            if name == "kata":
                env.update(kata_environment())
            with open(log_path, "a") as log:
                process = subprocess.Popen([str(binary), *args], cwd=STATE / "home",
                                           env=env,
                                           stdin=subprocess.DEVNULL,
                                           stdout=log, stderr=subprocess.STDOUT)
            children.append((name, process))
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"{name} exited {process.returncode}; inspect {log_path}")
                try:
                    with HTTP.open(health, timeout=2) as response:
                        payload = json.load(response)
                    if not payload.get("version"):
                        raise RuntimeError(f"{name} health response has no version")
                    if name in ("kata", "agentsview") and payload.get("ok") is not True:
                        raise RuntimeError(f"{name} did not report a healthy API")
                    if name == "forge" and payload.get("status") != "ok":
                        raise RuntimeError("Forge did not report a healthy API")
                    if name == "agentsview" and (
                            payload.get("pid") != process.pid or payload.get("healthy") is not True):
                        raise RuntimeError("AgentsView answered from another process or is unhealthy")
                    break
                except (urllib.error.URLError, TimeoutError, ConnectionError):
                    if time.monotonic() >= deadline:
                        raise RuntimeError(f"{name} readiness timed out; inspect {log_path}")
                    time.sleep(0.2)
            print(f"{name} ready (PID {process.pid})", flush=True)
        saved = {"pid": os.getpid(), "start_time": process_identity(os.getpid()),
                 "children": {name: process.pid for name, process in children},
                 "external_services": external}
        json_write(STATE / "runtime/supervisor.json", saved, replace=True)
        saved_supervisor = True
        print(f"Local environment ready; Forge: http://127.0.0.1:{FORGE_PORT}/", flush=True)
        print("Ctrl+C or `python3 scripts/local_env.py stop` stops owned services, not saved data.", flush=True)
        while True:
            for name, process in children:
                if process.poll() is not None:
                    raise RuntimeError(f"{name} exited {process.returncode}; stopping owned services")
            time.sleep(0.5)
    finally:
        failures = []
        for name, process in reversed(children):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                failures.append(f"{name} required SIGKILL")
            print(f"{name} stopped", flush=True)
        if children or saved_supervisor:
            try:
                check_ports(owned_ports)
            except OSError:
                failures.append("a documented listener port is still occupied")
            json_write(STATE / "runtime/shutdown.json", {"ok": not failures, "errors": failures},
                       replace=True)
            (STATE / "runtime/supervisor.json").unlink(missing_ok=True)
        os.close(lock_fd)
        if failures:
            raise RuntimeError("; ".join(failures))


def stop():
    settings()
    saved = supervisor()
    if saved is None:
        print("No live supervisor; no process was signaled. "
              "Independently managed services were left untouched.")
        return
    os.kill(saved["pid"], signal.SIGTERM)
    deadline = time.monotonic() + 70
    while (STATE / "runtime/supervisor.json").exists():
        if time.monotonic() >= deadline:
            raise RuntimeError("supervisor shutdown timed out; inspect local logs; no other PID was signaled")
        time.sleep(0.2)
    result = json.loads(private_read(STATE / "runtime/shutdown.json"))
    if not result["ok"]:
        raise RuntimeError("shutdown was incomplete: " + "; ".join(result["errors"]))
    saved_external = saved.get("external_services", {})
    check_ports(supervised_ports(saved_external))
    print("Owned services stopped; settings, projects, sessions and databases are retained.")
    for name, service in saved_external.items():
        print(f"{name} is managed separately by {service['unit']}; this command did not stop it.")


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("setup", help="create missing private settings without overwriting existing ones")
    init.add_argument("--corpus", type=Path, required=True)
    init.add_argument("--forge-binary", type=Path, required=True)
    commands.add_parser("run", help="run supervised services; retain independent services and saved state")
    commands.add_parser("stop", help="signal only the verified local supervisor")
    commands.add_parser("status", help="show the verified supervisor and persistent project registry")
    key = commands.add_parser("set-key", help="prompt privately for the USAi key; never supply it on the command line")
    key.add_argument("--private-only", action="store_true", help="do not link/change existing global Pi credentials")
    commands.add_parser("configure-private-pi-tracking",
                        help="configure fresh AgentsView for private Pi usage only, without starting it")
    tracking = commands.add_parser("configure-tracking", help="configure explicit Copilot/Pi archive sources")
    tracking.add_argument("--copilot-dir", type=Path, required=True)
    tracking.add_argument("--pi-dir", type=Path, action="append", required=True)
    tracking.add_argument("--archive-content", choices=("usage", "transcripts", "full"), required=True)
    commands.add_parser("install-agentsview-service", help="enable the configured AgentsView user service")
    commands.add_parser("agentsview-run", help="run the standalone configured AgentsView service")
    review_install = commands.add_parser("install-roborev-service",
                                        help="enable the configured native roborev user service")
    review_install.add_argument("--binary", type=Path, help="select an existing native roborev executable")
    commands.add_parser("install-pi-extensions", help="install pinned extensions in private Pi only")
    commands.add_parser("install-pi-review-extension", help="compatibility alias for install-pi-extensions")
    review_service = commands.add_parser("roborev-run", help="run the standalone configured roborev service")
    review_service.add_argument("--node-executable", type=Path, required=True)
    commands.add_parser("install-forge-service", help="enable the configured Forge user service")
    forge_service = commands.add_parser("forge-run", help="run the configured Forge service in the foreground")
    forge_service.add_argument("--node-executable", type=Path)
    commands.add_parser("install-kata-service", help="enable the configured Kata user service")
    catalog = commands.add_parser("list-models", help="refresh advertised USAi model IDs using the private key")
    catalog.add_argument("--base-url", required=True)
    provider = commands.add_parser("configure-provider", help="set non-secret USAi connection details")
    provider.add_argument("--base-url", required=True)
    provider.add_argument("--model", required=True)
    provider.add_argument("--api", required=True,
                          choices=("openai-completions", "openai-responses", "anthropic-messages"))
    register = commands.add_parser("register", help="register an existing local Git project without editing it")
    register.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "setup":
            setup(args.corpus, args.forge_binary)
        elif args.command == "run":
            serve()
        elif args.command == "stop":
            stop()
        elif args.command == "status":
            print(json.dumps(status(), indent=2))
        elif args.command == "set-key":
            set_key(private_only=args.private_only)
        elif args.command == "configure-private-pi-tracking":
            configure_private_pi_tracking()
        elif args.command == "configure-tracking":
            configure_tracking(args.copilot_dir, args.pi_dir, args.archive_content)
        elif args.command == "install-agentsview-service":
            install_agentsview_service()
        elif args.command == "agentsview-run":
            agentsview_run()
        elif args.command == "install-roborev-service":
            install_roborev_service(args.binary)
        elif args.command in ("install-pi-extensions", "install-pi-review-extension"):
            install_pi_extensions()
        elif args.command == "roborev-run":
            roborev_run(args.node_executable)
        elif args.command == "forge-run":
            forge_run(args.node_executable)
        elif args.command == "install-forge-service":
            install_forge_service()
        elif args.command == "install-kata-service":
            install_kata_service()
        elif args.command == "configure-provider":
            configure_provider(args.base_url, args.model, args.api)
        elif args.command == "list-models":
            list_models(args.base_url)
        elif args.command == "register":
            settings()
            if forge_probe() is None:
                raise RuntimeError("start the Forge service or `forge-run` before registering a project")
            register_project(args.path)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
