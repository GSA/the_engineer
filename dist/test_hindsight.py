"""Offline Compose contract checks; no image, daemon, credentials or model calls."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "dist" / "hindsight.compose.yaml"
EXAMPLE = ROOT / "dist" / "hindsight.env.example"
IMAGE = (
    "ghcr.io/vectorize-io/hindsight-api:1.1.0@"
    "sha256:cdfeb26e92ad33d54a8a7e4cfe6e67b55d619f25ea5f5bba0a3281d701a82b36"
)


class HindsightComposeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if Path.cwd() != ROOT:
            raise RuntimeError("Run from the repository root.")
        if shutil.which("docker") is None:
            raise unittest.SkipTest("Optional Hindsight checks require Docker Compose.")
        compose = subprocess.run(
            ["docker", "compose", "version", "--short"],
            capture_output=True, text=True, timeout=30,
        )
        if compose.returncode:
            raise unittest.SkipTest(
                f"Optional Docker Compose is unavailable (exit {compose.returncode})."
            )
        cls.fixture = Path(".local") / f"hindsight-contract-{uuid.uuid4().hex}"
        cls.fixture.mkdir(parents=True, mode=0o700)
        cls.addClassCleanup(shutil.rmtree, cls.fixture)
        private_env = cls.fixture / "runtime.env"
        private_env.write_text(
            "HINDSIGHT_API_TENANT_API_KEY=synthetic-only-$RAW#literal\n"
            "HINDSIGHT_API_LLM_API_KEY=synthetic-only-not-a-credential\n"
        )
        private_env.chmod(0o600)
        cls.selectors = {
            "HINDSIGHT_PRIVATE_ENV": str(private_env.resolve()),
            "HINDSIGHT_DATA_VOLUME": "synthetic-hindsight-volume-not-created",
            "HINDSIGHT_LLM_PROVIDER": "openai",
            "HINDSIGHT_LLM_MODEL": "synthetic-model-not-called",
            "HINDSIGHT_LLM_BASE_URL": "https://model.invalid/v1",
            "HINDSIGHT_EMBEDDINGS_LOCAL_MODEL": "synthetic-embedding-not-loaded",
            "HINDSIGHT_RERANKER_LOCAL_MODEL": "synthetic-reranker-not-loaded",
        }
        cls.base_env = {
            key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ
        }
        cls.base_env.update(
            DOCKER_HOST=f"unix://{cls.fixture.resolve()}/no-daemon.sock",
            TMPDIR=str(cls.fixture.resolve()),
        )

    def compose(self, *args, selectors=None, profile=True):
        env = self.base_env | (self.selectors if selectors is None else selectors)
        command = [
            "docker", "compose", "--env-file", "/dev/null", "-f", str(COMPOSE),
        ]
        if profile:
            command += ["--profile", "hindsight"]
        return subprocess.run(
            command + ["config", *args],
            env=env, cwd=ROOT, capture_output=True, text=True, timeout=30,
        )

    def model(self):
        result = self.compose("--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_disabled_without_explicit_profile(self):
        result = self.compose("--services", profile=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_every_unresolved_selector_blocks_configuration(self):
        for key in self.selectors:
            with self.subTest(key=key):
                selectors = self.selectors | {key: ""}
                result = self.compose("--quiet", selectors=selectors)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(key, result.stderr)

    def test_missing_private_env_blocks_configuration(self):
        selectors = self.selectors | {
            "HINDSIGHT_PRIVATE_ENV": str(self.fixture.resolve() / "absent.env")
        }
        result = self.compose("--quiet", selectors=selectors)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("absent.env", result.stderr)

    def test_isolated_pinned_service_and_private_storage(self):
        model = self.model()
        self.assertEqual(model["name"], "engineer-hindsight")
        self.assertEqual(set(model["services"]), {"hindsight"})
        service = model["services"]["hindsight"]
        self.assertEqual(service["image"], IMAGE)
        self.assertEqual(service["profiles"], ["hindsight"])
        self.assertEqual(service["pull_policy"], "never")
        self.assertEqual(service["restart"], "no")
        self.assertEqual(service["stop_grace_period"], "1m0s")
        self.assertNotIn("build", service)
        self.assertNotIn("privileged", service)
        self.assertNotIn("network_mode", service)
        self.assertIsNone(service.get("command"))
        self.assertIsNone(service.get("entrypoint"))
        self.assertEqual(len(service["ports"]), 1)
        port = service["ports"][0]
        self.assertEqual(port["host_ip"], "127.0.0.1")
        self.assertEqual(port["published"], "18888")
        self.assertEqual(port["target"], 8888)
        self.assertEqual(len(service["volumes"]), 1)
        volume = service["volumes"][0]
        self.assertEqual(volume["type"], "volume")
        self.assertEqual(volume["source"], "data")
        self.assertEqual(volume["target"], "/home/hindsight/.pg0")
        self.assertEqual(model["volumes"]["data"], {
            "name": self.selectors["HINDSIGHT_DATA_VOLUME"], "external": True,
        })

    def test_auth_and_capture_controls(self):
        env = self.model()["services"]["hindsight"]["environment"]
        self.assertEqual(
            env["HINDSIGHT_API_TENANT_EXTENSION"],
            "hindsight_api.extensions.builtin.tenant:ApiKeyTenantExtension",
        )
        # Compose escapes dollars when serializing a reusable config document.
        self.assertEqual(
            env["HINDSIGHT_API_TENANT_API_KEY"].replace("$$", "$"),
            "synthetic-only-$RAW#literal",
        )
        for key in (
            "HINDSIGHT_ENABLE_CP", "HINDSIGHT_API_MCP_ENABLED",
            "HINDSIGHT_API_TENANT_MCP_AUTH_DISABLED",
            "HINDSIGHT_API_ENABLE_AUTO_CONSOLIDATION",
            "HINDSIGHT_API_ENABLE_OBSERVATIONS",
            "HINDSIGHT_API_ENABLE_FILE_UPLOAD_API", "HINDSIGHT_API_LLM_TRACE_ENABLED",
            "HINDSIGHT_API_LLM_DEBUG_DUMP_4XX", "HINDSIGHT_API_OTEL_TRACES_ENABLED",
            "HINDSIGHT_API_AUDIT_LOG_ENABLED", "HINDSIGHT_API_ACCESS_LOG",
        ):
            self.assertEqual(env[key], "false", key)
        self.assertEqual(env["HINDSIGHT_API_MCP_AUTH_TOKEN"], "")
        self.assertEqual(env["HINDSIGHT_API_DATABASE_URL"], "")

    def test_distinct_explicit_model_routes(self):
        env = self.model()["services"]["hindsight"]["environment"]
        self.assertEqual(env["HINDSIGHT_API_LLM_PROVIDER"], "openai")
        self.assertEqual(env["HINDSIGHT_API_LLM_BASE_URL"], "https://model.invalid/v1")
        self.assertEqual(env["HINDSIGHT_API_SKIP_LLM_VERIFICATION"], "true")
        self.assertEqual(env["HINDSIGHT_API_LLM_MAX_CONCURRENT"], "1")
        self.assertEqual(env["HINDSIGHT_API_DECISION_MODEL_PROVIDER"], "none")
        for prefix in ("EMBEDDINGS", "RERANKER"):
            self.assertEqual(env[f"HINDSIGHT_API_{prefix}_PROVIDER"], "local")
            self.assertEqual(env[f"HINDSIGHT_API_{prefix}_LOCAL_FORCE_CPU"], "true")
            self.assertEqual(env[f"HINDSIGHT_API_{prefix}_LOCAL_TRUST_REMOTE_CODE"], "false")
        for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"):
            self.assertEqual(env[key], "1")

    def test_example_has_only_blank_nonsecret_selectors(self):
        entries = dict(
            line.split("=", 1) for line in EXAMPLE.read_text().splitlines()
            if line and not line.startswith("#")
        )
        self.assertEqual(set(entries), set(self.selectors))
        self.assertTrue(all(value == "" for value in entries.values()))
        required = set(re.findall(r"\$\{([A-Z_]+):\?", COMPOSE.read_text()))
        self.assertEqual(required, set(entries))


if __name__ == "__main__":
    unittest.main()
