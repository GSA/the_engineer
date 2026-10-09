#!/usr/bin/env python3
"""Launch the private Pi profile, with USAi credentials only in its process."""

import os
import subprocess
import sys

from local_env import pi_launch


try:
    os.umask(0o077)
    command, environment = pi_launch(sys.argv[1:])
    os.execve(command[0], command, environment)
except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
    print(f"ERROR: {error}", file=sys.stderr)
    sys.exit(1)
