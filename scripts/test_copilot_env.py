import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import copilot_env
import local_env
import local_state


class CopilotEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="copilot-env-test-", dir=local_state.state_parent())
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state = self.root / "environment"
        self.addCleanup(patch.stopall)
        patch.object(local_env, "STATE", self.state).start()
        local_env.private_dir(self.state)
        local_env.private_dir(self.state / "pi")
        local_env.private_dir(self.state / "secrets")
        local_env.json_write(self.state / "environment.json", {"forge_binary": "/x"})
        local_env.json_write(self.state / "pi/models.json", {"providers": {"usai": {
            "baseUrl": "https://usai.example.test/v1", "api": "openai-completions",
            "apiKey": "${USAI_API_KEY}", "models": [{"id": "claude-sonnet-5.5"}]}}})
        local_env.json_write(self.state / "usai.json", {
            "model": "claude-sonnet-5.5", "review_model": "gpt-6.1-sol-latest-guardrails-defaultv2"})
        local_env.private_write(self.state / "secrets/usai-api-key", "test-only-token\n")
        self.copilot = self.root / "bin/copilot"
        self.copilot.parent.mkdir()
        self.copilot.write_text("#!/bin/sh\n")
        self.copilot.chmod(0o755)
        patch.object(copilot_env.shutil, "which", return_value=str(self.copilot)).start()

    def configure(self, model=None):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            copilot_env.configure_copilot(model)
        return output.getvalue()

    def test_configure_writes_private_home_with_mcp_and_contract_but_no_key(self):
        self.configure()
        home = self.state / "copilot"
        self.assertEqual(home.stat().st_mode & 0o777, 0o700)
        servers = json.loads((home / "mcp-config.json").read_text())["mcpServers"]
        self.assertEqual(set(servers), {"kata", "kenn-forge"})
        self.assertEqual(servers["kata"]["env"]["KATA_SERVER"], local_env.KATA_URL)
        self.assertEqual(servers["kenn-forge"]["url"], f"http://127.0.0.1:{local_env.FORGE_MCP_PORT}/mcp")
        self.assertEqual((home / "copilot-instructions.md").read_text(), local_env.CODER_CONTRACT.read_text())
        for path in home.rglob("*"):
            if path.is_file():
                self.assertNotIn("test-only-token", path.read_text())
        self.assertEqual(json.loads((self.state / "usai.json").read_text())["copilot_model"], "claude-sonnet-5.5")

    def test_configure_without_dev_tools_drops_kata_and_forge_servers(self):
        self.configure()
        local_env.json_write(self.state / "environment.json", {}, replace=True)
        self.configure()
        servers = json.loads((self.state / "copilot/mcp-config.json").read_text())["mcpServers"]
        self.assertEqual(servers, {})

    def test_configure_preserves_user_added_mcp_servers(self):
        self.configure()
        path = self.state / "copilot/mcp-config.json"
        saved = json.loads(path.read_text())
        saved["mcpServers"]["mine"] = {"type": "local", "command": "/bin/true", "tools": ["*"]}
        local_env.json_write(path, saved, replace=True)
        self.configure()
        self.assertIn("mine", json.loads(path.read_text())["mcpServers"])

    def test_copilot_model_must_be_a_supported_family(self):
        with self.assertRaisesRegex(RuntimeError, "Claude"):
            self.configure("gpt-6.1-sol-latest-guardrails-defaultv2")
        with self.assertRaisesRegex(RuntimeError, "Claude"):
            self.configure("gemini-4-argon")
        self.configure("claude-opus-5.5")
        self.assertEqual(copilot_env.copilot_model(), "claude-opus-5.5")

    def test_launch_uses_usai_byok_with_a_key_command_not_a_key(self):
        self.configure()
        with patch.dict(os.environ, {"COPILOT_PROVIDER_API_KEY": "inherited-secret",
                                     "COPILOT_PROVIDER_BEARER_TOKEN": "inherited-bearer"}):
            command, env = copilot_env.copilot_launch(["-p", "hello"])
        self.assertEqual(command[0], str(self.copilot))
        self.assertEqual(command[1:3], ["--plugin-dir", str(local_env.RUNTIME_ROOT / "superpowers")])
        self.assertEqual(command[-2:], ["-p", "hello"])
        self.assertEqual(env["COPILOT_HOME"], str(self.state / "copilot"))
        self.assertEqual(env["COPILOT_PROVIDER_BASE_URL"], "https://usai.example.test/v1")
        self.assertEqual(env["COPILOT_PROVIDER_TYPE"], "openai")
        self.assertEqual(env["COPILOT_MODEL"], "claude-sonnet-5.5")
        self.assertEqual(env["COPILOT_AUTO_UPDATE"], "false")
        self.assertIn("scripts/usai-key.py", env["COPILOT_PROVIDER_API_KEY_COMMAND"])
        self.assertEqual(env["COPILOT_PROVIDER_MAX_PROMPT_TOKENS"], "368000")
        self.assertNotIn("COPILOT_PROVIDER_API_KEY", env)
        self.assertNotIn("COPILOT_PROVIDER_BEARER_TOKEN", env)
        self.assertNotIn("test-only-token", json.dumps([command, env]))
        path = env["PATH"].split(os.pathsep)
        self.assertLess(path.index(str(copilot_env.host_setup.prefix() / "node/bin")),
                        path.index("/usr/bin") if "/usr/bin" in path else len(path))

    def test_launch_explains_missing_setup_in_plain_language(self):
        with self.assertRaisesRegex(RuntimeError, "engineer install"):
            copilot_env.copilot_launch([])
        self.configure()
        (self.state / "secrets/usai-api-key").unlink()
        with self.assertRaisesRegex(RuntimeError, "engineer key"):
            copilot_env.copilot_launch([])
        local_env.private_write(self.state / "secrets/usai-api-key", "test-only-token\n")
        patch.object(copilot_env.shutil, "which", return_value=None).start()
        with self.assertRaisesRegex(RuntimeError, "Copilot CLI is not installed"):
            copilot_env.copilot_launch([])

    def test_launch_refuses_api_key_arguments(self):
        self.configure()
        with self.assertRaisesRegex(RuntimeError, "never"):
            copilot_env.copilot_launch(["--api-key", "x"])

    def test_check_reports_skip_when_copilot_was_never_configured(self):
        self.assertEqual(copilot_env.check()[0], "SKIP")
        self.configure()
        self.assertEqual(copilot_env.check()[0], "PASS")
        patch.object(copilot_env.shutil, "which", return_value=None).start()
        status, message = copilot_env.check()
        self.assertEqual(status, "FAIL")
        self.assertIn("engineer install", message)


if __name__ == "__main__":
    unittest.main()
