#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
root="$PWD"
export PATH="$root/.local/tools/go-1.27.3/bin:$PATH"
export GOPATH="$root/.local/cache/go"
export GOCACHE="$root/.local/cache/go-build"
export BUN_INSTALL_CACHE_DIR="$root/.local/cache/bun"
export npm_config_cache="$root/.local/cache/npm"
export GOENV=off GOTOOLCHAIN=local GOTELEMETRY=off
export GOMAXPROCS=2 GOFLAGS="-p=2" CGO_ENABLED=1

if [[ "$(go version)" != "go version go1.27.3 linux/amd64" ]]; then
    echo "Expected workspace-local Go 1.27.3 for Linux amd64; see context/tools.md." >&2
    exit 1
fi

if [[ $# -eq 0 ]]; then
    set -- roborev forge kata agentsview
fi

for project in "$@"; do
    case "$project" in
        roborev|kata) bun_version=1.4.4 ;;
        forge|forge-local-kata) bun_version=1.4.4 ;;
        agentsview) bun_version= ;;
        *) echo "Unknown build target: $project" >&2; exit 2 ;;
    esac

    (
        if [[ "$project" == forge-local-kata ]]; then
            cd forge
        else
            cd "$project"
        fi
        if [[ "$project" == roborev || "$project" == kata ]]; then
            go mod download github.com/mattn/go-sqlite3
            include="$root/.local/include/$project"
            mkdir -p "$include"
            install -m 0644 \
                "$(go list -m -f '{{.Dir}}' github.com/mattn/go-sqlite3)/sqlite3-binding.h" \
                "$include/sqlite3.h"
            export CGO_CFLAGS="-O2 -g -I$include"
        fi
        if [[ -n "$bun_version" ]]; then
            export PATH="$root/.local/tools/bun-$bun_version/node_modules/@oven/bun-linux-x64/bin:$PATH"
            if [[ "$(bun --version)" != "$bun_version" ]]; then
                echo "Expected workspace-local Bun $bun_version; see context/tools.md." >&2
                exit 1
            fi
            if [[ "$project" == forge-local-kata ]]; then
                bun "$root/scripts/build-forge-local-kata.mjs"
                exit
            fi
            bun install --frozen-lockfile
            # Forge's frontend target otherwise invokes an unfrozen install.
            if [[ "$project" == forge ]]; then
                make build -o frontend-deps
            else
                make build
            fi
        else
            make build
        fi
    )
done
