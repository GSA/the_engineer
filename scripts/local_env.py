#!/usr/bin/env python3
"""Manage the persistent, workspace-local engineering environment."""

import argparse
import contextlib
from datetime import datetime, timezone
import fcntl
import getpass
import io
import json
import os
from pathlib import Path
import pwd
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
import zipfile


ROOT = Path(__file__).resolve().parent.parent


def resolve_runtime_root(source_root, environment=None):
    environment = os.environ if environment is None else environment
    override = environment.get("KENN_KOPY_RUNTIME_ROOT")
    if override:
        runtime_root = Path(override).expanduser()
        if not runtime_root.is_absolute():
            raise RuntimeError("KENN_KOPY_RUNTIME_ROOT must be an absolute path")
        runtime_root = runtime_root.resolve()
        if not runtime_root.is_dir():
            raise RuntimeError("KENN_KOPY_RUNTIME_ROOT must name an existing directory")
        return runtime_root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=source_root, text=True, capture_output=True, check=False, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return source_root
    if result.returncode != 0 or not result.stdout.strip():
        return source_root
    common = Path(result.stdout.strip())
    if not common.is_absolute():
        common = source_root / common
    common = common.resolve()
    return source_root if common == (source_root / ".git").resolve() else common.parent


RUNTIME_ROOT = resolve_runtime_root(ROOT)
# The one canonical coder contract; setup installs it as the private Pi AGENTS.md.
CODER_CONTRACT = ROOT / "scripts/pi-coder-contract.md"
STATE = RUNTIME_ROOT / ".local/environment"
GLOBAL_PI = Path.home() / ".pi/agent"
PI_VERSION = "1.5.2"
LEGACY_PI_REVIEW_EXTENSION = "npm:@nqbao/pi-json-schema@0.1.1"
PI_REVIEW_EXTENSION_PATH = RUNTIME_ROOT / "scripts/pi-extensions/json-schema.ts"
PI_REVIEW_EXTENSION = str(PI_REVIEW_EXTENSION_PATH)
PI_SUBAGENTS_EXTENSION = "npm:pi-subagents@0.88.0"
PI_EXTENSIONS = (PI_SUBAGENTS_EXTENSION,)
PI_DISABLED_BUILTIN_SUBAGENTS = (
    "claude-code",
    "claude-code-writer",
    "codex-exec",
    "codex-exec-writer",
    "cursor-agent",
    "cursor-agent-writer",
    "evidence-auditor",
    "researcher",
)
PI_PASSTHROUGH_SUBCOMMANDS = frozenset({"mcp", "list", "config", "install", "remove", "update"})
USAI_EMBEDDING_MODELS = frozenset({"cohere-v4", "cohere_english_v3", "text-embedding-005"})
ADVERSARIAL_MODEL_FAMILIES = frozenset({"claude", "openai", "gemini"})
USAI_CHAT_MODELS = (
    "claude-haiku-5.5",
    "claude-opus-5",
    "claude-opus-5.5",
    "claude-sonnet-5",
    "claude-sonnet-5.5",
    "claude_4_5_haiku",
    "claude_4_5_sonnet",
    "claude_4_6_sonnet",
    "claude_4_7_opus",
    "claude_4_8_opus",
    "gemini-3-7-flash",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-4-argon",
    "gpt-5.6-luna",
    "gpt-5.6-sol-latest-guardrails-defaultv2",
    "gpt-5.6-terra",
    "gpt-6-astra",
    "gpt-6-luna",
    "gpt-6-luna-guardrails-high",
    "gpt-6-sol-latest-guardrails-defaultv2",
    "gpt-6.1-sol-latest-guardrails-defaultv2",
    "gpt_5_2_default_v2",
    "gpt_5_4_default_v2",
    "gpt_5_5_default_v2",
    "llama_4_maverick",
)
# Deliberate caps below the providers' ~1M windows: Pi compacts at
# contextWindow - compaction.reserveTokens, and unset models default to 128k.
# GPT stays at 272k, below the providers' higher-priced long-context tier.
# Models without an entry keep Pi's 128k/16k defaults.
USAI_MODEL_LIMITS = {
    **{model: {"contextWindow": 400_000, "maxTokens": 32_000} for model in (
        "claude-haiku-5.5", "claude-opus-5", "claude-opus-5.5", "claude-sonnet-5.5", "gemini-4-argon",
    )},
    **{model: {"contextWindow": 272_000, "maxTokens": 32_000} for model in (
        "gpt-5.6-sol-latest-guardrails-defaultv2", "gpt-6.1-sol-latest-guardrails-defaultv2",
    )},
}
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
GH_BINARY = RUNTIME_ROOT / f".local/tools/gh-{GH_VERSION}/bin/gh"
JQ_VERSION = "1.7.1"
JQ_BINARY = RUNTIME_ROOT / f".local/tools/jq-{JQ_VERSION}/bin/jq"
PYDEPS_DIR = RUNTIME_ROOT / ".local/tools/pydeps"
DEFAULT_PORTS = {"roborev": 17373, "roborev_web": 17374, "kata": 17777,
                 "agentsview": 18080, "forge": 18091, "forge_mcp": 18092}
AGENTSVIEW_UNIT = "kenn-kopy-agentsview.service"
ROBOREV_UNIT = "kenn-kopy-roborev.service"
FORGE_UNIT = "kenn-kopy-forge.service"
KATA_UNIT = "kenn-kopy-kata.service"
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def parse_port_offset(value, source="KENN_KOPY_PORT_OFFSET"):
    if isinstance(value, str):
        if not re.fullmatch(r"\d{1,5}", value.strip()):
            raise RuntimeError(f"{source} must be a non-negative integer")
        value = int(value.strip())
    if type(value) is not int or value < 0:
        raise RuntimeError(f"{source} must be a non-negative integer")
    shifted = {port + value for port in DEFAULT_PORTS.values()}
    if max(shifted) > 65535:
        raise RuntimeError(f"{source} moves a service port above 65535")
    # Distros on one WSL2 VM share 127.0.0.1, so a shifted stack must avoid every default port.
    if value and shifted & set(DEFAULT_PORTS.values()):
        raise RuntimeError(f"{source}={value} overlaps the default ports; use e.g. 1000")
    return value


def resolve_port_offset(environment=None, config_path=None):
    """Use KENN_KOPY_PORT_OFFSET, else the offset saved by setup, else 0."""
    environment = os.environ if environment is None else environment
    if environment.get("KENN_KOPY_PORT_OFFSET", "").strip():
        return parse_port_offset(environment["KENN_KOPY_PORT_OFFSET"])
    config_path = STATE / "environment.json" if config_path is None else config_path
    try:
        saved = json.loads(Path(config_path).read_text())
    except (OSError, ValueError):
        return 0
    return parse_port_offset(saved.get("port_offset", 0), "saved port_offset")


def configure_ports(offset):
    global PORT_OFFSET, ROBOREV_PORT, ROBOREV_WEB_PORT, KATA_PORT, AGENTSVIEW_PORT
    global FORGE_PORT, FORGE_MCP_PORT, KATA_URL, PORTS, SERVICE_PORTS
    PORT_OFFSET = parse_port_offset(offset)
    ROBOREV_PORT = DEFAULT_PORTS["roborev"] + PORT_OFFSET
    ROBOREV_WEB_PORT = DEFAULT_PORTS["roborev_web"] + PORT_OFFSET
    KATA_PORT = DEFAULT_PORTS["kata"] + PORT_OFFSET
    AGENTSVIEW_PORT = DEFAULT_PORTS["agentsview"] + PORT_OFFSET
    FORGE_PORT = DEFAULT_PORTS["forge"] + PORT_OFFSET
    FORGE_MCP_PORT = DEFAULT_PORTS["forge_mcp"] + PORT_OFFSET
    KATA_URL = f"http://127.0.0.1:{KATA_PORT}"
    PORTS = (ROBOREV_PORT, ROBOREV_WEB_PORT, KATA_PORT, AGENTSVIEW_PORT, FORGE_PORT)
    SERVICE_PORTS = {"agentsview": (AGENTSVIEW_PORT,), "roborev": (ROBOREV_PORT, ROBOREV_WEB_PORT),
                     "kata": (KATA_PORT,), "forge": (FORGE_PORT,)}


configure_ports(resolve_port_offset())


def private_dir(path, *, create=True):
    if create:
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


def install_forge_extension():
    """Install the Forge workspace extension directory; Pi loads extensions/forge-workspace/index.ts.

    The superseded single-file extensions/forge-workspace.ts is removed so Pi never loads both.
    """
    source = RUNTIME_ROOT / "scripts/pi-extensions/forge-workspace"
    destination = STATE / "pi/extensions/forge-workspace"
    legacy = STATE / "pi/extensions/forge-workspace.ts"
    if not source.is_dir():
        return
    private_dir(STATE / "pi/extensions")
    private_dir(destination)
    names = {path.name: path for path in source.glob("*.ts")}
    for name, path in names.items():
        private_write(destination / name, path.read_text(), replace=True)
    for stale in destination.iterdir():
        if stale.name not in names:
            stale.unlink()
    legacy.unlink(missing_ok=True)


def json_write(path, value, *, replace=False):
    private_write(path, json.dumps(value, indent=2) + "\n", replace=replace)


def settings(*, create=True):
    private_dir(STATE, create=create)
    config = json.loads(private_read(STATE / "environment.json"))
    saved = parse_port_offset(config.get("port_offset", 0), "saved port_offset")
    if saved != PORT_OFFSET:
        raise RuntimeError(f"KENN_KOPY_PORT_OFFSET={PORT_OFFSET} differs from the saved "
                           f"port_offset {saved}; unset it or rerun setup in a fresh environment")
    return config


def host_git_settings(host_config=None):
    host_config = (Path.home() / ".gitconfig") if host_config is None else Path(host_config)
    values = {}
    if not host_config.is_file():
        return values
    try:
        section = ""
        for raw_line in host_config.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("#", ";")):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip().split()[0].lower()
                continue
            if "=" in line and section in ("user", "http"):
                key, value = (part.strip() for part in line.split("=", 1))
                if value:
                    values[f"{section}.{key.lower()}"] = value
    except OSError:
        return {}
    return values


def seed_isolated_gitconfig(home=None, *, host_config=None):
    home = (STATE / "home") if home is None else Path(home)
    private_dir(home)
    path = home / ".gitconfig"
    existing = private_read(path) if (path.exists() or path.is_symlink()) else ""
    host = host_git_settings(host_config)
    blocks = []
    if "[http]" not in existing and host.get("http.sslcainfo"):
        blocks.append(f"[http]\n\tsslCAinfo = {host['http.sslcainfo']}\n")
    if "[user]" not in existing and host.get("user.name") and host.get("user.email"):
        blocks.append(
            f"[user]\n\tname = {host['user.name']}\n\temail = {host['user.email']}\n"
        )
    if '[credential "https://github.com"]' not in existing:
        blocks.append(
            '[credential "https://github.com"]\n'
            "\thelper = \n"
            f"\thelper = !{GH_BINARY} auth git-credential\n"
            '[credential "https://gist.github.com"]\n'
            "\thelper = \n"
            f"\thelper = !{GH_BINARY} auth git-credential\n"
        )
    if blocks:
        updated = existing + ("" if not existing or existing.endswith("\n") else "\n") + "".join(blocks)
        private_write(path, updated, replace=True)
    git_config_dir = home / ".config/git"
    private_dir(home / ".config")
    private_dir(git_config_dir)
    ignore_path = git_config_dir / "ignore"
    existing_ignore = private_read(ignore_path) if (ignore_path.exists() or ignore_path.is_symlink()) else ""
    required_ignores = ("/AGENTS.override.md", "/.superpowers/", "/.local/", "/.roborev/")
    missing_ignores = [entry for entry in required_ignores if entry not in existing_ignore.splitlines()]
    if missing_ignores:
        updated_ignore = (
            existing_ignore
            + ("" if not existing_ignore or existing_ignore.endswith("\n") else "\n")
            + "\n".join(missing_ignores)
            + "\n"
        )
        private_write(ignore_path, updated_ignore, replace=True)


