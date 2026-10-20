#!/usr/bin/python3
"""Invoke private Kata with explicit, actor-checked application project selection."""

import os
import subprocess
import sys

from local_env import kata_launch


try:
    os.umask(0o077)
    command, environment = kata_launch(sys.argv[1:], allow_application_projects=True)
    os.execve(command[0], command, environment)
except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
    print(f"ERROR: {error}", file=sys.stderr)
    sys.exit(1)
