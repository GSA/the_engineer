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

mkdir -p .local/downloads .local/tools
gh_version=2.102.0
gh_binary=".local/tools/gh-$gh_version/bin/gh"
if [[ ! -x "$gh_binary" ]]; then
    archive=".local/downloads/gh_${gh_version}_linux_amd64.tar.gz"
    curl --fail --location --silent --show-error --max-time 180 \
        "https://github.com/cli/cli/releases/download/v$gh_version/gh_${gh_version}_linux_amd64.tar.gz" \
        -o "$archive"
    printf '%s\n' \
        "bb766f710eef8ede859c18578c72c327597cd4c8a85b06001b1f3843c6019386  $archive" \
        | sha256sum --check
    mkdir -p ".local/tools/gh-$gh_version"
    tar -xzf "$archive" -C ".local/tools/gh-$gh_version" --strip-components=1
fi
if [[ "$("$gh_binary" --version)" != "gh version $gh_version "* ]]; then
    echo "GitHub CLI version mismatch in $gh_binary." >&2
    exit 1
fi

jq_version=1.7.1
jq_binary=".local/tools/jq-$jq_version/bin/jq"
if [[ ! -x "$jq_binary" ]]; then
    archive=".local/downloads/jq_${jq_version}_linux_amd64"
    curl --fail --location --silent --show-error --max-time 180 \
        "https://github.com/jqlang/jq/releases/download/jq-$jq_version/jq-linux-amd64" \
        -o "$archive"
    printf '%s\n' \
        "5942c9b0934e510ee61eb3e30273f1b3fe2590df93933a93d7c58b81d19c8ff5  $archive" \
        | sha256sum --check
    mkdir -p ".local/tools/jq-$jq_version/bin"
    cp "$archive" "$jq_binary"
    chmod 755 "$jq_binary"
fi
if [[ "$("$jq_binary" --version)" != "jq-$jq_version" ]]; then
    echo "jq version mismatch in $jq_binary." >&2
    exit 1
fi

export npm_config_cache="$PWD/.local/cache/npm"
mkdir -p .local/downloads .local/tools/go-1.27.3
if [[ ! -x .local/tools/go-1.27.3/bin/go ]]; then
    curl --fail --location --silent --show-error --max-time 180 \
        https://go.dev/dl/go1.27.3.linux-amd64.tar.gz \
        -o .local/downloads/go1.27.3.linux-amd64.tar.gz
    printf '%s\n' \
        '65efbc80fdc1fa2cd2631cad5b481777a68e8725f34e89f50fc6ac714e379b40  .local/downloads/go1.27.3.linux-amd64.tar.gz' \
        | sha256sum --check
    tar -xzf .local/downloads/go1.27.3.linux-amd64.tar.gz \
        -C .local/tools/go-1.27.3 --strip-components=1
fi
if [[ "$(.local/tools/go-1.27.3/bin/go version)" != "go version go1.27.3 linux/amd64" ]]; then
    echo "Go version mismatch in .local/tools/go-1.27.3." >&2
    exit 1
fi

for version in 1.3.14 1.4.0 1.4.4; do
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
