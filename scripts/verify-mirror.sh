#!/usr/bin/env bash
# Verify that mirrored repositories on the destination hold exactly the same
# branch and tag tips as the source. Read-only: nothing is created or pushed.
#
# Usage mirrors mirror-helix-to-github.sh:
#   scripts/verify-mirror.sh --source-org FSS19-Cloud --dest-org GSA \
#       --repos-file mirror-repos.txt
#
# Options: --source-host, --source-org, --dest-host, --dest-org, --dest-prefix,
#          --protocol https|ssh, --repos-file, plus bare repo specs.
#
# Exit status is non-zero if any repository differs.

set -o errexit
set -o nounset
set -o pipefail

umask 0077

SOURCE_HOST="${HELIX_HOST:-github.helix.gsa.gov}"
SOURCE_ORG="${HELIX_ORG:-}"
DEST_HOST="${GITHUB_DEST_HOST:-github.com}"
DEST_ORG="${GITHUB_DEST_ORG:-GSA}"
DEST_PREFIX=""
PROTOCOL="https"
REPO_ARGS=()

die() { printf 'ERROR: %s\n' "$*" >&2; exit 2; }
log() { printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"; }

read_repos_file() {
    local file="$1" line
    [ -r "$file" ] || die "cannot read repos file: $file"
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%%#*}"
        line="$(printf '%s' "$line" | tr -d '\r' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
        if [ -n "$line" ]; then
            REPO_ARGS+=("$line")
        fi
    done < "$file"
    return 0
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --source-host) SOURCE_HOST="${2:?}"; shift 2 ;;
        --source-org) SOURCE_ORG="${2:?}"; shift 2 ;;
        --dest-host) DEST_HOST="${2:?}"; shift 2 ;;
        --dest-org) DEST_ORG="${2:?}"; shift 2 ;;
        --dest-prefix) DEST_PREFIX="${2:?}"; shift 2 ;;
        --protocol) PROTOCOL="${2:?}"; shift 2 ;;
        --repos-file) read_repos_file "${2:?}"; shift 2 ;;
        -h|--help) sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        -*) die "unknown option: $1" ;;
        *) REPO_ARGS+=("$1"); shift ;;
    esac
done

[ "${#REPO_ARGS[@]}" -gt 0 ] || die "no repositories given"
export GIT_TERMINAL_PROMPT=0

source_url() {
    if [ "$PROTOCOL" = "ssh" ]; then
        printf 'git@%s:%s/%s.git' "$SOURCE_HOST" "$1" "$2"
    else
        printf 'https://%s/%s/%s.git' "$SOURCE_HOST" "$1" "$2"
    fi
}

# Real refs only: annotated tags also emit a peeled "^{}" line.
tips() { git ls-remote --heads --tags "$1" | grep -v '\^{}$' | sort; }

FAILED=0
for spec in "${REPO_ARGS[@]}"; do
    source_path="${spec%%=*}"
    dest_name="${spec#*=}"
    if [ "$dest_name" = "$spec" ]; then
        dest_name=""
    fi
    case "$source_path" in
        */*) src_org="${source_path%%/*}"; src_repo="${source_path##*/}" ;;
        *) src_org="$SOURCE_ORG"; src_repo="$source_path" ;;
    esac
    src_repo="${src_repo%.git}"
    [ -n "$src_org" ] || die "bare name '$spec' needs --source-org"
    if [ -z "$dest_name" ]; then
        dest_name="$src_repo"
    fi
    dest_name="${DEST_PREFIX}${dest_name}"

    src_url="$(source_url "$src_org" "$src_repo")"
    dest_url="https://$DEST_HOST/$DEST_ORG/$dest_name.git"

    if ! src_tips="$(tips "$src_url" 2>&1)"; then
        log "FAIL  $src_org/$src_repo: cannot read source ($src_tips)"
        FAILED=$((FAILED + 1)); continue
    fi
    if ! dest_tips="$(tips "$dest_url" 2>&1)"; then
        log "FAIL  $dest_name: cannot read destination ($dest_tips)"
        FAILED=$((FAILED + 1)); continue
    fi

    if [ "$src_tips" = "$dest_tips" ]; then
        log "OK    $src_org/$src_repo -> $DEST_ORG/$dest_name  ($(printf '%s\n' "$src_tips" | wc -l | tr -d ' ') refs, identical tips)"
    else
        log "DIFF  $src_org/$src_repo -> $DEST_ORG/$dest_name"
        # diff exits 1 on differences, which is the expected result here.
        { diff <(printf '%s\n' "$src_tips") <(printf '%s\n' "$dest_tips") || [ $? -eq 1 ]; } |
            sed 's/^/        /' | head -40
        FAILED=$((FAILED + 1))
    fi
done

echo
if [ "$FAILED" -ne 0 ]; then
    log "$FAILED repository/repositories differ"
    exit 1
fi
log "all repositories verified identical"