def base_environment(roborev_executable=None):
    home = STATE / "home"
    roborev_executable = roborev_binary() if roborev_executable is None else roborev_executable
    env = {
        "PATH": os.pathsep.join([str(GH_BINARY.parent), str(roborev_executable.parent),
                                str(RUNTIME_ROOT / "kata"), str(RUNTIME_ROOT / "agentsview"),
                                str(JQ_BINARY.parent), str(PYDEPS_DIR / "bin"),
                                os.environ["PATH"], str(Path.home() / ".local/bin")]),
        "KENN_KOPY_RUNTIME_ROOT": str(RUNTIME_ROOT),
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
        "KATA_SERVER": KATA_URL,
        "KENN_FORGE_API_URL": f"http://127.0.0.1:{FORGE_PORT}",
        "KENN_FORGE_HOME": str(STATE / "forge"),
        "AGENTSVIEW_DATA_DIR": str(STATE / "agentsview"),
        "AGENTSVIEW_NO_DAEMON": "1",
        "PI_CODING_AGENT_DIR": str(STATE / "pi"),
        "PI_OFFLINE": "1",
        "GH_CONFIG_DIR": str(STATE / "gh"),
        "GH_PROMPT_DISABLED": "1",
    }
    if PYDEPS_DIR.is_dir():
        existing_py = os.environ.get("PYTHONPATH", "").strip()
        env["PYTHONPATH"] = f"{PYDEPS_DIR}{os.pathsep}{existing_py}" if existing_py else str(PYDEPS_DIR)
    return env


def verify_pi(config, *, env=None):
    executable = config["pi_executable"]
    result = subprocess.run([executable, "--version"], env=base_environment() if env is None else env,
                            text=True, capture_output=True, check=True, timeout=15)
    if result.stdout.strip() != PI_VERSION:
        raise RuntimeError(f"expected Pi {PI_VERSION}; update the local setup deliberately")
    return executable


def default_pi_subagents_settings(*, review_model=None):
    reviewer_model = f"usai/{normalize_usai_model(review_model)}" if review_model else "inherit"
    overrides = {
        name: {
            "advertise": True,
            "description": description,
            "model": reviewer_model if name == "reviewer" else "inherit",
        }
        for name, description in PI_SUBAGENT_DESCRIPTIONS.items()
    }
    for disabled_name in PI_DISABLED_BUILTIN_SUBAGENTS:
        overrides[disabled_name] = {
            "disabled": True,
            "advertise": False,
        }
    return {
        "defaultProvider": "usai",
        "defaultModel": "inherit",
        "toolActivation": "eager",
        "modelScope": {
            "enforce": True,
            "strict": True,
            "allow": ["inherit", "usai/*"],
        },
        "agentOverrides": overrides,
    }


def merge_pi_subagents_settings(existing, *, review_model=None):
    if review_model is None and (STATE / "usai.json").exists():
        try:
            review_model = json.loads(private_read(STATE / "usai.json")).get("review_model")
        except (OSError, ValueError):
            review_model = None
    defaults = default_pi_subagents_settings(review_model=review_model)
    if not isinstance(existing, dict):
        return defaults
    merged = {**defaults, **existing}
    scope = existing.get("modelScope")
    merged["modelScope"] = {**defaults["modelScope"], **(scope if isinstance(scope, dict) else {})}
    overrides = existing.get("agentOverrides")
    merged_overrides = {}
    for name, default_override in defaults["agentOverrides"].items():
        current = overrides.get(name) if isinstance(overrides, dict) and isinstance(overrides.get(name), dict) else {}
        combined = {**default_override, **current}
        if name == "reviewer":
            existing_model = current.get("model")
            if review_model:
                if existing_model in (None, "inherit") or (
                    isinstance(existing_model, str) and existing_model.startswith("usai/")
                ):
                    combined["model"] = defaults["agentOverrides"]["reviewer"]["model"]
            elif existing_model is None:
                combined["model"] = "inherit"
        merged_overrides[name] = combined
    if isinstance(overrides, dict):
        for name, value in overrides.items():
            if name not in merged_overrides and isinstance(value, dict):
                merged_overrides[name] = dict(value)
    merged["agentOverrides"] = merged_overrides
    return merged


def librarian_binding(corpus, executable=None, reader=None, root=None, selection=None):
    explicit = (executable, root)
    # The current toolkit resolves its reader module under --root; only a legacy
    # release takes the reader CLI as an argument, so it stays optional.
    if any(value is not None for value in (*explicit, reader, selection)) and not all(explicit):
        raise RuntimeError("--librarian-executable and --librarian-root must be supplied together")
    if all(explicit):
        server = executable.expanduser().resolve()
        reader = reader.expanduser().resolve() if reader is not None else None
        root = root.expanduser().resolve()
        selection = selection.expanduser().resolve() if selection is not None else None
        if selection is not None and not selection.is_relative_to(root):
            raise RuntimeError("--librarian-selection must stay within --librarian-root")
    else:
        root = corpus
        server = corpus / "tools/context-mcp/.venv/bin/qualified-context-mcp"
        reader = corpus / "tools/context-index/context_index.py"
        selection = None
    return server, reader, root, selection


def setup(corpus, forge_binary, librarian_executable=None, librarian_reader=None,
          librarian_root=None, librarian_selection=None):
    corpus = corpus.expanduser().resolve()
    forge_binary = forge_binary.resolve()
    server, reader, root, selection = librarian_binding(
        corpus, librarian_executable, librarian_reader, librarian_root, librarian_selection)
    for path in (server, forge_binary) + ((reader,) if reader is not None else ()):
        if not path.is_file() or not os.access(path, os.R_OK):
            raise RuntimeError(f"missing readable prerequisite: {path}")
    if not os.access(server, os.X_OK):
        raise RuntimeError(f"Librarian executable is not executable: {server}")
    if not root.is_dir() or not os.access(root, os.R_OK | os.X_OK):
        raise RuntimeError(f"missing readable and searchable Librarian root: {root}")
    if selection is not None and (not selection.is_file() or not os.access(selection, os.R_OK)):
        raise RuntimeError(f"missing readable Librarian selection: {selection}")
    try:
        subprocess.run([str(server), "--help"], text=True, capture_output=True,
                       check=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) else str(error)
        raise RuntimeError(f"Librarian runtime/dependencies unavailable: {detail}") from error
    pi = shutil.which("pi")
    if pi is None:
        raise RuntimeError(f"install Pi {PI_VERSION} before setup")
    config = {"corpus": str(corpus), "forge_binary": str(forge_binary),
              "pi_executable": str(Path(pi).resolve()), "pi_version": PI_VERSION}
    if PORT_OFFSET:
        config["port_offset"] = PORT_OFFSET
    if librarian_executable is not None:
        config.update({
            "librarian_executable": str(server),
            "librarian_reader": str(reader) if reader is not None else None,
            "librarian_root": str(root),
            "librarian_selection": str(selection) if selection is not None else None,
        })
    private_dir(STATE)
    for name in ("home", "runtime", "tmp", "logs", "secrets", "pi", "forge",
                 "roborev", "kata", "agentsview"):
        private_dir(STATE / name)
    seed_isolated_gitconfig(STATE / "home")
    verify_pi(config)
    config_path = STATE / "environment.json"
    if config_path.exists():
        saved = json.loads(private_read(config_path))
        # verify_pi() proved the saved executable now runs PI_VERSION, so an
        # older recorded pi_version is the only difference setup migrates.
        if dict(saved, pi_version=PI_VERSION) != config:
            raise RuntimeError(f"setup differs from saved paths/version/port offset; inspect {config_path} first")
        if saved != config:
            print(f"Migrating saved pi_version {saved.get('pi_version')!r} -> {PI_VERSION}")
            json_write(config_path, config, replace=True)
    json_write(config_path, config)
    wrapper = RUNTIME_ROOT / "scripts/pi-local.py"
    disabled = "".join(f'\n[[agents]]\nkey = "{key}"\nenabled = false\n'
                       for key in ("claude", "codex", "gemini", "opencode", "aider"))
    private_write(
        STATE / "forge/config.toml",
        f'host = "127.0.0.1"\nport = {FORGE_PORT}\n'
        f'[roborev]\nendpoint = "http://127.0.0.1:{ROBOREV_PORT}"\ninit_managed_clones = false\n'
        '[tmux]\ncommand = ["tmux", "-L", "kenn-kopy-local"]\n'
        f'[mcp]\nenabled = true\nhost = "127.0.0.1"\nport = {FORGE_MCP_PORT}\n'
        '[[agents]]\nkey = "pi"\nlabel = "Pi (USAi)"\nenabled = true\n'
        f'command = [{json.dumps(str(wrapper))}]\n'
        '[[agents]]\nkey = "pi-argon"\nlabel = "Pi (Gemini 4 Argon)"\nenabled = true\n'
        f'command = [{json.dumps(str(wrapper))}, "--model", "gemini-4-argon"]\n' + disabled,
    )
    roborev_path = STATE / "roborev/config.toml"
    private_write(
        roborev_path,
        f'server_addr = "127.0.0.1:{ROBOREV_PORT}"\nmax_workers = 1\ndefault_agent = "pi"\n'
        f'pi_cmd = {json.dumps(str(wrapper))}\n'
        f'[web]\nlisten = "127.0.0.1:{ROBOREV_WEB_PORT}"\n',
    )
    roborev_defaults = {
        "review_min_severity": "medium",
        "refine_min_severity": "medium",
        "fix_min_severity": "medium",
        "auto_close_passing_reviews": True,
    }
    raw = private_read(roborev_path)
    existing = tomllib.loads(raw)
    missing = "".join(f"{key} = {json.dumps(value)}\n"
                      for key, value in roborev_defaults.items() if key not in existing)
    if missing:
        private_write(roborev_path, missing + raw, replace=True)
    managed_worktrees = re.escape(str(RUNTIME_ROOT / ".local/environment/forge/worktrees"))
    launcher_migrations = (
        (STATE / "forge/config.toml",
         re.compile(r'(?ms)(\[\[agents\]\]\nkey = "pi(?:-argon)?"\n.*?^command = \[)'
                    rf'"{managed_worktrees}/[^"\n]*/scripts/pi-local\.py"'),
         lambda match: match.group(1) + json.dumps(str(wrapper))),
        (STATE / "roborev/config.toml",
         re.compile(rf'(?m)^pi_cmd = "{managed_worktrees}/[^"\n]*/scripts/pi-local\.py"$'),
         lambda _match: f'pi_cmd = {json.dumps(str(wrapper))}'),
    )
    for path, pattern, replacement in launcher_migrations:
        if path.exists():
            content = private_read(path)
            migrated, count = pattern.subn(replacement, content)
            if count and migrated != content:
                private_write(path, migrated, replace=True)
    private_write(
        STATE / "kata/config.toml",
        f'listen = "127.0.0.1:{KATA_PORT}"\nactive_daemon = "local"\n'
        f'[[daemon]]\nname = "local"\nurl = "{KATA_URL}"\n',
    )
    json_write(
        STATE / "pi/settings.json",
        {
            "defaultThinkingLevel": "off",
            "packages": [str(RUNTIME_ROOT / "superpowers")],
            "lastChangelogVersion": PI_VERSION,
            "subagents": default_pi_subagents_settings(),
        },
    )
    librarian_args = ["--root", str(root)]
    if reader is not None:
        librarian_args.extend(["--reader", str(reader)])
    if selection is not None:
        librarian_args.extend(["--manifest", str(selection)])
    servers = {
        LIBRARIAN_MCP_SERVER: {
            "command": str(server),
            "args": librarian_args,
            "exposure": "codemode",
            "timeout": 60,
        },
        "kata": {
            "command": str(RUNTIME_ROOT / "kata/kata"),
            "args": ["mcp", "serve"],
            "exposure": "direct",
            "timeout": 30,
            "env": {"KATA_SERVER": KATA_URL},
        },
        "kenn-forge": {
            "type": "http",
            "url": f"http://127.0.0.1:{FORGE_MCP_PORT}/mcp",
            "exposure": "direct",
            "timeout": 60,
        },
    }
    mcp_path = STATE / "pi/mcp.json"
    if mcp_path.exists():
        mcp = json.loads(private_read(mcp_path))
        saved = mcp.get("mcpServers")
        if not isinstance(saved, dict):
            raise RuntimeError(f"invalid saved MCP settings; inspect {mcp_path} first")
        saved = dict(saved)
        renamed = migrate_librarian_server(saved, mcp_path)
        saved_librarian = saved.get(LIBRARIAN_MCP_SERVER)
        audited = {**servers[LIBRARIAN_MCP_SERVER],
                   "args": servers[LIBRARIAN_MCP_SERVER]["args"] + audit_args(PI_AUDIT_LABEL)}
        if saved_librarian is not None and saved_librarian not in (servers[LIBRARIAN_MCP_SERVER], audited):
            raise RuntimeError(f"saved Librarian binding differs; inspect {mcp_path} first")
        missing = {name: value for name, value in servers.items() if name not in saved}
        if missing or renamed:
            json_write(mcp_path, {**mcp, "mcpServers": {**saved, **missing}}, replace=True)
    else:
        json_write(mcp_path, {"mcpServers": servers})
    private_write(STATE / "pi/AGENTS.md", CODER_CONTRACT.read_text(), replace=True)
    private_dir(STATE / "pi/extensions")
    install_forge_extension()
    print(f"Persistent local settings/data: {STATE}")
    print(f"Private USAi key destination: {STATE / 'secrets/usai-api-key'}")
    print("Existing settings were preserved. No service or model request was started.")


