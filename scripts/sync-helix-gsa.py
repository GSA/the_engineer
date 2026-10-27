#!/usr/bin/env python3
"""Keep working clones that carry both the Helix and the GSA GitHub remote.

One checkout per repository under --into, with two remotes:

    origin  https://github.com/<DEST_ORG>/<repo>.git     (GSA mirror)
    helix   https://<SOURCE_HOST>/<SOURCE_ORG>/<repo>.git (upstream)

That single clone is enough to pull continuously, to patch, to fork a branch
and to open a pull request on either side.

Commands
    status   fetch both remotes and report per-branch divergence (read-only)
    pull     fast-forward GSA branches from Helix; never force, never merge
    push     push a local branch to Helix and optionally open a PR there

Safety rules this tool will not break:
  * The working tree and the checked-out branch are never touched. Syncing
    moves remote refs with refspecs, so a dirty tree and a feature branch
    survive every run.
  * Nothing is ever force-pushed and no merge is ever created. A branch that
    moved on both sides is reported and skipped, and the run exits non-zero.
  * No branch is ever deleted on either remote.

Usage
    scripts/sync-helix-gsa.py status --repos-file scripts/mirror-repos.txt \\
        --source-org FSS19-Cloud --into ~/falcon
    scripts/sync-helix-gsa.py pull --repos-file scripts/mirror-repos.txt \\
        --source-org FSS19-Cloud --into ~/falcon
    scripts/sync-helix-gsa.py push --repo supply-chain-user-interface \\
        --branch feat/my-change --pr --into ~/falcon

Exit status: 0 clean, 1 something needs a human, 2 usage or environment error.
"""

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys


# Branch comparison outcomes.
IN_SYNC = "in-sync"
NEW_ON_HELIX = "new-on-helix"
GSA_BEHIND = "gsa-behind"
GSA_AHEAD = "gsa-ahead"
DIVERGED = "diverged"
ONLY_ON_GSA = "only-on-gsa"

# Outcomes that `pull` can resolve by itself with a plain fast-forward push.
FORWARDABLE = (NEW_ON_HELIX, GSA_BEHIND)
# Outcomes that always need a person to decide.
NEEDS_HUMAN = (DIVERGED,)

PUSH_BATCH = 50
JSON_MODE = False

# A blocked VPN route makes git hang rather than fail, which would wedge an
# unattended run forever. The reachability probe is always bounded.
PREFLIGHT_TIMEOUT = 30

# Helix tags are fetched outside refs/tags so that adding the helix remote
# cannot rewrite or shadow tags an existing working clone already has.
HELIX_TAG_NS = "refs/helix-tags"


def log(message):
    print(message, file=sys.stderr if JSON_MODE else sys.stdout, flush=True)


def die(message, code=2):
    print(f"ERROR: {message}", file=sys.stderr, flush=True)
    raise SystemExit(code)


def git(args, cwd=None, check=True, quiet_env=True, timeout=None):
    """Run git and return (returncode, combined output)."""
    env = dict(os.environ)
    if quiet_env:
        # Fail instead of blocking a cron run on a credential prompt.
        env.setdefault("GIT_TERMINAL_PROMPT", "0")
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        message = f"git {' '.join(args)} timed out after {timeout}s"
        if check:
            raise GitError(message)
        return 124, message
    output = completed.stdout.strip()
    if check and completed.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {output}")
    return completed.returncode, output


class GitError(RuntimeError):
    pass


def parse_spec(spec, source_org, dest_prefix):
    """Turn one repos-file line into (source_org, source_repo, dest_name).

    Accepted forms match the existing mirror scripts: "name",
    "source-org/name" and "source-org/name=dest".
    """
    source_path, _, explicit_dest = spec.partition("=")
    source_path = source_path.strip()
    explicit_dest = explicit_dest.strip()
    if not source_path:
        raise ValueError(f"empty repository spec: {spec!r}")
    parts = source_path.split("/")
    if len(parts) > 2:
        raise ValueError(f"too many path segments: {spec!r}")
    if len(parts) == 2:
        src_org, src_repo = parts
    else:
        if not source_org:
            raise ValueError(f"bare name {source_path!r} needs --source-org")
        src_org, src_repo = source_org, parts[0]
    if src_repo.endswith(".git"):
        src_repo = src_repo[: -len(".git")]
    dest = explicit_dest or src_repo
    return src_org, src_repo, f"{dest_prefix}{dest}"


