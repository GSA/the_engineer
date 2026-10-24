#!/usr/bin/python3
"""Invoke roborev against this workspace's private profile and managed daemon."""

import os
import subprocess
import sys
from pathlib import Path

# Resolve the canonical script when invoked through ~/.local/bin/roborev.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_env import roborev_launch, roborev_warnings


try:
    os.umask(0o077)
    command, environment = roborev_launch(sys.argv[1:])
    command_args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    if command_args and command_args[0] in ("status", "doctor"):
        for warning in roborev_warnings():
            print(f"WARNING: {warning}", file=sys.stderr)
    os.execve(command[0], command, environment)
except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
    print(f"ERROR: {error}", file=sys.stderr)
    sys.exit(1)
