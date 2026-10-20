#!/usr/bin/env bash
# Mirror Git repositories from a Helix (GitHub Enterprise) host to private
# repositories in a GitHub.com organization.
#
# Runs on a single host that can reach both the VPN-side source host and
# github.com. Never embeds credentials: authentication comes from the Git
# credential helpers configured for each host (see `gh auth setup-git`).
#
# Usage:
#   scripts/mirror-helix-to-github.sh [options] <repo> [<repo> ...]
#   scripts/mirror-helix-to-github.sh [options] --repos-file repos.txt
#
# Each <repo> is one of:
#   name                      source org = --source-org, destination = name
#   source-org/name           destination = name
#   source-org/name=dest      explicit destination name
#
# Options:
#   --source-host HOST    default: $HELIX_HOST or github.helix.gsa.gov
#   --source-org ORG      default org for bare repo names ($HELIX_ORG)
#   --dest-org ORG        GitHub.com org (default: $GITHUB_DEST_ORG or GSA)
#   --dest-prefix STR     prefix added to every destination repo name
#   --workdir DIR         where mirrors are cloned (default: mktemp -d)
#   --keep                keep the clones and logs after a successful run
#   --max-blob-mb N       fail a repo if any blob exceeds N MB (default 100)
#   --dry-run             clone + audit only: no repo creation, no push
#   --allow-nonempty      push even if the destination repo already has refs
#   -h | --help           this text
#
# Exit status is non-zero if any repository failed. Per-repo logs are written
# to <workdir>/logs/<dest>.log and a summary is printed at the end.

set -o errexit
set -o nounset
set -o pipefail

umask 0077

SOURCE_HOST="${HELIX_HOST:-github.helix.gsa.gov}"
SOURCE_ORG="${HELIX_ORG:-}"
DEST_ORG="${GITHUB_DEST_ORG:-GSA}"
DEST_PREFIX=""
WORKDIR=""
KEEP=0
MAX_BLOB_MB=100
DRY_RUN=0
ALLOW_NONEMPTY=0
REPO_ARGS=()

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 2
}

log() {
    printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

usage() {
    sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
}

read_repos_file() {
    local file="$1" line
    [ -r "$file" ] || die "cannot read repos file: $file"
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%%#*}"
        line="$(printf '%s' "$line" | tr -d '\r' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
        [ -n "$line" ] && REPO_ARGS+=("$line")
    done < "$file"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --source-host) SOURCE_HOST="${2:?--source-host needs a value}"; shift 2 ;;
        --source-org) SOURCE_ORG="${2:?--source-org needs a value}"; shift 2 ;;
        --dest-org) DEST_ORG="${2:?--dest-org needs a value}"; shift 2 ;;
        --dest-prefix) DEST_PREFIX="${2:?--dest-prefix needs a value}"; shift 2 ;;
        --workdir) WORKDIR="${2:?--workdir needs a value}"; shift 2 ;;
        --repos-file) read_repos_file "${2:?--repos-file needs a value}"; shift 2 ;;
        --max-blob-mb) MAX_BLOB_MB="${2:?--max-blob-mb needs a value}"; shift 2 ;;
        --keep) KEEP=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        --allow-nonempty) ALLOW_NONEMPTY=1; shift ;;
        -h|--help) usage; exit 0 ;;
        --) shift; while [ "$#" -gt 0 ]; do REPO_ARGS+=("$1"); shift; done ;;
        -*) die "unknown option: $1" ;;
        *) REPO_ARGS+=("$1"); shift ;;
    esac
done

[ "${#REPO_ARGS[@]}" -gt 0 ] || die "no repositories given (use arguments or --repos-file)"
command -v git >/dev/null 2>&1 || die "git is not installed"
if [ "$DRY_RUN" -eq 0 ]; then
    command -v gh >/dev/null 2>&1 || die "gh is not installed (needed to create private repos)"
fi
case "$MAX_BLOB_MB" in
    ''|*[!0-9]*) die "--max-blob-mb must be an integer" ;;
