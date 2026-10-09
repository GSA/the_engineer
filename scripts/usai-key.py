#!/usr/bin/env python3
"""Pi credential command; stdout is the token and must not be displayed."""

import sys

from local_env import load_usai_key


try:
    print(load_usai_key())
except (OSError, ValueError, RuntimeError) as error:
    print(f"ERROR: {error}", file=sys.stderr)
    sys.exit(1)