def read_repos_file(path):
    specs = []
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"cannot read repos file {path}: {error}") from error
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            specs.append(line)
    return specs


def classify(ahead, behind, on_helix, on_gsa):
    """Classify one branch. ahead/behind are GSA-relative commit counts."""
    if on_helix and not on_gsa:
        return NEW_ON_HELIX
    if on_gsa and not on_helix:
        return ONLY_ON_GSA
    if ahead == 0 and behind == 0:
        return IN_SYNC
    if ahead == 0:
        return GSA_BEHIND
    if behind == 0:
        return GSA_AHEAD
    return DIVERGED


def chunked(items, size):
    for start in range(0, len(items), size):
        yield items[start : start + size]


class Repo:
    """One working clone carrying both remotes."""

    def __init__(self, path, src_org, src_repo, dest_name, config):
        self.path = Path(path)
        self.src_org = src_org
        self.src_repo = src_repo
        self.dest_name = dest_name
        self.config = config
        # Plain attributes, not properties: tests point them at local bare
        # repositories so the real git behavior can be exercised offline.
        if config.protocol == "ssh":
            self.helix_url = f"git@{config.source_host}:{src_org}/{src_repo}.git"
        else:
            self.helix_url = (
                f"https://{config.source_host}/{src_org}/{src_repo}.git"
            )
        self.gsa_url = f"https://{config.dest_host}/{config.dest_org}/{dest_name}.git"

    # -- setup ---------------------------------------------------------

    def is_clone(self):
        return (self.path / ".git").is_dir() or (self.path / "HEAD").is_file()

    def remote_url(self, name):
        code, out = git(["remote", "get-url", name], cwd=self.path, check=False)
        return out if code == 0 else None

    def normalize_url(self, url):
        """Resolve insteadOf rewrites so comparison does not false-mismatch."""
        code, out = git(["ls-remote", "--get-url", url], cwd=self.path, check=False)
        return out if code == 0 and out else url

    def ensure(self, dry_run=False):
        """Clone if missing, then make sure both remotes point where we expect.

        Returns a list of human-readable problems; empty means ready.
        """
        problems = []
        if not self.path.exists():
            if dry_run:
                log(f"    would clone {self.gsa_url}")
                return ["clone missing (dry run)"]
            log(f"    cloning {self.gsa_url}")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            code, out = git(
                ["clone", "--origin", "origin", self.gsa_url, str(self.path)], check=False
            )
            if code != 0:
                return [f"clone failed: {out.splitlines()[-1] if out else code}"]
        elif not self.is_clone():
            return [f"{self.path} exists and is not a git repository"]

        existing_origin = self.remote_url("origin")
        if existing_origin is None:
            problems.append("no 'origin' remote; refusing to guess")
        elif self.normalize_url(existing_origin) not in (
            self.normalize_url(self.gsa_url),
            self.gsa_url,
        ):
            problems.append(
                f"origin is {existing_origin}, expected {self.gsa_url}; "
                "refusing to repoint an unrelated clone"
            )

        existing_helix = self.remote_url("helix")
        if existing_helix is None:
            if dry_run:
                log(f"    would add remote helix -> {self.helix_url}")
            else:
                git(["remote", "add", "helix", self.helix_url], cwd=self.path)
                log(f"    added remote helix -> {self.helix_url}")
        elif self.normalize_url(existing_helix) not in (
            self.normalize_url(self.helix_url),
            self.helix_url,
        ):
            problems.append(
                f"remote 'helix' is {existing_helix}, expected {self.helix_url}; "
                "fix it by hand so no history is sent to the wrong host"
            )

        if not dry_run and not problems:
            self.configure_helix_refspecs()
        return problems

    def configure_helix_refspecs(self):
        """Keep Helix refs in their own namespaces.

        Branches land in refs/remotes/helix/*, which is conventional. Tags are
        deliberately kept out of refs/tags so that fetching Helix cannot
        silently move a tag the clone already had from GSA.
        """
        # Replace both values every time: a plain `git config` write fails once
        # the key is multi-valued, which breaks every run after the first.
        git(
            ["config", "--unset-all", "remote.helix.fetch"],
            cwd=self.path,
            check=False,
        )
        git(
            ["config", "--add", "remote.helix.fetch", "+refs/heads/*:refs/remotes/helix/*"],
            cwd=self.path,
        )
        git(
            [
                "config",
                "--add",
                "remote.helix.fetch",
                f"+refs/tags/*:{HELIX_TAG_NS}/*",
            ],
            cwd=self.path,
        )
        git(["config", "remote.helix.tagOpt", "--no-tags"], cwd=self.path)

    # -- reading state -------------------------------------------------

    def fetch(self, remote):
        code, out = git(
            ["fetch", "--prune", "--quiet", remote], cwd=self.path, check=False
        )
        if code != 0:
            tail = out.splitlines()[-1] if out else f"exit {code}"
            return f"fetch {remote} failed: {tail}"
        return None

    def refs(self, prefix):
        """Map short ref name -> object id for everything under prefix."""
        _, out = git(
            ["for-each-ref", "--format=%(refname) %(objectname)", prefix], cwd=self.path
        )
        found = {}
        for line in out.splitlines():
            refname, _, oid = line.partition(" ")
            short = refname[len(prefix) :].lstrip("/")
            if not short or short == "HEAD":
                continue
            found[short] = oid
        return found

    def counts(self, left, right):
        """Commits unique to left, then unique to right."""
        _, out = git(
            ["rev-list", "--left-right", "--count", f"{left}...{right}"], cwd=self.path
        )
        try:
            ahead, behind = out.split()
            return int(ahead), int(behind)
        except ValueError:
            raise GitError(f"unexpected rev-list output for {left}...{right}: {out!r}")

    def default_branch(self, remote):
        code, out = git(
            ["symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD"],
            cwd=self.path,
            check=False,
        )
        if code != 0:
            return None
        return out.split("/", 1)[1] if "/" in out else out

    def compare(self):
        """Compare Helix and GSA branches. Returns a list of row dicts."""
        helix = self.refs("refs/remotes/helix")
        gsa = self.refs("refs/remotes/origin")
        rows = []
        for branch in sorted(set(helix) | set(gsa)):
            on_helix, on_gsa = branch in helix, branch in gsa
            ahead = behind = 0
            if on_helix and on_gsa:
                if helix[branch] != gsa[branch]:
                    ahead, behind = self.counts(
                        f"refs/remotes/origin/{branch}", f"refs/remotes/helix/{branch}"
                    )
            rows.append(
                {
                    "branch": branch,
                    "state": classify(ahead, behind, on_helix, on_gsa),
                    "gsa_ahead": ahead,
                    "gsa_behind": behind,
                }
            )
        return rows

    def has_helix_refs(self):
        """Whether any Helix branch ref is present locally.

        Without this, a clone that has never fetched Helix reports every GSA
        branch as "only on GSA", which looks like a real finding instead of a
        missing fetch.
        """
        return bool(self.refs("refs/remotes/helix"))

    def compare_tags(self):
        helix = self.refs(HELIX_TAG_NS)
        gsa = self.refs("refs/tags")
        rows = []
        for tag in sorted(set(helix) | set(gsa)):
            if tag in helix and tag not in gsa:
                state = NEW_ON_HELIX
            elif tag in gsa and tag not in helix:
                state = ONLY_ON_GSA
            elif helix[tag] == gsa[tag]:
                state = IN_SYNC
            else:
                state = DIVERGED
            rows.append({"tag": tag, "state": state})
        return rows

    # -- writing -------------------------------------------------------

    def forward_to_gsa(self, rows, dry_run=False):
        """Push fast-forwardable Helix branch tips to GSA. Never force."""
        branches = [r["branch"] for r in rows if r["state"] in FORWARDABLE]
        if not branches:
            return [], None
        specs = [f"refs/remotes/helix/{b}:refs/heads/{b}" for b in branches]
        if dry_run:
            log(f"    would push {len(specs)} branch(es) to origin")
            return branches, None
        pushed = []
        # Pair names with specs: a branch name can contain '/', so the name
        # cannot be recovered from the refspec by splitting on it.
        for batch in chunked(list(zip(branches, specs)), PUSH_BATCH):
            names = [name for name, _ in batch]
            refspecs = [spec for _, spec in batch]
            code, out = git(["push", "origin", *refspecs], cwd=self.path, check=False)
            if code != 0:
                tail = "\n".join(out.splitlines()[-6:])
                return pushed, f"push to origin failed after {len(pushed)}: {tail}"
            pushed.extend(names)
            log(f"    pushed {len(pushed)}/{len(specs)} branch(es)")
        return pushed, None

    def forward_tags_to_gsa(self, tag_rows, dry_run=False):
        new = [r["tag"] for r in tag_rows if r["state"] == NEW_ON_HELIX]
        if not new:
            return [], None
        specs = [f"{HELIX_TAG_NS}/{t}:refs/tags/{t}" for t in new]
        if dry_run:
            log(f"    would push {len(specs)} new tag(s) to origin")
            return new, None
        for batch in chunked(specs, PUSH_BATCH):
            code, out = git(["push", "origin", *batch], cwd=self.path, check=False)
            if code != 0:
                tail = "\n".join(out.splitlines()[-6:])
                return [], f"tag push failed: {tail}"
        log(f"    pushed {len(new)} new tag(s)")
        return new, None

    def push_branch(self, branch, remote, dry_run=False):
        """Push one local branch to a remote without force."""
        code, _ = git(
            ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
            cwd=self.path,
            check=False,
        )
        if code != 0:
            return f"no local branch {branch!r} in {self.path}"
        if dry_run:
            log(f"    would push {branch} -> {remote}")
            return None
        code, out = git(
            ["push", remote, f"refs/heads/{branch}:refs/heads/{branch}"],
            cwd=self.path,
            check=False,
        )
        if code != 0:
            tail = "\n".join(out.splitlines()[-6:])
            return f"push of {branch} to {remote} failed: {tail}"
        log(f"    pushed {branch} to {remote}")
        return None