esac

# Fail instead of hanging on an interactive credential prompt.
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=/bin/false

CREATED_WORKDIR=0
if [ -z "$WORKDIR" ]; then
    WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/helix-mirror.XXXXXX")"
    CREATED_WORKDIR=1
else
    mkdir -p "$WORKDIR"
fi
LOGDIR="$WORKDIR/logs"
mkdir -p "$LOGDIR"

cleanup() {
    if [ "$KEEP" -eq 0 ] && [ "$CREATED_WORKDIR" -eq 1 ] && [ "${FAILED_COUNT:-1}" -eq 0 ]; then
        rm -rf "$WORKDIR"
    else
        log "workspace retained: $WORKDIR"
    fi
}
trap cleanup EXIT

log "source host : $SOURCE_HOST"
log "destination : github.com/$DEST_ORG (private)"
log "workspace   : $WORKDIR"
[ "$DRY_RUN" -eq 1 ] && log "mode        : DRY RUN (no creation, no push)"

SUMMARY=()
FAILED_COUNT=0

audit_blob_sizes() {
    # Prints offending "size path" lines; returns 1 when any blob is too big.
    local limit_bytes=$((MAX_BLOB_MB * 1024 * 1024)) offenders
    offenders="$(
        git rev-list --objects --all |
        git cat-file --batch-check='%(objecttype) %(objectsize) %(rest)' |
        awk -v limit="$limit_bytes" '$1 == "blob" && $2 > limit {
            size = $2; $1 = ""; $2 = "";
            sub(/^[[:space:]]+/, "");
            printf "%.1f MB  %s\n", size / 1048576, $0
        }' | sort -rn | head -20
    )"
    if [ -n "$offenders" ]; then
        printf '%s\n' "$offenders"
        return 1
    fi
    return 0
}

audit_submodules() {
    # Prints every distinct submodule URL found on any branch or tag.
    local ref
    for ref in $(git for-each-ref --format='%(refname)' refs/heads refs/tags); do
        git show "$ref:.gitmodules" 2>/dev/null || true
    done | sed -n 's/^[[:space:]]*url[[:space:]]*=[[:space:]]*//p' | sort -u
}

