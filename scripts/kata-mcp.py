#!/usr/bin/env python3
"""Serve native Kata MCP for this project with a fixed client actor."""

import os
import sys

from local_env import kata_mcp_launch


try:
    os.umask(0o077)
    if len(sys.argv) != 2:
        raise RuntimeError("usage: kata-mcp.py <pi|copilot>; scope overrides are not accepted")
    command, environment = kata_mcp_launch(sys.argv[1])
    os.execve(command[0], command, environment)
except (OSError, ValueError, KeyError, RuntimeError) as error:
    print(f"ERROR: {error}", file=sys.stderr)
    sys.exit(1)
