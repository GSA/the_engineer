#!/usr/bin/env bash
# Fresh-host acceptance in a disposable rootless Podman container (Kata p4ke).
# Usage: dist/container/run-acceptance.sh [REVISION]   (default: HEAD, which must be pushed)
# Credentials are optional: with KEEP=1 the container stays up so you can run
#   podman exec -it -u engineer engi-accept bash -lc 'cd ~/kenn-kopy && python3 scripts/local_env.py set-key'
# and gh-local.py auth login, then rerun accept. Otherwise it is removed on exit.
# GOPROXY is forwarded only when set; otherwise dist/install.py applies its own
# 'https://proxy.golang.org|direct' default (Go then falls back to the source repository
# when a TLS proxy answers 403 for go.kenn.io) and records that in the install receipt.
# SUBMODULE_MIRRORS="agentsview=/host/path/or/URL ..." supplies owner-approved mirrors for
# pins that upstream remotes cannot serve; host paths are mounted read-only. Nothing is
# published. Timing and fix receipts go to $ACCEPT_LOG_DIR (default .local/acceptance).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
revision=$(git -C "$root" rev-parse "${1:-HEAD}")
source_url=${ENGINEER_SOURCE:-https://github.com/GSA/the_engineer.git}
name=${NAME:-engi-accept}
image=${IMAGE:-localhost/engi-fresh-host:24.04}
log_dir=${ACCEPT_LOG_DIR:-$root/.local/acceptance}
mkdir -p "$log_dir"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
log="$log_dir/$stamp-${revision:0:12}.log"
receipt="$log_dir/$stamp-${revision:0:12}.json"
started=$(date +%s)
phases_file=$(mktemp)
phase() {  # phase NAME START: append NAME=elapsed (the pipeline below is a subshell, so use a file)
    echo "$1=$(( $(date +%s) - $2 ))" >>"$phases_file"
}

# Mirrors: host paths are bind-mounted read-only at /mirrors/NAME; URLs pass through.
mounts=()
mirror_args=""
fixes=()
for entry in ${SUBMODULE_MIRRORS:-}; do
    module=${entry%%=*}; target=${entry#*=}
    if [[ $module == "$entry" || -z $target ]]; then
        echo "SUBMODULE_MIRRORS entries must be NAME=PATH_OR_URL: $entry" >&2; exit 2
    fi
    if [[ $target != *://* && $target != *@*:* ]]; then
        [[ -d $target ]] || { echo "Mirror path not found: $target" >&2; exit 2; }
        mounts+=(-v "$(cd "$target" && pwd):/mirrors/$module:ro")
        target=/mirrors/$module
        fixes+=("local submodule mirror for $module (owner-approved source of the pin)")
    else
        fixes+=("submodule mirror URL for $module")
    fi
    mirror_args+=" --submodule-mirror $(printf %q "$module=$target")"
done

# Host CAs (for example a corporate TLS proxy) are staged in ignored extra-ca/.
mkdir -p "$here/extra-ca"
find "$here/extra-ca" -mindepth 1 -delete
cp /usr/local/share/ca-certificates/*.crt "$here/extra-ca/" 2>/dev/null || true
build_started=$(date +%s)
podman build -t "$image" "$here"
phase image_build "$build_started"
podman rm -f "$name" >/dev/null 2>&1 || true
podman run -d --name "$name" --systemd=always --tmpfs /tmp "${mounts[@]}" "$image" >/dev/null
[[ ${KEEP:-0} == 1 ]] || trap 'podman rm -f "$name" >/dev/null' EXIT

for _ in $(seq 60); do
    podman exec "$name" systemctl is-active --quiet user@1000.service && break
    sleep 1
done

user_exec() {
    podman exec -u engineer -w /home/engineer \
        -e XDG_RUNTIME_DIR=/run/user/1000 \
        -e DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
        ${GOPROXY:+-e GOPROXY="$GOPROXY"} \
        -e PATH=/home/engineer/.local/engi-pi/node_modules/.bin:/home/engineer/.local/bin:/usr/local/bin:/usr/bin:/bin \
        "$name" bash -lc "$1"
}

safe_directory=true
# Read-only host mirrors are owned by another uid inside the container.
[[ -z $mirror_args ]] || safe_directory="git config --global --add safe.directory '*'"
record_fixes=""
for fix in "${fixes[@]}"; do record_fixes+=" --record-fix $(printf %q "$fix")"; done

{
    echo "revision=$revision source=$source_url"
    install_started=$(date +%s)
    user_exec "set -euxo pipefail
        mkdir -p ~/.local/bin && ln -sf /usr/bin/fdfind ~/.local/bin/fd
        npm install --no-fund --no-audit --prefix ~/.local/engi-pi @earendil-works/pi-coding-agent@1.5.0
        git clone --quiet '$source_url' ~/kenn-kopy
        git -C ~/kenn-kopy checkout --quiet --detach '$revision'
        cd ~/kenn-kopy
        $safe_directory
        bash dist/install.sh --check --corpus /opt/fake-corpus$mirror_args
        bash dist/install.sh --corpus /opt/fake-corpus --services user$mirror_args$record_fixes \
            --usai-base-url https://usai.invalid/api/v1 --usai-model claude-opus-5.5 \
            --usai-review-model gpt-5.6-terra --register-repo ~/kenn-kopy"
    phase install "$install_started"
    accept_started=$(date +%s)
    status=0
    user_exec "cd ~/kenn-kopy && python3 scripts/local_env.py accept --repo ~/kenn-kopy" || status=$?
    phase accept "$accept_started"
    echo "accept_exit=$status"
    # Copy the installer's own receipt (phase timings, defaults, mirrors) out of the container.
    podman cp "$name:/home/engineer/kenn-kopy/.local/install-receipts/." "$log_dir/install-receipts-$stamp" \
        2>/dev/null || echo "note: no installer receipt found in the container"
    exit "$status"
} 2>&1 | tee "$log" && status=0 || status=$?
python3 - "$receipt" "$revision" "$source_url" "$stamp" "$(( $(date +%s) - started ))" \
    "$status" "${SUBMODULE_MIRRORS:-}" "$phases_file" <<'PY'
import json, sys
path, revision, source, stamp, elapsed, status, mirrors, phases = sys.argv[1:]
timings = dict(line.strip().split("=", 1) for line in open(phases) if "=" in line)
json.dump({
    "schema": "engineer.acceptance-receipt/v1", "revision": revision, "source": source,
    "started_at": stamp, "elapsed_seconds": int(elapsed),
    "phase_seconds": {name: int(value) for name, value in timings.items()},
    "accept_exit": int(status), "submodule_mirrors": mirrors.split(),
    "hands_on_note": "scripted run; interactive credential steps (set-key, gh auth login) "
                     "are separate and must be timed by the operator",
}, open(path, "w"), indent=2)
PY
rm -f "$phases_file"
echo "Log: $log"
echo "Receipt: $receipt"
exit "$status"