for spec in "${REPO_ARGS[@]}"; do
    source_path="${spec%%=*}"
    dest_name="${spec#*=}"
    [ "$dest_name" = "$spec" ] && dest_name=""

    case "$source_path" in
        */*/*) log "SKIP $spec: too many path segments"; SUMMARY+=("FAIL  $spec  (bad spec)"); FAILED_COUNT=$((FAILED_COUNT + 1)); continue ;;
        */*) src_org="${source_path%%/*}"; src_repo="${source_path##*/}" ;;
        *)
            if [ -z "$SOURCE_ORG" ]; then
                log "SKIP $spec: bare name needs --source-org"
                SUMMARY+=("FAIL  $spec  (no source org)")
                FAILED_COUNT=$((FAILED_COUNT + 1))
                continue
            fi
            src_org="$SOURCE_ORG"; src_repo="$source_path" ;;
    esac
    src_repo="${src_repo%.git}"
    [ -n "$dest_name" ] || dest_name="$src_repo"
    dest_name="${DEST_PREFIX}${dest_name}"
    dest_full="$DEST_ORG/$dest_name"

    src_url="https://$SOURCE_HOST/$src_org/$src_repo.git"
    dest_url="https://github.com/$dest_full.git"
    mirror_dir="$WORKDIR/$src_org--$src_repo.git"
    repo_log="$LOGDIR/$dest_name.log"

    log "=== $src_org/$src_repo -> $dest_full"

    repo_failed() {
        log "    FAILED: $1 (log: $repo_log)"
        SUMMARY+=("FAIL  $src_org/$src_repo -> $dest_full  ($1)")
        FAILED_COUNT=$((FAILED_COUNT + 1))
    }

    # 1. Mirror clone from the VPN-side host.
    if [ -d "$mirror_dir" ]; then
        log "    reusing existing clone $mirror_dir"
    elif ! git clone --mirror "$src_url" "$mirror_dir" >>"$repo_log" 2>&1; then
        repo_failed "clone failed"
        continue
    fi

    cd "$mirror_dir"

    # 2. Drop refs GitHub.com refuses on push (GHE pull-request refs).
    pull_refs="$(git for-each-ref --format='%(refname)' 'refs/pull/*' | wc -l | tr -d ' ')"
    if [ "$pull_refs" != "0" ]; then
        log "    pruning $pull_refs read-only refs/pull/* ref(s)"
        git for-each-ref --format='delete %(refname)' 'refs/pull/*' | git update-ref --stdin
        git gc --prune=now --quiet >>"$repo_log" 2>&1 || true
    fi

    branches="$(git for-each-ref --format='%(refname)' refs/heads | wc -l | tr -d ' ')"
    tags="$(git for-each-ref --format='%(refname)' refs/tags | wc -l | tr -d ' ')"
    size_kb="$(du -sk . | awk '{print $1}')"
    log "    refs: $branches branch(es), $tags tag(s); on-disk $((size_kb / 1024)) MB"

    # 3. Large-file gate.
    if ! big_blobs="$(audit_blob_sizes)"; then
        {
            echo "blobs over ${MAX_BLOB_MB}MB:"
            printf '%s\n' "$big_blobs"
        } | tee -a "$repo_log"
        repo_failed "blob over ${MAX_BLOB_MB}MB"
        cd "$WORKDIR"
        continue
    fi
    log "    large-file check: no blob over ${MAX_BLOB_MB}MB"

    # 4. Submodule URL audit (reported, never auto-rewritten).
    submodule_urls="$(audit_submodules)"
    if [ -n "$submodule_urls" ]; then
        log "    submodule URLs found (review before relying on this mirror):"
        printf '%s\n' "$submodule_urls" | sed 's/^/        /' | tee -a "$repo_log"
    else
        log "    submodule audit: no .gitmodules on any branch or tag"
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        SUMMARY+=("DRY   $src_org/$src_repo -> $dest_full  ($branches branches, $tags tags)")
        cd "$WORKDIR"
        continue
    fi

    # 5. Create the private destination if it does not exist.
    if gh repo view "$dest_full" >>"$repo_log" 2>&1; then
        log "    destination exists"
        existing_refs="$(git ls-remote --heads --tags "$dest_url" 2>>"$repo_log" | wc -l | tr -d ' ')"
        if [ "$existing_refs" != "0" ] && [ "$ALLOW_NONEMPTY" -eq 0 ]; then
            repo_failed "destination already has $existing_refs ref(s); use --allow-nonempty"
            cd "$WORKDIR"
            continue
        fi
    else
        log "    creating private repo $dest_full"
        if ! gh repo create "$dest_full" --private \
                --description "Mirror of $SOURCE_HOST/$src_org/$src_repo" >>"$repo_log" 2>&1; then
            repo_failed "gh repo create failed (token may lack org repo-creation rights)"
            cd "$WORKDIR"
            continue
        fi
    fi

    # 6. Push every ref.
    if ! git push --mirror "$dest_url" >>"$repo_log" 2>&1; then
        repo_failed "push failed"
        cd "$WORKDIR"
        continue
    fi

    pushed="$(git ls-remote --heads --tags "$dest_url" 2>>"$repo_log" | wc -l | tr -d ' ')"
    log "    pushed; destination now reports $pushed ref(s)"
    SUMMARY+=("OK    $src_org/$src_repo -> $dest_full  ($branches branches, $tags tags)")
    cd "$WORKDIR"
done

echo
echo "Summary"
printf '%s\n' "${SUMMARY[@]}"
echo
if [ "$FAILED_COUNT" -ne 0 ]; then
    log "$FAILED_COUNT repository/repositories failed; see $LOGDIR"
    exit 1
fi
log "all repositories processed successfully"
