#!/usr/bin/env python3
"""Open persistent standalone terminals without touching Forge's tmux server."""

import argparse
import os
import sys

from local_env import terminal_launch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    opening = actions.add_parser("open", help="create or reattach a persistent session")
    opening.add_argument("name", nargs="?", default="engi-platform")
    actions.add_parser("list", help="list this workspace's standalone sessions")
    stopping = actions.add_parser("stop", help="terminate exactly one named session and its processes")
    stopping.add_argument("name")
    args = parser.parse_args(sys.argv[1:] or ["open"])
    if args.action == "open" and not (sys.stdin.isatty() and sys.stdout.isatty()):
        parser.error("open requires an interactive terminal")
    try:
        os.umask(0o077)
        command, environment = terminal_launch(args.action, getattr(args, "name", "engi-platform"))
        os.execve(command[0], command, environment)
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
