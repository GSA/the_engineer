#!/usr/bin/env bash
# Clone the mirrored private GSA repositories into working checkouts.
#
# Reads the same repos file as mirror-helix-to-github.sh, but clones from the
# github.com destination rather than Helix, so `origin` is the remote you will
# open pull requests against. Idempotent: an existing clone is fetched and
# reported, never overwritten or reset.
#
# Usage:
#   scripts/clone-gsa-repos.sh --repos-file mirror-repos.txt --dest-org GSA \
#       --into ~/falcon
#
# Options:
#   --into DIR          parent directory for the clones (default: ~/falcon)
#   --dest-org ORG      GitHub.com org holding the mirrors (default GSA)
#   --dest-host HOST    default github.com
#   --dest-prefix STR   prefix used when the mirrors were created
#   --source-org ORG    only needed to parse bare names in the repos file
#   --repos-file FILE   newline-separated repo specs
#   --bare              clone bare instead of a working tree
#   -h | --help         this text
#
# Exit status is non-zero if any repository failed.

set -o errexit
set -o nounset
set -o pipefail

INTO="$HOME/falcon"
DEST_HOST="${GITHUB_DEST_HOST:-github.com}"
DEST_ORG="${GITHUB_DEST_ORG:-GSA}"
DEST_PREFIX=""
SOURCE_ORG="${HELIX_ORG:-}"
BARE=0
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
        --into) INTO="${2:?}"; shift 2 ;;
        --dest-org) DEST_ORG="${2:?}"; shift 2 ;;
        --dest-host) DEST_HOST="${2:?}"; shift 2 ;;
        --dest-prefix) DEST_PREFIX="${2:?}"; shift 2 ;;
        --source-org) SOURCE_ORG="${2:?}"; shift 2 ;;
        --repos-file) read_repos_file "${2:?}"; shift 2 ;;
        --bare) BARE=1; shift ;;
        -h|--help) sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        -*) die "unknown option: $1" ;;
        *) REPO_ARGS+=("$1"); shift ;;
    esac
done

[ "${#REPO_ARGS[@]}" -gt 0 ] || die "no repositories given (use arguments or --repos-file)"
command -v git >/dev/null 2>&1 || die "git is not installed"
command -v gh >/dev/null 2>&1 || die "gh is not installed"

export GIT_TERMINAL_PROMPT=0

# These are private repositories: confirm the destination login before looping.
if ! login="$(GH_HOST="$DEST_HOST" gh api user --jq .login 2>&1)"; then
    printf 'gh said:\n\n%s\n\n' "$login" >&2
    die "not authenticated to $DEST_HOST. Run 'gh auth login --hostname $DEST_HOST'."
fi
log "authenticated to $DEST_HOST as $login"

mkdir -p "$INTO"
log "cloning into $INTO"

SUMMARY=()
FAILED=0

for spec in "${REPO_ARGS[@]}"; do
    source_path="${spec%%=*}"
    dest_name="${spec#*=}"
    if [ "$dest_name" = "$spec" ]; then
        dest_name=""
    fi
    case "$source_path" in
        */*) src_repo="${source_path##*/}" ;;
        *) src_repo="$source_path" ;;
    esac
    src_repo="${src_repo%.git}"
    if [ -z "$dest_name" ]; then
        dest_name="$src_repo"
    fi
    dest_name="${DEST_PREFIX}${dest_name}"
    dest_full="$DEST_ORG/$dest_name"
    url="https://$DEST_HOST/$dest_full.git"
    if [ "$BARE" -eq 1 ]; then
        target="$INTO/$dest_name.git"
    else
        target="$INTO/$dest_name"
    fi

    log "=== $dest_full"

    # Refuse to touch a directory that is not a clone of this repository.
    # Compare rewritten URLs so insteadOf/pushInsteadOf rules do not cause a
    # false mismatch; --get-url resolves without any network access.
    expected_url="$(git ls-remote --get-url "$url" 2>/dev/null || printf '%s' "$url")"
    if [ -e "$target" ]; then
        if [ -d "$target/.git" ] || [ -d "$target/refs" ]; then
            existing="$(git -C "$target" ls-remote --get-url origin 2>/dev/null || true)"
            if [ "$existing" != "$expected_url" ] && [ "$existing" != "$url" ]; then
                log "    SKIP: $target exists with origin '$existing', not $url"
                SUMMARY+=("SKIP  $dest_full  (different origin)")
                FAILED=$((FAILED + 1))
                continue
            fi
            log "    exists; fetching updates (no reset, no checkout change)"
            if git -C "$target" fetch --all --tags --prune --quiet; then
                branch="$(git -C "$target" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
                log "    fetched; on branch $branch"
                SUMMARY+=("FETCH $dest_full -> $target  (branch $branch)")
            else
                log "    fetch failed"
                SUMMARY+=("FAIL  $dest_full  (fetch failed)")
                FAILED=$((FAILED + 1))
            fi
            continue
        fi
        log "    SKIP: $target exists and is not a git repository"
        SUMMARY+=("SKIP  $dest_full  (path occupied)")
        FAILED=$((FAILED + 1))
        continue
    fi

    clone_args=(--origin origin)
    [ "$BARE" -eq 1 ] && clone_args+=(--bare)
    if ! git clone "${clone_args[@]}" "$url" "$target" 2>&1 | sed 's/^/        /'; then
        rm -rf "$target"
        log "    clone failed"
        SUMMARY+=("FAIL  $dest_full  (clone failed)")
        FAILED=$((FAILED + 1))
        continue
    fi

    branch="$(git -C "$target" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
    branches="$(git -C "$target" for-each-ref --format='%(refname)' 'refs/remotes/origin' |
        grep -cv '/HEAD$' || true)"
    log "    cloned at branch $branch; $branches remote branch(es)"
    SUMMARY+=("OK    $dest_full -> $target  (branch $branch)")
done

echo
echo "Summary"
printf '%s\n' "${SUMMARY[@]}"
echo
if [ "$FAILED" -ne 0 ]; then
    log "$FAILED repository/repositories need attention"
    exit 1
fi
log "all repositories ready under $INTO"
