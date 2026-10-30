import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

import local_env


class RuntimeRootTests(unittest.TestCase):
    def test_normal_checkout_uses_source_root(self):
        source = Path("/checkout")
        with patch.object(local_env.subprocess, "run", return_value=MagicMock(
                returncode=0, stdout=".git\n")):
            self.assertEqual(local_env.resolve_runtime_root(source, {}), source)

    def test_linked_worktree_uses_git_common_checkout(self):
        source = Path("/checkout/.local/environment/forge/worktrees/repo/task")
        common = Path("/checkout/.git")
        with patch.object(local_env.subprocess, "run", return_value=MagicMock(
                returncode=0, stdout=str(common) + "\n")):
            self.assertEqual(local_env.resolve_runtime_root(source, {}), Path("/checkout"))

    def test_explicit_runtime_root_must_be_absolute_and_existing(self):
        with self.assertRaisesRegex(RuntimeError, "absolute"):
            local_env.resolve_runtime_root(Path("/checkout"),
                                           {"KENN_KOPY_RUNTIME_ROOT": "relative"})
        with self.assertRaisesRegex(RuntimeError, "existing directory"):
            local_env.resolve_runtime_root(
                Path("/checkout"), {"KENN_KOPY_RUNTIME_ROOT": "/missing/runtime/root"})

    def test_explicit_runtime_root_wins_without_git_lookup(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(local_env.subprocess, "run") as run:
            root = Path(directory)
            self.assertEqual(local_env.resolve_runtime_root(
                Path("/worktree"), {"KENN_KOPY_RUNTIME_ROOT": str(root)}), root)
        run.assert_not_called()


class PiVersionTests(unittest.TestCase):
    def test_approved_runtime_is_accepted(self):
        config = {"pi_executable": "/test/pi"}
        with patch.object(local_env.subprocess, "run",
                          return_value=MagicMock(stdout="1.4.0\n")):
            self.assertEqual(local_env.verify_pi(config, env={}), "/test/pi")

    def test_other_versions_are_rejected(self):
        for version in ("1.0.3", "1.4.1", ""):
            with self.subTest(version=version), \
                    patch.object(local_env.subprocess, "run",
                                 return_value=MagicMock(stdout=version)), \
                    self.assertRaisesRegex(RuntimeError, r"expected Pi 1\.4\.0"):
                local_env.verify_pi({"pi_executable": "/test/pi"}, env={})


class PortOffsetTests(unittest.TestCase):
    def test_valid_offsets_are_accepted(self):
        for value, expected in (("0", 0), (" 1000 ", 1000), (1000, 1000), (20000, 20000)):
            with self.subTest(value=value):
                self.assertEqual(local_env.parse_port_offset(value), expected)

    def test_invalid_or_colliding_offsets_are_rejected(self):
        # 1 maps roborev 17373 onto 17374; 11 maps AgentsView 18080 onto Forge 18091.
        for value in ("-1", "abc", "1.5", True, -5, "1", "11", "48000"):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                local_env.parse_port_offset(value)

    def test_environment_overrides_saved_offset_and_missing_settings_default_to_zero(self):
        with tempfile.TemporaryDirectory(dir=local_env.ROOT / ".local") as directory:
            path = Path(directory) / "environment.json"
            self.assertEqual(local_env.resolve_port_offset({}, path), 0)
            path.write_text('{"port_offset": 2000}')
            self.assertEqual(local_env.resolve_port_offset({}, path), 2000)
            self.assertEqual(local_env.resolve_port_offset({"KENN_KOPY_PORT_OFFSET": "1000"}, path), 1000)
            self.assertEqual(local_env.resolve_port_offset({"KENN_KOPY_PORT_OFFSET": ""}, path), 2000)


class LocalEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="local-env-test-", dir=local_env.ROOT / ".local")
        self.addCleanup(self.temporary.cleanup)
        cwd = Path.cwd()
        self.addCleanup(os.chdir, cwd)
        self.root = Path(self.temporary.name)
        self.state = self.root / "environment"
        self.addCleanup(patch.stopall)
        patch.object(local_env, "STATE", self.state).start()
        self.global_pi = self.root / "global-pi"
        self.global_pi.mkdir()
        patch.object(local_env, "GLOBAL_PI", self.global_pi).start()
        self.corpus = self.root / "corpus"
        server = self.corpus / "tools/context-mcp/.venv/bin/qualified-context-mcp"
        server.parent.mkdir(parents=True)
        server.write_text("#!/bin/sh\nexit 0\n")
        server.chmod(0o755)
        reader = self.corpus / "tools/context-index/context_index.py"
        reader.parent.mkdir(parents=True)
        reader.touch()
        self.binary = self.root / "forge"
        self.binary.touch()
        self.binary.chmod(0o755)
        patch.object(local_env.shutil, "which", return_value="/usr/bin/pi").start()
        patch.object(local_env, "verify_pi", return_value="/usr/bin/pi").start()
        # Forge may be explicitly running on the developer host; tests model the
        # normal stopped state unless a test opts into a probe response.
        patch.object(local_env, "forge_probe", return_value=None).start()
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.setup(self.corpus, self.binary)

    def provider(self):
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.configure_provider("https://usai.example.test/v1", "demo-model", "openai-completions")

    def key(self):
        local_env.private_write(self.state / "secrets/usai-api-key", "test-only-token\n", replace=True)

    def test_setup_persists_launchers_from_canonical_runtime_checkout(self):
        wrapper = str(local_env.RUNTIME_ROOT / "scripts/pi-local.py")
        self.assertIn(wrapper, (self.state / "forge/config.toml").read_text())
        self.assertIn(wrapper, (self.state / "roborev/config.toml").read_text())
        if local_env.RUNTIME_ROOT != local_env.ROOT:
            source_wrapper = str(local_env.ROOT / "scripts/pi-local.py")
            self.assertNotIn(source_wrapper, (self.state / "forge/config.toml").read_text())
            self.assertNotIn(source_wrapper, (self.state / "roborev/config.toml").read_text())

    def test_setup_migrates_managed_launcher_from_a_deleted_other_worktree(self):
        stale = str(local_env.RUNTIME_ROOT / ".local/environment/forge/worktrees/host/repo/deleted/scripts/pi-local.py")
        canonical = str(local_env.RUNTIME_ROOT / "scripts/pi-local.py")
        paths = (self.state / "forge/config.toml", self.state / "roborev/config.toml")
        for path in paths:
            local_env.private_write(
                path, path.read_text().replace(canonical, stale) + "\n# retained edit\n",
                replace=True,
            )
        with patch.object(local_env, "ROOT", local_env.RUNTIME_ROOT), \
                contextlib.redirect_stdout(io.StringIO()):
            local_env.setup(self.corpus, self.binary)
        for path in paths:
            content = path.read_text()
            self.assertIn(canonical, content)
            self.assertNotIn(stale, content)
            self.assertIn("# retained edit", content)

    def test_setup_preserves_custom_pi_launcher_commands(self):
        forge = self.state / "forge/config.toml"
        roborev = self.state / "roborev/config.toml"
        forge_content = forge.read_text().replace(
            f'command = [{json.dumps(str(local_env.RUNTIME_ROOT / "scripts/pi-local.py"))}]',
            'command = ["/opt/company-agent/scripts/pi-local.py"]',
        )
        roborev_content = roborev.read_text().replace(
            f'pi_cmd = {json.dumps(str(local_env.RUNTIME_ROOT / "scripts/pi-local.py"))}',
            'pi_cmd = "/opt/review-agent/scripts/pi-local.py"',
        )
        local_env.private_write(forge, forge_content, replace=True)
        local_env.private_write(roborev, roborev_content, replace=True)
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.setup(self.corpus, self.binary)
        self.assertIn('command = ["/opt/company-agent/scripts/pi-local.py"]', forge.read_text())
        self.assertIn('pi_cmd = "/opt/review-agent/scripts/pi-local.py"', roborev.read_text())
    def test_legacy_librarian_binding_keeps_saved_shape_and_command(self):
        environment = json.loads((self.state / "environment.json").read_text())
        self.assertEqual(environment, {
            "corpus": str(self.corpus),
            "forge_binary": str(self.binary),
            "pi_executable": "/usr/bin/pi",
            "pi_version": local_env.PI_VERSION,
        })
        server = json.loads((self.state / "pi/mcp.json").read_text())["mcpServers"]["falcon-context"]
        self.assertEqual(server, {
            "command": str(self.corpus / "tools/context-mcp/.venv/bin/qualified-context-mcp"),
            "args": ["--root", str(self.corpus), "--reader",
                     str(self.corpus / "tools/context-index/context_index.py")],
            "exposure": "codemode",
            "timeout": 60,
        })

    def explicit_librarian(self):
        executable = self.root / "toolkit/.venv/bin/librarian-mcp"
        reader = self.root / "toolkit/tools/context-index/context_index.py"
        selection = self.root / "toolkit/config/selection.local.json"
        for path in (executable, reader, selection):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
        return executable, reader, selection

    def test_explicit_librarian_binding_and_selection_are_saved_and_reused(self):
        executable, reader, selection = self.explicit_librarian()
        state = self.root / "explicit-environment"
        toolkit = executable.parents[2]
        with patch.object(local_env, "STATE", state), contextlib.redirect_stdout(io.StringIO()):
            local_env.setup(self.corpus, self.binary, executable, reader, toolkit, selection)
            mcp_path = state / "pi/mcp.json"
            mcp = json.loads(mcp_path.read_text())
            mcp["mcpServers"]["unrelated"] = {"command": "/retained/tool", "args": []}
            local_env.json_write(mcp_path, mcp, replace=True)
            local_env.setup(self.corpus, self.binary, executable, reader, toolkit, selection)
        self.assertEqual(json.loads(mcp_path.read_text())["mcpServers"]["unrelated"]["command"],
                         "/retained/tool")
        binding = json.loads(mcp_path.read_text())["mcpServers"]["falcon-context"]
        self.assertEqual(binding["command"], str(executable))
        self.assertEqual(binding["args"], ["--root", str(toolkit), "--reader", str(reader),
                                           "--manifest", str(selection)])
        saved = json.loads((state / "environment.json").read_text())
        self.assertEqual(saved["librarian_executable"], str(executable))
        self.assertEqual(saved["librarian_reader"], str(reader))
        self.assertEqual(saved["librarian_root"], str(toolkit))
        self.assertEqual(saved["librarian_selection"], str(selection))

    def test_setup_rejects_conflicting_saved_mcp_binding_without_mutation(self):
        path = self.state / "pi/mcp.json"
        config = json.loads(path.read_text())
        config["mcpServers"]["falcon-context"]["command"] = "/different/provider"
        local_env.json_write(path, config, replace=True)
        before = path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "Librarian binding differs"):
            local_env.setup(self.corpus, self.binary)
        self.assertEqual(path.read_bytes(), before)

    def test_explicit_librarian_binding_without_reader_omits_the_flag(self):
        # The current toolkit rejects --reader and loads its reader module from
        # --root, so a reader-free binding must not persist that flag.
        executable, _, selection = self.explicit_librarian()
        state = self.root / "current-toolkit-environment"
        toolkit = executable.parents[2]
        with patch.object(local_env, "STATE", state), contextlib.redirect_stdout(io.StringIO()):
            local_env.setup(self.corpus, self.binary, executable, None, toolkit, selection)
        binding = json.loads((state / "pi/mcp.json").read_text())["mcpServers"]["falcon-context"]
        self.assertEqual(binding["args"], ["--root", str(toolkit), "--manifest", str(selection)])
        saved = json.loads((state / "environment.json").read_text())
        self.assertIsNone(saved["librarian_reader"])

    def test_explicit_librarian_tuple_and_prerequisites_are_required(self):
        executable, reader, selection = self.explicit_librarian()
        with self.assertRaisesRegex(RuntimeError, "together"):
            local_env.setup(self.corpus, self.binary, None, reader, self.corpus, None)
        toolkit = executable.parents[2]
        executable.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, "not executable"):
            local_env.setup(self.corpus, self.binary, executable, reader, toolkit, selection)
        executable.write_text("#!/bin/sh\necho missing dependency >&2\nexit 1\n")
        executable.chmod(0o755)
        with self.assertRaisesRegex(RuntimeError, "runtime/dependencies unavailable.*missing dependency"):
            local_env.setup(self.corpus, self.binary, executable, reader, toolkit, selection)

    def test_explicit_librarian_selection_outside_root_is_rejected_without_writes(self):
        executable, reader, _ = self.explicit_librarian()
        state = self.root / "outside-selection-environment"
        outside = self.root / "outside-selection.json"
        outside.touch()
        with patch.object(local_env, "STATE", state), \
                self.assertRaisesRegex(RuntimeError, "within --librarian-root"):
            local_env.setup(self.corpus, self.binary, executable, reader,
                            executable.parents[2], outside)
        self.assertFalse(state.exists())

    def test_explicit_librarian_root_must_be_readable_and_searchable(self):
        executable, reader, _ = self.explicit_librarian()
        toolkit = executable.parents[2]
        real_access = os.access

        def access(path, mode):
            if Path(path) == toolkit and mode & os.X_OK:
                return False
            return real_access(path, mode)

        state = self.root / "non-searchable-root-environment"
        with patch.object(local_env, "STATE", state), \
                patch.object(local_env.os, "access", side_effect=access), \
                self.assertRaisesRegex(RuntimeError, "readable and searchable"):
            local_env.setup(self.corpus, self.binary, executable, reader, toolkit)

    def test_configure_librarian_rebinds_existing_environment_and_mcp(self):
        executable, _, selection = self.explicit_librarian()
        toolkit = executable.parents[2]
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.configure_librarian(toolkit)
        saved = json.loads((self.state / "environment.json").read_text())
        self.assertEqual(saved["librarian_executable"], str(executable))
        self.assertIsNone(saved["librarian_reader"])
        self.assertEqual(saved["librarian_root"], str(toolkit))
        self.assertEqual(saved["librarian_selection"], str(selection))
        binding = json.loads((self.state / "pi/mcp.json").read_text())["mcpServers"]["falcon-context"]
        self.assertEqual(binding["command"], str(executable))
        self.assertEqual(binding["args"], ["--root", str(toolkit), "--manifest", str(selection)])

    def test_provision_librarian_mvp_packages_initializes_and_optionally_binds_mcp(self):
        source = self.root / "the_librarian"
        (source / "tools/context_index").mkdir(parents=True)
        (source / "tools/context-mcp/src/the_librarian_mcp").mkdir(parents=True)
        (source / "config").mkdir(parents=True)
        (source / "release-files.json").write_text(json.dumps([
            "tools/package.py",
            "tools/initialize.py",
            "tools/context_index/context_index.py",
            "tools/context-mcp/src/the_librarian_mcp/__init__.py",
            "tools/context-mcp/src/the_librarian_mcp/server.py",
            "tools/context-mcp/src/the_librarian_mcp/preflight.py",
            "config/policy.json",
        ]))
        (source / "tools/package.py").write_text(
            "import argparse, json, zipfile\nfrom pathlib import Path\n"
            "p = argparse.ArgumentParser(); p.add_argument('--output', type=Path, required=True)\n"
            "args = p.parse_args(); root = Path(__file__).resolve().parents[1]\n"
            "with zipfile.ZipFile(args.output, 'w') as zf:\n"
            "    for f in json.loads((root / 'release-files.json').read_text()):\n"
            "        zf.writestr(f, (root / f).read_bytes())\n"
        )
        (source / "tools/initialize.py").write_text("import sys\nsys.exit(0)\n")
        (source / "tools/context_index/context_index.py").write_text("import sys\nsys.exit(0)\n")
        (source / "tools/context-mcp/src/the_librarian_mcp/__init__.py").write_text("")
        (source / "tools/context-mcp/src/the_librarian_mcp/server.py").write_text(
            "import jsonschema, mcp\n"
            "def main():\n"
            "    assert mcp.MCP_READY and jsonschema.JSONSCHEMA_READY\n"
            "    return 0\n"
        )
        (source / "tools/context-mcp/src/the_librarian_mcp/preflight.py").write_text("def main(): return 0\n")
        (source / "config/policy.json").write_text('{"schema_version": 1}\n')
        offline_site = self.root / "offline-site-packages"
        (offline_site / "mcp").mkdir(parents=True)
        (offline_site / "jsonschema").mkdir(parents=True)
        (offline_site / "mcp/__init__.py").write_text("MCP_READY = True\n")
        (offline_site / "jsonschema/__init__.py").write_text("JSONSCHEMA_READY = True\n")
        dest = self.root / "falcon-librarian-mvp"
        inbox = self.root / "inbox"
        repos = self.root / "repos"
        inbox.mkdir()
        repos.mkdir()
        with self.assertRaisesRegex(RuntimeError, "isolated directory outside --source"):
            local_env.provision_librarian_mvp(source, source)
        with (
            patch.dict(os.environ, {"LIBRARIAN_OFFLINE_SITE_PACKAGES": str(offline_site)}),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            summary = local_env.provision_librarian_mvp(
                source, dest, inbox=inbox, repos_root=repos, bind_mcp=True,
            )
        self.assertEqual(summary["instance_root"], str(dest))
        self.assertTrue((dest / "config/policy.local.json").is_file())
        self.assertTrue((dest / "config/selection.local.json").is_file())
        self.assertTrue((dest / ".local/mvp-sources.json").is_file())
        self.assertTrue((dest / ".local/engineer-context.json").is_file())
        self.assertFalse((source / ".local").exists())
        binding = json.loads((self.state / "pi/mcp.json").read_text())["mcpServers"]["falcon-context"]
        self.assertEqual(binding["command"], str(dest / ".venv/bin/librarian-mcp"))
        self.assertEqual(binding["args"], ["--root", str(dest), "--manifest", str(dest / "config/selection.local.json")])

    def test_setup_preserves_edited_settings(self):
        path = self.state / "pi/settings.json"
        content = '{"theme":"light","custom":"retained"}\n'
        local_env.private_write(path, content, replace=True)
        forge = self.state / "forge/config.toml"
        edited = forge.read_text() + "\n# user setting retained\n"
        local_env.private_write(forge, edited, replace=True)
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.setup(self.corpus, self.binary)
        self.assertEqual(path.read_text(), content)
        self.assertEqual(forge.read_text(), edited)

    def test_setup_rejects_unintentional_path_change(self):
        other = self.root / "other-forge"
        other.touch()
        with self.assertRaisesRegex(RuntimeError, "differs"):
            local_env.setup(self.corpus, other)

    def test_setup_migrates_only_stale_saved_pi_version(self):
        path = self.state / "environment.json"
        saved = json.loads(path.read_text())
        local_env.private_write(path, json.dumps(dict(saved, pi_version="1.0.3")), replace=True)
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.setup(self.corpus, self.binary)
        self.assertEqual(json.loads(path.read_text()), saved)

    def test_setup_rejects_stale_pi_version_with_other_differences(self):
        path = self.state / "environment.json"
        stale = dict(json.loads(path.read_text()), pi_version="1.0.3",
                     pi_executable="/old/pi")
        local_env.private_write(path, json.dumps(stale), replace=True)
        with self.assertRaisesRegex(RuntimeError, "differs"):
            local_env.setup(self.corpus, self.binary)
        self.assertEqual(json.loads(path.read_text()), stale)

    def test_setup_does_not_migrate_version_when_pi_check_fails(self):
        path = self.state / "environment.json"
        stale = dict(json.loads(path.read_text()), pi_version="1.0.3")
        local_env.private_write(path, json.dumps(stale), replace=True)
        with patch.object(local_env, "verify_pi", side_effect=RuntimeError("expected Pi")), \
                self.assertRaisesRegex(RuntimeError, "expected Pi"):
            local_env.setup(self.corpus, self.binary)
        self.assertEqual(json.loads(path.read_text()), stale)

    def test_default_offset_keeps_existing_ports_and_saved_settings(self):
        self.assertNotIn("port_offset", json.loads((self.state / "environment.json").read_text()))
        self.assertIn("port = 18091\n", (self.state / "forge/config.toml").read_text())
        self.assertIn('listen = "127.0.0.1:17777"', (self.state / "kata/config.toml").read_text())
        self.assertEqual(local_env.PORTS, (17373, 17374, 17777, 18080, 18091))

    def test_port_offset_moves_every_generated_endpoint(self):
        self.addCleanup(local_env.configure_ports, local_env.PORT_OFFSET)
        local_env.configure_ports(1000)
        state = self.root / "offset-environment"
        patch.object(local_env, "STATE", state).start()
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.setup(self.corpus, self.binary)
        self.assertEqual(json.loads((state / "environment.json").read_text())["port_offset"], 1000)
        forge = local_env.validate_forge_config()
        self.assertEqual((forge["port"], forge["mcp"]["port"]), (19091, 19092))
        self.assertEqual(forge["roborev"]["endpoint"], "http://127.0.0.1:18373")
        local_env.validate_roborev_config()
        local_env.validate_kata_config()
        self.assertIn('url = "http://127.0.0.1:18777"', (state / "kata/config.toml").read_text())
        servers = json.loads((state / "pi/mcp.json").read_text())["mcpServers"]
        self.assertEqual(servers["kata"]["env"]["KATA_SERVER"], "http://127.0.0.1:18777")
        self.assertEqual(servers["kenn-forge"]["url"], "http://127.0.0.1:19092/mcp")
        env = local_env.base_environment()
        self.assertEqual(env["KATA_SERVER"], "http://127.0.0.1:18777")
        self.assertEqual(env["KENN_FORGE_API_URL"], "http://127.0.0.1:19091")
        self.assertIn("19080", local_env.agentsview_command())
        self.assertEqual(local_env.PORTS, (18373, 18374, 18777, 19080, 19091))
        self.assertEqual(local_env.SERVICE_PORTS["roborev"], (18373, 18374))
        with patch.object(local_env.socket, "socket") as probe:
            local_env.check_ports()
        bound = [call.args[0][1] for call in probe.return_value.__enter__.return_value.bind.call_args_list]
        self.assertEqual(bound, list(local_env.PORTS))
        local_env.configure_ports(0)
        with self.assertRaisesRegex(RuntimeError, "differs from the saved port_offset 1000"):
            local_env.settings()

    def test_profile_is_private_and_uses_existing_corpus(self):
        for path in (self.state, self.state / "secrets", self.state / "pi"):
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
        mcp = json.loads((self.state / "pi/mcp.json").read_text())
        server = mcp["mcpServers"]["falcon-context"]
        self.assertIn(str(self.corpus), server["args"])
        self.assertEqual(server["exposure"], "codemode")
        self.assertEqual(mcp["mcpServers"]["kata"]["exposure"], "direct")
        self.assertNotIn("cwd", mcp["mcpServers"]["kata"])
        self.assertEqual(mcp["mcpServers"]["kenn-forge"]["url"], "http://127.0.0.1:18092/mcp")
        self.assertEqual(mcp["mcpServers"]["kenn-forge"]["exposure"], "direct")
        self.assertTrue((self.state / "pi/extensions/forge-workspace.ts").is_file())
        self.assertIn("[mcp]\nenabled = true", (self.state / "forge/config.toml").read_text())
        self.assertEqual((self.state / "pi/mcp.json").stat().st_mode & 0o777, 0o600)

    def test_isolated_gitconfig_and_forge_runtime_env_passthrough(self):
        (self.state / "home/.gitconfig").unlink(missing_ok=True)
        host_gitconfig = self.root / "host.gitconfig"
        host_gitconfig.write_text(
            "[http]\n\tsslCAinfo = /etc/ssl/certs/ca-certificates.crt\n"
            "[user]\n\tname = Test Engineer\n\temail = engineer@example.gov\n"
        )
        local_env.seed_isolated_gitconfig(self.state / "home", host_config=host_gitconfig)
        gitconfig_text = (self.state / "home/.gitconfig").read_text()
        self.assertIn("name = Test Engineer", gitconfig_text)
        self.assertIn("email = engineer@example.gov", gitconfig_text)
        self.assertIn("sslCAinfo = /etc/ssl/certs/ca-certificates.crt", gitconfig_text)
        self.assertIn("auth git-credential", gitconfig_text)
        ignore_text = (self.state / "home/.config/git/ignore").read_text()
        self.assertIn("/AGENTS.override.md", ignore_text)
        self.assertIn("/.superpowers/", ignore_text)

        self.provider()
        self.key()
        with patch.dict(os.environ, {
            "KENN_FORGE_RUNTIME_SESSION_KEY": "ws_runtime_123",
            "KENN_FORGE_API_URL": "http://127.0.0.1:18091",
        }):
            _, env = local_env.pi_launch(["--no-session", "-p", "Synthetic test"])
        self.assertEqual(env["KENN_FORGE_RUNTIME_SESSION_KEY"], "ws_runtime_123")
        self.assertEqual(env["KENN_FORGE_API_URL"], "http://127.0.0.1:18091")
        self.assertIn(str(local_env.JQ_BINARY.parent), env["PATH"].split(os.pathsep))
        self.assertIn(str(local_env.PYDEPS_DIR / "bin"), env["PATH"].split(os.pathsep))
        self.assertEqual(env["PATH"].split(os.pathsep)[-1], str(Path.home() / ".local/bin"))

    def test_missing_usai_fails_without_fallback(self):
        with self.assertRaisesRegex(RuntimeError, "no provider fallback"):
            local_env.pi_launch([])

    def test_key_is_only_in_pi_environment(self):
        self.provider()
        self.key()
        command, env = local_env.pi_launch(["--no-session", "-p", "Synthetic test"])
        self.assertEqual(command[1:5], ["--provider", "usai", "--model", "demo-model"])
        self.assertEqual(env["USAI_API_KEY"], "test-only-token")
        self.assertNotIn("test-only-token", " ".join(command))
        self.assertNotIn("USAI_API_KEY", local_env.base_environment())
        self.assertNotIn("test-only-token", (self.state / "pi/models.json").read_text())

    def test_selected_model_removed_from_catalog_fails_before_loading_key(self):
        self.provider()
        path = self.state / "pi/models.json"
        config = json.loads(path.read_text())
        config["providers"]["usai"]["models"] = [{"id": "new-unverified-model"}]
        local_env.json_write(path, config, replace=True)
        with patch.object(local_env, "load_usai_key") as key, \
                self.assertRaisesRegex(RuntimeError, "missing from pi/models.json"):
            local_env.pi_launch(["--no-session", "-p", "Synthetic test"])
        key.assert_not_called()

    def test_credential_free_mcp_command(self):
        command, env = local_env.pi_launch(["mcp", "list"])
        self.assertEqual(command, ["/usr/bin/pi", "mcp", "list"])
        self.assertNotIn("USAI_API_KEY", env)

    def test_terminal_uses_separate_private_socket_and_native_copilot_home(self):
        with patch.object(local_env.shutil, "which", return_value="/usr/bin/tmux"), \
                patch.dict(os.environ, {
                    "USAI_API_KEY": "test-only-token", "GITHUB_TOKEN": "test-only-token",
                    "TMUX": "foreign-server", "KATA_REF": "foreign-task",
                }):
            command, env = local_env.terminal_launch("open", "pi")
        self.assertEqual(command, [
            "/usr/bin/tmux", "-S", str(self.state / "runtime/terminal/tmux.sock"),
            "-f", str(local_env.ROOT / "scripts/terminal.tmux.conf"),
            "new-session", "-A", "-s", "pi", "-c", str(local_env.ROOT),
        ])
        self.assertEqual((self.state / "runtime/terminal").stat().st_mode & 0o777, 0o700)
        self.assertEqual(env["HOME"], str(Path.home()))
        self.assertEqual(env["PI_CODING_AGENT_DIR"], str(self.state / "pi"))
        for variable in ("USAI_API_KEY", "GITHUB_TOKEN", "TMUX", "KATA_REF"):
            self.assertNotIn(variable, env)
        self.assertNotIn("test-only-token", " ".join(command))
        self.assertEqual(local_env.base_environment()["HOME"], str(self.state / "home"))

    def test_terminal_preserves_native_xdg_paths_without_changing_settings(self):
        before = (self.state / "environment.json").read_bytes()
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/test/config"}):
            _, env = local_env.terminal_launch("open")
        self.assertEqual(env["XDG_CONFIG_HOME"], "/test/config")
        self.assertEqual((self.state / "environment.json").read_bytes(), before)

    def test_terminal_stops_only_exact_named_session(self):
        command, _ = local_env.terminal_launch("stop", "pi")
        self.assertEqual(command[-3:], ["kill-session", "-t", "=pi"])
        command, _ = local_env.terminal_launch("list")
        self.assertIn("list-sessions", command)
        self.assertNotIn("new-session", command)

    def test_terminal_rejects_invalid_actions_and_session_targets(self):
        for name in ("", "-pi", "pi:1", "pi.work", "*", "pi;echo", "x" * 49):
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, "session names"):
                local_env.terminal_launch("stop", name)
        with self.assertRaisesRegex(RuntimeError, "terminal action"):
            local_env.terminal_launch("kill-server")
        with patch.object(local_env.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "tmux is missing"):
                local_env.terminal_launch("open")

    def test_terminal_rejects_symlink_or_regular_file_as_socket(self):
        local_env.terminal_launch("list")
        path = self.state / "runtime/terminal/tmux.sock"
        path.symlink_to(self.state / "environment.json")
        with self.assertRaisesRegex(RuntimeError, "owned tmux socket"):
            local_env.terminal_launch("open")
        path.unlink()
        path.touch()
        with self.assertRaisesRegex(RuntimeError, "owned tmux socket"):
            local_env.terminal_launch("list")

    def test_terminal_entrypoint_executes_scoped_command(self):
        with patch.object(sys, "argv", ["terminal-local.py", "list"]), \
                patch.object(os, "execve") as execute, \
                patch.object(os, "umask", return_value=0o077), \
                patch.object(os, "chdir") as chdir:
            with self.assertRaises(SystemExit) as exit_result:
                runpy.run_path(str(local_env.ROOT / "scripts/terminal-local.py"), run_name="__main__")
        self.assertIsNone(exit_result.exception.code)
        self.assertIn("list-sessions", execute.call_args.args[1])
        chdir.assert_not_called()

    def test_terminal_entrypoint_refuses_noninteractive_open(self):
        with patch.object(sys, "argv", ["terminal-local.py", "open"]), \
                patch.object(sys.stdin, "isatty", return_value=False), \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exit_result:
                runpy.run_path(str(local_env.ROOT / "scripts/terminal-local.py"), run_name="__main__")
        self.assertEqual(exit_result.exception.code, 2)

    def test_pi_extension_installation_is_private_pinned_and_preserves_settings(self):
        path = self.state / "pi/settings.json"
        config = json.loads(path.read_text())
        config["theme"] = "retained"
        config.pop("subagents", None)
        local_env.json_write(path, config, replace=True)
        before = config.copy()

        installed = []

        def install(command, **kwargs):
            self.assertEqual(command[:2], ["/usr/bin/pi", "install"])
            self.assertIn(command[2], local_env.PI_EXTENSIONS)
            installed.append(command[2])
            self.assertEqual(kwargs["cwd"], self.state / "home")
            self.assertEqual(kwargs["env"]["PI_CODING_AGENT_DIR"], str(self.state / "pi"))
            self.assertNotIn("USAI_API_KEY", kwargs["env"])
            self.assertTrue(kwargs["check"])
            current = json.loads(path.read_text())
            current["packages"] = list(dict.fromkeys([*current["packages"], command[2]]))
            local_env.json_write(path, current, replace=True)

        with patch.object(local_env.subprocess, "run", side_effect=install) as run:
            with contextlib.redirect_stdout(io.StringIO()):
                local_env.install_pi_extensions()
                local_env.install_pi_review_extension()
        saved = json.loads(path.read_text())
        self.assertEqual(run.call_count, 2 * len(local_env.PI_EXTENSIONS))
        self.assertEqual(installed, list(local_env.PI_EXTENSIONS) * 2)
        self.assertEqual(saved["theme"], before["theme"])
        self.assertIn(str(local_env.RUNTIME_ROOT / "superpowers"), saved["packages"])
        for extension in local_env.PI_EXTENSIONS:
            self.assertEqual(saved["packages"].count(extension), 1)
        self.assertEqual(saved["subagents"]["defaultProvider"], "usai")
        self.assertEqual(saved["subagents"]["defaultModel"], "inherit")
        self.assertEqual(saved["subagents"]["modelScope"]["allow"], ["inherit", "usai/*"])
        for name in ("delegate", "oracle", "reviewer", "scout", "worker"):
            self.assertEqual(saved["subagents"]["agentOverrides"][name]["model"], "inherit")
            self.assertTrue(saved["subagents"]["agentOverrides"][name]["advertise"])
        self.assertEqual(list(self.global_pi.iterdir()), [])

    def test_configure_provider_populates_usai_subagent_settings(self):
        path = self.state / "pi/settings.json"
        local_env.json_write(path, {"defaultThinkingLevel": "off"}, replace=True)
        self.provider()
        saved = json.loads(path.read_text())
        self.assertEqual(saved["defaultProvider"], "usai")
        self.assertEqual(saved["defaultModel"], "demo-model")
        self.assertEqual(saved["subagents"]["defaultProvider"], "usai")
        self.assertEqual(saved["subagents"]["defaultModel"], "inherit")
        self.assertEqual(saved["subagents"]["modelScope"]["allow"], ["inherit", "usai/*"])
        for name in ("delegate", "oracle", "reviewer", "scout", "worker"):
            self.assertEqual(saved["subagents"]["agentOverrides"][name]["model"], "inherit")

    def test_review_extension_installation_reports_failure_and_wrong_profile(self):
        with patch.object(local_env.subprocess, "run", side_effect=local_env.subprocess.CalledProcessError(
                1, ["pi", "install"])):
            with self.assertRaises(local_env.subprocess.CalledProcessError):
                local_env.install_pi_extensions()
        with patch.object(local_env.subprocess, "run"):
            with self.assertRaisesRegex(RuntimeError, "isolated profile"):
                local_env.install_pi_extensions()

    def test_roborev_selected_native_binary_is_shared_by_commands_and_child_path(self):
        binary = self.root / "native/bin/roborev"
        binary.parent.mkdir(parents=True)
        binary.touch()
        binary.chmod(0o755)
        local_env.json_write(self.state / "roborev-service.json",
                             {"unit": local_env.ROBOREV_UNIT, "binary": str(binary)})
        self.assertEqual(local_env.roborev_command()[0], str(binary))
        env = local_env.base_environment()
        self.assertEqual(env["PATH"].split(os.pathsep)[1], str(binary.parent))
        self.assertEqual(env["KENN_KOPY_RUNTIME_ROOT"], str(local_env.RUNTIME_ROOT))
        binary.unlink()
        with self.assertRaisesRegex(RuntimeError, "missing executable"):
            local_env.roborev_command()
        local_env.json_write(self.state / "roborev-service.json",
                             {"binary": "relative/roborev"}, replace=True)
        with self.assertRaisesRegex(RuntimeError, "absolute path"):
            local_env.roborev_binary()

    def test_roborev_warnings_distinguish_managed_and_unmanaged_processes(self):
        proc = self.root / "proc"
        for pid, cmd in ((111, b"/native/roborev\0daemon\0run\0"),
                         (222, b"/native/roborev\0daemon\0run\0"),
                         (333, b"/native/roborev\0status\0")):
            entry = proc / str(pid)
            entry.mkdir(parents=True)
            (entry / "cmdline").write_bytes(cmd)
        with patch.object(local_env, "user_service_pid", return_value=111), \
                patch.object(local_env, "supervisor", return_value=None), \
                patch.object(local_env.socket, "socket") as socket:
            socket.return_value.__enter__.return_value.connect_ex.return_value = 1
            warnings = local_env.roborev_warnings(proc_root=proc)
            self.assertEqual(len(warnings), 1)
            self.assertIn("PID 222", warnings[0])
            socket.return_value.__enter__.return_value.connect_ex.return_value = 0
            warnings = local_env.roborev_warnings(proc_root=proc)
            self.assertEqual(sum("7373" in w for w in warnings), 2)
        with patch.object(local_env, "user_service_pid", side_effect=RuntimeError("inactive")), \
                patch.object(local_env, "supervisor", return_value={"children": {"roborev": 111}}), \
                patch.object(local_env.socket, "socket") as socket:
            socket.return_value.__enter__.return_value.connect_ex.return_value = 1
            self.assertEqual(len(local_env.roborev_warnings(proc_root=proc)), 1)
        with patch.object(local_env, "user_service_pid", return_value=111), \
                patch.object(local_env, "supervisor", side_effect=RuntimeError("stale identity")), \
                patch.object(local_env.socket, "socket") as socket:
            socket.return_value.__enter__.return_value.connect_ex.return_value = 1
            self.assertEqual(len(local_env.roborev_warnings(proc_root=proc)), 1)

    def test_permissive_key_is_rejected(self):
        self.provider()
        self.key()
        (self.state / "secrets/usai-api-key").chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, "private regular file"):
            local_env.pi_launch([])

    def test_symlink_key_is_rejected(self):
        self.provider()
        target = self.root / "outside-key"
        target.write_text("test-only-token")
        (self.state / "secrets/usai-api-key").symlink_to(target)
        with self.assertRaises(OSError):
            local_env.pi_launch([])
        with self.assertRaises(OSError):
            local_env.private_write(self.state / "secrets/usai-api-key", "replacement", replace=True)
        self.assertEqual(target.read_text(), "test-only-token")

    def test_invalid_key_does_not_appear_in_error(self):
        for bad in ("test-only-token\nanother-line", "test-only-token\x00"):
            with self.subTest(), self.assertRaises(RuntimeError) as error:
                local_env.validate_key(bad)
            self.assertNotIn(bad, str(error.exception))

    def test_model_and_key_overrides_are_rejected(self):
        for flag in ("--api-key", "--api-key=anything", "--provider", "--model=other"):
            with self.subTest(flag=flag), self.assertRaisesRegex(RuntimeError, "saved USAi model"):
                local_env.pi_launch([flag])

    def test_provider_updates_preserve_unrelated_configuration(self):
        path = self.state / "pi/models.json"
        local_env.json_write(path, {"providers": {"local": {"models": [{"id": "keep"}]}}})
        self.provider()
        self.assertIn("local", json.loads(path.read_text())["providers"])

    def test_provider_rejects_embedded_credentials_and_plaintext(self):
        for url in ("http://usai.example.test/v1", "https://token@usai.example.test/v1",
                    "https://usai.example.test/v1?key=test"):
            with self.subTest(url=url), self.assertRaisesRegex(RuntimeError, "HTTPS without credentials"):
                local_env.configure_provider(url, "model", "openai-completions")

    def test_pid_reuse_is_not_signaled(self):
        local_env.json_write(self.state / "runtime/supervisor.json",
                             {"pid": os.getpid(), "start_time": "not-the-current-process"})
        with patch.object(local_env.os, "kill") as kill, self.assertRaisesRegex(RuntimeError, "reused"):
            local_env.stop()
        kill.assert_not_called()

    def save_exited_supervisor(self):
        with local_env.subprocess.Popen(
                [local_env.sys.executable, "-c", "pass"],
                stdout=local_env.subprocess.DEVNULL, stderr=local_env.subprocess.DEVNULL) as process:
            process.wait(timeout=10)
        path = self.state / "runtime/supervisor.json"
        local_env.json_write(path, {"pid": process.pid, "start_time": "previous-instance"})
        return path

    def test_status_retains_stale_metadata_and_reports_independent_services(self):
        path = self.save_exited_supervisor()
        before = path.read_bytes()
        external = {"agentsview": {"unit": local_env.AGENTSVIEW_UNIT, "pid": 123}}
        errors = io.StringIO()
        with patch.object(local_env, "managed_services", return_value=external):
            with contextlib.redirect_stderr(errors):
                result = local_env.status()
        self.assertEqual(result["stack"], "stopped")
        self.assertIsNone(result["supervisor"])
        self.assertEqual(result["agentsview_service"], external["agentsview"])
        self.assertIsNone(result["forge"])
        self.assertEqual(path.read_bytes(), before)
        self.assertIn("stale supervisor metadata retained", errors.getvalue())

    def test_stop_with_exited_supervisor_signals_nothing_and_retains_metadata(self):
        path = self.save_exited_supervisor()
        before = path.read_bytes()
        output = io.StringIO()
        with patch.object(local_env.os, "kill") as kill:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                local_env.stop()
        kill.assert_not_called()
        self.assertEqual(path.read_bytes(), before)
        self.assertIn("No live supervisor", output.getvalue())
        self.assertIn("no process was signaled", output.getvalue())
        self.assertFalse((self.state / "runtime/shutdown.json").exists())

    def test_stop_without_supervisor_metadata_signals_nothing(self):
        with patch.object(local_env.os, "kill") as kill:
            with contextlib.redirect_stdout(io.StringIO()):
                local_env.stop()
        kill.assert_not_called()

    def test_supervisor_read_errors_remain_visible(self):
        local_env.json_write(self.state / "runtime/supervisor.json",
                             {"pid": os.getpid(), "start_time": "current"})
        with patch.object(local_env, "process_identity", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                local_env.supervisor()

    def test_key_handoff_requires_terminal(self):
        with patch.object(local_env.sys.stdin, "isatty", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "terminal"):
                local_env.set_key()
        self.assertFalse((self.state / "secrets/usai-api-key").exists())

    def test_private_only_key_handoff_does_not_read_or_change_global_profiles(self):
        self.cli_providers()
        before = {path.name: path.read_bytes() for path in self.global_pi.iterdir()}
        with patch.object(local_env.sys.stdin, "isatty", return_value=True), \
                patch.object(local_env.getpass, "getpass", return_value="test-only-token"), \
                patch.object(local_env, "link_cli_key", side_effect=AssertionError("global access")), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            local_env.set_key(private_only=True)
        self.assertEqual(local_env.load_usai_key(), "test-only-token")
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.global_pi.iterdir()})
        self.assertIn("Global Pi credentials were not changed", output.getvalue())

    def cli_providers(self):
        models = {"providers": {
            "usai": {"apiKey": "old-test-only-token", "models": [{"id": "retained"}]},
            "other": {"apiKey": "$OTHER_KEY"},
        }}
        settings = {"theme": "retained", "packages": ["retained-package"], "litellm": {
            "providers": {"litellm-usai": {"apiKey": "!old-helper", "baseUrl": "https://usai.example.test"}},
            "mcp": {"enabled": False},
        }}
        for name, config in (("models.json", models), ("settings.json", settings)):
            (self.global_pi / name).write_text(json.dumps(config))
            (self.global_pi / name).chmod(0o644)
        return models, settings

    def test_set_key_links_both_profiles_without_copying_token_or_settings(self):
        models, settings = self.cli_providers()
        before = (self.state / "pi/settings.json").read_bytes()
        output = io.StringIO()
        for token in ("first-test-only-token", "rotated-test-only-token"):
            with patch.object(local_env.sys.stdin, "isatty", return_value=True):
                with patch.object(local_env.getpass, "getpass", return_value=token):
                    with contextlib.redirect_stdout(output):
                        local_env.set_key()
            self.assertEqual(local_env.load_usai_key(), token)
            cli_models = json.loads((self.global_pi / "models.json").read_text())
            cli_settings = json.loads((self.global_pi / "settings.json").read_text())
            command = cli_models["providers"]["usai"]["apiKey"]
            self.assertTrue(command.startswith("!"))
            self.assertIn(str(local_env.RUNTIME_ROOT / "scripts/usai-key.py"), command)
            if local_env.RUNTIME_ROOT != local_env.ROOT:
                self.assertNotIn(str(local_env.ROOT / "scripts/usai-key.py"), command)
            self.assertEqual(cli_settings["litellm"]["providers"]["litellm-usai"]["apiKey"], command)
            models["providers"]["usai"]["apiKey"] = command
            settings["litellm"]["providers"]["litellm-usai"]["apiKey"] = command
            self.assertEqual(cli_models, models)
            self.assertEqual(cli_settings, settings)
            for name in ("models.json", "settings.json"):
                path = self.global_pi / name
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertNotIn(token, path.read_text())
            self.assertNotIn(token, output.getvalue())
        self.assertEqual((self.state / "pi/settings.json").read_bytes(), before)
        self.assertEqual((self.state / "secrets/usai-api-key").stat().st_mode & 0o777, 0o600)
        self.assertIn("2 existing global Pi", output.getvalue())

    def test_set_key_does_not_create_unconfigured_global_providers(self):
        output = io.StringIO()
        with patch.object(local_env.sys.stdin, "isatty", return_value=True):
            with patch.object(local_env.getpass, "getpass", return_value="test-only-token"):
                with contextlib.redirect_stdout(output):
                    local_env.set_key()
        self.assertEqual(local_env.load_usai_key(), "test-only-token")
        self.assertEqual(list(self.global_pi.iterdir()), [])
        self.assertIn("0 existing global Pi", output.getvalue())

    def test_cli_key_link_rejects_symlink_without_replacing_private_key(self):
        self.cli_providers()
        self.key()
        path = self.global_pi / "settings.json"
        content = path.read_bytes()
        path.unlink()
        target = self.root / "outside-settings"
        target.write_bytes(content)
        path.symlink_to(target)
        before = (self.global_pi / "models.json").read_bytes()
        with patch.object(local_env.sys.stdin, "isatty", return_value=True):
            with patch.object(local_env.getpass, "getpass", return_value="new-test-only-token"):
                with self.assertRaises(OSError):
                    local_env.set_key()
        self.assertEqual((self.global_pi / "models.json").read_bytes(), before)
        self.assertEqual(target.read_bytes(), content)
        self.assertEqual(local_env.load_usai_key(), "test-only-token")

    def test_cli_key_link_rejects_writable_config_and_saved_auth_override(self):
        self.cli_providers()
        path = self.global_pi / "models.json"
        before = path.read_bytes()
        path.chmod(0o666)
        with self.assertRaisesRegex(RuntimeError, "non-writable-by-others"):
            local_env.link_cli_key()
        path.chmod(0o644)
        local_env.json_write(self.global_pi / "auth.json", {
            "litellm-usai": {"type": "api_key", "key": "test-only-token"},
        })
        with self.assertRaisesRegex(RuntimeError, "auth.json overrides"):
            local_env.link_cli_key()
        self.assertEqual(path.read_bytes(), before)

    def test_cli_key_link_invalid_config_does_not_partially_update_other_profile(self):
        self.cli_providers()
        path = self.global_pi / "settings.json"
        before = (self.global_pi / "models.json").read_bytes()
        for config in ([], {"litellm": []}, {"litellm": {"providers": []}}):
            path.write_text(json.dumps(config))
            with self.subTest(config=config), self.assertRaises(RuntimeError):
                local_env.link_cli_key()
            self.assertEqual((self.global_pi / "models.json").read_bytes(), before)

    def test_set_key_rejects_unsafe_private_key_before_changing_cli_configs(self):
        self.cli_providers()
        self.key()
        (self.state / "secrets/usai-api-key").chmod(0o644)
        before = {name: (self.global_pi / name).read_bytes() for name in ("models.json", "settings.json")}
        with patch.object(local_env.sys.stdin, "isatty", return_value=True):
            with patch.object(local_env.getpass, "getpass", return_value="new-test-only-token"):
                with self.assertRaisesRegex(RuntimeError, "private regular file"):
                    local_env.set_key()
        for name, content in before.items():
            self.assertEqual((self.global_pi / name).read_bytes(), content)

    def test_credential_helper_reads_current_private_key_without_logs(self):
        for token in ("first-test-only-token", "rotated-test-only-token"):
            local_env.private_write(self.state / "secrets/usai-api-key", token + "\n", replace=True)
            output, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                runpy.run_path(str(local_env.ROOT / "scripts/usai-key.py"))
            self.assertEqual(output.getvalue(), token + "\n")
            self.assertEqual(errors.getvalue(), "")

    def test_credential_helper_missing_key_fails_explicitly_without_stdout(self):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            with self.assertRaises(SystemExit) as error:
                runpy.run_path(str(local_env.ROOT / "scripts/usai-key.py"))
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("ERROR:", errors.getvalue())

    def test_model_discovery_saves_only_metadata_without_changing_provider(self):
        self.provider()
        self.key()
        provider_before = (self.state / "pi/models.json").read_bytes()
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = json.dumps({
            "data": [{"id": "model-b"}, {"id": "model-a"}, {"id": "model-b"}],
        }).encode()
        output = io.StringIO()
        with patch.object(local_env.urllib.request, "build_opener", return_value=opener):
            with contextlib.redirect_stdout(output):
                ids = local_env.list_models("https://usai.example.test/v1/")
        self.assertEqual(ids, ["model-a", "model-b"])
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://usai.example.test/v1/models")
        saved = (self.state / "usai-models.json").read_text()
        self.assertNotIn("test-only-token", saved + output.getvalue())
        self.assertEqual((self.state / "pi/models.json").read_bytes(), provider_before)
        self.assertEqual((self.state / "usai-models.json").stat().st_mode & 0o777, 0o600)

    def test_model_discovery_refuses_redirects_and_does_not_log_body(self):
        self.key()
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError(
            "https://usai.example.test/v1/models", 302, "redirect", {}, None)
        with patch.object(local_env.urllib.request, "build_opener", return_value=opener) as build:
            with self.assertRaisesRegex(RuntimeError, "redirects are refused"):
                local_env.list_models("https://usai.example.test/v1")
            handler = build.call_args.args[0]
            self.assertIsNone(handler.redirect_request(None, None, 302, "", {}, "https://other.example"))
        self.assertFalse((self.state / "usai-models.json").exists())

    def test_invalid_model_list_preserves_previous_catalog(self):
        self.key()
        saved = self.state / "usai-models.json"
        local_env.json_write(saved, {"models": ["retained"]})
        before = saved.read_bytes()
        opener = MagicMock()
        for payload in ({"data": []}, {"data": [{"id": None}]}, {"other": []}):
            opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()
            with self.subTest(payload=payload):
                with patch.object(local_env.urllib.request, "build_opener", return_value=opener):
                    with self.assertRaises(RuntimeError):
                        local_env.list_models("https://usai.example.test/v1")
                self.assertEqual(saved.read_bytes(), before)

    def tracking_sources(self):
        copilot = self.root / "copilot"
        (copilot / "session-state").mkdir(parents=True)
        pi = self.root / "pi-sessions"
        pi.mkdir()
        path = self.state / "agentsview/config.toml"
        local_env.private_write(path, '# retained comment\ncursor_secret = "test-only-secret"\n')
        patch.object(local_env, "agentsview_request", return_value={
            "session_providers": [{"id": "copilot"}, {"id": "pi"}, {"id": "claude"}],
        }).start()
        return copilot, pi, path

    def test_private_pi_tracking_is_offline_and_only_uses_private_sessions(self):
        with patch.object(local_env, "agentsview_request", side_effect=AssertionError("network")), \
                contextlib.redirect_stdout(io.StringIO()):
            local_env.configure_private_pi_tracking()
        config_path = self.state / "agentsview/config.toml"
        config = local_env.tomllib.loads(config_path.read_text())
        self.assertEqual(config["archive_content"], "usage")
        self.assertEqual(config["agents"], {"pi": {"dirs": [str(self.state / "pi/sessions")]}})
        self.assertEqual(config_path.stat().st_mode & 0o777, 0o600)
        metadata = self.state / "agentsview-tracking.json"
        self.assertEqual(json.loads(metadata.read_text())["pi_dirs"], [str(self.state / "pi/sessions")])
        before = (config_path.read_bytes(), metadata.read_bytes())
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.configure_private_pi_tracking()
        self.assertEqual(before, (config_path.read_bytes(), metadata.read_bytes()))

    def test_private_pi_tracking_preserves_existing_configured_sources(self):
        copilot, pi, config = self.tracking_sources()
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.configure_tracking(copilot, [pi], "usage")
        metadata = self.state / "agentsview-tracking.json"
        before = (config.read_bytes(), metadata.read_bytes())
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.configure_private_pi_tracking()
        self.assertEqual(before, (config.read_bytes(), metadata.read_bytes()))

    def test_private_pi_tracking_rejects_unconfigured_existing_settings(self):
        config = self.state / "agentsview/config.toml"
        local_env.private_write(config, 'archive_content = "full"\n')
        with self.assertRaisesRegex(RuntimeError, "existing AgentsView"):
            local_env.configure_private_pi_tracking()
        self.assertEqual(config.read_text(), 'archive_content = "full"\n')
        self.assertFalse((self.state / "agentsview-tracking.json").exists())

    def test_tracking_preserves_config_and_scopes_sources(self):
        copilot, pi, path = self.tracking_sources()
        before = path.read_text()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            local_env.configure_tracking(copilot, [pi, self.state / "pi/sessions"], "usage")
        config = local_env.tomllib.loads(path.read_text())
        self.assertIn(before, path.read_text())
        self.assertEqual(config["archive_content"], "usage")
        self.assertEqual(config["disabled_agents"], ["claude"])
        self.assertEqual(config["agents"]["copilot"]["dirs"], [str(copilot)])
        self.assertEqual(config["agents"]["pi"]["dirs"], [str(pi), str(self.state / "pi/sessions")])
        self.assertNotIn("test-only-secret", output.getvalue())
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_tracking_rerun_preserves_config_bytes(self):
        copilot, pi, path = self.tracking_sources()
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.configure_tracking(copilot, [pi], "usage")
            before = path.read_bytes()
            local_env.configure_tracking(copilot, [pi], "usage")
        self.assertEqual(path.read_bytes(), before)

    def test_tracking_refuses_overwriting_different_archive_policy(self):
        copilot, pi, path = self.tracking_sources()
        local_env.private_write(path, 'archive_content = "full"\n', replace=True)
        before = path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "archive_content differs"):
            local_env.configure_tracking(copilot, [pi], "usage")
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((self.state / "agentsview-tracking.json").exists())

    def test_tracking_rejects_wrong_copilot_root(self):
        _, pi, _ = self.tracking_sources()
        with self.assertRaisesRegex(RuntimeError, "session-state"):
            local_env.configure_tracking(pi, [pi], "usage")

    def test_tracking_refuses_busy_config_without_writes(self):
        copilot, pi, path = self.tracking_sources()
        before = path.read_bytes()
        with open(str(path) + ".lock", "w") as lock:
            local_env.fcntl.flock(lock, local_env.fcntl.LOCK_EX | local_env.fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, "config is busy"):
                local_env.configure_tracking(copilot, [pi], "usage")
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((self.state / "agentsview-tracking.json").exists())

    def test_tracking_refuses_changing_existing_sources(self):
        copilot, pi, path = self.tracking_sources()
        with contextlib.redirect_stdout(io.StringIO()):
            local_env.configure_tracking(copilot, [pi], "usage")
        before = path.read_bytes()
        metadata = (self.state / "agentsview-tracking.json").read_bytes()
        other = self.root / "other-pi-sessions"
        other.mkdir()
        with self.assertRaisesRegex(RuntimeError, "pi directories differ"):
            local_env.configure_tracking(copilot, [other], "usage")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual((self.state / "agentsview-tracking.json").read_bytes(), metadata)

    def test_agentsview_environment_does_not_override_multi_directory_pi_sources(self):
        env = local_env.agentsview_environment()
        self.assertNotIn("PI_CODING_AGENT_DIR", env)
        self.assertNotIn("USAI_API_KEY", env)
        self.assertEqual(env["HOME"], str(self.state / "home"))
        self.assertEqual(env["AGENTSVIEW_TELEMETRY_ENABLED"], "0")

    def test_agentsview_command_enables_sync_only_when_tracking_is_configured(self):
        self.assertIn("--no-sync", local_env.agentsview_command())
        local_env.json_write(self.state / "agentsview-tracking.json", {})
        self.assertNotIn("--no-sync", local_env.agentsview_command())

    def test_systemd_paths_are_quoted_and_specifiers_escaped(self):
        self.assertEqual(local_env.systemd_quote('/path with spaces/100%/$name/a"b'),
                         '"/path with spaces/100%%/$$name/a\\"b"')
        with self.assertRaisesRegex(RuntimeError, "line breaks"):
            local_env.systemd_quote("/path\ninjection")

    def test_stopped_stack_status_does_not_query_forge(self):
        with patch.object(local_env, "managed_agentsview", return_value={"pid": 123}) as managed:
            with patch.object(local_env, "api") as api:
                result = local_env.status()
        self.assertEqual(result["stack"], "stopped")
        self.assertEqual(result["agentsview_service"]["pid"], 123)
        api.assert_not_called()
        managed.assert_called_once()

    def test_running_status_refreshes_independent_service_pid(self):
        local_env.json_write(self.state / "runtime/supervisor.json", {})
        saved = {"pid": 456, "external_services": {"agentsview": {"pid": 123}}}
        current = {"unit": local_env.AGENTSVIEW_UNIT, "pid": 789}
        with patch.object(local_env, "managed_agentsview", return_value=current):
            with patch.object(local_env, "supervisor", return_value=saved):
                with patch.object(local_env, "api", return_value={"projects": []}):
                    result = local_env.status()
        self.assertEqual(result["stack"], "running")
        self.assertEqual(result["supervisor"]["external_services"]["agentsview"], current)
        self.assertEqual(result["agentsview_service"], current)

    def test_managed_agentsview_refuses_another_process(self):
        local_env.json_write(self.state / "agentsview-service.json", {"unit": local_env.AGENTSVIEW_UNIT})
        with patch.object(local_env.subprocess, "run", return_value=MagicMock(
                stdout="MainPID=123\nActiveState=active\n")):
            with patch.object(local_env, "agentsview_request", return_value={
                    "pid": 456, "healthy": True, "version": "test"}):
                with self.assertRaisesRegex(RuntimeError, "does not match"):
                    local_env.managed_agentsview()

    def test_agentsview_health_uses_the_actual_ping_endpoint(self):
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = b'{"healthy":true}'
        with patch.object(local_env, "HTTP", opener):
            self.assertTrue(local_env.agentsview_request("GET", "/ping")["healthy"])
        self.assertEqual(opener.open.call_args.args[0].full_url, "http://127.0.0.1:18080/api/ping")

    def node_executable(self):
        node = self.root / "node-runtime/bin/node"
        node.parent.mkdir(parents=True)
        node.touch()
        node.chmod(0o755)
        return node

    def test_roborev_environment_pins_node_without_credentials(self):
        node = self.node_executable()
        with patch.dict(os.environ, {"PATH": "/usr/bin:/bin", "USAI_API_KEY": "not-inherited"}):
            env = local_env.node_environment(node)
        self.assertEqual(env["PATH"].split(os.pathsep)[0], str(node.parent))
        self.assertNotIn("USAI_API_KEY", env)
        self.assertEqual(env["PI_CODING_AGENT_DIR"], str(self.state / "pi"))

    def test_roborev_rejects_missing_node_and_nonlocal_bindings(self):
        with self.assertRaisesRegex(RuntimeError, "missing executable Node"):
            local_env.node_environment(self.root / "missing-node")
        config = self.state / "roborev/config.toml"
        local_env.private_write(config, 'server_addr = "0.0.0.0:17373"\n', replace=True)
        with self.assertRaisesRegex(RuntimeError, "loopback"):
            local_env.validate_roborev_config()

    def test_roborev_service_installation_preserves_settings_and_records_node(self):
        node = self.node_executable()
        binary = self.root / "native-roborev"
        binary.touch()
        binary.chmod(0o755)
        config = self.state / "roborev/config.toml"
        before = config.read_bytes()
        def systemctl(command, **kwargs):
            inactive = ("is-active" in command
                        and not (self.state / "roborev-service.json").exists())
            return MagicMock(returncode=3 if inactive else 0)

        with patch.object(local_env.shutil, "which", return_value=str(node)):
            with patch.object(local_env.subprocess, "run", side_effect=systemctl) as run, \
                    patch.object(local_env, "check_ports"):
                with patch.object(local_env, "managed_roborev", return_value={"pid": 123}):
                    with contextlib.redirect_stdout(io.StringIO()):
                        local_env.install_roborev_service(binary)
                        first = (self.state / "systemd" / local_env.ROBOREV_UNIT).read_bytes()
                        local_env.install_roborev_service()
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual((self.state / "systemd" / local_env.ROBOREV_UNIT).read_bytes(), first)
        text = first.decode()
        self.assertIn(f'ExecStart="{binary}" "daemon" "run"', text)
        self.assertIn(str(node.parent), text)
        self.assertIn(f'Environment="ROBOREV_DATA_DIR={self.state / "roborev"}"', text)
        self.assertIn(f'WorkingDirectory={self.state / "home"}\n', text)
        self.assertNotIn("local_env.py", text)
        self.assertIn("WantedBy=default.target", text)
        self.assertNotIn("USAI_API_KEY", text)
        self.assertIn(unittest.mock.call(
            ["systemctl", "--user", "enable", "--now", local_env.ROBOREV_UNIT],
            check=True, timeout=60), run.call_args_list)
        self.assertTrue((self.state / "roborev-service.json").exists())
        self.assertEqual(local_env.roborev_binary(), binary)

    def test_roborev_binary_change_refuses_active_service_without_mutation(self):
        node = self.node_executable()
        binary = self.root / "replacement-roborev"
        binary.touch()
        binary.chmod(0o755)
        marker = self.state / "roborev-service.json"
        local_env.json_write(marker, {"unit": local_env.ROBOREV_UNIT})
        before = marker.read_bytes()
        with patch.object(local_env.shutil, "which", return_value=str(node)), \
                patch.object(local_env.subprocess, "run", return_value=MagicMock(returncode=0)), \
                self.assertRaisesRegex(RuntimeError, "finish reviews and stop"):
            local_env.install_roborev_service(binary)
        self.assertEqual(marker.read_bytes(), before)
        self.assertFalse((self.state / "systemd").exists())

    def test_roborev_binary_change_preserves_unit_and_marker_after_late_start(self):
        node = self.node_executable()
        binary = self.root / "replacement-roborev"
        binary.touch()
        binary.chmod(0o755)
        marker = self.state / "roborev-service.json"
        local_env.json_write(marker, {"unit": local_env.ROBOREV_UNIT})
        before = marker.read_bytes()
        unit = self.state / "systemd" / local_env.ROBOREV_UNIT
        def systemctl(command, **kwargs):
            return MagicMock(returncode=3 if "is-active" in command else 0)

        for previous in (None, "original unit bytes\n"):
            with self.subTest(previous=previous):
                if previous is not None:
                    local_env.private_write(unit, previous)
                with patch.object(local_env.shutil, "which", return_value=str(node)), \
                        patch.object(local_env.subprocess, "run", side_effect=systemctl) as run, \
                        patch.object(local_env, "check_ports"), \
                        patch.object(local_env, "user_service_pid", return_value=123), \
                        patch.object(local_env.os.path, "samefile", return_value=False), \
                        self.assertRaisesRegex(RuntimeError, "executable differs"):
                    local_env.install_roborev_service(binary)
                self.assertEqual(marker.read_bytes(), before)
                if previous is None:
                    self.assertFalse(unit.exists())
                else:
                    self.assertEqual(unit.read_text(), previous)
                self.assertEqual(run.call_args.args[0], ["systemctl", "--user", "daemon-reload"])

    def test_managed_roborev_checks_requested_executable_identity(self):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.read.side_effect = [b'{"pid":123,"ok":true,"version":"test"}', b'{"version":"test"}']
        response.status = 200
        response.headers = {"Content-Type": "text/html"}
        binary = self.root / "native-roborev"
        with patch.object(local_env, "user_service_pid", return_value=123), \
                patch.object(local_env.os.path, "samefile", return_value=True) as samefile, \
                patch.object(local_env, "HTTP", opener):
            result = local_env.managed_roborev(required=True, binary=binary)
        self.assertEqual(result["pid"], 123)
        samefile.assert_called_once_with("/proc/123/exe", binary)

    def test_managed_roborev_refuses_another_process(self):
        local_env.json_write(self.state / "roborev-service.json", {"unit": local_env.ROBOREV_UNIT})
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = (
            b'{"pid":456,"ok":true,"version":"test"}')
        with patch.object(local_env, "user_service_pid", return_value=123):
            with patch.object(local_env, "HTTP", opener):
                with self.assertRaisesRegex(RuntimeError, "does not match"):
                    local_env.managed_roborev()

    def test_managed_roborev_checks_database_and_web_health(self):
        local_env.json_write(self.state / "roborev-service.json", {"unit": local_env.ROBOREV_UNIT})
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.read.side_effect = [b'{"pid":123,"ok":true,"version":"test"}', b'{"version":"test"}']
        response.status = 200
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        with patch.object(local_env, "user_service_pid", return_value=123):
            with patch.object(local_env, "HTTP", opener):
                service = local_env.managed_roborev()
        self.assertEqual(service["pid"], 123)
        self.assertEqual([call.args[0] for call in opener.open.call_args_list[:2]], [
            "http://127.0.0.1:17373/api/ping", "http://127.0.0.1:17373/api/status",
        ])
        request = opener.open.call_args_list[2].args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:17374/reviews")
        self.assertEqual(request.get_header("Accept"), "text/html")

    def test_supervised_ports_exclude_both_independent_services(self):
        self.assertEqual(local_env.supervised_ports({}), local_env.PORTS)
        self.assertEqual(local_env.supervised_ports({"agentsview": {}}),
                         (17373, 17374, 17777, 18091))
        self.assertEqual(local_env.supervised_ports({"agentsview": {}, "roborev": {}}),
                         (17777, 18091))

    def test_stop_preserves_both_independent_services(self):
        external = {
            "agentsview": {"unit": local_env.AGENTSVIEW_UNIT},
            "roborev": {"unit": local_env.ROBOREV_UNIT},
        }
        local_env.json_write(self.state / "runtime/shutdown.json", {"ok": True})
        with patch.object(local_env, "supervisor", return_value={"pid": 123, "external_services": external}):
            with patch.object(local_env.os, "kill") as kill:
                with patch.object(local_env, "check_ports") as ports:
                    with contextlib.redirect_stdout(io.StringIO()):
                        local_env.stop()
        kill.assert_called_once_with(123, local_env.signal.SIGTERM)
        ports.assert_called_once_with((17777, 18091))

    def test_status_includes_roborev_without_starting_forge(self):
        service = {"unit": local_env.ROBOREV_UNIT, "pid": 123}
        with patch.object(local_env, "managed_services", return_value={"roborev": service}):
            with patch.object(local_env, "api") as api:
                result = local_env.status()
        self.assertEqual(result["roborev_service"], service)
        self.assertIsNone(result["agentsview_service"])
        api.assert_not_called()

    def test_forge_run_is_explicit_and_uses_current_node_when_unspecified(self):
        node = self.node_executable()
        with patch.object(local_env.shutil, "which", return_value=str(node)):
            with patch.object(local_env, "check_ports") as ports:
                with patch.object(local_env.os, "execve", side_effect=RuntimeError("exec")) as execute:
                    with self.assertRaisesRegex(RuntimeError, "exec"):
                        local_env.forge_run()
        ports.assert_called_once_with((local_env.FORGE_PORT,))
        executable, command, environment = execute.call_args.args
        self.assertEqual(executable, str(self.binary))
        self.assertEqual(command[0], str(self.binary))
        self.assertEqual(environment["PATH"].split(os.pathsep)[0], str(node.parent))
        self.assertFalse((self.state / "forge-service.json").exists())

    def test_forge_command_retains_private_config_and_disabled_sync(self):
        command = local_env.forge_command(local_env.settings())
        self.assertEqual(command[0], str(self.binary))
        self.assertIn(str(self.state / "forge/config.toml"), command)
        self.assertIn("--disable-sync", command)
        self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")
        local_env.private_write(self.state / "forge/config.toml", 'host = "0.0.0.0"\nport = 18091\n',
                                replace=True)
        with self.assertRaisesRegex(RuntimeError, "loopback"):
            local_env.validate_forge_config()

    def test_forge_command_enables_sync_only_with_configured_repositories(self):
        config = self.state / "forge/config.toml"
        local_env.private_write(
            config,
            config.read_text() + '\n[[repos]]\nowner = "example"\nname = "service"\n',
            replace=True,
        )
        before = config.read_bytes()
        command = local_env.forge_command(local_env.settings())
        self.assertNotIn("--disable-sync", command)
        self.assertIn(str(config), command)
        self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")
        self.assertEqual(config.read_bytes(), before)

    def test_status_reports_explicit_forge_without_claiming_service_management(self):
        forge = {"managed": False, "version": "test", "revision": "commit"}
        local_env.forge_probe.return_value = forge
        with patch.object(local_env, "api", return_value={"projects": []}) as api:
            result = local_env.status()
        self.assertEqual(result["forge"], forge)
        self.assertEqual(result["projects"], {"projects": []})
        api.assert_called_once_with("GET", "/projects")

    def test_all_persistent_services_leave_no_supervised_ports(self):
        self.assertEqual(local_env.supervised_ports(dict.fromkeys(local_env.SERVICE_PORTS)), ())

    def test_forge_service_installation_preserves_state_and_pins_node(self):
        node = self.node_executable()
        config = self.state / "forge/config.toml"
        database = self.state / "forge/forge.db"
        database.write_bytes(b"persistent-workspace-fixture")
        before = config.read_bytes()
        with patch.object(local_env.shutil, "which", return_value=str(node)):
            with patch.object(local_env.subprocess, "run", return_value=MagicMock(returncode=0)) as run:
                with patch.object(local_env, "managed_forge", return_value={"pid": 123}):
                    with contextlib.redirect_stdout(io.StringIO()):
                        local_env.install_forge_service()
                        first = (self.state / "systemd" / local_env.FORGE_UNIT).read_bytes()
                        local_env.install_forge_service()
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(database.read_bytes(), b"persistent-workspace-fixture")
        self.assertEqual((self.state / "systemd" / local_env.FORGE_UNIT).read_bytes(), first)
        self.assertIn('"forge-run" "--node-executable" ' + local_env.systemd_quote(node), first.decode())
        self.assertIn(local_env.systemd_quote(local_env.RUNTIME_ROOT / "scripts/local_env.py"),
                      first.decode())
        if local_env.RUNTIME_ROOT != local_env.ROOT:
            self.assertNotIn(local_env.systemd_quote(local_env.ROOT / "scripts/local_env.py"),
                             first.decode())
        self.assertIn("WantedBy=default.target", first.decode())
        self.assertNotIn("USAI_API_KEY", first.decode())
        self.assertIn(unittest.mock.call(
            ["systemctl", "--user", "enable", "--now", local_env.FORGE_UNIT],
            check=True, timeout=60), run.call_args_list)
        self.assertEqual(json.loads((self.state / "forge-service.json").read_text()),
                         {"unit": local_env.FORGE_UNIT})

    def forge_runtime(self, **overrides):
        runtime = {"pid": 123, "service": "kenn-forge", "version": "test",
                   "address": "127.0.0.1:18091",
                   "metadata": {"data_dir": str(self.state / "forge"),
                                "config_path": str(self.state / "forge/config.toml")}}
        local_env.json_write(self.state / "forge/daemon.123.json",
                             {**runtime, **overrides}, replace=True)

    def forge_opener(self, **overrides):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.read.return_value = json.dumps(
            {"status": "ok", "version": "test", "revision": "commit", **overrides}).encode()
        response.status = 200
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        return opener

    def test_managed_forge_checks_runtime_health_and_dashboard(self):
        self.forge_runtime()
        opener = self.forge_opener()
        with patch.object(local_env, "user_service_pid", return_value=123):
            with patch.object(local_env, "HTTP", opener):
                service = local_env.managed_forge(required=True)
        self.assertEqual(service, {"unit": local_env.FORGE_UNIT, "pid": 123,
                                   "version": "test", "revision": "commit"})
        self.assertEqual([call.args[0] for call in opener.open.call_args_list], [
            "http://127.0.0.1:18091/healthz", "http://127.0.0.1:18091/",
        ])

    def test_managed_forge_requires_marker_unless_installing(self):
        with patch.object(local_env, "user_service_pid") as pid:
            self.assertIsNone(local_env.managed_forge())
        pid.assert_not_called()

    def test_managed_forge_rejects_wrong_runtime_identity(self):
        for key, value in (("pid", 456), ("service", "other"), ("address", "0.0.0.0:18091"),
                           ("metadata", {"data_dir": "/other", "config_path": "/other/config"})):
            with self.subTest(key=key):
                self.forge_runtime(**{key: value})
                with patch.object(local_env, "user_service_pid", return_value=123):
                    with self.assertRaisesRegex(RuntimeError, "runtime identity"):
                        local_env.managed_forge(required=True)

    def test_managed_forge_rejects_invalid_health_and_dashboard(self):
        self.forge_runtime()
        with patch.object(local_env, "user_service_pid", return_value=123):
            for key, value in (("status", "error"), ("version", "other"), ("revision", "")):
                with self.subTest(key=key):
                    with patch.object(local_env, "HTTP", self.forge_opener(**{key: value})):
                        with self.assertRaisesRegex(RuntimeError, "database health"):
                            local_env.managed_forge(required=True)
            opener = self.forge_opener()
            opener.open.return_value.__enter__.return_value.headers = {"Content-Type": "application/json"}
            with patch.object(local_env, "HTTP", opener):
                with self.assertRaisesRegex(RuntimeError, "dashboard"):
                    local_env.managed_forge(required=True)

    def test_status_reports_managed_forge_without_unmanaged_probe(self):
        service = {"unit": local_env.FORGE_UNIT, "pid": 123, "version": "test", "revision": "commit"}
        with patch.object(local_env, "managed_services", return_value={"forge": service}):
            with patch.object(local_env, "api", return_value={"projects": []}):
                result = local_env.status()
        self.assertEqual(result["forge_service"], service)
        self.assertEqual(result["forge"], {"managed": True, **service})
        local_env.forge_probe.assert_not_called()

    def test_supervisor_launches_and_stops_only_unmanaged_forge(self):
        external = {name: {"unit": name + ".service", "pid": 123}
                    for name in ("kata", "roborev", "agentsview")}
        process = MagicMock(pid=456)
        process.poll.return_value = None
        with patch.object(local_env, "managed_services", return_value=external), \
                patch.object(local_env, "check_ports") as ports, \
                patch.object(local_env, "HTTP", self.forge_opener()), \
                patch.object(local_env.subprocess, "Popen", return_value=process) as start, \
                patch.object(local_env.time, "sleep", side_effect=SystemExit(0)), \
                patch.object(local_env.signal, "signal"), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                local_env.serve()
        start.assert_called_once()
        self.assertEqual(start.call_args.args[0], local_env.forge_command(local_env.settings()))
        self.assertEqual(ports.call_args_list, [
            unittest.mock.call((18091,)), unittest.mock.call((18091,)),
        ])
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=15)
        self.assertFalse((self.state / "runtime/supervisor.json").exists())

    def test_kata_service_installation_preserves_profile_and_is_repeatable(self):
        config = self.state / "kata/config.toml"
        database = self.state / "kata/kata.db"
        database.write_bytes(b"persistent-task-fixture")
        before = config.read_bytes()
        with patch.object(local_env.subprocess, "run", return_value=MagicMock(returncode=0)) as run:
            with patch.object(local_env, "managed_kata", return_value={"pid": 123}):
                with contextlib.redirect_stdout(io.StringIO()):
                    local_env.install_kata_service()
                    first = (self.state / "systemd" / local_env.KATA_UNIT).read_bytes()
                    local_env.install_kata_service()
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(database.read_bytes(), b"persistent-task-fixture")
        self.assertEqual((self.state / "systemd" / local_env.KATA_UNIT).read_bytes(), first)
        self.assertIn('ExecStart="/usr/bin/env" "-i"', first.decode())
        self.assertIn(f'"KATA_HOME={self.state / "kata"}"', first.decode())
        self.assertIn(f'"KATA_DSN={database}"', first.decode())
        self.assertIn('"KATA_DB="', first.decode())
        self.assertIn(f'"{local_env.RUNTIME_ROOT / "kata/kata"}" "daemon" "start"', first.decode())
        self.assertNotIn("Environment=", first.decode())
        self.assertNotIn("local_env.py", first.decode())
        self.assertIn("WantedBy=default.target", first.decode())
        self.assertNotIn("USAI_API_KEY", first.decode())
        self.assertIn(unittest.mock.call(
            ["systemctl", "--user", "enable", "--now", local_env.KATA_UNIT],
            check=True, timeout=60), run.call_args_list)
        self.assertEqual(json.loads((self.state / "kata-service.json").read_text()),
                         {"unit": local_env.KATA_UNIT})

    def test_supervisor_pins_only_kata_storage(self):
        external = {name: {"unit": name + ".service", "pid": 123}
                    for name in ("forge", "roborev", "agentsview")}
        process = MagicMock(pid=456)
        process.poll.return_value = None
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(
            {"ok": True, "version": "test"},
        ).encode()
        with patch.dict(os.environ, {"KATA_DSN": "/other/dsn.db", "KATA_DB": "/other/legacy.db"}), \
                patch.object(local_env, "managed_services", return_value=external), \
                patch.object(local_env, "check_ports"), \
                patch.object(local_env, "HTTP", opener), \
                patch.object(local_env.subprocess, "Popen", return_value=process) as start, \
                patch.object(local_env.time, "sleep", side_effect=SystemExit(0)), \
                patch.object(local_env.signal, "signal"), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                local_env.serve()
        start.assert_called_once()
        self.assertEqual(start.call_args.args[0], local_env.kata_command())
        env = start.call_args.kwargs["env"]
        self.assertEqual(env["KATA_DSN"], str(self.state / "kata/kata.db"))
        self.assertEqual(env["KATA_DB"], "")
        self.assertNotIn("KATA_DSN", local_env.base_environment())
        self.assertNotIn("KATA_DB", local_env.base_environment())
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=15)

    def test_kata_service_command_does_not_inherit_kata_overrides(self):
        probe = self.root / "environment_probe.py"
        probe.write_text("import json, os\nprint(json.dumps(dict(os.environ)))\n")
        with patch.object(local_env, "kata_command", return_value=[sys.executable, str(probe)]), \
                patch.dict(os.environ, {
                    "KATA_AUTH_TOKEN": "synthetic-token",
                    "KATA_AUTH_TOKEN_FILE": "/synthetic/token",
                    "KATA_DSN": "/other/database",
                    "KATA_DB": "/other/legacy.db",
                    "KATA_SERVER": "https://daemon.example",
                    "KATA_TRUST_PRIVATE_NETWORK": "1",
                }):
            command = local_env.kata_service_command()
            result = subprocess.run(
                command, check=True, capture_output=True, text=True, env=os.environ.copy(),
            )

        service_environment = json.loads(result.stdout)
        self.assertEqual(service_environment["KATA_HOME"], str(self.state / "kata"))
        self.assertEqual(service_environment["KATA_DSN"], str(self.state / "kata/kata.db"))
        self.assertEqual(service_environment["KATA_DB"], "")
        self.assertNotIn("KATA_AUTH_TOKEN", service_environment)
        self.assertNotIn("KATA_AUTH_TOKEN_FILE", service_environment)
        self.assertNotIn("KATA_SERVER", service_environment)
        self.assertNotIn("KATA_TRUST_PRIVATE_NETWORK", service_environment)

    def test_kata_rejects_nonlocal_or_separate_web_bindings_and_missing_binary(self):
        for content in ('listen = "0.0.0.0:17777"\n',
                        'listen = "127.0.0.1:17777"\n[web]\nlisten = "0.0.0.0:17778"\n'):
            local_env.private_write(self.state / "kata/config.toml", content, replace=True)
            with self.assertRaisesRegex(RuntimeError, "loopback"):
                local_env.validate_kata_config()
        with patch.object(Path, "is_file", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "missing executable Kata"):
                local_env.kata_command()

    def kata_opener(self, *, pid=123, health=None):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.read.side_effect = [
            json.dumps({"pid": pid, "service": "kata", "ok": True, "version": "test"}).encode(),
            json.dumps(health if health is not None else {
                "ok": True, "version": "test", "schema_version": 30,
                "api_schema_version": "0.24.0", "db_path": str(self.state / "kata/kata.db"),
            }).encode(),
        ]
        response.status = 200
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        return opener

    def test_managed_kata_checks_service_database_and_html_readiness(self):
        opener = self.kata_opener()
        with patch.object(local_env, "user_service_pid", return_value=123):
            with patch.object(local_env, "HTTP", opener):
                result = local_env.managed_kata(required=True)
        self.assertEqual(result, {"unit": local_env.KATA_UNIT, "pid": 123,
                                 "version": "test", "schema_version": 30,
                                 "api_schema_version": "0.24.0"})
        self.assertEqual([call.args[0] for call in opener.open.call_args_list[:2]], [
            "http://127.0.0.1:17777/api/v1/ping", "http://127.0.0.1:17777/api/v1/health",
        ])
        request = opener.open.call_args_list[2].args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:17777/kata")
        self.assertEqual(request.get_header("Accept"), "text/html")

    def test_managed_kata_requires_ownership_marker_unless_installing(self):
        with patch.object(local_env, "user_service_pid") as pid:
            self.assertIsNone(local_env.managed_kata())
        pid.assert_not_called()

    def test_managed_kata_rejects_another_process(self):
        with patch.object(local_env, "user_service_pid", return_value=123):
            with patch.object(local_env, "HTTP", self.kata_opener(pid=456)):
                with self.assertRaisesRegex(RuntimeError, "managed user service"):
                    local_env.managed_kata(required=True)

    def test_managed_kata_rejects_wrong_database_and_invalid_health(self):
        good = {"ok": True, "version": "test", "schema_version": 30,
                "api_schema_version": "0.24.0", "db_path": str(self.state / "kata/kata.db")}
        for key, value in (("db_path", "/wrong/kata.db"), ("schema_version", 0),
                           ("schema_version", True), ("api_schema_version", ""),
                           ("version", "other"), ("ok", False)):
            with self.subTest(key=key, value=value):
                with patch.object(local_env, "user_service_pid", return_value=123):
                    with patch.object(local_env, "HTTP", self.kata_opener(health={**good, key: value})):
                        with self.assertRaisesRegex(RuntimeError, "private profile"):
                            local_env.managed_kata(required=True)

    def test_all_four_independent_services_leave_no_supervised_ports(self):
        self.assertEqual(local_env.supervised_ports(dict.fromkeys(local_env.SERVICE_PORTS)), ())

    def test_stopped_supervisor_status_still_reports_kata(self):
        service = {"unit": local_env.KATA_UNIT, "pid": 123}
        with patch.object(local_env, "managed_services", return_value={"kata": service}):
            with patch.object(local_env, "api") as api:
                result = local_env.status()
        self.assertEqual(result["stack"], "stopped")
        self.assertEqual(result["kata_service"], service)
        api.assert_not_called()

    def test_supervisor_without_owned_children_cleans_up_and_keeps_services(self):
        external = {name: {"unit": name + ".service", "pid": 123}
                    for name in local_env.SERVICE_PORTS}
        with patch.object(local_env, "managed_services", return_value=external):
            with patch.object(local_env, "check_ports") as ports:
                with patch.object(local_env, "register_project"):
                    with patch.object(local_env.subprocess, "Popen") as start:
                        with patch.object(local_env.time, "sleep", side_effect=SystemExit(0)):
                            with patch.object(local_env.signal, "signal"):
                                with contextlib.redirect_stdout(io.StringIO()):
                                    with self.assertRaises(SystemExit):
                                        local_env.serve()
        start.assert_not_called()
        self.assertEqual(ports.call_args_list, [unittest.mock.call(()), unittest.mock.call(())])
        self.assertFalse((self.state / "runtime/supervisor.json").exists())
        self.assertEqual(json.loads((self.state / "runtime/shutdown.json").read_text()),
                         {"ok": True, "errors": []})

    def test_stop_preserves_all_independent_services(self):
        external = {name: {"unit": name + ".service"} for name in local_env.SERVICE_PORTS}
        local_env.json_write(self.state / "runtime/shutdown.json", {"ok": True})
        with patch.object(local_env, "supervisor", return_value={"pid": 123, "external_services": external}):
            with patch.object(local_env.os, "kill") as kill:
                with patch.object(local_env, "check_ports") as ports:
                    with contextlib.redirect_stdout(io.StringIO()):
                        local_env.stop()
        kill.assert_called_once_with(123, local_env.signal.SIGTERM)
        ports.assert_called_once_with(())

    def test_github_cli_uses_private_profile_without_inherited_tokens(self):
        with patch.object(Path, "is_file", return_value=True):
            with patch.object(local_env.os, "access", return_value=True):
                with patch.dict(os.environ, {"GH_TOKEN": "not-inherited",
                                             "GITHUB_TOKEN": "not-inherited",
                                             "USAI_API_KEY": "not-inherited"}):
                    command, env = local_env.github_cli_launch(["api", "user"])
        self.assertEqual(command, [str(local_env.GH_BINARY), "api", "user"])
        self.assertEqual(env["GH_CONFIG_DIR"], str(self.state / "gh"))
        self.assertNotIn("GH_PROMPT_DISABLED", env)
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "USAI_API_KEY"):
            self.assertNotIn(name, env)
        self.assertEqual((self.state / "gh").stat().st_mode & 0o777, 0o700)

    def test_github_cli_rejects_missing_tool(self):
        with patch.object(Path, "is_file", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "bootstrap-toolchains"):
                local_env.github_cli_launch(["--version"])

    def test_service_readiness_waits_for_runtime_record(self):
        readiness = MagicMock(side_effect=[FileNotFoundError("not published yet"), {"pid": 123}])
        with patch.object(local_env.subprocess, "run", return_value=MagicMock(returncode=3)):
            with patch.object(local_env, "check_ports"), patch.object(local_env.time, "sleep"):
                local_env.install_user_service(local_env.AGENTSVIEW_UNIT, "agentsview-run", "test",
                                               (18080,), readiness)
        self.assertEqual(readiness.call_count, 2)

    def test_configure_provider_populates_usai_chat_models_and_excludes_embeddings(self):
        local_env.json_write(
            self.state / "usai-models.json",
            {
                "base_url": "https://usai.example.test/v1",
                "fetched_at": "2026-04-16T00:00:00+00:00",
                "models": [*local_env.USAI_CHAT_MODELS, "cohere_english_v3", "text-embedding-005"],
            },
            replace=True,
        )
        local_env.configure_provider(
            "https://usai.example.test/v1",
            "claude-opus-5",
            "openai-completions",
        )
        models = json.loads((self.state / "pi/models.json").read_text())
        entries = models["providers"]["usai"]["models"]
        ids = {entry["id"] for entry in entries}
        for chat_model in local_env.USAI_CHAT_MODELS:
            self.assertIn(chat_model, ids)
        for embedding_model in local_env.USAI_EMBEDDING_MODELS:
            self.assertNotIn(embedding_model, ids)
        for entry in entries:
            self.assertEqual(entry["compat"].get("supportsDeveloperRole"), False)

    def test_configure_provider_supports_adversarial_coder_reviewer_pairings_and_rollback(self):
        self.key()
        for coder, reviewer, coder_family, reviewer_family in (
            ("claude-opus-5.5", "gpt-6.1-sol-latest-guardrails-defaultv2", "claude", "openai"),
            ("gpt-6.1-sol-latest-guardrails-defaultv2", "claude-opus-5.5", "openai", "claude"),
            ("gemini-4-argon", "gpt-6.1-sol-latest-guardrails-defaultv2", "gemini", "openai"),
        ):
            with self.subTest(coder=coder, reviewer=reviewer):
                local_env.configure_provider(
                    "https://usai.example.test/v1",
                    coder,
                    "openai-completions",
                    review_model=reviewer,
                )
                usai_cfg = json.loads((self.state / "usai.json").read_text())
                self.assertEqual(usai_cfg, {"model": coder, "review_model": reviewer})
                roborev_cfg = local_env.tomllib.loads((self.state / "roborev/config.toml").read_text())
                self.assertEqual(roborev_cfg["default_model"], reviewer)
                self.assertEqual(roborev_cfg["review_model"], reviewer)
                local_env.validate_roborev_config()
                coder_cmd, _ = local_env.pi_launch(["-p", "code"])
                self.assertEqual(coder_cmd[1:5], ["--provider", "usai", "--model", coder])
                reviewer_cmd, _ = local_env.pi_launch(["--model", reviewer, "-p", "--no-session"])
                self.assertEqual(reviewer_cmd[1:5], ["--provider", "usai", "--model", reviewer])
                self.assertEqual(reviewer_cmd[5:], ["-p", "--no-session"])
                argon_cmd, _ = local_env.pi_launch(["--model", "gemini-4-argon", "-p", "--no-session"])
                self.assertEqual(argon_cmd[1:5], ["--provider", "usai", "--model", "gemini-4-argon"])
                routing = local_env.model_routing()
                self.assertEqual(
                    routing,
                    {
                        "coder_model": coder,
                        "coder_family": coder_family,
                        "reviewer_model": reviewer,
                        "reviewer_family": reviewer_family,
                        "paired_adversarial": True,
                    },
                )
        local_env.configure_provider(
            "https://usai.example.test/v1",
            "claude-opus-5.5",
            "openai-completions",
        )
        self.assertEqual(json.loads((self.state / "usai.json").read_text()), {"model": "claude-opus-5.5"})
        roborev_cfg = local_env.tomllib.loads((self.state / "roborev/config.toml").read_text())
        self.assertNotIn("default_model", roborev_cfg)
        self.assertNotIn("review_model", roborev_cfg)
        local_env.validate_roborev_config()
        with self.assertRaisesRegex(RuntimeError, "saved USAi model"):
            local_env.pi_launch(["--model", "gpt-6.1-sol-latest-guardrails-defaultv2"])

    def test_configure_provider_rejects_same_family_or_invalid_review_models(self):
        for coder, reviewer in (
            ("claude-opus-5.5", "claude-sonnet-5.5"),
            ("gpt-6.1-sol-latest-guardrails-defaultv2", "gpt-5.6-sol-latest-guardrails-defaultv2"),
            ("gemini-4-argon", "gemini-3.8-flash"),
            ("claude-opus-5.5", "llama_4_maverick"),
            ("claude-opus-5.5", "cohere_english_v3"),
        ):
            with self.subTest(coder=coder, reviewer=reviewer), self.assertRaises(RuntimeError):
                local_env.configure_provider(
                    "https://usai.example.test/v1",
                    coder,
                    "openai-completions",
                    review_model=reviewer,
                )
        local_env.configure_provider(
            "https://usai.example.test/v1",
            "claude-opus-5.5",
            "openai-completions",
            review_model="gpt-6.1-sol-latest-guardrails-defaultv2",
        )
        local_env.sync_roborev_review_model("gpt-5.6-sol-latest-guardrails-defaultv2")
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            local_env.validate_roborev_config()