PI_AUDIT_LABEL = "pi-forge"
COPILOT_AUDIT_LABEL = "copilot"
COPILOT_TOOLS = ["status", "search", "get", "get_many", "catalog", "review_events"]
AUDIT_FLAGS = ("--audit-log", "--agent-label")
LIBRARIAN_COMMANDS = ("librarian-mcp", "qualified-context-mcp")
LIBRARIAN_MCP_SERVER = "falcon-librarian"
LEGACY_LIBRARIAN_MCP_SERVERS = ("falcon-context",)


def migrate_librarian_server(servers, path):
    """Rename a legacy Librarian MCP server entry in ``servers`` in place; return whether it changed."""
    renamed = False
    for legacy in LEGACY_LIBRARIAN_MCP_SERVERS:
        if legacy not in servers:
            continue
        entry = servers.pop(legacy)
        current = servers.setdefault(LIBRARIAN_MCP_SERVER, entry)
        if current != entry:
            raise RuntimeError(f"both {legacy} and {LIBRARIAN_MCP_SERVER} are bound differently; "
                               f"inspect {path} first")
        renamed = True
    return renamed


def audit_args(label):
    """Opt-in private audit: a bare --audit-log writes <root>/.local/audit/<label>-mcp-access.jsonl."""
    return ["--audit-log", "--agent-label", label]


def librarian_supports_audit(help_text):
    return all(flag in help_text for flag in AUDIT_FLAGS)


def librarian_server_args(root, reader, selection, label=None):
    args = ["--root", str(root)]
    if reader is not None:
        args.extend(["--reader", str(reader)])
    if selection is not None:
        args.extend(["--manifest", str(selection)])
    return args + (audit_args(label) if label else [])


def unmanaged_binding_candidates():
    """Client configs that may hold a Librarian binding but are not owned by configure-librarian."""
    try:
        home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    except KeyError:
        home = Path.home()
    return [home / ".copilot/mcp-config.json", RUNTIME_ROOT / ".pi/mcp.json",
            RUNTIME_ROOT / ".github/mcp.json", GLOBAL_PI / "mcp.json"]


def unmanaged_binding_report(paths, managed=()):
    """Describe, without modifying, Librarian bindings outside configure-librarian's ownership."""
    skip = {Path(path).resolve() for path in managed}
    lines = []
    for path in paths:
        path = Path(path)
        if not path.is_file() or path.resolve() in skip:
            continue
        try:
            servers = json.loads(path.read_text()).get("mcpServers", {})
            if not isinstance(servers, dict):
                raise ValueError("mcpServers is not an object")
        except (OSError, ValueError, AttributeError):
            lines.append(f"Unmanaged binding {path}: unreadable; not inspected or modified")
            continue
        for name, server in servers.items():
            if not isinstance(server, dict):
                continue
            command, args = str(server.get("command", "")), server.get("args", [])
            if (name not in (LIBRARIAN_MCP_SERVER, *LEGACY_LIBRARIAN_MCP_SERVERS)
                    and Path(command).name not in LIBRARIAN_COMMANDS):
                continue
            args = args if isinstance(args, list) else []
            if "--audit-log" in args and "--agent-label" in args[:-1:]:
                label = args[args.index("--agent-label") + 1]
                lines.append(f"Unmanaged binding {path}: {name} audit label {label}; not modified")
            else:
                lines.append(f"Unmanaged binding {path}: {name} has no audit flags; not modified. "
                             "To audit it, add `--audit-log --agent-label LABEL` yourself with a "
                             f"label distinct from {PI_AUDIT_LABEL} and {COPILOT_AUDIT_LABEL}.")
    return lines


def configure_librarian(librarian_root, librarian_executable=None,
                        librarian_reader=None, librarian_selection=None,
                        audit=False, copilot_config=None):
    config = settings()
    root = librarian_root.expanduser().resolve()
    executable = (
        (root / ".venv/bin/librarian-mcp")
        if librarian_executable is None else librarian_executable
    )
    selection = librarian_selection
    if selection is None and (root / "config/selection.local.json").is_file():
        selection = root / "config/selection.local.json"
    server, reader, root, selection = librarian_binding(
        Path(config["corpus"]), executable, librarian_reader, root, selection,
    )
    for path in (server,) + ((reader,) if reader is not None else ()):
        if not path.is_file() or not os.access(path, os.R_OK):
            raise RuntimeError(f"missing readable prerequisite: {path}")
    if not os.access(server, os.X_OK):
        raise RuntimeError(f"Librarian executable is not executable: {server}")
    if not root.is_dir() or not os.access(root, os.R_OK | os.X_OK):
        raise RuntimeError(f"missing readable and searchable Librarian root: {root}")
    if selection is not None and (not selection.is_file() or not os.access(selection, os.R_OK)):
        raise RuntimeError(f"missing readable Librarian selection: {selection}")
    try:
        help_result = subprocess.run([str(server), "--help"], text=True, capture_output=True,
                                     check=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) else str(error)
        raise RuntimeError(f"Librarian runtime/dependencies unavailable: {detail}") from error
    can_audit = librarian_supports_audit(help_result.stdout + help_result.stderr)
    if audit and not can_audit:
        raise RuntimeError(
            f"installed {server} lacks {' and '.join(AUDIT_FLAGS)}; reinstall the Librarian MCP "
            f"adapter from a checkout that includes the audit interface (the_librarian#9e3j), "
            "then rerun with --audit. Nothing was changed.")
    copilot_path = None
    copilot = None
    if copilot_config is not None:
        copilot_path = Path(copilot_config).expanduser().resolve()
        if copilot_path.exists():
            copilot = json.loads(private_read(copilot_path))
            if not isinstance(copilot, dict) or not isinstance(copilot.get("mcpServers", {}), dict):
                raise RuntimeError(f"invalid saved MCP settings; inspect {copilot_path} first")
        else:
            copilot = {}
        copilot_servers = copilot.setdefault("mcpServers", {})
        migrate_librarian_server(copilot_servers, copilot_path)
    updated_config = {
        **config,
        "librarian_executable": str(server),
        "librarian_reader": str(reader) if reader is not None else None,
        "librarian_root": str(root),
        "librarian_selection": str(selection) if selection is not None else None,
    }
    librarian_args = librarian_server_args(root, reader, selection, PI_AUDIT_LABEL if audit else None)
    mcp_path = STATE / "pi/mcp.json"
    mcp = json.loads(private_read(mcp_path)) if mcp_path.exists() else {}
    saved = mcp.get("mcpServers") if mcp else {}
    if not isinstance(saved, dict):
        raise RuntimeError(f"invalid saved MCP settings; inspect {mcp_path} first")
    saved = dict(saved)
    migrate_librarian_server(saved, mcp_path)
    previously_audited = "--audit-log" in (saved.get(LIBRARIAN_MCP_SERVER) or {}).get("args", [])
    json_write(STATE / "environment.json", updated_config, replace=True)
    json_write(
        mcp_path,
        {
            **mcp,
            "mcpServers": {
                **saved,
                LIBRARIAN_MCP_SERVER: {
                    "command": str(server),
                    "args": librarian_args,
                    "exposure": "codemode",
                    "timeout": 60,
                },
            },
        },
        replace=True,
    )
    if copilot_path is not None:
        servers = copilot_servers
        entry = servers.get(LIBRARIAN_MCP_SERVER)
        entry = dict(entry) if isinstance(entry, dict) else {"type": "local", "tools": COPILOT_TOOLS,
                                                              "timeout": 60000}
        entry.update({"command": str(server), "cwd": str(root),
                      "args": librarian_server_args(root, reader, selection,
                                                    COPILOT_AUDIT_LABEL if audit else None)})
        servers[LIBRARIAN_MCP_SERVER] = entry
        copilot_path.parent.mkdir(parents=True, exist_ok=True)
        json_write(copilot_path, copilot, replace=True)
    print(f"Librarian MCP provider bound to {root}")
    audit_dir = root / ".local/audit"
    if audit:
        labels = [PI_AUDIT_LABEL] + ([COPILOT_AUDIT_LABEL] if copilot_path is not None else [])
        print("Audit: enabled for " + ", ".join(f"{label} -> {audit_dir}/{label}-mcp-access.jsonl"
                                                for label in labels))
        print("Activation: running clients keep their old binding until restarted; start a new "
              "Pi/Forge session (or restart Copilot) to pick up the audit flags. Records appear "
              f"only for calls made after that restart. Summarize with librarian-audit --root {root} report.")
    elif not can_audit:
        print("Audit: unavailable; the installed adapter lacks "
              f"{' and '.join(AUDIT_FLAGS)}. Reinstall it, then rerun with --audit.")
    else:
        print("Audit: disabled" + (" (previous audit flags removed)" if previously_audited else "")
              + "; pass --audit to record every returned payload privately.")
    for line in unmanaged_binding_report(unmanaged_binding_candidates(),
                                         managed=[copilot_path] if copilot_path else ()):
        print(line)


