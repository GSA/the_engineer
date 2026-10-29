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
#   --protocol https|ssh  source clone protocol (default https)
#   --prompt              allow Git to prompt for source credentials
#   --skip-preflight      skip the source-host reachability check
#   --dest-org ORG        GitHub.com org (default: $GITHUB_DEST_ORG or GSA)
#   --dest-host HOST      destination host (default github.com)
#   --dest-prefix STR     prefix added to every destination repo name
#   --workdir DIR         where mirrors are cloned (default: mktemp -d)
#   --keep                keep the clones and logs after a successful run
#   --max-blob-mb N       fail a repo if any blob exceeds N MB (default 100)
#   --batch-size N        push refs in batches of N instead of one push
#                         (default: one push, then automatic batched retry)
#   --dry-run             clone + audit only: no repo creation, no push
#   --allow-nonempty      push even if the destination repo already has refs
#   -h | --help           this text
#
# Every destination, new or existing, must be confirmed private with no
# GitHub Pages site and no rename/transfer redirect before each push, and has
# GitHub Actions disabled so mirrored workflows cannot publish or deploy.
# Privacy is checked again after pushing.
#
# Exit status is non-zero if any repository failed. Per-repo logs are written
# to <workdir>/logs/<dest>.log and a summary is printed at the end.

set -o errexit
set -o nounset
set -o pipefail

umask 0077

# Never die silently: report where an unexpected non-zero status came from.
trap 'status=$?; printf "ERROR: unexpected failure at %s line %s (status %s)\n" "${BASH_SOURCE[0]}" "$LINENO" "$status" >&2' ERR

SOURCE_HOST="${HELIX_HOST:-github.helix.gsa.gov}"
SOURCE_ORG="${HELIX_ORG:-}"
PROTOCOL="https"
ALLOW_PROMPT=0
SKIP_PREFLIGHT=0
DEST_ORG="${GITHUB_DEST_ORG:-GSA}"
DEST_HOST="${GITHUB_DEST_HOST:-github.com}"
DEST_PREFIX=""
WORKDIR=""
KEEP=0
MAX_BLOB_MB=100
BATCH_SIZE=0
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
        if [ -n "$line" ]; then
            REPO_ARGS+=("$line")
        fi
    done < "$file"
    # A trailing comment or blank line must not leave a non-zero status here,
    # or errexit would abort the whole script without printing anything.
    return 0
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --source-host) SOURCE_HOST="${2:?--source-host needs a value}"; shift 2 ;;
        --source-org) SOURCE_ORG="${2:?--source-org needs a value}"; shift 2 ;;
        --protocol) PROTOCOL="${2:?--protocol needs a value}"; shift 2 ;;
        --prompt) ALLOW_PROMPT=1; shift ;;
        --skip-preflight) SKIP_PREFLIGHT=1; shift ;;
        --dest-org) DEST_ORG="${2:?--dest-org needs a value}"; shift 2 ;;
        --dest-host) DEST_HOST="${2:?--dest-host needs a value}"; shift 2 ;;
        --dest-prefix) DEST_PREFIX="${2:?--dest-prefix needs a value}"; shift 2 ;;
        --workdir) WORKDIR="${2:?--workdir needs a value}"; shift 2 ;;
        --repos-file) read_repos_file "${2:?--repos-file needs a value}"; shift 2 ;;
        --max-blob-mb) MAX_BLOB_MB="${2:?--max-blob-mb needs a value}"; shift 2 ;;
        --batch-size) BATCH_SIZE="${2:?--batch-size needs a value}"; shift 2 ;;
        --keep) KEEP=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        --allow-nonempty) ALLOW_NONEMPTY=1; shift ;;
        -h|--help) usage; exit 0 ;;
        --) shift; while [ "$#" -gt 0 ]; do REPO_ARGS+=("$1"); shift; done ;;
        -*) die "unknown option: $1" ;;
        *) REPO_ARGS+=("$1"); shift ;;
    esac
done