class AcceptanceTests(unittest.TestCase):
    setUp = LocalEnvironmentTests.setUp
    provider = LocalEnvironmentTests.provider
    key = LocalEnvironmentTests.key

    def accepted_host(self):
        home = self.root / "home"
        (home / ".local/bin").mkdir(parents=True)
        for name in ("kata", "roborev"):
            (home / ".local/bin" / name).symlink_to(local_env.RUNTIME_ROOT / {
                "kata": "kata/kata", "roborev": "roborev/bin/roborev"}[name])
        (home / ".roborev").symlink_to(self.state / "roborev")
        settings = json.loads(local_env.private_read(self.state / "pi/settings.json"))
        settings["packages"] = [*settings.get("packages", []), *local_env.PI_EXTENSIONS]
        local_env.json_write(self.state / "pi/settings.json", settings, replace=True)
        self.provider()
        self.key()
        local_env.private_dir(self.state / "gh")
        local_env.private_write(self.state / "gh/hosts.yml", "github.com:\n    user: synthetic\n")
        servers = json.loads(local_env.private_read(self.state / "pi/mcp.json"))["mcpServers"]
        mcp = "".join(f"{name}: connected, 1 tools (direct)\n" for name in servers)
        patch.object(local_env, "accept_command_output", side_effect=lambda command: {
            "submodule": " abc forge (v1)\n abc kata (v1)\n",
            "mcp": mcp}[command]).start()
        patch.object(local_env, "accept_binaries", return_value=[]).start()
        for name in ("managed_kata", "managed_agentsview", "managed_roborev", "managed_forge"):
            patch.object(local_env, name, return_value={"pid": 1}).start()
        return home

    def run_accept(self, home, repos=()):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            failures = local_env.accept(home=home, repos=repos)
        return failures, output.getvalue()

    def test_complete_host_passes_without_logging_credentials(self):
        home = self.accepted_host()
        failures, output = self.run_accept(home)
        self.assertEqual(failures, [], output)
        self.assertNotIn("test-only-token", output)
        self.assertNotIn("synthetic", output)
        for name in ("pi", "pi-extensions", "submodules", "native-links", "mcp",
                     "service:kata", "service:forge", "usai-provider", "usai-key", "github-login"):
            self.assertIn(f"PASS {name}", output)

    def test_missing_credentials_services_and_drift_are_each_reported(self):
        home = self.accepted_host()
        (self.state / "secrets/usai-api-key").unlink()
        (self.state / "gh/hosts.yml").unlink()
        (home / ".roborev").unlink()
        patch.object(local_env, "managed_forge", side_effect=RuntimeError("not active")).start()
        patch.object(local_env, "accept_command_output", side_effect=lambda command: {
            "submodule": "+abc forge (v1)\n",
            "mcp": "kata: failed\n"}[command]).start()
        failures, output = self.run_accept(home)
        self.assertEqual(set(failures), {"submodules", "native-links", "mcp", "service:forge",
                                         "usai-key", "github-login"})
        self.assertIn("set-key", output)
        self.assertIn("gh-local.py auth login", output)

    def test_registered_repo_needs_forge_project_and_roborev_hook(self):
        home = self.accepted_host()
        repo = self.root / "repo"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        with patch.object(local_env, "api", return_value={"projects": []}):
            failures, _ = self.run_accept(home, [repo])
        self.assertEqual(failures, [f"repo:{repo.resolve()}"])
        hook = repo / ".git/hooks/post-commit"
        hook.write_text("#!/bin/sh\nroborev post-commit\n")
        registered = {"projects": [{"local_path": str(repo)}]}
        with patch.object(local_env, "api", return_value=registered):
            failures, _ = self.run_accept(home, [repo])
        self.assertEqual(failures, [f"repo:{repo.resolve()}"])
        hook.chmod(0o755)
        with patch.object(local_env, "api", return_value=registered):
            failures, output = self.run_accept(home, [repo])
        self.assertEqual(failures, [], output)

    def test_provider_requires_saved_model_entry(self):
        home = self.accepted_host()
        models = json.loads(local_env.private_read(self.state / "pi/models.json"))
        models["providers"]["usai"]["models"] = []
        local_env.json_write(self.state / "pi/models.json", models, replace=True)
        failures, _ = self.run_accept(home)
        self.assertEqual(failures, ["usai-provider"])

    def test_mcp_probe_does_not_seed_isolated_git_config(self):
        self.accepted_host()
        patch.stopall()
        patch.object(local_env, "STATE", self.state).start()
        patch.object(local_env, "verify_pi", return_value="/usr/bin/pi").start()
        with patch.object(local_env, "seed_isolated_gitconfig") as seed, \
                patch.object(local_env.subprocess, "run") as run:
            run.return_value.stdout = ""
            local_env.accept_command_output("mcp")
        seed.assert_not_called()
        self.assertEqual(run.call_args.args[0], ["/usr/bin/pi", "mcp", "list"])


if __name__ == "__main__":
    unittest.main()