def _candidate_offline_site_packages(source: Path, py_ver: str) -> list[Path]:
    candidates: list[Path] = []
    env_override = os.environ.get("LIBRARIAN_OFFLINE_SITE_PACKAGES")
    if env_override:
        candidates.append(Path(env_override).expanduser())
    candidates.extend([
        source / ".venv/lib" / py_ver / "site-packages",
        source / "tools/context-mcp/.venv/lib" / py_ver / "site-packages",
    ])
    candidates.extend(sorted(source.glob(".venv/lib/python*/site-packages")))
    candidates.extend(sorted(source.glob("tools/context-mcp/.venv/lib/python*/site-packages")))
    env_file = STATE / "environment.json"
    if env_file.is_file():
        try:
            env = json.loads(env_file.read_text())
            for key in ("corpus", "librarian_root"):
                val = env.get(key)
                if val:
                    p = Path(val).expanduser()
                    candidates.extend([
                        p / ".venv/lib" / py_ver / "site-packages",
                        p / "tools/context-mcp/.venv/lib" / py_ver / "site-packages",
                        p.parent / "the_librarian/.venv/lib" / py_ver / "site-packages",
                    ])
        except (OSError, json.JSONDecodeError):
            pass
    candidates.extend([
        Path.home() / "the_librarian/.venv/lib" / py_ver / "site-packages",
        Path.home() / "falcon-docs/tools/context-mcp/.venv/lib" / py_ver / "site-packages",
    ])
    for entry in sys.path:
        if entry and "site-packages" in entry:
            candidates.append(Path(entry))
    seen: set[Path] = set()
    unique: list[Path] = []
    for cand in candidates:
        try:
            resolved = cand.resolve()
        except OSError:
            continue
        if resolved not in seen and cand.is_dir():
            seen.add(resolved)
            unique.append(cand)
    return unique


