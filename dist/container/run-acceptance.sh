#!/usr/bin/env bash
# Fresh-host acceptance of the teammate path in a disposable rootless Podman container.
# Usage: dist/container/run-acceptance.sh [REVISION]   (default: HEAD)
# The container clones ENGINEER_SOURCE (default: the GitHub repository; a local checkout
# path is mounted read-only, so unpushed revisions can be tested), then runs
#   ./engineer install --yes --copilot yes && ./engineer add-repo ~/engineer && ./engineer doctor
# exactly as the README quickstart does, minus the interactive key and GitHub sign-in.
# With KEEP=1 the container stays up so you can run
#   podman exec -it -u engineer engi-accept bash -lc 'cd ~/engineer && ./engineer key'
# and ./engineer login, then ./engineer doctor. Otherwise it is removed on exit.
# GOPROXY is forwarded only when set. Timing receipts go to $ACCEPT_LOG_DIR
# (default .local/acceptance).
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

mounts=()
clone_url=$source_url
if [[ -d $source_url ]]; then
    mounts+=(-v "$(cd "$source_url" && pwd):/source:ro")
    clone_url=/source
fi

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
        "$name" bash -lc "$1"
}

{
    echo "revision=$revision source=$source_url"
    install_started=$(date +%s)
    user_exec "set -euxo pipefail
        git config --global --add safe.directory '*'
        git clone --quiet '$clone_url' ~/engineer
        git -C ~/engineer checkout --quiet --detach '$revision'
        cd ~/engineer
        ./engineer install --yes --copilot yes || true
        ./engineer add-repo ~/engineer"
    phase install "$install_started"
    accept_started=$(date +%s)
    status=0
    user_exec "cd ~/engineer && ./engineer doctor" || status=$?
    phase doctor "$accept_started"
    echo "doctor_exit=$status"
    podman cp "$name:/home/engineer/engineer/.local/install-receipts/." "$log_dir/install-receipts-$stamp" \
        2>/dev/null || echo "note: no installer receipt found in the container"
    exit "$status"
} 2>&1 | tee "$log" && status=0 || status=$?
python3 - "$receipt" "$revision" "$source_url" "$stamp" "$(( $(date +%s) - started ))" \
    "$status" "$phases_file" <<'PY'
import json, sys
path, revision, source, stamp, elapsed, status, phases = sys.argv[1:]
timings = dict(line.strip().split("=", 1) for line in open(phases) if "=" in line)
json.dump({
    "schema": "engineer.acceptance-receipt/v2", "revision": revision, "source": source,
    "started_at": stamp, "elapsed_seconds": int(elapsed),
    "phase_seconds": {name: int(value) for name, value in timings.items()},
    "doctor_exit": int(status),
    "hands_on_note": "scripted run; the interactive USAi key and GitHub sign-in are separate "
                     "and must be timed by the operator",
}, open(path, "w"), indent=2)
PY
rm -f "$phases_file"
echo "Log: $log"
echo "Receipt: $receipt"
exit "$status"
