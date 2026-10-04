#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [[ "$(uname -s)/$(uname -m)" != Linux/x86_64 ]]; then
    echo "This initial toolchain bootstrap supports Linux x86_64 only." >&2
    exit 1
fi
for tool in curl tar sha256sum npm; do
    command -v "$tool" >/dev/null || {
        echo "Required prerequisite is missing: $tool" >&2
        exit 1
    }
done

export npm_config_cache="$PWD/.local/cache/npm"
mkdir -p .local/downloads .local/tools/go-1.27.1
if [[ ! -x .local/tools/go-1.27.1/bin/go ]]; then
    curl --fail --location --silent --show-error --max-time 180 \
        https://go.dev/dl/go1.27.1.linux-amd64.tar.gz \
        -o .local/downloads/go1.27.1.linux-amd64.tar.gz
    printf '%s\n' \
        '63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445  .local/downloads/go1.27.1.linux-amd64.tar.gz' \
        | sha256sum --check
    tar -xzf .local/downloads/go1.27.1.linux-amd64.tar.gz \
        -C .local/tools/go-1.27.1 --strip-components=1
fi
if [[ "$(.local/tools/go-1.27.1/bin/go version)" != "go version go1.27.1 linux/amd64" ]]; then
    echo "Go version mismatch in .local/tools/go-1.27.1." >&2
    exit 1
fi

for version in 1.3.14 1.4.0; do
    binary=".local/tools/bun-$version/node_modules/@oven/bun-linux-x64/bin/bun"
    if [[ ! -x "$binary" ]]; then
        npm install --prefix ".local/tools/bun-$version" --ignore-scripts \
            --no-audit --no-fund --save-exact "@oven/bun-linux-x64@$version"
    fi
    if [[ "$("$binary" --version)" != "$version" ]]; then
        echo "Bun version mismatch in $binary" >&2
        exit 1
    fi
done
