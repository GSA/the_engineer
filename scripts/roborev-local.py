#!/usr/bin/python3
"""Invoke roborev against this workspace's private profile and managed daemon."""

import os
import subprocess
import sys

from local_env import roborev_launch


try:
    os.umask(0o077)
    command, environment = roborev_launch(sys.argv[1:])
    os.execve(command[0], command, environment)
except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
    print(f"ERROR: {error}", file=sys.stderr)
    sys.exit(1)
