#!/usr/bin/env bash
set -euo pipefail

if ! command -v python3 >/dev/null; then
    echo "ERROR: Python 3.11+ is required. On Ubuntu 24.04+, install python3." >&2
    exit 1
fi
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
    echo "ERROR: Python 3.11+ is required; the current python3 is too old." >&2
    exit 1
fi
exec python3 "$(dirname -- "${BASH_SOURCE[0]}")/install.py" "$@"