if [ "${#REPO_ARGS[@]}" -eq 0 ]; then
    die "no repositories to process: every line of the repos file was blank or commented out, and no repository was given as an argument"
fi
log_count="${#REPO_ARGS[@]}"
command -v git >/dev/null 2>&1 || die "git is not installed"
if [ "$DRY_RUN" -eq 0 ]; then
    command -v gh >/dev/null 2>&1 || die "gh is not installed (needed to create private repos)"
fi
case "$MAX_BLOB_MB" in
    ''|*[!0-9]*) die "--max-blob-mb must be an integer" ;;
esac
case "$BATCH_SIZE" in
    ''|*[!0-9]*) die "--batch-size must be an integer" ;;
esac

case "$PROTOCOL" in
    https|ssh) ;;
    *) die "--protocol must be https or ssh" ;;
esac

# By default fail instead of hanging on an interactive credential prompt.
# --prompt is for the first run on a host where the credential helper has no
# stored credential yet and you want to type it once.
if [ "$ALLOW_PROMPT" -eq 0 ]; then
    export GIT_TERMINAL_PROMPT=0
    export GIT_ASKPASS=/bin/false
else
    export GIT_TERMINAL_PROMPT=1
    unset GIT_ASKPASS
fi

CREATED_WORKDIR=0
if [ -z "$WORKDIR" ]; then
    WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/helix-mirror.XXXXXX")"
    CREATED_WORKDIR=1
else
    mkdir -p "$WORKDIR"
    WORKDIR="$(cd "$WORKDIR" && pwd)"
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
log "destination : $DEST_HOST/$DEST_ORG (private)"
log "workspace   : $WORKDIR"
log "repositories: $log_count -> ${REPO_ARGS[*]}"
log "protocol    : $PROTOCOL"
if [ "$DRY_RUN" -eq 1 ]; then
    log "mode        : DRY RUN (no creation, no push)"
fi

SUMMARY=()
FAILED_COUNT=0

source_url() {
    # $1 = org, $2 = repo
    if [ "$PROTOCOL" = "ssh" ]; then
        printf 'git@%s:%s/%s.git' "$SOURCE_HOST" "$1" "$2"
    else
        printf 'https://%s/%s/%s.git' "$SOURCE_HOST" "$1" "$2"
    fi
}

preflight() {
    # Distinguish "no network route" from "not authenticated" from "wrong name"
    # before looping over repositories and reporting four identical failures.
    local probe_org probe_repo probe_url output
    probe_org="${1%%/*}"
    probe_repo="${1##*/}"
    probe_repo="${probe_repo%.git}"
    probe_url="$(source_url "$probe_org" "$probe_repo")"

    log "preflight   : resolving $SOURCE_HOST"
    if ! getent hosts "$SOURCE_HOST" >/dev/null 2>&1 && \
       ! host "$SOURCE_HOST" >/dev/null 2>&1 && \
       ! nslookup "$SOURCE_HOST" >/dev/null 2>&1; then
        die "cannot resolve $SOURCE_HOST. The VPN is probably not connected on this host, or the host name is wrong. Nothing was cloned."
    fi
    log "preflight   : DNS resolves"

    log "preflight   : contacting $probe_url"
    if output="$(git ls-remote --heads "$probe_url" 2>&1)"; then
        log "preflight   : source reachable and authenticated"
        return 0
    fi

    printf 'preflight failed. git said:\n\n%s\n\n' "$output" >&2
    case "$output" in
        *"could not read Username"*|*"terminal prompts disabled"*|*"Authentication failed"*|*"403"*)
            die "the source host needs credentials this host does not have. Run 'gh auth login --hostname $SOURCE_HOST --git-protocol https' (or use --protocol ssh with a registered key), then re-run. Add --prompt to type a token once." ;;
        *"not found"*|*"Repository not found"*|*"404"*)
            die "authenticated or anonymous access worked but '$probe_org/$probe_repo' was not found. Check the org/repo spelling in the repos file." ;;
        *"Could not resolve host"*)
            die "DNS resolved locally but git could not resolve $SOURCE_HOST. Check the VPN DNS settings or any proxy configuration." ;;
        *"Connection timed out"*|*"Connection refused"*|*"Failed to connect"*|*"unable to access"*)
            die "network path to $SOURCE_HOST is blocked. Confirm the VPN is up and that this host is allowed to reach it." ;;
        *"certificate"*|*"SSL"*|*"TLS"*)
            die "TLS verification failed for $SOURCE_HOST. The internal CA certificate is probably missing. Install the CA bundle rather than disabling verification." ;;
        *"Permission denied (publickey)"*)
            die "SSH key was rejected by $SOURCE_HOST. Register a key on that host or use --protocol https." ;;
        *)
            die "could not reach the source host; see the git message above." ;;
    esac
}

