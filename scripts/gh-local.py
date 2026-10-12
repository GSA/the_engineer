#!/usr/bin/python3
"""Run GitHub CLI with Forge's isolated login profile, without inherited tokens."""

import os
import subprocess
import sys

from local_env import github_cli_launch


try:
    os.umask(0o077)
    command, environment = github_cli_launch(sys.argv[1:])
    os.execve(command[0], command, environment)
except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
    print(f"ERROR: {error}", file=sys.stderr)
    sys.exit(1)
