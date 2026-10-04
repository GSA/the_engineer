#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

git submodule sync --recursive
git submodule update --init --recursive --checkout
