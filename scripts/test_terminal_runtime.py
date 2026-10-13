import fcntl
import os
from pathlib import Path
import pty
import shutil
import struct
import subprocess
import tempfile
import termios
import time
import unittest
from unittest.mock import patch

import local_env


@unittest.skipUnless(shutil.which("tmux"), "tmux is not installed")
class TerminalRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="terminal-test-", dir=local_env.ROOT / ".local")
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name)
        self.state.chmod(0o700)
        state_patch = patch.object(local_env, "STATE", self.state)
        state_patch.start()
        self.addCleanup(state_patch.stop)
        local_env.private_write(self.state / "environment.json", "{}\n")
        command, self.environment = local_env.terminal_launch("open", "pilot")
        self.environment["TERM"] = "xterm-256color"
        self.tmux = command[:5]
        self.addCleanup(self.stop_server)
        self.command = command

    def run_tmux(self, *args, check=True):
        result = subprocess.run(
            [*self.tmux, *args], env=self.environment, cwd=local_env.ROOT,
            capture_output=True, text=True, timeout=5,
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def stop_server(self):
        self.run_tmux("kill-server", check=False)

    def start(self, name):
        self.run_tmux("new-session", "-d", "-s", name, "-c", str(local_env.ROOT))

    def pane_pid(self, name):
        return self.run_tmux("display-message", "-p", "-t", f"={name}:", "#{pane_pid}").stdout.strip()

    def wait_for(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.05)
        self.fail("tmux did not reach the expected state within five seconds")

    def test_actual_attach_detach_and_terminal_disconnect_preserve_shell(self):
        self.start("pilot")
        original_pid = self.pane_pid("pilot")
        for disconnect in (False, True):
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))

            def controlling_terminal():
                os.setsid()
                fcntl.ioctl(0, termios.TIOCSCTTY, 0)

            client = subprocess.Popen(
                self.command, env=self.environment, cwd=local_env.ROOT,
                stdin=slave, stdout=slave, stderr=slave, preexec_fn=controlling_terminal,
            )
            os.close(slave)
            try:
                self.wait_for(lambda: self.run_tmux(
                    "display-message", "-p", "-t", "=pilot:", "#{session_attached}",
                ).stdout.strip() == "1")
                if disconnect:
                    os.close(master)
                    master = None
                else:
                    os.write(master, b"\x02d")
                client.wait(timeout=5)
                self.wait_for(lambda: self.run_tmux(
                    "display-message", "-p", "-t", "=pilot:", "#{session_attached}",
                ).stdout.strip() == "0")
                self.assertEqual(self.pane_pid("pilot"), original_pid)
                os.kill(int(original_pid), 0)
            finally:
                if master is not None:
                    os.close(master)
                if client.poll() is None:
                    client.terminate()
                    client.wait(timeout=5)
        self.assertEqual(self.run_tmux("list-sessions", "-F", "#{session_name}").stdout, "pilot\n")

    def test_actual_socket_isolation_profile_environment_and_exact_stop(self):
        with patch.dict(os.environ, {"USAI_API_KEY": "synthetic-not-a-secret"}):
            _, self.environment = local_env.terminal_launch("open", "pilot")
        self.start("pilot")
        self.start("pilot-other")
        sibling_pid = self.pane_pid("pilot-other")
        for variable in ("USAI_API_KEY", "GITHUB_TOKEN"):
            self.assertNotEqual(self.run_tmux("show-environment", "-g", variable, check=False).returncode, 0)
        profile = self.run_tmux("show-environment", "-g", "PI_CODING_AGENT_DIR").stdout.strip()
        self.assertEqual(profile, f"PI_CODING_AGENT_DIR={self.state / 'pi'}")
        self.assertEqual(
            self.run_tmux("show-options", "-gv", "default-command").stdout.strip(),
            "exec /bin/bash --noprofile --norc",
        )
        marker = self.state / "synthetic-shell-check"
        self.run_tmux("send-keys", "-t", "=pilot:", "-l", f"printf ready > '{marker}'")
        self.run_tmux("send-keys", "-t", "=pilot:", "Enter")
        self.wait_for(marker.exists)
        self.assertEqual(marker.read_text(), "ready")
        stop, env = local_env.terminal_launch("stop", "pilot")
        subprocess.run(stop, env=env, capture_output=True, check=True, timeout=5)
        self.assertEqual(self.run_tmux("list-sessions", "-F", "#{session_name}").stdout, "pilot-other\n")
        self.assertEqual(self.pane_pid("pilot-other"), sibling_pid)


if __name__ == "__main__":
    unittest.main()
