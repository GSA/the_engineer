"""GitHub Copilot CLI on USAi: a private COPILOT_HOME with bring-your-own-key settings.

Copilot reads the USAi key per request through scripts/usai-key.py
(COPILOT_PROVIDER_API_KEY_COMMAND), so the key is never placed in an
environment variable, argument or file under COPILOT_HOME. The user's own
~/.copilot is never read or changed.
"""

import json
import os
from pathlib import Path
import shutil
import sys

import host_setup
import local_env

DEFAULT_COPILOT_MODEL = "claude-sonnet-5.5"
# Verified 2026-11-13 with Copilot CLI 1.0.111: Claude models complete tool calls
# through USAi's OpenAI-compatible API; GPT Sol returns 422 and Gemini rejects
# Copilot's tool schema.
SUPPORTED_FAMILIES = ("claude",)
TOOLS_BIN = Path.home() / ".local/engineer/npm/bin"
INHERITED_SECRETS = ("COPILOT_PROVIDER_API_KEY", "COPILOT_PROVIDER_BEARER_TOKEN",
                     "COPILOT_PROVIDER_HEADERS", "COPILOT_PROVIDERS_CONFIG")


def copilot_home():
    return local_env.STATE / "copilot"


def copilot_binary():
    path = os.pathsep.join([str(TOOLS_BIN), os.environ.get("PATH", "")])
    return shutil.which("copilot", path=path)


def validate_copilot_model(model):
    model = local_env.normalize_usai_model(model)
    if local_env.usai_model_family(model) not in SUPPORTED_FAMILIES:
        raise RuntimeError(f"{model} does not work with Copilot on USAi; choose a Claude model "
                           f"(for example {DEFAULT_COPILOT_MODEL})")
    return model


def copilot_model():
    try:
        saved = json.loads(local_env.private_read(local_env.STATE / "usai.json"))
    except FileNotFoundError:
        return DEFAULT_COPILOT_MODEL
    model = saved.get("copilot_model") or saved.get("model") or DEFAULT_COPILOT_MODEL
    try:
        return validate_copilot_model(model)
    except RuntimeError:
        return DEFAULT_COPILOT_MODEL


def mcp_servers():
    return {
        "kata": {
            "type": "local",
            "command": str(local_env.RUNTIME_ROOT / "kata/kata"),
            "args": ["mcp", "serve"],
            "env": {"KATA_SERVER": local_env.KATA_URL},
            "tools": ["*"],
        },
        "kenn-forge": {
            "type": "http",
            "url": f"http://127.0.0.1:{local_env.FORGE_MCP_PORT}/mcp",
            "tools": ["*"],
        },
    }


def configure_copilot(model=None):
    """Create or refresh the private Copilot home; preserve servers the user added."""
    local_env.settings()
    model = validate_copilot_model(model) if model else copilot_model()
    home = copilot_home()
    local_env.private_dir(home)
    path = home / "mcp-config.json"
    saved = json.loads(local_env.private_read(path)) if path.exists() else {}
    servers = saved.get("mcpServers", {})
    if not isinstance(servers, dict):
        raise RuntimeError(f"invalid Copilot MCP settings; inspect {path} first")
    local_env.json_write(path, {**saved, "mcpServers": {**servers, **mcp_servers()}}, replace=True)
    local_env.private_write(home / "copilot-instructions.md",
                            local_env.CODER_CONTRACT.read_text(), replace=True)
    usai_path = local_env.STATE / "usai.json"
    usai = json.loads(local_env.private_read(usai_path)) if usai_path.exists() else {}
    local_env.json_write(usai_path, {**usai, "copilot_model": model}, replace=True)
    print(f"Copilot uses USAi model {model}; its settings are private in {home}.")


def usai_base_url():
    try:
        models = json.loads(local_env.private_read(local_env.STATE / "pi/models.json"))
        return models["providers"]["usai"]["baseUrl"]
    except (FileNotFoundError, KeyError, TypeError) as error:
        raise RuntimeError("the USAi connection is not set up yet; run ./engineer install") from error


def copilot_launch(args):
    if any(arg == "--api-key" or arg.startswith("--api-key=") for arg in args):
        raise RuntimeError("never pass a key on the command line; run ./engineer key instead")
    try:
        local_env.settings()
    except FileNotFoundError:
        raise RuntimeError("Engineer is not installed yet; run ./engineer install") from None
    if not (copilot_home() / "mcp-config.json").exists():
        raise RuntimeError("Copilot is not set up for USAi yet; run ./engineer install")
    try:
        local_env.load_usai_key()
    except FileNotFoundError:
        raise RuntimeError("no USAi key is saved yet; run ./engineer key") from None
    binary = copilot_binary()
    if binary is None:
        raise RuntimeError("Copilot CLI is not installed; run ./engineer install")
    model = copilot_model()
    limits = local_env.USAI_MODEL_LIMITS.get(model, {})
    env = {key: value for key, value in os.environ.items() if key not in INHERITED_SECRETS}
    env.update({
        "COPILOT_HOME": str(copilot_home()),
        "COPILOT_AUTO_UPDATE": "false",
        "COPILOT_PROVIDER_BASE_URL": usai_base_url(),
        "COPILOT_PROVIDER_TYPE": "openai",
        "COPILOT_PROVIDER_API_KEY_COMMAND": " ".join(
            [sys.executable, str(local_env.RUNTIME_ROOT / "scripts/usai-key.py")]),
        "COPILOT_MODEL": model,
        "PATH": host_setup.tool_path(path=os.pathsep.join([str(TOOLS_BIN), env.get("PATH", "")])),
    })
    if limits:
        env["COPILOT_PROVIDER_MAX_PROMPT_TOKENS"] = str(limits["contextWindow"] - limits["maxTokens"])
        env["COPILOT_PROVIDER_MAX_OUTPUT_TOKENS"] = str(limits["maxTokens"])
    command = [binary, "--plugin-dir", str(local_env.RUNTIME_ROOT / "superpowers"), *args]
    return command, env


def check():
    """Return (status, message) for ./engineer doctor; SKIP when Copilot was not chosen."""
    if not copilot_home().exists():
        return "SKIP", "Copilot on USAi was not set up (optional)"
    if copilot_binary() is None:
        return "FAIL", "Copilot CLI is missing; run ./engineer install"
    if not (copilot_home() / "mcp-config.json").exists():
        return "FAIL", "Copilot settings are missing; run ./engineer install"
    return "PASS", f"Copilot uses USAi model {copilot_model()}"