if [ "$SKIP_PREFLIGHT" -eq 0 ]; then
    preflight_spec="${REPO_ARGS[0]%%=*}"
    case "$preflight_spec" in
        */*) : ;;
        *) preflight_spec="$SOURCE_ORG/$preflight_spec" ;;
    esac
    preflight "$preflight_spec"

    # Check the destination too, before spending time on large clones.
    if [ "$DRY_RUN" -eq 0 ]; then
        log "preflight   : checking $DEST_HOST login"
        if ! dest_login="$(GH_HOST="$DEST_HOST" gh api user --jq .login 2>&1)"; then
            printf 'gh said:\n\n%s\n\n' "$dest_login" >&2
            die "not authenticated to $DEST_HOST. Run 'gh auth login --hostname $DEST_HOST'. Nothing was cloned."
        fi
        log "preflight   : $DEST_HOST authenticated as $dest_login"
        if ! GH_HOST="$DEST_HOST" gh api "orgs/$DEST_ORG" --jq .login >/dev/null 2>&1; then
            die "account $dest_login cannot see organization $DEST_ORG on $DEST_HOST. Confirm membership and that the token has the 'read:org' scope."
        fi
        log "preflight   : $DEST_ORG visible to $dest_login"
    fi
fi

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

remote_ref_count() {
    # Count real refs on the destination. Annotated tags also emit a peeled
    # "refs/tags/x^{}" line, which must not inflate the comparison.
    # Fails (rather than reporting 0) when the destination cannot be read.
    local refs
    refs="$(git ls-remote --heads --tags "$1" 2>>"$repo_log")" || return 1
    printf '%s\n' "$refs" | grep -v '\^{}$' | grep -c . || true
}

destination_private() {
    # Succeeds only when the exact destination (no rename/transfer redirect)
    # is private and has no GitHub Pages site, which can be public even for a
    # private repository. Any lookup failure counts as not private.
    local info
    info="$(GH_HOST="$DEST_HOST" gh api "repos/$dest_full" \
        --jq '[.full_name, .visibility, (.private | tostring), (.has_pages | tostring)] | join(" ")' \
        2>>"$repo_log")" || { log "    visibility check: destination lookup failed"; return 1; }
    local name visibility private pages
    read -r name visibility private pages <<<"$info"
    if [ "${name,,}" != "${dest_full,,}" ]; then
        log "    visibility check: $dest_full resolves to $name (renamed or transferred)"
        return 1
    fi
    if [ "$visibility" != "private" ] || [ "$private" != "true" ]; then
        log "    visibility check: $dest_full is $visibility, not private"
        return 1
    fi
    if [ "$pages" != "false" ]; then
        log "    visibility check: $dest_full has GitHub Pages enabled"
        return 1
    fi
    return 0
}

disable_destination_actions() {
    # Mirrored workflows would otherwise run on push and could publish or
    # deploy repository content.
    GH_HOST="$DEST_HOST" gh api -X PUT "repos/$dest_full/actions/permissions" \
        -F enabled=false >>"$repo_log" 2>&1
}

push_in_batches() {
    # Push refs a batch at a time. GitHub rejects a single pack over ~2GB and
    # hundreds of refs in one push can also time out; batches keep each
    # request small and make a partial failure resumable.
    local url="$1" size="$2" refs=() total sent=0 batch
    mapfile -t refs < <(git for-each-ref --format='%(refname)' refs/heads refs/tags)
    total="${#refs[@]}"
    log "    pushing $total ref(s) in batches of $size"
    while [ "$sent" -lt "$total" ]; do
        batch=("${refs[@]:sent:size}")
        if ! destination_private; then
            log "    destination is no longer private; stopping before batch at ref $((sent + 1))"
            return 1
        fi
        if ! git push "$url" "${batch[@]/#/+}" >>"$repo_log" 2>&1; then
            log "    git push output:"
            sed 's/^/        /' "$repo_log" | tail -15
            log "    failed in batch starting at ref $((sent + 1)) of $total"
            return 1
        fi
        sent=$((sent + ${#batch[@]}))
        log "    pushed $sent/$total ref(s)"
    done
    return 0
}

for spec in "${REPO_ARGS[@]}"; do
    source_path="${spec%%=*}"
    dest_name="${spec#*=}"
    if [ "$dest_name" = "$spec" ]; then
        dest_name=""
    fi

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
    if [ -z "$dest_name" ]; then
        dest_name="$src_repo"
    fi
    dest_name="${DEST_PREFIX}${dest_name}"
    dest_full="$DEST_ORG/$dest_name"

    src_url="$(source_url "$src_org" "$src_repo")"
    dest_url="https://$DEST_HOST/$dest_full.git"
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
        log "    reusing existing clone $mirror_dir; refreshing from source"
        if ! { git --git-dir="$mirror_dir" remote set-url origin "$src_url" &&
               git --git-dir="$mirror_dir" remote update --prune origin; } >>"$repo_log" 2>&1; then
            log "    git fetch output:"
            sed 's/^/        /' "$repo_log" | tail -15
            repo_failed "refreshing retained clone from source failed"
            continue
        fi
        # remote update does not move a mirror's symbolic HEAD, so follow the
        # source's current default branch explicitly.
        if ! src_head_out="$(git ls-remote --symref "$src_url" HEAD 2>>"$repo_log")"; then
            repo_failed "reading source default branch failed"
            continue
        fi
        src_head="$(printf '%s\n' "$src_head_out" | awk '/^ref:/ {print $2; exit}')"
        if [ -n "$src_head" ]; then
            git --git-dir="$mirror_dir" symbolic-ref HEAD "$src_head" >>"$repo_log" 2>&1 || true
        fi
    else
        log "    cloning $src_url"
        if ! git clone --mirror "$src_url" "$mirror_dir" >>"$repo_log" 2>&1; then
            # Show the reason inline; a log path alone is not a diagnosis.
            log "    git clone output:"
            sed 's/^/        /' "$repo_log" | tail -15
            rm -rf "$mirror_dir"
            repo_failed "clone failed"
            continue
        fi
    fi

    cd "$mirror_dir"

    # 2. Drop refs GitHub.com refuses on push (GHE pull-request refs).
    # Note the pattern: git's for-each-ref glob does not cross '/', so
    # 'refs/pull/*' matches nothing. Use the prefix form instead.
    pull_refs="$(git for-each-ref --format='%(refname)' 'refs/pull' | wc -l | tr -d ' ')"
    if [ "$pull_refs" != "0" ]; then
        log "    pruning $pull_refs read-only refs/pull ref(s)"
        git for-each-ref --format='delete %(refname)' 'refs/pull' | git update-ref --stdin
        git gc --prune=now --quiet >>"$repo_log" 2>&1 || true
    fi

    branches="$(git for-each-ref --format='%(refname)' refs/heads | wc -l | tr -d ' ')"
    tags="$(git for-each-ref --format='%(refname)' refs/tags | wc -l | tr -d ' ')"
    size_kb="$(du -sk . | awk '{print $1}')"
    # The source's default branch. A mirror push does not carry this over, so
    # the destination would otherwise show whatever the org default is.
    default_branch="$(git symbolic-ref --short HEAD 2>/dev/null || true)"
    if [ -n "$default_branch" ]; then
        log "    refs: $branches branch(es), $tags tag(s); on-disk $((size_kb / 1024)) MB; default $default_branch"
    else
        log "    refs: $branches branch(es), $tags tag(s); on-disk $((size_kb / 1024)) MB; default branch undetermined"
    fi

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
    # GH_HOST pins gh to the destination host now that two hosts are logged in.
    if GH_HOST="$DEST_HOST" gh repo view "$dest_full" >>"$repo_log" 2>&1; then
        log "    destination exists"
        if ! existing_refs="$(remote_ref_count "$dest_url")"; then
            repo_failed "could not list destination refs; refusing to push"
            cd "$WORKDIR"
            continue
        fi
        if [ "$existing_refs" != "0" ] && [ "$ALLOW_NONEMPTY" -eq 0 ]; then
            repo_failed "destination already has $existing_refs ref(s); use --allow-nonempty"
            cd "$WORKDIR"
            continue
        fi
    else
        log "    creating private repo $dest_full"
        if ! GH_HOST="$DEST_HOST" gh repo create "$dest_full" --private \
                --description "Mirror of $SOURCE_HOST/$src_org/$src_repo" >>"$repo_log" 2>&1; then
            log "    gh repo create output:"
            sed 's/^/        /' "$repo_log" | tail -10
            repo_failed "gh repo create failed (token may lack org repo-creation rights)"
            cd "$WORKDIR"
            continue
        fi
    fi

    # Never push unless the destination is confirmed private, Pages-free and
    # has Actions disabled. Visibility is rechecked immediately before pushing.
    if ! destination_private; then
        repo_failed "destination is not confirmed private; refusing to push"
        cd "$WORKDIR"
        continue
    fi
    if ! disable_destination_actions; then
        repo_failed "could not disable GitHub Actions on destination; refusing to push"
        cd "$WORKDIR"
        continue
    fi

    # 6. Push every ref. One push is fastest; batching is the fallback for
    # repos with very many refs or a pack too large for a single request.
    push_ok=0
    if [ "$BATCH_SIZE" -gt 0 ]; then
        if push_in_batches "$dest_url" "$BATCH_SIZE"; then
            push_ok=1
        fi
    elif destination_private && git push --mirror "$dest_url" >>"$repo_log" 2>&1; then
        push_ok=1
    else
        log "    single mirror push failed:"
        sed 's/^/        /' "$repo_log" | tail -15
        log "    retrying in batches of 50"
        if push_in_batches "$dest_url" 50; then
            push_ok=1
        fi
    fi
    # Any push attempt may have transferred refs, so confirm privacy again.
    if ! destination_private; then
        repo_failed "DESTINATION IS NOT CONFIRMED PRIVATE AFTER PUSH; make it private or delete it now"
        cd "$WORKDIR"
        continue
    fi
    if [ "$push_ok" -ne 1 ]; then
        repo_failed "push failed"
        cd "$WORKDIR"
        continue
    fi

    # 7. Verify the destination holds exactly the refs we sent, then set the
    # default branch, which --mirror does not transfer.
    expected_refs=$((branches + tags))
    pushed="$(remote_ref_count "$dest_url")" || pushed="unreadable"
    if [ "$pushed" != "$expected_refs" ]; then
        repo_failed "ref count mismatch: sent $expected_refs, destination reports $pushed"
        cd "$WORKDIR"
        continue
    fi
    log "    verified $pushed ref(s) on destination"

    if [ -n "$default_branch" ]; then
        if GH_HOST="$DEST_HOST" gh repo edit "$dest_full" \
                --default-branch "$default_branch" >>"$repo_log" 2>&1; then
            log "    default branch set to $default_branch"
        else
            log "    WARNING: could not set default branch to $default_branch; set it in the web UI"
        fi
    fi

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
