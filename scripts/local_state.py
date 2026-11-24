"""Test helper: a parent directory for scratch state under the checkout's ignored .local/."""

from pathlib import Path

import local_env


def state_parent():
    """Return the checkout's `.local` directory, creating it on a fresh clone (CI)."""
    path = Path(local_env.ROOT) / ".local"
    path.mkdir(exist_ok=True)
    return path
