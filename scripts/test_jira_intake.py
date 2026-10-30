#!/usr/bin/env python3
"""Tests for jira-intake.py using a non-identifying Jira XML export fixture."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import textwrap
import unittest


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "jira-intake.py"
FIXTURE = HERE / "fixtures" / "jira-export-sample.xml"
spec = importlib.util.spec_from_file_location("jira_intake", MODULE_PATH)
intake = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intake)


def run_main(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = intake.main(list(args))
    return code, out.getvalue(), err.getvalue()


APPROVED_TASKS = textwrap.dedent(
    """
    [[refinement]]
    id = "R1"
    text = "The warning appears on the edit form only."
    approved_by = "owner"
    approved_at = "2026-11-01"

    [[assumption]]
    id = "A1"
    text = "Retired means status code V or Y."

    [[question]]
    id = "Q1"
    text = "Does this supersede an earlier ticket?"
    blocking = true
    resolution = "No; confirmed by owner."

    [[task]]
    id = "T1"
    project = "demo-backend"
    title = "Expose retired flag"
    outcome = "API reports whether the replacement widget is retired."
    acceptance = ["Flag is true for retired widgets."]
    approved_by = "owner"
    approved_at = "2026-11-01"

    [[task]]
    id = "T2"
    project = "demo-frontend"
    title = "Show retired warning"
    outcome = "Edit form shows the soft warning."
    acceptance = ["Warning is non-blocking.", "Text matches the ticket."]
    depends_on = ["T1"]
    refinements = ["R1"]
    approved_by = "owner"
    approved_at = "2026-11-01"
    """
)


class ParseExportTests(unittest.TestCase):
    def test_extracts_identity_and_original_text(self):
        ticket = intake.parse_export(FIXTURE.read_bytes())
        self.assertEqual(ticket["key"], "DEMO-7")
        self.assertEqual(ticket["url"], "https://jira.example.invalid/browse/DEMO-7")
        self.assertEqual(ticket["summary"], "Warn when a widget is retired")
        self.assertEqual(ticket["type"], "Story")
        self.assertEqual(ticket["parent"], "DEMO-1")
        self.assertEqual(ticket["status"], "To Do")
        self.assertIn('soft warning: "Replacement widget is retired"', ticket["description_html"])
        self.assertEqual(
            ticket["description_text"],
            'If the replacement widget is retired then soft warning: "Replacement widget is retired"\n\n'
            "Handled with catalog changes.",
        )
        self.assertEqual(ticket["acceptance_criteria_text"], "Warning is non-blocking.")
        self.assertEqual(ticket["custom_fields"]["Epic Link"], ["[EP] Demo Epic"])
        self.assertIn("at Mon Oct 19 21:31:34 UTC 2026", ticket["export_generated"])

    def test_rejects_multi_item_export(self):
        data = FIXTURE.read_text().replace("</item>", "</item><item><key>X-1</key></item>")
        with self.assertRaisesRegex(intake.IntakeError, "exactly one"):
            intake.parse_export(data.encode())


class IntakeFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".gitignore").write_text(".local/\n")
        self.out = self.root / ".local" / "intake"

    def tearDown(self):
        self.tmp.cleanup()

    def init(self):
        code, out, err = run_main(
            "init", str(FIXTURE), "--dir", str(self.out), "--access-path", "owner-supplied XML export"
        )
        self.assertEqual(code, 0, err)
        return self.out / "DEMO-7"

    def test_init_retains_private_verbatim_source_and_provenance(self):
        ticket_dir = self.init()
        self.assertEqual((ticket_dir / "source.xml").read_bytes(), FIXTURE.read_bytes())
        source = json.loads((ticket_dir / "source.json").read_text())
        self.assertEqual(source["ticket"]["key"], "DEMO-7")
        self.assertEqual(source["provenance"]["access_path"], "owner-supplied XML export")
        self.assertEqual(source["provenance"]["sha256"], intake.sha256(FIXTURE.read_bytes()))
        self.assertEqual(stat.S_IMODE((ticket_dir / "source.xml").stat().st_mode), 0o600)
        draft = (ticket_dir / "intake.toml").read_text()
        self.assertIn('key = "DEMO-7"', draft)
        self.assertIn("Warning is non-blocking.", draft)

    def test_init_refuses_tracked_destination(self):
        code, _, err = run_main(
            "init", str(FIXTURE), "--dir", str(self.root / "intake"), "--access-path", "owner export"
        )
        self.assertEqual(code, 1)
        self.assertIn("not ignored by Git", err)

    def test_init_requires_access_path(self):
        with self.assertRaises(SystemExit):
            run_main("init", str(FIXTURE), "--dir", str(self.out))

    def test_init_does_not_overwrite_existing_intake(self):
        self.init()
        code, _, err = run_main(
            "init", str(FIXTURE), "--dir", str(self.out), "--access-path", "owner export"
        )
        self.assertEqual(code, 1)
        self.assertIn("already exists", err)

    def test_fresh_draft_has_no_approved_tasks(self):
        ticket_dir = self.init()
        code, _, err = run_main("check", str(ticket_dir / "intake.toml"))
        self.assertEqual(code, 1)
        self.assertIn("no tasks", err)

    def write_tasks(self, ticket_dir, extra):
        path = ticket_dir / "intake.toml"
        path.write_text(path.read_text() + extra)
        return path

    def test_check_passes_approved_decomposition(self):
        path = self.write_tasks(self.init(), APPROVED_TASKS)
        code, out, err = run_main("check", str(path))
        self.assertEqual(code, 0, err)
        self.assertIn("2 approved tasks", out)

    def test_check_reports_every_problem(self):
        bad = APPROVED_TASKS.replace('resolution = "No; confirmed by owner."', "")
        bad = bad.replace('depends_on = ["T1"]', 'depends_on = ["T9"]')
        bad = bad.replace('refinements = ["R1"]', 'refinements = ["A1"]')
        bad = bad.replace('approved_by = "owner"\napproved_at = "2026-11-01"\n\n[[task]]', "\n[[task]]", 1)
        path = self.write_tasks(self.init(), bad)
        code, _, err = run_main("check", str(path))
        self.assertEqual(code, 1)
        self.assertIn("Q1: blocking question is unresolved", err)
        self.assertIn("T2: unknown dependency T9", err)
        self.assertIn("T2: A1 is not an approved refinement", err)
        self.assertIn("T1: missing approved_by", err)

    def test_check_rejects_scalar_acceptance(self):
        bad = APPROVED_TASKS.replace(
            'acceptance = ["Flag is true for retired widgets."]',
            'acceptance = "Flag is true for retired widgets."',
        )
        path = self.write_tasks(self.init(), bad)
        code, _, err = run_main("record", str(path), "--apply")
        self.assertEqual(code, 1)
        self.assertIn("T1: acceptance must be a nonempty list", err)

    def test_check_reports_missing_task_id(self):
        bad = APPROVED_TASKS.replace('id = "T1"\n', "", 1).replace('depends_on = ["T1"]', "")
        path = self.write_tasks(self.init(), bad)
        code, _, err = run_main("check", str(path))
        self.assertEqual(code, 1)
        self.assertIn("every task needs a nonempty string id", err)

    def test_check_rejects_dependency_cycle(self):
        cyclic = APPROVED_TASKS.replace(
            'outcome = "API reports', 'depends_on = ["T2"]\noutcome = "API reports'
        )
        path = self.write_tasks(self.init(), cyclic)
        code, _, err = run_main("check", str(path))
        self.assertEqual(code, 1)
        self.assertIn("dependency cycle", err)

    def test_check_detects_changed_source(self):
        ticket_dir = self.init()
        path = self.write_tasks(ticket_dir, APPROVED_TASKS)
        os.chmod(ticket_dir / "source.xml", 0o600)
        (ticket_dir / "source.xml").write_bytes(FIXTURE.read_bytes() + b"\n")
        code, _, err = run_main("check", str(path))
        self.assertEqual(code, 1)
        self.assertIn("source.xml no longer matches", err)

    def test_record_dry_run_prints_traceable_commands_in_order(self):
        path = self.write_tasks(self.init(), APPROVED_TASKS)
        code, out, err = run_main("record", str(path))
        self.assertEqual(code, 0, err)
        first, second = out.index("Expose retired flag"), out.index("Show retired warning")
        self.assertLess(first, second)
        self.assertIn("--project demo-backend", out)
        self.assertIn("jira.key=DEMO-7", out)
        self.assertIn("--idempotency-key jira-DEMO-7-T2", out)
        self.assertIn("--blocked-by '<T1>'", out)
        self.assertFalse((path.parent / "recorded.json").exists())
        self.assertNotIn("Replacement widget is retired", out)
        self.assertNotIn("edit form only", out)

    def test_record_apply_creates_tasks_with_traceability(self):
        path = self.write_tasks(self.init(), APPROVED_TASKS)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        log = self.root / "kata.log"
        fake = bin_dir / "kata"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            f"log = open({str(log)!r}, 'a')\n"
            "log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "log.close()\n"
            "n = sum(1 for _ in open(log.name))\n"
            "print(json.dumps({'issue': {'short_id': f'ab{n:02d}'}}))\n"
        )
        fake.chmod(0o755)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{old_path}"
        try:
            code, out, err = run_main("record", str(path), "--apply")
        finally:
            os.environ["PATH"] = old_path
        self.assertEqual(code, 0, err)
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual(len(calls), 2)
        body_path = Path(calls[1][calls[1].index("--body-file") + 1])
        self.assertEqual(stat.S_IMODE(body_path.stat().st_mode), 0o600)
        body = body_path.read_text()
        self.assertIn("DEMO-7", body)
        self.assertIn("https://jira.example.invalid/browse/DEMO-7", body)
        self.assertIn("- Warning is non-blocking.", body)
        self.assertIn("R1: The warning appears on the edit form only.", body)
        self.assertIn("demo-backend#ab01", calls[1])
        recorded = json.loads((path.parent / "recorded.json").read_text())
        self.assertEqual(recorded["tasks"], {"T1": "demo-backend#ab01", "T2": "demo-frontend#ab02"})
        self.assertIn("demo-frontend#ab02", out)

    def test_record_refuses_failing_check(self):
        ticket_dir = self.init()
        code, _, err = run_main("record", str(ticket_dir / "intake.toml"), "--apply")
        self.assertEqual(code, 1)
        self.assertIn("no tasks", err)


if __name__ == "__main__":
    unittest.main()
