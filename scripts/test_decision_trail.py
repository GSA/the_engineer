#!/usr/bin/env python3
"""Tests for decision-trail.py using synthetic, non-identifying sources."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("decision_trail", HERE / "decision-trail.py")
trail = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trail)

BODY = "SYNTHETIC-DOCUMENT-BODY-MUST-NOT-APPEAR"
HEAD = "a" * 40
FIRST = "b" * 40
MERGE = "c" * 40


def audit_record(tool, outcome="ok", when="2026-11-02T10:00:05+00:00", label="pi-forge", body=BODY, **extra):
    text = json.dumps({"audience": "authorized-local", "notice": "handle per audience",
                       "pieces": [{"locator": "documents/a.md#x", "source_hash": "h1", "text": body}]})
    return {"schema": "librarian-mcp-audit-v1", "agent_label": label, "tool": tool, "outcome": outcome,
            "started_at": when, "completed_at": when, "arguments": {"locator": "documents/a.md#x"},
            "returned_text": text, "returned_chars": len(text),
            "returned_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "references": {"locators": ["documents/a.md#x"], "source_hashes": ["h1"], "record_ids": []}, **extra}


ref_end = lambda job: job['git_ref'].split('..')[-1]


class FakeSources:
    def __init__(self, **overrides):
        self.data = {
            "kata": {"issue": {"uid": "U1", "short_id": "ab12", "title": "Add thing", "status": "closed",
                               "revision": 3, "author": "owner", "body": "ticket body text",
                               "updated_at": "2026-11-02T09:00:00Z"},
                     "comments": [{"author": "owner", "created_at": "2026-11-02T09:30:00Z",
                                   "body": "Chose option B because it keeps the contract unchanged."}]},
            "git": [{"sha": FIRST, "subject": "feat: first", "date": "2026-11-02T10:10:00Z"},
                    {"sha": HEAD, "subject": "fix: second", "date": "2026-11-02T10:20:00Z"}],
            "jobs": [{"id": 7, "git_ref": FIRST, "status": "done", "verdict": "F", "agent": "pi",
                      "model": "reviewer-model", "reasoning": "standard", "closed": True,
                      "finished_at": "2026-11-02T10:15:00Z", "repo_path": "/repo"}],
            "findings": {7: [{"severity": "medium", "location": "x.py:3", "problem": "bad"}]},
            "comments": {7: [{"commenter": "owner", "created_at": "2026-11-02T10:16:00Z",
                              "response": "Fixed in the follow-up commit."}]},
            "pr": {"url": "https://example.invalid/pr/1", "state": "MERGED", "headRefOid": HEAD,
                   "mergedBy": {"login": "human", "is_bot": False}, "mergedAt": "2026-11-02T11:00:00Z",
                   "mergeCommit": {"oid": MERGE}, "reviewDecision": "", "reviews": [], "statusCheckRollup": [],
                   "body": "Implements the thing.", "comments": []},
        }
        self.data.update(overrides)

    def kata(self, ref): return self.data["kata"]
    def commits(self, repo, spec): return self.data["git"]
    def review_jobs(self, repo): return self.data["jobs"]
    def review_findings(self, job): return self.data["findings"].get(job, [])
    def review_responses(self, job): return self.data["comments"].get(job, [])
    def pull_request(self, ref): return self.data["pr"]
    def covered(self, repo, job):
        return set(self.data.get("covered", {}).get(job["id"], {ref_end(job)}))

    def workspace(self, workspace_id):
        return self.data.get("workspace", {"qualified_id": "proj#ab12", "session_ids": ["sess-1"]})


class DecisionTrailTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)

    def audit_log(self, *records, name="pi-forge-mcp-access.jsonl"):
        path = self.root / name
        path.write_text("".join(json.dumps(record) + "\n" for record in records))
        return path

    def session_file(self, model="coder-model"):
        path = self.root / "session.jsonl"
        lines = [{"type": "session", "id": "sess-1", "timestamp": "2026-11-02T10:00:00Z", "cwd": "/work"},
                 {"type": "model_change", "timestamp": "2026-11-02T10:00:01Z", "provider": "usai", "modelId": model},
                 {"type": "message", "timestamp": "2026-11-02T10:30:00Z", "message": {"role": "assistant"}}]
        path.write_text("".join(json.dumps(line) + "\n" for line in lines))
        return path

    def spec(self, **overrides):
        base = {"kata": "proj#ab12", "repo": "/repo", "commits": "base..HEAD", "pr": "o/r#1",
                "audit_logs": [self.audit_log(audit_record("status"), audit_record("get"),
                                              audit_record("get", "error", body="fail"), name="default.jsonl")],
                "session_file": self.session_file(), "workspace_id": "ws1", "intake": None}
        base.update(overrides)
        return base

    def build(self, spec=None, sources=None):
        return trail.build(spec or self.spec(), sources or FakeSources())

    def test_complete_trail_links_every_stage_without_document_bodies(self):
        report = self.build()
        text = trail.render(report)
        self.assertNotIn(BODY, text)
        self.assertNotIn("ticket body text", text)
        self.assertIn(hashlib.sha256(b"ticket body text").hexdigest(), text)
        self.assertEqual(report["evidence"]["records"], 3)
        self.assertEqual({"ok": 2, "error": 1}, report["evidence"]["outcomes"])
        self.assertEqual(report["evidence"]["hash_mismatches"], 0)
        self.assertIn("documents/a.md#x", text)
        self.assertIn("audience=authorized-local", text)
        self.assertIn("reviewer-model", text)
        self.assertIn("coder-model", text)
        self.assertIn("Fixed in the follow-up commit.", text)
        self.assertIn("human", report["publication"]["decision"])
        self.assertIn("Chose option B", text)

    def test_missing_links_are_listed_explicitly(self):
        sources = FakeSources(jobs=[], pr={**FakeSources().data["pr"], "state": "OPEN", "mergedBy": None,
                                           "mergedAt": None, "mergeCommit": None, "headRefOid": "d" * 40})
        report = self.build(self.spec(audit_logs=[], session_file=None, workspace_id=None), sources)
        gaps = set(report["gaps"])
        self.assertTrue({"ticket-approval", "audit-log", "session", "workspace", "check-outcomes",
                         f"review:{FIRST[:12]}", f"review:{HEAD[:12]}", "human-decision",
                         "pr-head-reviewed", "qualifier-model"} <= gaps, gaps)
        text = trail.render(report)
        self.assertIn("MISSING", text)
        for gap in report["gaps"]:
            self.assertIn(gap, text)

    def test_labels_alone_never_prove_session_identity(self):
        text = trail.render(self.build())
        self.assertIn("agent label", text)
        self.assertIn("not proof of task or session identity", text)
        self.assertIn("time overlap", text)
        report = self.build(self.spec(session_file=None))
        self.assertIn("session", report["gaps"])
        self.assertEqual(report["evidence"]["in_session_window"], None)

    def test_audit_record_outside_session_window_is_not_attributed(self):
        log = self.audit_log(audit_record("get", when="2026-11-02T12:00:00+00:00"))
        report = self.build(self.spec(audit_logs=[log]))
        self.assertEqual(report["evidence"]["in_session_window"], 0)

    def test_tampered_returned_text_is_reported_as_hash_mismatch(self):
        bad = audit_record("get")
        bad["returned_text"] += " "
        report = self.build(self.spec(audit_logs=[self.audit_log(bad)]))
        self.assertEqual(report["evidence"]["hash_mismatches"], 1)
        self.assertIn("audit-hash-mismatch", report["gaps"])

    def test_invalid_audit_lines_are_counted_not_hidden(self):
        path = self.root / "x.jsonl"
        path.write_text("not json\n" + json.dumps(audit_record("get")) + "\n")
        report = self.build(self.spec(audit_logs=[path]))
        self.assertEqual(report["evidence"]["invalid_lines"], 1)
        self.assertIn("audit-invalid-lines", report["gaps"])

    def test_rationale_is_labelled_stated_and_never_claims_hidden_reasoning(self):
        text = trail.render(self.build())
        self.assertIn("stated rationale", text.lower())
        self.assertIn("hidden reasoning is not captured", text.lower())

    def test_unreviewed_commit_and_unmatched_head_are_visible(self):
        sources = FakeSources()
        report = self.build(sources=sources)
        self.assertIn(f"review:{HEAD[:12]}", report["gaps"])
        self.assertIn("pr-head-reviewed", report["gaps"])
        self.assertNotIn(f"review:{FIRST[:12]}", report["gaps"])

    def test_range_review_covers_every_commit_it_examined(self):
        report = self.build(sources=FakeSources(covered={7: {FIRST, HEAD}}))
        self.assertNotIn(f"review:{HEAD[:12]}", report["gaps"])

    def test_failed_review_without_disposition_is_a_gap(self):
        report = self.build(sources=FakeSources(comments={}, jobs=[{**FakeSources().data["jobs"][0], "closed": False}]))
        self.assertIn("disposition:7", report["gaps"])

    def test_intake_record_supplies_ticket_approval(self):
        intake = self.root / "intake"
        intake.mkdir()
        (intake / "source.json").write_text(json.dumps({"ticket": {"key": "T-1"}, "provenance": {"sha256": "ab" * 32}}))
        (intake / "recorded.json").write_text(json.dumps({"ticket": "T-1", "tasks": {"t": "proj#ab12"}}))
        (intake / "intake.toml").write_text(
            '[[task]]\nid = "t"\ntitle = "x"\napproved_by = "owner"\napproved_at = "2026-11-01"\n')
        report = self.build(self.spec(intake=intake))
        self.assertNotIn("ticket-approval", report["gaps"])
        self.assertEqual(report["ticket"]["approval"]["approved_by"], "owner")
        self.assertEqual(report["ticket"]["jira_key"], "T-1")

    def test_intake_for_another_task_does_not_approve_this_one(self):
        intake = self.root / "intake"
        intake.mkdir()
        (intake / "source.json").write_text(json.dumps({"ticket": {"key": "T-1"}, "provenance": {"sha256": "ab" * 32}}))
        (intake / "recorded.json").write_text(json.dumps({"ticket": "T-1", "tasks": {"t": "proj#other"}}))
        (intake / "intake.toml").write_text('[[task]]\nid = "t"\napproved_by = "o"\napproved_at = "d"\n')
        self.assertIn("ticket-approval", self.build(self.spec(intake=intake))["gaps"])

    def test_workspace_for_another_task_or_session_is_a_gap(self):
        other = FakeSources(workspace={"qualified_id": "proj#zzzz", "session_ids": ["sess-1"]})
        self.assertIn("workspace-link", self.build(sources=other)["gaps"])
        other = FakeSources(workspace={"qualified_id": "proj#ab12", "session_ids": ["other"]})
        self.assertIn("workspace-link", self.build(sources=other)["gaps"])
        self.assertNotIn("workspace-link", self.build()["gaps"])

    def test_operator_asserted_approval_is_labelled_unverified(self):
        report = self.build(self.spec(approval={"approved_by": "owner", "approved_at": "2026-11-01"}))
        self.assertNotIn("ticket-approval", report["gaps"])
        self.assertIn("operator-asserted", trail.render(report))

    def test_write_report_is_private_and_stays_under_local(self):
        local = self.root / ".local"
        local.mkdir(mode=0o700)
        out = trail.write_report("run one", "text\n", local)
        self.assertEqual(out.parent, local / "decision-trail")
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(out.parent.stat().st_mode), 0o700)
        with self.assertRaises(trail.TrailError):
            trail.write_report("../escape", "x", local)


if __name__ == "__main__":
    unittest.main()