class Config:
    def __init__(self, args):
        self.source_host = args.source_host
        self.source_org = args.source_org
        self.dest_host = args.dest_host
        self.dest_org = args.dest_org
        self.dest_prefix = args.dest_prefix
        self.protocol = args.protocol
        self.into = Path(args.into).expanduser()


def build_repos(args, config):
    specs = list(args.repo_specs)
    if args.repos_file:
        specs.extend(read_repos_file(args.repos_file))
    if not specs:
        die("no repositories given: pass specs or --repos-file")
    repos = []
    for spec in specs:
        src_org, src_repo, dest_name = parse_spec(
            spec, config.source_org, config.dest_prefix
        )
        if args.only and dest_name not in args.only and src_repo not in args.only:
            continue
        repos.append(
            Repo(config.into / dest_name, src_org, src_repo, dest_name, config)
        )
    if not repos:
        die("no repositories left after --repo filtering")
    return repos


def lock(into):
    """One writer per --into tree, so overlapping cron runs cannot interleave."""
    into.mkdir(parents=True, exist_ok=True)
    handle = open(into / ".sync-helix-gsa.lock", "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        die(f"another sync is already running in {into}")
    return handle


def describe(row):
    state = row["state"]
    if state == IN_SYNC:
        return "identical"
    if state == NEW_ON_HELIX:
        return "only on Helix (will be created on GSA)"
    if state == ONLY_ON_GSA:
        return "only on GSA (local/feature branch, left alone)"
    if state == GSA_BEHIND:
        return f"GSA behind by {row['gsa_behind']} (fast-forwardable)"
    if state == GSA_AHEAD:
        return f"GSA ahead by {row['gsa_ahead']} (not upstreamed to Helix)"
    return (
        f"DIVERGED: GSA +{row['gsa_ahead']} / Helix +{row['gsa_behind']} "
        "(needs a human)"
    )


MAX_LISTED = 25


def report(repo, rows, tag_rows, verbose):
    buckets = {}
    for row in rows:
        buckets.setdefault(row["state"], []).append(row)
    summary = ", ".join(f"{len(buckets[state])} {state}" for state in sorted(buckets))
    log(f"    branches: {summary or 'none'}")
    if not repo.has_helix_refs():
        log(
            "    NOTE: no Helix refs present locally, so the states above are "
            "not a real comparison. Fetch Helix before trusting them."
        )
        return
    # Always name the states a person must act on; list the rest only on -v.
    always = (DIVERGED, GSA_AHEAD)
    on_request = (GSA_BEHIND, NEW_ON_HELIX, ONLY_ON_GSA)
    for state in always + (on_request if verbose else ()):
        entries = buckets.get(state, [])
        for row in entries[:MAX_LISTED]:
            log(f"      {row['branch']}: {describe(row)}")
        if len(entries) > MAX_LISTED:
            log(f"      ... and {len(entries) - MAX_LISTED} more {state}")
    odd_tags = [r for r in tag_rows if r["state"] in (NEW_ON_HELIX, DIVERGED)]
    if odd_tags:
        log(f"    tags needing attention: {len(odd_tags)}")
        for row in odd_tags[:MAX_LISTED]:
            log(f"      {row['tag']}: {row['state']}")


def open_pull_request(repo, branch, base, title, body, dry_run):
    """Open a PR on the Helix host with gh, pinned to that host."""
    if not base:
        base, error = remote_default_branch(repo, "helix")
        if error:
            return f"cannot determine Helix default branch; pass --base explicitly ({error})"
    command = [
        "gh",
        "pr",
        "create",
        "--repo",
        f"{repo.src_org}/{repo.src_repo}",
        "--base",
        base,
        "--head",
        branch,
        "--title",
        title or branch,
        "--body",
        body or "",
    ]
    if dry_run:
        log(f"    would open PR on {repo.config.source_host}: {branch} -> {base}")
        return None
    env = dict(os.environ, GH_HOST=repo.config.source_host)
    completed = subprocess.run(
        command,
        cwd=str(repo.path),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    out = completed.stdout.strip()
    if completed.returncode != 0:
        return f"gh pr create failed: {out}"
    log(f"    {out}")
    return None


def remote_default_branch(repo, remote):
    code, out = git(
        ["ls-remote", "--symref", remote, "HEAD"],
        cwd=repo.path,
        check=False,
        timeout=PREFLIGHT_TIMEOUT,
    )
    if code != 0:
        return None, out or f"git ls-remote exited {code}"
    for line in out.splitlines():
        target, separator, ref = line.partition("\t")
        prefix = "ref: refs/heads/"
        if separator and ref == "HEAD" and target.startswith(prefix):
            branch = target[len(prefix):]
            if branch:
                return branch, None
    return None, "remote HEAD does not advertise a branch"


def preflight_helix(repo, timeout=PREFLIGHT_TIMEOUT):
    """One bounded reachability probe before looping, with actionable advice."""
    code, out = git(
        ["ls-remote", "--heads", repo.helix_url], check=False, timeout=timeout
    )
    if code == 0:
        return None
    if code == 124:
        return (
            f"no response from {repo.config.source_host} within {timeout}s. The VPN "
            "route is blocked or needs a proxy; run this on a host that can reach "
            "both remotes, or pass --skip-preflight once you know it works."
        )
    lowered = out.lower()
    if "could not resolve host" in lowered:
        return (
            f"cannot resolve {repo.config.source_host}: the VPN is probably not "
            "connected on this host"
        )
    if any(
        hint in lowered
        for hint in ("could not read username", "terminal prompts disabled", "403", "authentication failed")
    ):
        return (
            f"{repo.config.source_host} needs credentials this host does not have. "
            f"Run: gh auth login --hostname {repo.config.source_host} --git-protocol https"
        )
    if "not found" in lowered or "404" in lowered:
        return f"{repo.src_org}/{repo.src_repo} not found on {repo.config.source_host}"
    if any(hint in lowered for hint in ("timed out", "refused", "failed to connect", "unable to access")):
        return f"network path to {repo.config.source_host} is blocked; confirm the VPN is up"
    if any(hint in lowered for hint in ("certificate", "ssl", "tls")):
        return (
            f"TLS verification failed for {repo.config.source_host}; install the "
            "internal CA bundle rather than disabling verification"
        )
    return f"cannot reach {repo.config.source_host}: {out.splitlines()[-1] if out else code}"


def run_sync(args, config, repos, do_push):
    results = []
    failures = 0
    attention = 0

    if not args.no_fetch and not args.skip_preflight:
        problem = preflight_helix(repos[0])
        if problem:
            die(problem)
        log(f"preflight   : {config.source_host} reachable")

    for repo in repos:
        log(f"=== {repo.src_org}/{repo.src_repo} -> {repo.path}")
        record = {"repo": repo.dest_name, "path": str(repo.path), "problems": []}
        try:
            problems = repo.ensure(dry_run=args.dry_run)
            if problems:
                for problem in problems:
                    log(f"    SKIP: {problem}")
                record["problems"] = problems
                failures += 1
                results.append(record)
                continue

            if not args.no_fetch:
                for remote in ("helix", "origin"):
                    error = repo.fetch(remote)
                    if error:
                        log(f"    {error}")
                        record["problems"].append(error)
                if record["problems"]:
                    failures += 1
                    results.append(record)
                    continue

            rows = repo.compare()
            tag_rows = repo.compare_tags()
            record["branches"] = rows
            record["tags"] = tag_rows
            report(repo, rows, tag_rows, args.verbose)

            if not repo.has_helix_refs():
                # Refuse to call a run clean when the upstream side was never
                # read: that is exactly how a silent no-op looks like success.
                message = (
                    "no Helix refs locally; nothing was compared "
                    "(drop --no-fetch, or check Helix access)"
                )
                log(f"    {message}")
                record["problems"].append(message)
                failures += 1
                results.append(record)
                continue

            helix_default = repo.default_branch("helix")
            gsa_default = repo.default_branch("origin")
            record["helix_default"] = helix_default
            record["gsa_default"] = gsa_default
            if helix_default and gsa_default and helix_default != gsa_default:
                log(
                    f"    note: default branch differs (Helix {helix_default}, "
                    f"GSA {gsa_default}); not changed"
                )

            if do_push:
                pushed, error = repo.forward_to_gsa(rows, dry_run=args.dry_run)
                record["pushed"] = pushed
                if error:
                    log(f"    {error}")
                    record["problems"].append(error)
                    failures += 1
                    results.append(record)
                    continue
                if not pushed:
                    log("    nothing to fast-forward")
                tags_pushed, tag_error = repo.forward_tags_to_gsa(
                    tag_rows, dry_run=args.dry_run
                )
                record["tags_pushed"] = tags_pushed
                if tag_error:
                    log(f"    {tag_error}")
                    record["problems"].append(tag_error)
                    failures += 1
                    results.append(record)
                    continue

            needs = [r for r in rows if r["state"] in NEEDS_HUMAN]
            needs += [r for r in tag_rows if r["state"] in NEEDS_HUMAN]
            if needs:
                attention += len(needs)
                record["needs_attention"] = len(needs)
        except GitError as error:
            log(f"    FAILED: {error}")
            record["problems"].append(str(error))
            failures += 1
        results.append(record)

    log("")
    log("Summary")
    for record in results:
        if record["problems"]:
            log(f"  FAIL  {record['repo']}: {record['problems'][0]}")
        elif record.get("needs_attention"):
            log(f"  DIVER {record['repo']}: {record['needs_attention']} ref(s) need a human")
        elif do_push and record.get("pushed"):
            log(f"  SYNCD {record['repo']}: {len(record['pushed'])} branch(es) advanced")
        else:
            log(f"  OK    {record['repo']}")
    if args.json:
        print(json.dumps(results, indent=2))
    if failures:
        log(f"{failures} repository/repositories failed")
        return 1
    if attention:
        log(f"{attention} ref(s) diverged and were left untouched")
        return 1
    return 0


def run_push(args, config, repos):
    if len(repos) != 1:
        die("push works on one repository: use --repo NAME")
    repo = repos[0]
    record = {"repo": repo.dest_name, "branch": args.branch, "problems": []}

    def finish(code):
        if args.json:
            print(json.dumps([record], indent=2))
        return code

    log(f"=== {repo.path}")
    problems = repo.ensure(dry_run=args.dry_run)
    if problems:
        for problem in problems:
            log(f"    SKIP: {problem}")
        record["problems"].extend(problems)
        return finish(1)
    if not args.no_fetch:
        error = repo.fetch("helix")
        if error:
            log(f"    {error}")
            record["problems"].append(error)
            return finish(1)
    error = repo.push_branch(args.branch, "helix", dry_run=args.dry_run)
    if error:
        log(f"    {error}")
        record["problems"].append(error)
        return finish(1)
    record["pushed" if not args.dry_run else "would_push"] = [args.branch]
    if args.pr:
        error = open_pull_request(
            repo, args.branch, args.base, args.title, args.body, args.dry_run
        )
        if error:
            log(f"    {error}")
            record["problems"].append(error)
            return finish(1)
        record["pull_request"] = "would-create" if args.dry_run else "created"
    return finish(0)


def add_common_arguments(parser):
    parser.add_argument("repo_specs", nargs="*", metavar="REPO")
    parser.add_argument("--repos-file")
    parser.add_argument(
        "--repo",
        dest="only",
        action="append",
        default=[],
        help="limit to this repository (repeatable)",
    )
    parser.add_argument("--into", default=os.environ.get("FALCON_CLONES", "~/falcon"))
    parser.add_argument(
        "--source-host", default=os.environ.get("HELIX_HOST", "github.helix.gsa.gov")
    )
    parser.add_argument("--source-org", default=os.environ.get("HELIX_ORG", ""))
    parser.add_argument(
        "--dest-host", default=os.environ.get("GITHUB_DEST_HOST", "github.com")
    )
    parser.add_argument("--dest-org", default=os.environ.get("GITHUB_DEST_ORG", "GSA"))
    parser.add_argument("--dest-prefix", default="")
    parser.add_argument("--protocol", choices=("https", "ssh"), default="https")
    parser.add_argument("--no-fetch", action="store_true", help="use cached refs only")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", help="print machine-readable results")
    parser.add_argument("-v", "--verbose", action="store_true")


def main(argv=None):
    global JSON_MODE
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="report divergence; changes nothing")
    add_common_arguments(status)

    pull = sub.add_parser("pull", help="fast-forward GSA branches from Helix")
    add_common_arguments(pull)

    push = sub.add_parser("push", help="push a local branch to Helix, optionally with a PR")
    add_common_arguments(push)
    push.add_argument("--branch", required=True, help="local branch to send upstream")
    push.add_argument("--pr", action="store_true", help="open a pull request on Helix")
    push.add_argument("--base", default="", help="PR base branch (default: Helix HEAD)")
    push.add_argument("--title", default="")
    push.add_argument("--body", default="")

    args = parser.parse_args(argv)
    JSON_MODE = args.json
    config = Config(args)
    try:
        repos = build_repos(args, config)
    except ValueError as error:
        die(str(error))

    handle = lock(config.into)
    try:
        log(f"source      : {config.source_host}")
        log(f"destination : {config.dest_host}/{config.dest_org}")
        log(f"clones      : {config.into}")
        if args.dry_run:
            log("mode        : DRY RUN")
        if args.command == "status":
            return run_sync(args, config, repos, do_push=False)
        if args.command == "pull":
            return run_sync(args, config, repos, do_push=True)
        return run_push(args, config, repos)
    finally:
        handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
