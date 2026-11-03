#!/usr/bin/env python3
"""Read-only engineering decision-trail retrospective.

Joins outputs that already exist for one task into a private, readable report:
approved ticket and revision, what the Librarian returned (by hash, from the
`librarian-audit` JSONL), task/workspace/session, commits, review findings and
dispositions, the pull request and the human decision. Nothing is launched,
claimed, commented or closed, and returned document text is never copied.

  decision-trail.py --kata PROJECT#ID --repo DIR --commits BASE..HEAD \\
      --pr OWNER/REPO#N --audit-log LOG --session-file FILE --workspace ID \\
      --intake DIR --name NAME

A link that cannot be shown is reported as MISSING; it is never inferred.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib
import urllib.parse
import urllib.request
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL = REPO_ROOT / ".local"
AUDIT_SCHEMA = "librarian-mcp-audit-v1"
CALL_ROWS = 200
QUOTE_CHARS = 600
GAPS = {
    "ticket-approval": "no verifiable owner approval of the ticket (intake record or --approved-by)",
    "audit-log": "no Librarian audit log supplied; the evidence actually returned is unknown",
    "audit-hash-mismatch": "an audit record's returned text does not match its recorded SHA-256",
    "audit-invalid-lines": "audit log lines could not be read",
    "session": "no Pi session file; session window and coder model are unknown",
    "workspace": "no workspace id or Forge lookup failed; task-to-session link is unverified",
    "workspace-link": "Forge's workspace does not match this task and session",
    "check-outcomes": "no recorded check outcomes on the pull request",
    "human-decision": "no human merge or review decision recorded",
    "pr": "no pull request",
    "pr-head-reviewed": "no finished review covers the pull request head commit",
    "qualifier-model": "Librarian qualifier model is not captured by any supplied source",
}


class TrailError(ValueError):
    pass


def instant(value):
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def short(sha):
    return str(sha)[:12]


def ref_end(job):
    return str(job.get("git_ref", "")).split("..")[-1]


def read_session(path):
    """First/last timestamps, session id and model roles from a Pi session file."""
    session = {"id": None, "start": None, "end": None, "models": []}
    for line in Path(path).read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        when = instant(event.get("timestamp"))
        if when:
            session["start"] = min(session["start"] or when, when)
            session["end"] = max(session["end"] or when, when)
        if event.get("type") == "session":
            session["id"] = event.get("id")
        if event.get("type") == "model_change":
            model = f"{event.get('provider')}/{event.get('modelId')}"
            if model not in session["models"]:
                session["models"].append(model)
    return session


def read_audit(paths, window):
    """Body-free view of audit records: counts, hash checks and per-call rows."""
    evidence = {"records": 0, "invalid_lines": 0, "hash_mismatches": 0, "outcomes": {}, "labels": {},
                "tools": {}, "calls": [], "in_session_window": None if window is None else 0,
                "qualifications": []}
    for path in paths:
        for line in Path(path).read_text().splitlines():
            try:
                record = json.loads(line)
                assert record["schema"] == AUDIT_SCHEMA
                text = record["returned_text"]
            except (ValueError, KeyError, TypeError, AssertionError):
                evidence["invalid_lines"] += 1
                continue
            evidence["records"] += 1
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if digest != record.get("returned_sha256"):
                evidence["hash_mismatches"] += 1
            for bucket, key in (("outcomes", "outcome"), ("labels", "agent_label"), ("tools", "tool")):
                value = str(record.get(key))
                evidence[bucket][value] = evidence[bucket].get(value, 0) + 1
            started = instant(record.get("started_at"))
            inside = window is not None and started is not None and window[0] <= started <= window[1]
            if inside:
                evidence["in_session_window"] += 1
            qualification = ""
            try:
                packet = json.loads(text)
                if isinstance(packet, dict) and packet.get("audience"):
                    qualification = f"audience={packet['audience']}"
                    if qualification not in evidence["qualifications"]:
                        evidence["qualifications"].append(qualification)
            except ValueError:
                pass
            references = record.get("references") or {}
            evidence["calls"].append({
                "at": record.get("started_at"), "label": record.get("agent_label"), "tool": record.get("tool"),
                "outcome": record.get("outcome"), "sha256": record.get("returned_sha256"),
                "chars": record.get("returned_chars"), "locators": references.get("locators", []),
                "source_hashes": references.get("source_hashes", []), "qualification": qualification,
                "in_window": inside if window is not None else None})
    evidence["calls"].sort(key=lambda call: str(call["at"]))
    return evidence


def read_intake(directory, kata_ref):
    """Approval of the intake task that was recorded as this Kata task, else None."""
    directory = Path(directory)
    recorded = json.loads((directory / "recorded.json").read_text())
    source = json.loads((directory / "source.json").read_text())
    ids = [task for task, ref in recorded.get("tasks", {}).items() if ref == kata_ref]
    plan = tomllib.loads((directory / "intake.toml").read_text())
    for task in plan.get("task", []):
        if task.get("id") in ids and task.get("approved_by") and task.get("approved_at"):
            return {"approved_by": task["approved_by"], "approved_at": task["approved_at"], "source": "intake record",
                    "jira_key": source["ticket"]["key"], "jira_sha256": source["provenance"]["sha256"]}
    return None


def build(spec, sources):
    gaps = []

    def gap(name):
        if name not in gaps:
            gaps.append(name)

    report = {"name": spec.get("name"), "gaps": gaps, "generated_at": datetime.now(timezone.utc).isoformat()}
    kata = sources.kata(spec["kata"])
    issue = kata["issue"]
    approval = read_intake(spec["intake"], spec["kata"]) if spec.get("intake") else None
    if approval is None and spec.get("approval"):
        approval = {**spec["approval"], "source": "operator-asserted, not verified"}
    if approval is None:
        gap("ticket-approval")
    body = issue.get("body", "")
    report["ticket"] = {"ref": spec["kata"], "title": issue.get("title"), "status": issue.get("status"),
                        "revision": issue.get("revision"), "updated_at": issue.get("updated_at"),
                        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                        "approval": approval, "jira_key": (approval or {}).get("jira_key")}
    report["rationale"] = [
        {"source": f"Kata comment by {c.get('author')}", "at": c.get("created_at"), "text": c.get("body", "")}
        for c in kata.get("comments", [])]

    session = read_session(spec["session_file"]) if spec.get("session_file") else None
    window = (session["start"], session["end"]) if session and session["start"] else None
    if session is None:
        gap("session")
    report["session"] = session
    report["workspace"] = {"id": spec.get("workspace_id")}
    if not spec.get("workspace_id"):
        gap("workspace")
    else:
        try:
            workspace = sources.workspace(spec["workspace_id"])
        except (OSError, ValueError, KeyError) as error:
            report["workspace"]["error"] = str(error)
            gap("workspace")
        else:
            report["workspace"].update(workspace)
            same_task = workspace.get("qualified_id") == spec["kata"]
            same_session = session is not None and session["id"] in workspace.get("session_ids", [])
            if not (same_task and same_session):
                gap("workspace-link")

    paths = [Path(p) for p in spec.get("audit_logs", [])]
    if not paths:
        gap("audit-log")
    evidence = read_audit(paths, window)
    if evidence["hash_mismatches"]:
        gap("audit-hash-mismatch")
    if evidence["invalid_lines"]:
        gap("audit-invalid-lines")
    report["evidence"] = evidence
    if not spec.get("qualifier_model"):
        gap("qualifier-model")
    report["models"] = {"coder": session["models"] if session else [], "qualifier": spec.get("qualifier_model")}

    commits = sources.commits(spec["repo"], spec["commits"])
    jobs = [job for job in sources.review_jobs(spec["repo"]) if job.get("status") == "done"]
    reviews, report["commits"] = [], []
    for commit in commits:
        covering = [job for job in jobs if ref_end(job) == commit["sha"]]
        if not covering:
            gap(f"review:{short(commit['sha'])}")
        report["commits"].append({**commit, "reviews": [job["id"] for job in covering]})
        reviews.extend(job for job in covering if job not in reviews)
    report["reviews"] = []
    for job in reviews:
        findings = sources.review_findings(job["id"])
        responses = sources.review_responses(job["id"])
        if job.get("verdict") != "P" and not job.get("closed") and not responses:
            gap(f"disposition:{job['id']}")
        report["reviews"].append({"job": job["id"], "commit": ref_end(job), "agent": job.get("agent"),
                                  "model": job.get("model"), "reasoning": job.get("reasoning"),
                                  "verdict": job.get("verdict"), "closed": job.get("closed"),
                                  "finished_at": job.get("finished_at"), "findings": findings,
                                  "responses": responses})
        for response in responses:
            report["rationale"].append({"source": f"review {job['id']} response by {response.get('commenter')}",
                                        "at": response.get("created_at"), "text": response.get("response", "")})
    report["models"]["reviewers"] = sorted({f"{j.get('agent')}/{j.get('model')} ({j.get('reasoning')})" for j in reviews})

    pr = sources.pull_request(spec["pr"]) if spec.get("pr") else None
    report["pr"] = pr
    report["publication"] = {"decision": None}
    if pr is None:
        gap("pr")
        gap("human-decision")
        gap("check-outcomes")
    else:
        if pr.get("body"):
            report["rationale"].append({"source": "pull request description", "at": None, "text": pr["body"]})
        if not any(ref_end(job) == pr.get("headRefOid") for job in jobs):
            gap("pr-head-reviewed")
        if not pr.get("statusCheckRollup"):
            gap("check-outcomes")
        merger = pr.get("mergedBy") or {}
        if pr.get("mergedAt") and merger.get("login") and not merger.get("is_bot"):
            report["publication"]["decision"] = (
                f"merged by human {merger['login']} at {pr['mergedAt']} as {(pr.get('mergeCommit') or {}).get('oid')}")
        else:
            gap("human-decision")
    return report


def clip(text):
    text = " ".join(str(text).split())
    return text if len(text) <= QUOTE_CHARS else text[:QUOTE_CHARS] + " ..."


def render(report):
    out = []
    ticket, evidence = report["ticket"], report["evidence"]
    out += [f"# Decision trail: {report.get('name') or ticket['ref']}", "",
            f"Generated {report['generated_at']}. Private: built from existing outputs; no document text is copied.", ""]
    out += ["## 1. Approved ticket and revision",
            f"- Task {ticket['ref']} ({ticket['status']}), revision {ticket['revision']} at report time, "
            f"updated {ticket['updated_at']}; body SHA-256 {ticket['body_sha256']}"]
    approval = ticket["approval"]
    if approval:
        out.append(f"- Approved by {approval['approved_by']} at {approval['approved_at']} ({approval['source']})")
        if ticket.get("jira_key"):
            out.append(f"- Jira {ticket['jira_key']}, source SHA-256 {approval.get('jira_sha256')}")
    else:
        out.append("- MISSING ticket-approval: " + GAPS["ticket-approval"])
    out += ["", "## 2. Evidence actually returned by the Librarian"]
    if not evidence["records"] and not evidence["invalid_lines"]:
        out.append("- MISSING audit-log: " + GAPS["audit-log"])
    else:
        window = evidence["in_session_window"]
        out += [f"- {evidence['records']} call(s); outcomes {evidence['outcomes']}; tools {evidence['tools']}; "
                f"agent labels {evidence['labels']}",
                f"- Hash check: {evidence['hash_mismatches']} mismatch(es); {evidence['invalid_lines']} unreadable line(s)",
                "- Qualifications seen: " + (", ".join(evidence["qualifications"]) or "none recorded"),
                "- Calls inside the session window by time overlap: "
                + ("unknown (no session)" if window is None else str(window)),
                "- An agent label is a name for a binding, not proof of task or session identity; "
                "only time overlap with the session below links these calls to the work.", "",
                "| started | label | tool | outcome | returned sha256 | chars | in window | locators / source hashes |",
                "|---|---|---|---|---|---|---|---|"]
        for call in evidence["calls"][:CALL_ROWS]:
            refs = ", ".join(call["locators"] + call["source_hashes"])
            out.append(f"| {call['at']} | {call['label']} | {call['tool']} | {call['outcome']} | "
                       f"{str(call['sha256'])[:16]} | {call['chars']} | {call['in_window']} | {refs} |")
        if len(evidence["calls"]) > CALL_ROWS:
            out.append(f"\n{len(evidence['calls']) - CALL_ROWS} further call(s) omitted from this table.")
        for name in ("audit-hash-mismatch", "audit-invalid-lines"):
            if name in report["gaps"]:
                out.append(f"- MISSING {name}: {GAPS[name]}")
    session, workspace = report["session"], report["workspace"]
    out += ["", "## 3. Task, workspace and session"]
    if session:
        out.append(f"- Pi session {session['id']} from {session['start']} to {session['end']}")
    else:
        out.append("- MISSING session: " + GAPS["session"])
    out.append(f"- Workspace {workspace.get('id') or 'none'}: "
               + (f"Forge says task {workspace.get('qualified_id')}, sessions {workspace.get('session_ids')}"
                  if workspace.get("qualified_id") else "not looked up"))
    for name in ("workspace", "workspace-link"):
        if name in report["gaps"]:
            out.append(f"- MISSING {name}: {GAPS[name]}")
    models = report["models"]
    out += ["", "## 4. Model roles (as recorded; hidden reasoning is not captured)",
            "- Coder: " + (", ".join(models["coder"]) or "unknown"),
            "- Reviewer: " + ("; ".join(models["reviewers"]) or "no finished reviews"),
            "- Librarian qualifier: " + (models["qualifier"] or "MISSING qualifier-model: " + GAPS["qualifier-model"])]
    out += ["", "## 5. Commits and review"]
    for commit in report["commits"]:
        reviewed = ", ".join(f"job {job}" for job in commit["reviews"]) or f"MISSING review:{short(commit['sha'])}"
        out.append(f"- {short(commit['sha'])} {commit.get('date')} {commit.get('subject')} -> {reviewed}")
    for review in report["reviews"]:
        out.append(f"- Review {review['job']} on {short(review['commit'])}: verdict {review['verdict']}, "
                   f"{len(review['findings'])} finding(s), closed={review['closed']}")
        for finding in review["findings"]:
            out.append(f"  - {finding.get('severity')} {finding.get('location')}: {clip(finding.get('problem'))}")
        for response in review["responses"]:
            out.append(f"  - disposition by {response.get('commenter')} at {response.get('created_at')}: "
                       f"{clip(response.get('response'))}")
        if f"disposition:{review['job']}" in report["gaps"]:
            out.append(f"  - MISSING disposition:{review['job']}: failing review without a comment or close")
    out += ["", "## 6. Checks, pull request and human decision"]
    pr = report["pr"]
    if pr:
        out += [f"- PR {pr.get('url')} state {pr.get('state')}, head {short(pr.get('headRefOid'))}",
                f"- Review decision: {pr.get('reviewDecision') or 'none recorded'}; "
                f"{len(pr.get('reviews') or [])} review(s)"]
    for name in ("pr", "pr-head-reviewed", "check-outcomes"):
        if name in report["gaps"]:
            out.append(f"- MISSING {name}: {GAPS[name]}")
    decision = report["publication"]["decision"]
    out.append("- Publication authorized: " + decision if decision else "- MISSING human-decision: " + GAPS["human-decision"])
    out += ["", "## 7. Stated rationale (what people and tools wrote, quoted; hidden reasoning is not captured)"]
    out += [f"- {item['source']}{' at ' + item['at'] if item['at'] else ''}: {clip(item['text'])}"
            for item in report["rationale"] if item["text"]] or ["- none recorded"]
    out += ["", "## Missing links"]
    out += [f"- MISSING {name}: " + GAPS.get(name.split(":")[0], "") for name in report["gaps"]] or ["- none"]
    return "\n".join(out) + "\n"


def write_report(name, text, local=LOCAL):
    if not re.fullmatch(r"[A-Za-z0-9._-][A-Za-z0-9._ -]{0,79}", name) or ".." in name:
        raise TrailError(f"unsafe report name {name!r}")
    local = Path(local)
    directory = local / "decision-trail"
    directory.mkdir(mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    path = directory / (name.replace(" ", "-") + ".md")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    os.chmod(path, 0o600)
    return path


class LiveSources:
    """Read-only probes against kata, git, roborev, Forge and gh."""

    def __init__(self, roborev_url, forge_url):
        self.roborev_url, self.forge_url = roborev_url, forge_url

    @staticmethod
    def run(argv, cwd=None):
        return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=True, timeout=60).stdout

    def get(self, base, path):
        request = urllib.request.Request(base + path, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    def kata(self, ref):
        return json.loads(self.run(["kata", "show", ref, "--json"]))

    def commits(self, repo, spec):
        lines = self.run(["git", "-C", repo, "log", "--reverse", "--format=%H%x1f%s%x1f%cI", spec]).splitlines()
        return [dict(zip(("sha", "subject", "date"), line.split("\x1f"))) for line in lines]

    def review_jobs(self, repo):
        return json.loads(self.run(["roborev", "list", "--json", "--all-branches", "--limit", "500"], cwd=repo))

    def review_findings(self, job):
        shown = json.loads(self.run(["roborev", "show", "--json", "--job", str(job)]))
        return (shown.get("structured_output") or {}).get("findings", [])

    def review_responses(self, job):
        return self.get(self.roborev_url, f"/comments?job_id={job}")["responses"]

    def pull_request(self, ref):
        repo, number = ref.rsplit("#", 1)
        fields = "url,state,headRefOid,mergedBy,mergedAt,mergeCommit,reviewDecision,reviews,statusCheckRollup,body"
        return json.loads(self.run(["gh", "pr", "view", number, "--repo", repo, "--json", fields]))

    def workspace(self, workspace_id):
        quoted = urllib.parse.quote(workspace_id)
        workspace = self.get(self.forge_url, f"/workspaces/{quoted}")
        sessions = self.get(self.forge_url, f"/workspaces/{quoted}/agent-sessions")["sessions"]
        return {"qualified_id": (workspace.get("kata") or {}).get("qualified_id"),
                "session_ids": [item["session_id"] for item in sessions]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--kata", required=True, help="PROJECT#ID of the task")
    parser.add_argument("--repo", required=True, help="worktree or repository holding the commits")
    parser.add_argument("--commits", required=True, help="git revision range, e.g. origin/main..HEAD")
    parser.add_argument("--pr", help="OWNER/REPO#NUMBER")
    parser.add_argument("--audit-log", action="append", default=[], help="librarian-mcp audit JSONL (repeatable)")
    parser.add_argument("--session-file", help="Pi session JSONL for the work")
    parser.add_argument("--workspace", help="Forge workspace id")
    parser.add_argument("--intake", help="private jira-intake directory for the approved ticket")
    parser.add_argument("--approved-by", help="operator-asserted approver when no intake record exists")
    parser.add_argument("--approved-at")
    parser.add_argument("--qualifier-model", help="Librarian qualifier model, if known from another record")
    parser.add_argument("--name", required=True, help="report name under .local/decision-trail/")
    parser.add_argument("--roborev-url", default=os.environ.get("ROBOREV_API_URL", "http://127.0.0.1:17373/api"))
    parser.add_argument("--forge-url", default=os.environ.get("FORGE_API_URL", "http://127.0.0.1:18091/api/v1"))
    options = parser.parse_args(argv)
    approval = {"approved_by": options.approved_by, "approved_at": options.approved_at} \
        if options.approved_by and options.approved_at else None
    spec = {"name": options.name, "kata": options.kata, "repo": options.repo, "commits": options.commits,
            "pr": options.pr, "audit_logs": options.audit_log, "session_file": options.session_file,
            "workspace_id": options.workspace, "intake": options.intake, "approval": approval,
            "qualifier_model": options.qualifier_model}
    try:
        report = build(spec, LiveSources(options.roborev_url, options.forge_url))
        path = write_report(options.name, render(report))
    except (TrailError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"{path}: {len(report['gaps'])} missing link(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