def _write_librarian_entrypoint(path, python_executable, module_name):
    script = (
        f"#!{python_executable}\n"
        "# -*- coding: utf-8 -*-\n"
        "import re\n"
        "import sys\n"
        f"from {module_name} import main\n"
        "if __name__ == '__main__':\n"
        "    sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])\n"
        "    sys.exit(main())\n"
    )
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def provision_librarian_mvp(source, dest, *, inbox=None, repos_root=None, bind_mcp=False):
    source = source.expanduser().resolve()
    dest = dest.expanduser().resolve()
    if not source.is_dir() or not (source / "tools/package.py").is_file() or not (source / "tools/initialize.py").is_file():
        raise RuntimeError(f"missing Librarian toolkit source checkout: {source}")
    if dest == source or dest.is_relative_to(source) or source.is_relative_to(dest):
        raise RuntimeError("--dest must be an isolated directory outside --source")
    resolved_inbox = None
    if inbox is not None:
        resolved_inbox = inbox.expanduser().resolve()
        if not resolved_inbox.is_dir() or not os.access(resolved_inbox, os.R_OK | os.X_OK):
            raise RuntimeError(f"missing readable and searchable inbox directory: {resolved_inbox}")
    resolved_repos = None
    if repos_root is not None:
        resolved_repos = repos_root.expanduser().resolve()
        if not resolved_repos.is_dir() or not os.access(resolved_repos, os.R_OK | os.X_OK):
            raise RuntimeError(f"missing readable and searchable repos root: {resolved_repos}")
    with tempfile.TemporaryDirectory(prefix="librarian-mvp-pkg-") as temp_dir:
        archive_path = Path(temp_dir) / "librarian-release.zip"
        subprocess.run(
            [sys.executable, str(source / "tools/package.py"), "--output", str(archive_path)],
            cwd=source, text=True, capture_output=True, check=True, timeout=60,
        )
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path, "r") as archive:
            for member in archive.infolist():
                target = (dest / member.filename).resolve()
                if not target.is_relative_to(dest):
                    raise RuntimeError(f"unsafe release archive entry: {member.filename}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member.filename))
    venv_dir = dest / ".venv"
    venv_python = venv_dir / "bin/python"
    if not venv_python.exists():
        subprocess.run(
            [sys.executable, "-m", "venv", "--without-pip", str(venv_dir)],
            text=True, capture_output=True, check=True, timeout=60,
        )
    py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    dest_site = venv_dir / "lib" / py_ver / "site-packages"
    dest_site.mkdir(parents=True, exist_ok=True)
    candidate_sites = _candidate_offline_site_packages(source, py_ver)
    selected_site = next(
        (c for c in candidate_sites if (c / "mcp").exists() and (c / "jsonschema").exists()),
        candidate_sites[0] if candidate_sites else None,
    )
    if selected_site is not None and selected_site.resolve() != dest_site.resolve():
        shutil.copytree(selected_site, dest_site, dirs_exist_ok=True)
    mcp_pkg_src = dest / "tools/context-mcp/src/the_librarian_mcp"
    if mcp_pkg_src.is_dir():
        shutil.copytree(mcp_pkg_src, dest_site / "the_librarian_mcp", dirs_exist_ok=True)
    _write_librarian_entrypoint(venv_dir / "bin/librarian-mcp", venv_python, "the_librarian_mcp.server")
    _write_librarian_entrypoint(venv_dir / "bin/librarian-preflight", venv_python, "the_librarian_mcp.preflight")
    policy_local = dest / "config/policy.local.json"
    if not policy_local.exists():
        json_write(policy_local, {
            "audience": "authorized-local",
            "storage_roots": {
                "catalog_home": "tools/catalog/.local",
                "review_events_home": "tools/review_events/.local",
                "context_index_db": "tools/context_index/.local/index.sqlite3",
                "intake_home": ".local/intake",
                "extractions_home": ".local/extractions",
                "diagnostics_log": ".local/diagnostics/retrieval-events.jsonl",
                "selection_manifest": "config/selection.local.json",
            },
        })
    selection_local = dest / "config/selection.local.json"
    if not selection_local.exists():
        json_write(selection_local, {
            "schema_version": 1,
            "audience": "authorized-local",
            "documents": [],
            "context_rules": {},
            "renditions": [],
        })
    init_proc = subprocess.run(
        [str(venv_python), str(dest / "tools/initialize.py"), "--root", str(dest)],
        cwd=dest, text=True, capture_output=True, timeout=60,
    )
    if init_proc.returncode != 0 and "Index is stale; run build" in (init_proc.stderr or ""):
        subprocess.run(
            [str(venv_python), "-m", "tools.context_index.context_index", "--root", str(dest), "build"],
            cwd=dest, text=True, capture_output=True, check=True, timeout=60,
        )
        subprocess.run(
            [str(venv_python), str(dest / "tools/initialize.py"), "--root", str(dest)],
            cwd=dest, text=True, capture_output=True, check=True, timeout=60,
        )
    elif init_proc.returncode != 0:
        raise subprocess.CalledProcessError(
            init_proc.returncode, init_proc.args, output=init_proc.stdout, stderr=init_proc.stderr
        )
    subprocess.run(
        [str(venv_python), "-m", "tools.context_index.context_index", "--root", str(dest), "status"],
        cwd=dest, text=True, capture_output=True, check=True, timeout=60,
    )
    subprocess.run(
        [str(venv_dir / "bin/librarian-mcp"), "--help"],
        cwd=dest, text=True, capture_output=True, check=True, timeout=30,
    )
    private_dir(dest / ".local")
    json_write(dest / ".local/mvp-sources.json", {
        "schema": "librarian.mvp-instance/v1",
        "source_toolkit": str(source),
        "instance_root": str(dest),
        "inbox": str(resolved_inbox) if resolved_inbox is not None else None,
        "repos_root": str(resolved_repos) if resolved_repos is not None else None,
    }, replace=True)
    json_write(dest / ".local/engineer-context.json", {
        "schema": "engineer.context-config/v2",
        "librarian": {
            "project_id": "falcon-librarian-mvp",
            "executable": str(venv_dir / "bin/librarian-mcp"),
            "root": str(dest),
            "reader": None,
            "selection": str(selection_local),
        },
    }, replace=True)
    if bind_mcp:
        configure_librarian(dest, venv_dir / "bin/librarian-mcp", None, selection_local)
    summary = {
        "instance_root": str(dest),
        "executable": str(venv_dir / "bin/librarian-mcp"),
        "policy_local": str(policy_local),
        "selection_local": str(selection_local),
        "engineer_context_config": str(dest / ".local/engineer-context.json"),
        "inbox": str(resolved_inbox) if resolved_inbox is not None else None,
        "repos_root": str(resolved_repos) if resolved_repos is not None else None,
        "mcp_bound": bool(bind_mcp),
    }
    print(json.dumps(summary, indent=2))
    return summary


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
    command = "!" + shlex.join([sys.executable, str(RUNTIME_ROOT / "scripts/usai-key.py")])
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


def normalize_usai_model(model):
    if not isinstance(model, str):
        raise RuntimeError("supply the exact nonempty USAi model alias without whitespace")
    cleaned = model.strip()
    if cleaned.startswith("usai/"):
        cleaned = cleaned[len("usai/"):]
    if not cleaned or any(character.isspace() for character in cleaned) or "/" in cleaned:
        raise RuntimeError("supply the exact nonempty USAi model alias without whitespace")
    if cleaned in USAI_EMBEDDING_MODELS:
        raise RuntimeError(f"USAi embedding model cannot be used as an agent or reviewer model: {cleaned}")
    return cleaned


def usai_model_family(model):
    cleaned = normalize_usai_model(model)
    if cleaned.startswith(("claude-", "claude_")):
        return "claude"
    if cleaned.startswith(("gpt-", "gpt_")):
        return "openai"
    if cleaned.startswith("gemini-"):
        return "gemini"
    if cleaned.startswith("llama_"):
        return "llama"
    return None


def validate_paired_models(coder_model, review_model):
    coder = normalize_usai_model(coder_model)
    reviewer = normalize_usai_model(review_model)
    coder_family = usai_model_family(coder)
    reviewer_family = usai_model_family(reviewer)
    if (coder_family not in ADVERSARIAL_MODEL_FAMILIES
            or reviewer_family not in ADVERSARIAL_MODEL_FAMILIES
            or coder_family == reviewer_family):
        raise RuntimeError(
            "paired coder and reviewer models must be distinct Claude, OpenAI, or Gemini families"
        )
    catalog_path = STATE / "usai-models.json"
    if catalog_path.exists():
        catalog = json.loads(private_read(catalog_path))
        advertised = set(catalog.get("models", []))
        if advertised and (coder not in advertised or reviewer not in advertised):
            raise RuntimeError("paired coder and reviewer models must be present in advertised usai-models.json")
    return coder, reviewer


def discovered_usai_chat_models():
    models = list(USAI_CHAT_MODELS)
    catalog_path = STATE / "usai-models.json"
    if catalog_path.exists():
        catalog = json.loads(private_read(catalog_path))
        for model_id in catalog.get("models", []):
            if isinstance(model_id, str):
                cleaned = model_id.strip()
                if cleaned and cleaned not in USAI_EMBEDDING_MODELS and cleaned not in models:
                    models.append(cleaned)
    return tuple(models)


def sync_roborev_review_model(review_model):
    roborev_path = STATE / "roborev/config.toml"
    if not roborev_path.exists():
        return
    raw = private_read(roborev_path)
    tomllib.loads(raw)
    lines = raw.splitlines()
    top_lines = []
    section_lines = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if not in_section and stripped.startswith("[") and stripped.endswith("]"):
            in_section = True
        if in_section:
            section_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip() if "=" in stripped else ""
        if key in ("default_model", "review_model"):
            continue
        top_lines.append(line)
    if review_model is not None:
        top_lines.append(f"default_model = {json.dumps(review_model)}")
        top_lines.append(f"review_model = {json.dumps(review_model)}")
    rendered = "\n".join([*top_lines, *section_lines]) + "\n"
    tomllib.loads(rendered)
    private_write(roborev_path, rendered, replace=True)


def configure_provider(base_url, model, api, *, review_model=None):
    settings()
    base_url = validate_base_url(base_url)
    model = normalize_usai_model(model)
    if review_model is not None:
        model, review_model = validate_paired_models(model, review_model)
    path = STATE / "pi/models.json"
    models = json.loads(private_read(path)) if path.exists() else {}
    providers = models.setdefault("providers", {})
    provider = providers.setdefault("usai", {})
    provider.update({"baseUrl": base_url, "api": api, "apiKey": "${USAI_API_KEY}"})
    entries = [
        entry for entry in provider.setdefault("models", [])
        if not (isinstance(entry, dict) and entry.get("id") in USAI_EMBEDDING_MODELS)
    ]
    provider["models"] = entries
    required_models = [model]
    if review_model is not None and review_model not in required_models:
        required_models.append(review_model)
    for catalog_model in discovered_usai_chat_models():
        if catalog_model not in required_models:
            required_models.append(catalog_model)
    for required_model in required_models:
        if not any(entry.get("id") == required_model for entry in entries):
            entries.append({"id": required_model, "compat": {"supportsDeveloperRole": False}})
    for entry in entries:
        if isinstance(entry, dict) and entry.get("id"):
            compat = entry.get("compat")
            entry["compat"] = {**(compat if isinstance(compat, dict) else {}), "supportsDeveloperRole": False}
            entry.update(USAI_MODEL_LIMITS.get(entry["id"], {}))
    json_write(path, models, replace=True)
    settings_path = STATE / "pi/settings.json"
    pi_settings = json.loads(private_read(settings_path)) if settings_path.exists() else {}
    pi_settings.update({"defaultProvider": "usai", "defaultModel": model})
    pi_settings["subagents"] = merge_pi_subagents_settings(
        pi_settings.get("subagents"), review_model=review_model,
    )
    json_write(settings_path, pi_settings, replace=True)
    usai_state = {"model": model}
    if review_model is not None:
        usai_state["review_model"] = review_model
    json_write(STATE / "usai.json", usai_state, replace=True)
    sync_roborev_review_model(review_model)
    print("USAi provider configured without storing a key in model settings. No model call was made.")


def forge_kata_ref(cwd):
    """Return the tracked Kata ref from a Forge Kata workspace's override file."""
    try:
        text = (Path(cwd) / "AGENTS.override.md").read_text()
    except OSError:
        return ""
    section = text.partition("## Source Item\n")[2].partition("\n## ")[0]
    if "\n- Source kind: Kata task\n" not in "\n" + section:
        return ""
    match = re.search(r"^- Qualified ID: ([A-Za-z0-9][A-Za-z0-9_.-]*#[A-Za-z0-9]+)$", section, re.M)
    return match.group(1) if match else ""


def pi_launch(args):
    config = settings()
    seed_isolated_gitconfig(STATE / "home")
    executable = verify_pi(config)
    env = base_environment()
    for forge_var in ("KENN_FORGE_RUNTIME_SESSION_KEY", "KENN_FORGE_API_URL"):
        value = os.environ.get(forge_var, "").strip()
        if value:
            env[forge_var] = value
    # Kata's native Pi attention adapter tracks the issue named by KATA_REF.
    kata_ref = os.environ.get("KATA_REF", "").strip() or forge_kata_ref(Path.cwd())
    if kata_ref:
        env["KATA_REF"] = kata_ref
    if args and (args[0] in PI_PASSTHROUGH_SUBCOMMANDS or args == ["--version"] or args == ["--help"]):
        return [executable, *args], env
    requested_model = None
    cleaned_args = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--api-key" or arg.startswith("--api-key="):
            raise RuntimeError("the local agent uses the saved USAi model; configure-provider to change it")
        if arg == "--provider":
            if index + 1 >= len(args) or args[index + 1] != "usai":
                raise RuntimeError("the local agent uses the saved USAi model; configure-provider to change it")
            index += 2
            continue
        if arg.startswith("--provider="):
            if arg.split("=", 1)[1] != "usai":
                raise RuntimeError("the local agent uses the saved USAi model; configure-provider to change it")
            index += 1
            continue
        if arg == "--model":
            if index + 1 >= len(args):
                raise RuntimeError("the local agent uses the saved USAi model; configure-provider to change it")
            candidate = args[index + 1].strip()
            if candidate.startswith("usai/"):
                candidate = candidate[len("usai/"):]
            if not candidate:
                raise RuntimeError("the local agent uses the saved USAi model; configure-provider to change it")
            requested_model = candidate
            index += 2
            continue
        if arg.startswith("--model="):
            candidate = arg.split("=", 1)[1].strip()
            if candidate.startswith("usai/"):
                candidate = candidate[len("usai/"):]
            if not candidate:
                raise RuntimeError("the local agent uses the saved USAi model; configure-provider to change it")
            requested_model = candidate
            index += 1
            continue
        cleaned_args.append(arg)
        index += 1
    if requested_model is not None and not (STATE / "usai.json").exists():
        raise RuntimeError("the local agent uses the saved USAi model; configure-provider to change it")
    try:
        usai_cfg = json.loads(private_read(STATE / "usai.json"))
        default_model = usai_cfg["model"]
        review_model = usai_cfg.get("review_model")
        if review_model is not None:
            validate_paired_models(default_model, review_model)
        allowed_models = {default_model, "gemini-4-argon"}
        if review_model is not None:
            allowed_models.add(review_model)
        if requested_model is not None and requested_model not in allowed_models:
            raise RuntimeError("the local agent uses the saved USAi model; configure-provider to change it")
        model = requested_model or default_model
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
    if "--json-schema" in cleaned_args:
        cleaned_args = structured_review_args(cleaned_args)
    return [executable, "--provider", "usai", "--model", model, *cleaned_args], env


# Roborev's structured review is independent and read-only: it must not inherit
# coder policy from AGENTS files, the Forge workspace extension or Superpowers.
REVIEW_ISOLATION_FLAGS = ("--no-context-files", "--no-extensions", "--no-skills",
                          "--no-prompt-templates", "--no-mcp")


def structured_review_args(args):
    """Isolate a structured review, loading only the local schema extension."""
    schema_extension = str(PI_REVIEW_EXTENSION_PATH)
    legacy_npm_path = str(STATE / "pi/npm/node_modules/@nqbao/pi-json-schema")
    redundant_extensions = {
        PI_REVIEW_EXTENSION,
        LEGACY_PI_REVIEW_EXTENSION,
        schema_extension,
        legacy_npm_path,
    }
    kept = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in ("--extension", "-e") and index + 1 < len(args) and \
                args[index + 1] in redundant_extensions:
            index += 2
            continue
        if arg not in REVIEW_ISOLATION_FLAGS:
            kept.append(arg)
        index += 1
    return [*REVIEW_ISOLATION_FLAGS, "--extension", schema_extension, *kept]


def npm_package_name(spec):
    """Return the npm package of an `npm:name@version` Pi package spec, else None."""
    if not isinstance(spec, str) or not spec.startswith("npm:"):
        return None
    name = spec[len("npm:"):]
    return name.rsplit("@", 1)[0] if "@" in name[1:] else name


def install_pi_extensions():
    executable = verify_pi(settings())
    path = STATE / "pi/settings.json"
    private_read(path)
    private_write(STATE / "pi/AGENTS.md", CODER_CONTRACT.read_text(), replace=True)
    private_dir(STATE / "pi/extensions")
    install_forge_extension()
    for extension in PI_EXTENSIONS:
        subprocess.run(
            [executable, "install", extension],
            cwd=STATE / "home", env=base_environment(), check=True, timeout=180,
        )
        config = json.loads(private_read(path))
        if extension not in config.get("packages", []):
            raise RuntimeError(f"Pi did not save {extension} in the isolated profile")
    config = json.loads(private_read(path))
    if "packages" in config and isinstance(config["packages"], list):
        pinned = {npm_package_name(extension): extension for extension in PI_EXTENSIONS}
        config["packages"] = [
            pkg for pkg in config["packages"]
            if pkg != LEGACY_PI_REVIEW_EXTENSION
            and pinned.get(npm_package_name(pkg), pkg) == pkg
        ]
    config["subagents"] = merge_pi_subagents_settings(config.get("subagents"))
    json_write(path, config, replace=True)
    # Kata's native attention adapter only: AGENTS policy already carries the
    # Kata contract, so the adapter's prompt contract is removed.
    kata = str(RUNTIME_ROOT / "kata/kata")
    for command in ([kata, "agent-hook", "install", "pi", "--executable", kata],
                    [kata, "agent-hook", "uninstall", "pi", "--contract-only"]):
        subprocess.run(command, cwd=STATE / "home", env=base_environment(), check=True,
                       timeout=60, stdout=subprocess.DEVNULL)
    private_dir(STATE / "pi/extensions")
    print(f"Installed {', '.join(PI_EXTENSIONS)} and Kata Pi attention in the isolated Pi profile; no model request was made.")


def roborev_warnings(*, proc_root=Path("/proc")):
    """Read-only diagnostics: never start or signal another daemon."""
    warnings = []
    for host, family in (("127.0.0.1", socket.AF_INET), ("::1", socket.AF_INET6)):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as probe:
                probe.settimeout(0.2)
                if probe.connect_ex((host, 7373)) == 0:
                    warnings.append(f"unexpected listener at {host}:7373; managed roborev uses {ROBOREV_PORT}")
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
    request = urllib.request.Request(f"http://127.0.0.1:{FORGE_PORT}/api/v1" + path, data=data,
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


def check_ports(ports=None):
    for port in PORTS if ports is None else ports:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", port))


def agentsview_request(method, path, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    base = f"http://127.0.0.1:{AGENTSVIEW_PORT}/api"
    url = base + "/ping" if path == "/ping" else base + "/v1" + path
    request = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with HTTP.open(request, timeout=timeout) as response:
        return json.load(response)


def agentsview_command():
    args = [str(RUNTIME_ROOT / "agentsview/agentsview"), "serve", "--host", "127.0.0.1",
            "--port", str(AGENTSVIEW_PORT), "--no-browser", "--no-update-check"]
    if not (STATE / "agentsview-tracking.json").exists():
        args.append("--no-sync")
    return args


def direct_api_dirs():
    """Direct API session drop directories: the user's real home and the AgentsView service home."""
    real_home = pwd.getpwuid(os.getuid()).pw_dir
    return [f"{real_home}/.agentsview/direct-api", str(STATE / "home/.agentsview/direct-api")]


def configure_tracking(copilot_dir, pi_dirs, archive_content):
    settings()
    copilot_dir = copilot_dir.expanduser().resolve()
    if not (copilot_dir / "session-state").is_dir():
        raise RuntimeError("Copilot source must contain its existing session-state directory")
    private_dir(STATE / "pi/sessions")
    direct_api = direct_api_dirs()
    for directory in direct_api:
        # Writers may already have created these with default permissions, so do not require 0700.
        Path(directory).mkdir(mode=0o700, parents=True, exist_ok=True)
    pi_dirs = list(dict.fromkeys(str(path.expanduser().resolve()) for path in pi_dirs))
    if not pi_dirs or any(not Path(path).is_dir() for path in pi_dirs):
        raise RuntimeError("each Pi source must be an existing sessions directory")
    saved = agentsview_request("GET", "/settings")
    excluded = sorted(provider["id"] for provider in saved["session_providers"]
                      if provider["id"] not in ("copilot", "pi", "direct-api"))
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
        for agent, dirs in (("copilot", [str(copilot_dir)]), ("pi", pi_dirs),
                           ("direct-api", direct_api)):
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


GUARDED_SOL_PRICE_AS = {
    "gpt-5.6-sol-latest-guardrails-defaultv2": "gpt-5.6-sol",
    "gpt-6-sol-latest-guardrails-defaultv2": "gpt-6-sol",
    "gpt-6.1-sol-latest-guardrails-defaultv2": "gpt-6.1-sol",
}


def configure_agentsview_pricing():
    """Price guarded USAi Sol deployments as their catalog models (needs `price_as` upstream)."""
    path = STATE / "agentsview/config.toml"
    lock_fd = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, "rb") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("AgentsView config is busy; retry configure-agentsview-pricing") from error
        text = private_read(path)
        existing = tomllib.loads(text).get("custom_model_pricing", {})
        suffix = ""
        for model, target in GUARDED_SOL_PRICE_AS.items():
            if model in existing:
                if existing[model] != {"price_as": target}:
                    raise RuntimeError(f"existing custom_model_pricing for {model} differs; review before changing it")
            else:
                suffix += f'\n[custom_model_pricing."{model}"]\nprice_as = "{target}"\n'
        if suffix:
            updated = text + suffix
            tomllib.loads(updated)
            private_write(path, updated, replace=True)
    print("AgentsView prices guarded Sol deployments as their base models; restart AgentsView to apply.")


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
    direct_api = direct_api_dirs()
    for directory in direct_api:
        # Writers may already have created these with default permissions, so do not require 0700.
        Path(directory).mkdir(mode=0o700, parents=True, exist_ok=True)
    expected = {"archive_content": "usage", "agents": {
        "pi": {"dirs": [str(sessions)]}, "direct-api": {"dirs": direct_api}}}
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
            existing = config.get("agents", {}).get("direct-api")
            if existing is None:
                updated = private_read(path) + f'\n[agents.direct-api]\ndirs = {json.dumps(direct_api)}\n'
                tomllib.loads(updated)
                private_write(path, updated, replace=True)
                print("Added Direct API usage directories to existing AgentsView tracking.")
            elif existing.get("dirs") != direct_api:
                raise RuntimeError("existing AgentsView direct-api directories differ; review before changing them")
            print("Existing configured AgentsView tracking preserved; no sources or archive policy changed.")
            return
        if config and config != expected:
            raise RuntimeError("existing AgentsView settings require explicit tracking configuration; not overwritten")
        private_write(path, 'archive_content = "usage"\n\n[agents.pi]\n'
                      f'dirs = {json.dumps([str(sessions)])}\n\n[agents.direct-api]\n'
                      f'dirs = {json.dumps(direct_api)}\n')
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
    print(f"AgentsView user service enabled and responsive at http://127.0.0.1:{AGENTSVIEW_PORT}/")


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
        sys.executable, RUNTIME_ROOT / "scripts/local_env.py", command, *args,
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
    check_ports(SERVICE_PORTS["agentsview"])
    command = agentsview_command()
    os.chdir(STATE / "home")
    os.execve(command[0], command, agentsview_environment())


def validate_roborev_config():
    config = tomllib.loads(private_read(STATE / "roborev/config.toml"))
    if (config.get("server_addr") != f"127.0.0.1:{ROBOREV_PORT}"
            or config.get("web", {}).get("listen") != f"127.0.0.1:{ROBOREV_WEB_PORT}"):
        raise RuntimeError("roborev must retain the documented loopback API and UI ports")
    usai_path = STATE / "usai.json"
    if usai_path.exists():
        usai_cfg = json.loads(private_read(usai_path))
        coder_model = usai_cfg.get("model")
        review_model = usai_cfg.get("review_model")
        configured_review = config.get("review_model") or config.get("default_model")
        if review_model is not None:
            validate_paired_models(coder_model, review_model)
            if (config.get("review_model") != review_model
                    or config.get("default_model") != review_model):
                raise RuntimeError(
                    "roborev review_model/default_model does not match the configured USAi review_model"
                )
        elif configured_review is not None:
            raise RuntimeError(
                "roborev defines review_model/default_model without a paired USAi review_model in usai.json"
            )


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
    return RUNTIME_ROOT / "roborev/bin/roborev"


def roborev_command(binary=None):
    binary = roborev_binary() if binary is None else binary
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"missing executable roborev binary: {binary}")
    return [str(binary), "daemon", "run",
            "--addr", f"127.0.0.1:{ROBOREV_PORT}", "--config", str(STATE / "roborev/config.toml")]


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
    print(f"roborev user service enabled and responsive at http://127.0.0.1:{ROBOREV_WEB_PORT}/reviews")


def managed_roborev(*, required=False, binary=None):
    if not required and not (STATE / "roborev-service.json").exists():
        return None
    pid = user_service_pid(ROBOREV_UNIT)
    if binary is not None and not os.path.samefile(f"/proc/{pid}/exe", binary):
        raise RuntimeError("running roborev executable differs from the requested binary; "
                           "finish reviews, stop the service and reinstall before restarting")
    with HTTP.open(f"http://127.0.0.1:{ROBOREV_PORT}/api/ping", timeout=3) as response:
        health = json.load(response)
    if health.get("pid") != pid or health.get("ok") is not True or not health.get("version"):
        raise RuntimeError("roborev health does not match the managed user service")
    with HTTP.open(f"http://127.0.0.1:{ROBOREV_PORT}/api/status", timeout=3) as response:
        status = json.load(response)
    if status.get("version") != health["version"]:
        raise RuntimeError("roborev database status does not match its health version")
    request = urllib.request.Request(f"http://127.0.0.1:{ROBOREV_WEB_PORT}/reviews",
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
    print(f"Forge user service enabled and responsive at http://127.0.0.1:{FORGE_PORT}/")


def managed_forge(*, required=False):
    if not required and not (STATE / "forge-service.json").exists():
        return None
    pid = user_service_pid(FORGE_UNIT)
    private_dir(STATE / "forge", create=False)
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
    check_ports(SERVICE_PORTS["forge"])
    command = forge_command(config)
    private_dir(STATE / "gh")
    os.chdir(STATE / "home")
    os.execve(command[0], command, env)


def validate_kata_config():
    config = tomllib.loads(private_read(STATE / "kata/config.toml"))
    if config.get("listen") != f"127.0.0.1:{KATA_PORT}" or config.get("web", {}).get("listen"):
        raise RuntimeError("Kata must retain the documented loopback API and shared UI port")


def kata_command():
    binary = RUNTIME_ROOT / "kata/kata"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError("missing executable Kata binary; build it before starting the service")
    return [str(binary), "daemon", "start", "--foreground", "--no-auto-token",
            "--listen", f"127.0.0.1:{KATA_PORT}"]


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
    print(f"Kata user service enabled and responsive at {KATA_URL}/kata")


def managed_kata(*, required=False):
    if not required and not (STATE / "kata-service.json").exists():
        return None
    pid = user_service_pid(KATA_UNIT)
    with HTTP.open(f"{KATA_URL}/api/v1/ping", timeout=3) as response:
        ping = json.load(response)
    if (ping.get("pid") != pid or ping.get("service") != "kata"
            or ping.get("ok") is not True or not ping.get("version")):
        raise RuntimeError("Kata health does not match the managed user service")
    with HTTP.open(f"{KATA_URL}/api/v1/health", timeout=3) as response:
        health = json.load(response)
    if (health.get("ok") is not True or health.get("version") != ping["version"]
            or health.get("db_path") != str(STATE / "kata/kata.db")
            or type(health.get("schema_version")) is not int or health["schema_version"] <= 0
            or not health.get("api_schema_version")):
        raise RuntimeError("Kata database health does not match its private profile")
    request = urllib.request.Request(f"{KATA_URL}/kata",
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


def model_routing():
    usai_path = STATE / "usai.json"
    if not usai_path.exists():
        return None
    usai_cfg = json.loads(private_read(usai_path))
    coder_model = usai_cfg.get("model")
    review_model = usai_cfg.get("review_model") or coder_model
    coder_family = usai_model_family(coder_model) if coder_model else None
    reviewer_family = usai_model_family(review_model) if review_model else None
    return {
        "coder_model": coder_model,
        "coder_family": coder_family,
        "reviewer_model": review_model,
        "reviewer_family": reviewer_family,
        "paired_adversarial": bool(
            coder_family in ADVERSARIAL_MODEL_FAMILIES
            and reviewer_family in ADVERSARIAL_MODEL_FAMILIES
            and coder_family != reviewer_family
        ),
    }


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
            "port_offset": PORT_OFFSET,
            "forge": forge,
            "kata_service": external.get("kata"),
            "model_routing": model_routing(),
            "projects": api("GET", "/projects") if forge else None}


ACCEPT_SERVICES = ("kata", "agentsview", "roborev", "forge")
ACCEPT_MCP_SERVERS = (LIBRARIAN_MCP_SERVER, "kata", "kenn-forge")


def accept_command_output(name):
    """Read-only probes used by accept; isolated so tests can replace them."""
    if name == "submodule":
        command, env = ["git", "-C", str(RUNTIME_ROOT), "submodule", "status"], None
    else:
        command, env = [verify_pi(settings(create=False)), "mcp", "list"], base_environment()
    return subprocess.run(command, env=env, text=True, capture_output=True,
                          check=True, timeout=180).stdout


def accept_binaries():
    config = settings(create=False)
    binaries = (RUNTIME_ROOT / "kata/kata", RUNTIME_ROOT / "roborev/bin/roborev",
                RUNTIME_ROOT / "agentsview/agentsview", Path(config["forge_binary"]), GH_BINARY)
    return [str(path) for path in binaries if not (path.is_file() and os.access(path, os.X_OK))]


def accept_repo(repo):
    repo = repo.expanduser().resolve()
    if not any(Path(project["local_path"]).resolve() == repo
               for project in api("GET", "/projects")["projects"]):
        raise RuntimeError(f"not registered with Forge; run register {repo}")
    hook = subprocess.run(["git", "-C", str(repo), "rev-parse", "--path-format=absolute",
                           "--git-path", "hooks/post-commit"],
                          text=True, capture_output=True, check=True, timeout=15).stdout.strip()
    hook = Path(hook)
    if not os.access(hook, os.X_OK) or "roborev" not in hook.read_text(errors="replace"):
        raise RuntimeError("post-commit hook does not run roborev; run roborev init --no-daemon")
    if not repo_init_module().is_installed(repo):
        raise RuntimeError("protected-branch push guard missing; run "
                           f"{sys.executable} {RUNTIME_ROOT / 'scripts/local_env.py'} init-repo {repo}")


def repo_init_module():
    """Import scripts/repo_init.py even when this file was loaded by path from elsewhere."""
    scripts = str(Path(__file__).resolve().parent)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import repo_init
    return repo_init


def run_native(command, repo, label):
    """Run a native CLI in a repo with the managed environment; return stderr+stdout on success."""
    result = subprocess.run(command, cwd=repo, env=base_environment(), text=True,
                            capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"{label} failed (exit {result.returncode}): "
                           f"{(result.stderr or result.stdout).strip()}")
    return result.stdout + result.stderr


def init_repo_services():
    """Real service bindings for repo_init.init_repo; tests replace them with fakes."""
    module = repo_init_module()

    def forge_up():
        try:
            if forge_probe() is None:
                raise module.ServiceUnavailable(f"Forge is not answering on 127.0.0.1:{FORGE_PORT}")
        except urllib.error.URLError as error:
            raise module.ServiceUnavailable(f"Forge is unreachable: {error}") from error

    def register(repo):
        settings()
        forge_up()
        try:
            if any(Path(project["local_path"]).resolve() == repo for project in api("GET", "/projects")["projects"]):
                return "SKIP", "already registered with Forge"
            with contextlib.redirect_stdout(io.StringIO()):
                register_project(repo)
        except urllib.error.URLError as error:
            raise module.ServiceUnavailable(f"Forge is unreachable: {error}") from error
        return "OK", "registered with Forge"

    def roborev_init(repo):
        binary = roborev_binary()
        if not (binary.is_file() and os.access(binary, os.X_OK)):
            raise RuntimeError(f"missing executable roborev binary: {binary}")
        run_native([str(binary), "init", "--no-daemon", "--binary", str(binary)], repo, "roborev init")

    def kata_init(repo, project):
        binary = RUNTIME_ROOT / "kata/kata"
        if not os.access(binary, os.X_OK):
            raise RuntimeError(f"missing executable kata binary: {binary}")
        try:
            run_native([str(binary), "init", "--project", project], repo, "kata init")
        except RuntimeError as error:
            if "unavailable" in str(error):
                raise module.ServiceUnavailable("Kata daemon is not reachable") from error
            raise

    def kata_mapping(project):
        forge_up()
        try:
            listing = handoff_get("forge", "/kata/project-mappings")
        except urllib.error.URLError as error:
            raise module.ServiceUnavailable(f"Forge could not read Kata project mappings: {error}") from error
        item = next((item for item in listing["projects"] if item["project_name"] == project), None)
        if item is None:
            return "", ""
        return item["status"], ((item.get("repo") or {}).get("repo_path") or "").lower()

    return module.InitServices(
        command=f"{sys.executable} {RUNTIME_ROOT / 'scripts/local_env.py'}",
        register=register, roborev_init=roborev_init, kata_init=kata_init,
        kata_mapping=kata_mapping, verify=accept_repo)


def init_repo(path, *, project=None, skip_kata=False, remove_guard=False):
    return repo_init_module().init_repo(path, init_repo_services(), project=project,
                                        skip_kata=skip_kata, remove_guard_only=remove_guard)


def accept(home=None, repos=()):
    """Read-only fresh-host acceptance: report each check, never print secret values."""
    home = Path.home() if home is None else Path(home)
    command = f"{sys.executable} {RUNTIME_ROOT / 'scripts/local_env.py'}"

    def links():
        for link, target in ((home / ".local/bin/kata", RUNTIME_ROOT / "kata/kata"),
                             (home / ".local/bin/roborev", RUNTIME_ROOT / "roborev/bin/roborev"),
                             (home / ".roborev", STATE / "roborev")):
            if not link.is_symlink() or link.resolve() != target.resolve():
                raise RuntimeError(f"{link} must link to {target}; rerun dist/install.sh")

    def extensions():
        packages = json.loads(private_read(STATE / "pi/settings.json")).get("packages", [])
        missing = [name for name in PI_EXTENSIONS if name not in packages]
        if missing:
            raise RuntimeError(f"missing {', '.join(missing)}; run {command} install-pi-extensions")
        if not PI_REVIEW_EXTENSION_PATH.is_file():
            raise RuntimeError(f"missing {PI_REVIEW_EXTENSION_PATH}")

    def binaries():
        missing = accept_binaries()
        if missing:
            raise RuntimeError(f"missing executables {', '.join(missing)}; rerun dist/install.sh")

    def submodules():
        drift = [line.split()[1] for line in accept_command_output("submodule").splitlines()
                 if line and line[0] != " "]
        if drift:
            raise RuntimeError(f"not at pinned gitlinks: {', '.join(drift)}; "
                               "run scripts/bootstrap-sources.sh after preserving local changes")

    def mcp():
        servers = json.loads(private_read(STATE / "pi/mcp.json"))["mcpServers"]
        output = accept_command_output("mcp")
        absent = [name for name in ACCEPT_MCP_SERVERS if name not in servers]
        if absent:
            raise RuntimeError(f"not configured: {', '.join(absent)}; rerun {command} setup")
        missing = [name for name in servers if f"{name}: connected" not in output]
        if missing:
            raise RuntimeError(f"not connected: {', '.join(missing)}; "
                               "inspect scripts/pi-local.py mcp list")

    def provider():
        try:
            model = json.loads(private_read(STATE / "usai.json"))["model"]
            entries = json.loads(private_read(STATE / "pi/models.json"))["providers"]["usai"]["models"]
        except (FileNotFoundError, KeyError, TypeError) as error:
            raise RuntimeError(f"run {command} configure-provider") from error
        if not any(isinstance(entry, dict) and entry.get("id") == model for entry in entries):
            raise RuntimeError(f"saved model is missing from pi/models.json; run {command} configure-provider")

    def key():
        try:
            validate_key(private_read(STATE / "secrets/usai-api-key"))
        except UnicodeError:
            raise RuntimeError("USAi key file must contain a UTF-8 token; its value was not logged") from None
        except FileNotFoundError:
            raise RuntimeError(f"no private key; run {command} set-key") from None

    def github():
        try:
            hosts = private_read(STATE / "gh/hosts.yml")
        except FileNotFoundError:
            hosts = ""
        if not any(line.rstrip() == "github.com:" for line in hosts.splitlines()):
            raise RuntimeError(f"no GitHub login; run {RUNTIME_ROOT / 'scripts/gh-local.py'} auth login "
                               "--hostname github.com --web --git-protocol https --insecure-storage")

    def pi():
        config = settings(create=False)
        verify_pi(config)
        if config.get("pi_version") != PI_VERSION:
            raise RuntimeError(f"saved pi_version differs from {PI_VERSION}; rerun setup")

    def service(name):
        return lambda: globals()[f"managed_{name}"](required=True)

    checks = [("pi", pi), ("pi-extensions", extensions), ("binaries", binaries),
              ("submodules", submodules), ("native-links", links), ("mcp", mcp),
              *((f"service:{name}", service(name)) for name in ACCEPT_SERVICES),
              ("usai-provider", provider), ("usai-key", key), ("github-login", github),
              *((f"repo:{Path(repo).expanduser().resolve()}", lambda repo=repo: accept_repo(Path(repo)))
                for repo in repos)]
    failures = []
    for name, check in checks:
        try:
            check()
        except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
            failures.append(name)
            print(f"FAIL {name}: {error}", flush=True)
        else:
            print(f"PASS {name}", flush=True)
    print(f"Acceptance: {len(checks) - len(failures)}/{len(checks)} checks passed; "
          "no model call, service change or credential output was made.")
    return failures


POLICY_PROBE = ROOT / "scripts/pi-policy-probe.ts"
REVIEW_PROBE_ARGS = ("--mode", "json", "--json-schema", '{"type":"object"}', "--json-output",
                     os.devnull, "--json-fallback", "none", "--tools", "read,grep,find,ls,json_output")


def policy_probe(cwd, extra=()):
    """Report the policy Pi loads at cwd; the probe exits before any model request."""
    command, env = pi_launch(["--no-session", *extra, "--extension", str(POLICY_PROBE), "-p", "probe"])
    output = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True,
                            timeout=180).stdout
    for line in output.splitlines():
        if line.startswith("PI_POLICY_PROBE "):
            return json.loads(line.removeprefix("PI_POLICY_PROBE "))
    raise RuntimeError("policy probe did not report; inspect scripts/pi-local.py startup")


def policy_failures(surface, report, cwd):
    """Compare one probe report with the expected loaded policy for its surface."""
    private = str(STATE / "pi/AGENTS.md")
    override = str(Path(cwd) / "AGENTS.override.md")
    files, sections = report["context_files"], report["sections"]
    if surface == "review":
        loaded = [*files, *report["skills"]]
        loaded += ["forge_workspace"] if "forge_workspace" in sections else []
        loaded += ["Superpowers bootstrap"] if report["superpowers_bootstrap"] else []
        return [f"review inherits {item}" for item in loaded]
    failures = []
    if not report["superpowers_bootstrap"] or "using-superpowers" not in report["skills"]:
        failures.append("Superpowers is not loaded")
    if not Path(private).is_file():
        failures.append(f"private Pi coder contract {private} is missing")
    elif private not in files:
        failures.append("private Pi AGENTS.md is not loaded")
    if Path(private).is_file() and Path(private).read_text() != CODER_CONTRACT.read_text():
        failures.append("private Pi coder contract differs from scripts/pi-coder-contract.md; rerun setup")
    if surface == "forge":
        if override not in files:
            failures.append("AGENTS.override.md is not loaded")
        if "forge_workspace" not in sections:
            failures.append("Forge workspace policy section is missing")
    elif "forge_workspace" in sections:
        failures.append("Forge workspace policy loads outside a Forge workspace")
    return failures


def verify_pi_policy(cwd):
    """Probe coder and roborev review policy at cwd without a model request."""
    cwd = Path(cwd).expanduser().resolve()
    coder = "forge" if (cwd / "AGENTS.override.md").is_file() else "private"
    failures = []
    for surface, extra in ((coder, ()), ("review", REVIEW_PROBE_ARGS)):
        report = policy_probe(cwd, extra)
        problems = policy_failures(surface, report, cwd)
        failures += problems
        print(f"{'FAIL' if problems else 'PASS'} {surface}: context={report['context_files']} "
              f"skills={len(report['skills'])} bootstrap={report['superpowers_bootstrap']} "
              f"forge_workspace={'forge_workspace' in report['sections']}", flush=True)
        for problem in problems:
            print(f"  - {problem}", flush=True)
    print("Policy probe made no model call.")
    return failures


HANDOFF_BASES = {"forge": lambda: f"http://127.0.0.1:{FORGE_PORT}/api/v1",
                 "roborev": lambda: f"http://127.0.0.1:{ROBOREV_PORT}/api",
                 "agentsview": lambda: f"http://127.0.0.1:{AGENTSVIEW_PORT}/api/v1"}


def handoff_get(service, path, headers=None):
    """Read-only GET against one loopback service; isolated so tests can replace it."""
    request = urllib.request.Request(HANDOFF_BASES[service]() + path,
                                     headers={"Accept": "application/json", **(headers or {})})
    with HTTP.open(request, timeout=15) as response:
        return json.load(response)


def verify_handoff(workspace_id, commit=None):
    """Check one Forge Kata workspace's task, worktree, Pi, AgentsView and roborev linkage.

    Every probe is a read-only GET or git read; nothing is launched, claimed or closed.
    """
    failures, facts = [], {}

    def check(name, probe):
        try:
            detail = probe()
        except (OSError, ValueError, KeyError, TypeError, RuntimeError,
                subprocess.SubprocessError) as error:
            failures.append(name)
            print(f"FAIL {name}: {error}", flush=True)
        else:
            print(f"PASS {name}: {detail}", flush=True)

    def git(*args):
        return subprocess.run(["git", "-C", str(facts["worktree"]), *args], text=True,
                              capture_output=True, check=True, timeout=15).stdout.strip()

    workspace = handoff_get("forge", f"/workspaces/{urllib.parse.quote(workspace_id)}")
    kata = workspace.get("kata") or {}
    facts["worktree"] = Path(workspace["worktree_path"]).resolve()

    def task_detail():
        path = f"/kata/daemons/{kata['daemon_id']}/issues/{kata['issue_uid']}"
        result = handoff_get("forge", path)
        issue = result["detail"]["issue"]
        if result.get("daemon_health") != "connected":
            raise RuntimeError(f"Kata daemon health is {result.get('daemon_health')}")
        if (issue["uid"], issue["title"]) != (kata["issue_uid"], kata["title"]):
            raise RuntimeError("Forge task detail differs from the workspace's Kata task")
        return f"{kata['qualified_id']} {issue['title']!r}"

    def task_mapping():
        expected = f"{workspace['repo_owner']}/{workspace['repo_name']}".lower()
        mappings = handoff_get("forge", "/kata/project-mappings",
                               {"X-Kenn-Forge-Kata-Daemon": kata["daemon_id"]})
        if mappings["daemon_id"] != kata["daemon_id"]:
            raise RuntimeError(f"Forge returned daemon {mappings['daemon_id']} mappings")
        mapping = next((project for project in mappings["projects"]
                       if project["project_uid"] == kata["project_uid"]), None)
        if mapping is None:
            raise RuntimeError(f"Forge has no mapping for Kata project {kata['project_uid']}")
        actual = (mapping.get("repo") or {}).get("repo_path", "").lower()
        if mapping["status"] != "mapped" or actual != expected:
            raise RuntimeError(f"project maps to {actual or mapping['status']}, not {expected}")
        return f"{kata['project_uid']} -> {expected}"

    def worktree():
        branch = git("branch", "--show-current")
        if branch != workspace["git_head_ref"]:
            raise RuntimeError(f"worktree is on {branch!r}, not {workspace['git_head_ref']!r}")
        return f"{facts['worktree']} on {branch}"

    def pi_launch():
        sessions = handoff_get("forge", f"/workspaces/{urllib.parse.quote(workspace_id)}/agent-sessions")
        session = next((item for item in sessions["sessions"] if item["agent"] == "pi"), None)
        if session is None:
            raise RuntimeError("Forge reports no Pi session for this workspace")
        facts["session"] = session["session_id"]
        return f"target {session['target_key']} session {session['session_id']}"

    def agentsview():
        if "session" not in facts:
            raise RuntimeError("no Pi session to look up")
        try:
            session = handoff_get("agentsview", f"/sessions/pi:{facts['session']}")
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"AgentsView has not indexed pi:{facts['session']} "
                               f"(HTTP {error.code})") from None
        if Path(session["cwd"]).resolve() != facts["worktree"]:
            raise RuntimeError(f"AgentsView session cwd is {session['cwd']}")
        return session["id"]

    def resume():
        if "session" not in facts:
            raise RuntimeError("no Pi session to resume")
        saved = next((STATE / "pi/sessions").rglob(f"*_{facts['session']}.jsonl"), None)
        if saved is None:
            raise RuntimeError("no saved Pi session file; Forge cannot resume with --session")
        return f"pi --session {facts['session']}"

    def review_job():
        sha = git("rev-parse", commit or "HEAD")
        query = {"branch": workspace["git_head_ref"], "status": "done",
                 "exclude_job_type": "fix", "limit": 200}
        job = None
        while job is None:
            page = handoff_get("roborev", f"/jobs?{urllib.parse.urlencode(query)}")
            job = next((job for job in page["jobs"]
                        if job["git_ref"].split("..")[-1] == sha and job["status"] == "done"
                        and job.get("job_type") != "fix"
                        and Path(job["worktree_path"]).resolve() == facts["worktree"]), None)
            if not page.get("has_more") or not page.get("next_cursor"):
                break
            query["cursor"] = page["next_cursor"]
        if job is None:
            raise RuntimeError(f"no finished roborev job in this worktree ends at {sha[:12]}")
        facts["job"] = job
        return f"job {job['id']} verdict {job.get('verdict')} {job.get('web_url', '')}".rstrip()

    def review_disposition():
        job = facts.get("job")
        if job is None:
            raise RuntimeError("no review job to dispose")
        if job.get("verdict") == "P":
            return "passed"
        if job.get("closed"):
            return "closed"
        responses = handoff_get("roborev", f"/comments?job_id={job['id']}")["responses"]
        if not responses:
            raise RuntimeError(f"failing job {job['id']} has no comment or close; "
                               f"record a disposition with roborev comment {job['id']}")
        return f"{len(responses)} stored response(s)"

    for name, probe in (("task-detail", task_detail), ("task-mapping", task_mapping),
                        ("worktree", worktree), ("pi-launch", pi_launch),
                        ("agentsview", agentsview), ("resume", resume),
                        ("review-job", review_job), ("review-disposition", review_disposition)):
        check(name, probe)
    # Forge renders its Reviews tab only for pull_request workspaces; a Kata workspace's
    # review linkage is the roborev post-commit route and standalone review page.
    if workspace["item_type"] == "pull_request":
        print("PASS native-review-ui: Forge Reviews tab", flush=True)
    else:
        print(f"GAP native-review-ui: Forge shows no Reviews tab for {workspace['item_type']} "
              "workspaces; use the roborev review page above", flush=True)
    print(f"Handoff: {8 - len(failures)}/8 checks passed; read-only, no model call.")
    return failures


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
             f"http://127.0.0.1:{ROBOREV_PORT}/api/status"),
            ("kata", RUNTIME_ROOT / "kata/kata", kata_command()[1:],
             f"{KATA_URL}/api/v1/health"),
            ("agentsview", RUNTIME_ROOT / "agentsview/agentsview", agentsview_command()[1:],
             f"http://127.0.0.1:{AGENTSVIEW_PORT}/api/ping"),
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
    init.add_argument("--librarian-executable", type=Path)
    init.add_argument("--librarian-reader", type=Path)
    init.add_argument("--librarian-root", type=Path)
    init.add_argument("--librarian-selection", type=Path)
    commands.add_parser("run", help="run supervised services; retain independent services and saved state")
    commands.add_parser("stop", help="signal only the verified local supervisor")
    commands.add_parser("status", help="show the verified supervisor and persistent project registry")
    acceptance = commands.add_parser(
        "accept", help="read-only fresh-host acceptance of toolchains, Pi, MCP, services and credentials")
    acceptance.add_argument("--repo", type=Path, action="append", default=[],
                            help="also require Forge registration and roborev hooks (repeatable)")
    policy = commands.add_parser(
        "verify-pi-policy", help="show and check the policy coder and roborev review Pi load (no model call)")
    policy.add_argument("--cwd", type=Path, default=Path.cwd())
    handoff = commands.add_parser(
        "verify-handoff", help="check a Forge Kata workspace's task, Pi, AgentsView and roborev linkage")
    handoff.add_argument("workspace", help="Forge workspace ID")
    handoff.add_argument("--commit", help="commit whose review to check (default: worktree HEAD)")
    key = commands.add_parser("set-key", help="prompt privately for the USAi key; never supply it on the command line")
    key.add_argument("--private-only", action="store_true", help="do not link/change existing global Pi credentials")
    commands.add_parser("configure-agentsview-pricing",
                        help="price guarded USAi Sol deployments as their catalog models")
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
    provider.add_argument("--review-model", help="optional opposite-family USAi model for roborev reviews")
    provider.add_argument("--api", required=True,
                          choices=("openai-completions", "openai-responses", "anthropic-messages"))
    register = commands.add_parser("register", help="register an existing local Git project without editing it")
    register.add_argument("path", type=Path)
    init_repo_parser = commands.add_parser(
        "init-repo", help="initialize Forge, roborev, Kata and the protected-branch push guard in another Git repo")
    init_repo_parser.add_argument("path", type=Path)
    init_repo_parser.add_argument("--project", help="Kata project name (default: the repository directory name)")
    init_repo_parser.add_argument("--skip-kata", action="store_true", help="do not create .kata.toml")
    init_repo_parser.add_argument("--remove-guard", action="store_true",
                                  help="only remove the protected-branch push guard")
    lib_cfg = commands.add_parser("configure-librarian",
                                  help="rebind the private falcon-librarian MCP server to an isolated Librarian instance")
    lib_cfg.add_argument("--librarian-root", type=Path, required=True)
    lib_cfg.add_argument("--librarian-executable", type=Path)
    lib_cfg.add_argument("--librarian-reader", type=Path)
    lib_cfg.add_argument("--librarian-selection", type=Path)
    lib_cfg.add_argument("--audit", action="store_true",
                         help="opt in to the Librarian's private full-text audit log for managed bindings")
    lib_cfg.add_argument("--copilot-config", type=Path,
                         help="also bind this Copilot MCP config's falcon-librarian server (never implicit)")
    mvp = commands.add_parser("provision-librarian-mvp",
                              help="package and initialize an isolated Librarian MVP instance (Layer 1 isolation)")
    mvp.add_argument("--source", type=Path, default=Path.home() / "the_librarian")
    mvp.add_argument("--dest", type=Path, default=Path.home() / "falcon-librarian-mvp")
    mvp.add_argument("--inbox", type=Path)
    mvp.add_argument("--repos-root", type=Path)
    mvp.add_argument("--bind-mcp", action="store_true",
                     help="also rebind the private falcon-librarian MCP server to this instance")
    args = parser.parse_args()
    try:
        if args.command == "setup":
            setup(args.corpus, args.forge_binary, args.librarian_executable,
                  args.librarian_reader, args.librarian_root, args.librarian_selection)
        elif args.command == "configure-librarian":
            configure_librarian(args.librarian_root, args.librarian_executable,
                                args.librarian_reader, args.librarian_selection,
                                audit=args.audit, copilot_config=args.copilot_config)
        elif args.command == "provision-librarian-mvp":
            provision_librarian_mvp(args.source, args.dest, inbox=args.inbox,
                                    repos_root=args.repos_root, bind_mcp=args.bind_mcp)
        elif args.command == "run":
            serve()
        elif args.command == "stop":
            stop()
        elif args.command == "status":
            print(json.dumps(status(), indent=2))
        elif args.command == "accept":
            if accept(repos=args.repo):
                return 1
        elif args.command == "verify-pi-policy":
            if verify_pi_policy(args.cwd):
                return 1
        elif args.command == "verify-handoff":
            if verify_handoff(args.workspace, args.commit):
                return 1
        elif args.command == "set-key":
            set_key(private_only=args.private_only)
        elif args.command == "configure-agentsview-pricing":
            configure_agentsview_pricing()
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
        elif args.command == "install-pi-extensions":
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
            configure_provider(args.base_url, args.model, args.api, review_model=args.review_model)
        elif args.command == "list-models":
            list_models(args.base_url)
        elif args.command == "register":
            settings()
            if forge_probe() is None:
                raise RuntimeError("start the Forge service or `forge-run` before registering a project")
            register_project(args.path)
        elif args.command == "init-repo":
            return init_repo(args.path, project=args.project, skip_kata=args.skip_kata,
                             remove_guard=args.remove_guard)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
