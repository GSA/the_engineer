#!/usr/bin/env bash
# Fresh-host acceptance in a disposable rootless Podman container (Kata p4ke).
# Usage: dist/container/run-acceptance.sh [REVISION]   (default: HEAD, which must be pushed)
# Credentials are optional: with KEEP=1 the container stays up so you can run
#   podman exec -it -u engineer engi-accept bash -lc 'cd ~/kenn-kopy && python3 scripts/local_env.py set-key'
# and gh-local.py auth login, then rerun accept. Otherwise it is removed on exit.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
revision=$(git -C "$root" rev-parse "${1:-HEAD}")
source_url=${ENGINEER_SOURCE:-https://github.com/GSA/the_engineer.git}
name=${NAME:-engi-accept}
image=${IMAGE:-localhost/engi-fresh-host:24.04}
log_dir="$root/.local/acceptance"
mkdir -p "$log_dir"
log="$log_dir/$(date -u +%Y%m%dT%H%M%SZ)-${revision:0:12}.log"

# Host CAs (for example a corporate TLS proxy) are staged in ignored extra-ca/.
mkdir -p "$here/extra-ca"
find "$here/extra-ca" -mindepth 1 -delete
cp /usr/local/share/ca-certificates/*.crt "$here/extra-ca/" 2>/dev/null || true
podman build -t "$image" "$here"
podman rm -f "$name" >/dev/null 2>&1 || true
podman run -d --name "$name" --systemd=always --tmpfs /tmp "$image" >/dev/null
[[ ${KEEP:-0} == 1 ]] || trap 'podman rm -f "$name" >/dev/null' EXIT

for _ in $(seq 60); do
    podman exec "$name" systemctl is-active --quiet user@1000.service && break
    sleep 1
done

user_exec() {
    podman exec -u engineer -w /home/engineer \
        -e XDG_RUNTIME_DIR=/run/user/1000 \
        -e DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
        -e PATH=/home/engineer/.local/engi-pi/node_modules/.bin:/home/engineer/.local/bin:/usr/local/bin:/usr/bin:/bin \
        "$name" bash -lc "$1"
}

{
    echo "revision=$revision source=$source_url"
    user_exec "set -euxo pipefail
        mkdir -p ~/.local/bin && ln -sf /usr/bin/fdfind ~/.local/bin/fd
        npm install --no-fund --no-audit --prefix ~/.local/engi-pi @earendil-works/pi-coding-agent@1.4.0
        git clone --quiet '$source_url' ~/kenn-kopy
        git -C ~/kenn-kopy checkout --quiet --detach '$revision'
        cd ~/kenn-kopy
        bash dist/install.sh --check --corpus /opt/fake-corpus
        bash dist/install.sh --corpus /opt/fake-corpus --services user \
            --usai-base-url https://usai.invalid/api/v1 --usai-model claude-opus-5.5 \
            --usai-review-model gpt-5.6-terra --register-repo ~/kenn-kopy"
    set +e
    user_exec "cd ~/kenn-kopy && python3 scripts/local_env.py accept --repo ~/kenn-kopy"
    echo "accept_exit=$?"
} 2>&1 | tee "$log"
echo "Log: $log"
