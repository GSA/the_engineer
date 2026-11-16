import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import host_setup


def completed(command, code=0, stdout=""):
    return subprocess.CompletedProcess(command, code, stdout, "")


class FakeRunner:
    """Record commands; answer dpkg-query and version probes from a table."""

    def __init__(self, installed=(), node=None, systemd=True, versions=None, fail=()):
        self.commands = []
        self.installed = set(installed)
        self.node = node
        self.systemd = systemd
        self.versions = versions or {}
        self.fail = fail

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        if command[0] == "dpkg-query":
            ok = command[-1] in self.installed
            return completed(command, 0 if ok else 1, "install ok installed" if ok else "")
        if command == ["node", "--version"]:
            return completed(command, 0 if self.node else 1, self.node or "")
        if command[:2] == ["systemctl", "--user"]:
            return completed(command, 0 if self.systemd else 1)
        if command[-1] == "--version":
            name = Path(command[0]).name
            return completed(command, 0 if name in self.versions else 1, self.versions.get(name, ""))
        if any(word in command for word in self.fail):
            return completed(command, 1)
        return completed(command)


class HostSetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)

    def test_apt_runs_only_for_missing_packages_after_consent(self):
        runner = FakeRunner(installed=[p for p in host_setup.APT_PACKAGES if p != "tmux"])
        with patch("sys.stdout", io.StringIO()):
            installed = host_setup.install_apt_packages(lambda question, default: True, runner)
        self.assertEqual(installed, ["tmux"])
        self.assertIn(["sudo", "apt-get", "install", "-y", "--no-install-recommends", "tmux"], runner.commands)

    def test_apt_packages_include_pillow_for_demo_walkthroughs(self):
        self.assertIn("python3-pil", host_setup.APT_PACKAGES)

    def test_apt_is_not_run_without_consent_or_when_nothing_is_missing(self):
        runner = FakeRunner()
        with patch("sys.stdout", io.StringIO()), self.assertRaisesRegex(RuntimeError, "required"):
            host_setup.install_apt_packages(lambda question, default: False, runner)
        self.assertFalse(any(command[0] == "sudo" for command in runner.commands))
        runner = FakeRunner(installed=host_setup.APT_PACKAGES)
        self.assertEqual(host_setup.install_apt_packages(lambda *a: self.fail("asked"), runner), [])

    def test_apt_failure_is_reported_plainly(self):
        runner = FakeRunner(fail=("install",))
        with patch("sys.stdout", io.StringIO()), self.assertRaisesRegex(RuntimeError, "apt message"):
            host_setup.install_apt_packages(lambda *a: True, runner)

    def node_archive(self, path, payload=b"#!/bin/sh\necho v24.11.1\n"):
        with tarfile.open(path, "w:xz") as bundle:
            info = tarfile.TarInfo(f"node-v{host_setup.NODE_VERSION}-linux-x64/bin/node")
            info.size, info.mode = len(payload), 0o755
            bundle.addfile(info, io.BytesIO(payload))

    def test_suitable_existing_node_is_reused(self):
        runner = FakeRunner(node="v26.1.0")
        self.assertFalse(host_setup.install_node(self.home, runner, fetch=lambda *a: self.fail("download")))

    def test_old_node_installs_the_pinned_release_after_checksum(self):
        source = self.home / "node.tar.xz"
        self.node_archive(source)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        with patch.object(host_setup, "NODE_SHA256", digest), patch("sys.stdout", io.StringIO()):
            installed = host_setup.install_node(self.home, FakeRunner(node="v18.0.0"),
                                                fetch=lambda url, dest: Path(dest).write_bytes(source.read_bytes()))
        self.assertTrue(installed)
        self.assertTrue((host_setup.prefix(self.home) / "node/bin/node").is_file())

    def test_node_checksum_mismatch_installs_nothing(self):
        source = self.home / "node.tar.xz"
        self.node_archive(source)
        with patch("sys.stdout", io.StringIO()), self.assertRaisesRegex(RuntimeError, "checksum"):
            host_setup.install_node(self.home, FakeRunner(),
                                    fetch=lambda url, dest: Path(dest).write_bytes(source.read_bytes()))
        self.assertFalse((host_setup.prefix(self.home) / "node").exists())

    def test_npm_package_is_skipped_at_the_pinned_version(self):
        binary = host_setup.prefix(self.home) / "npm/bin/pi"
        binary.parent.mkdir(parents=True)
        binary.write_text("")
        runner = FakeRunner(versions={"pi": "1.5.2"})
        self.assertFalse(host_setup.install_npm_package("pkg", "1.5.2", "pi", self.home, runner))
        runner = FakeRunner(versions={"pi": "1.4.0"})
        with patch("sys.stdout", io.StringIO()):
            self.assertTrue(host_setup.install_npm_package("pkg", "1.5.2", "pi", self.home, runner))
        self.assertIn("pkg@1.5.2", runner.commands[-1])
        self.assertIn(str(host_setup.prefix(self.home) / "npm"), runner.commands[-1])

    def test_wsl_conf_gets_systemd_without_losing_other_settings(self):
        self.assertEqual(host_setup.wsl_conf_with_systemd(""), "[boot]\nsystemd=true\n")
        self.assertEqual(host_setup.wsl_conf_with_systemd("[user]\ndefault=me\n"),
                         "[user]\ndefault=me\n\n[boot]\nsystemd=true\n")
        self.assertEqual(host_setup.wsl_conf_with_systemd("[boot]\nsystemd=false\n[user]\ndefault=me\n"),
                         "[boot]\nsystemd=true\n[user]\ndefault=me\n")
        self.assertEqual(host_setup.wsl_conf_with_systemd("[boot]\ncommand=x\n[user]\ndefault=me\n"),
                         "[boot]\ncommand=x\nsystemd=true\n[user]\ndefault=me\n")

    def test_missing_systemd_on_wsl_asks_then_requires_a_restart(self):
        conf = self.home / "wsl.conf"
        runner = FakeRunner(systemd=False)
        with patch.object(host_setup, "is_wsl", return_value=True), patch("sys.stdout", io.StringIO()):
            with self.assertRaisesRegex(host_setup.NeedsRestart, "wsl --shutdown"):
                host_setup.ensure_systemd(lambda *a: True, runner, conf)
        self.assertTrue(any(command[:2] == ["sudo", "install"] for command in runner.commands))
        runner = FakeRunner(systemd=False)
        with patch.object(host_setup, "is_wsl", return_value=True), patch("sys.stdout", io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "required"):
                host_setup.ensure_systemd(lambda *a: False, runner, conf)
        self.assertFalse(any(command[0] == "sudo" for command in runner.commands))

    def test_shell_block_is_replaced_in_place_and_removed_cleanly(self):
        rc = self.home / ".bashrc"
        rc.write_text("alias ll='ls -l'\n")
        host_setup.write_shell_block(host_setup.shell_block("/opt/eng", copilot=True), self.home)
        host_setup.write_shell_block(host_setup.shell_block("/opt/eng", pi=True), self.home)
        text = rc.read_text()
        self.assertEqual(text.count(host_setup.SHELL_START), 1)
        self.assertIn('pi() { "/opt/eng/engineer" pi "$@"; }', text)
        self.assertNotIn("copilot()", text)
        host_setup.remove_shell_block(self.home)
        self.assertEqual(rc.read_text(), "alias ll='ls -l'\n")

    def test_undo_removes_only_recorded_items(self):
        fd = self.home / ".local/bin/fd"
        fd.parent.mkdir(parents=True)
        fd.symlink_to("/usr/bin/fdfind")
        (host_setup.prefix(self.home) / "npm/bin").mkdir(parents=True)
        mine = self.home / ".local/bin/mytool"
        mine.write_text("")
        host_setup.undo({}, self.home)
        self.assertTrue(fd.is_symlink())
        self.assertTrue(host_setup.prefix(self.home).exists())
        removed = host_setup.undo({"fd_link": True, "prefix": True}, self.home)
        self.assertFalse(fd.is_symlink())
        self.assertFalse(host_setup.prefix(self.home).exists())
        self.assertTrue(mine.exists())
        self.assertEqual(len(removed), 2)


if __name__ == "__main__":
    unittest.main()
