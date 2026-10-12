import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import kata_todo


class KataTodoTests(unittest.TestCase):
    def issue(self, **changes):
        issue = {
            "uid": "01M4RM6HV32B5T2DFG4XSHG2TM", "short_id": "g2tm",
            "title": "Preserve local settings", "status": "open", "labels": [],
            "metadata": {"migration.section": "Maintenance"},
        }
        issue.update(changes)
        return issue

    def test_render_groups_tasks_and_shows_blockers(self):
        rendered = kata_todo.render_tasks([
            self.issue(labels=["blocked"]),
            self.issue(short_id="next", metadata={}, title="New task"),
        ])
        self.assertIn("### Maintenance", rendered)
        self.assertIn("### New work", rendered)
        self.assertIn("engi-platform#g2tm", rendered)
        self.assertIn("**blocked**", rendered)
        self.assertIn("issue=01M4RM6HV32B5T2DFG4XSHG2TM", rendered)

    def test_render_rejects_invalid_or_closed_tasks(self):
        for changes in ({"status": "closed"}, {"short_id": "../other"},
                        {"uid": ""}, {"title": ""}, {"metadata": []}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                kata_todo.render_tasks([self.issue(**changes)])

    def test_replace_preserves_history_and_operating_notes(self):
        original = "notes\n" + kata_todo.START + "\nold\n" + kata_todo.END + "\nhistory\n"
        result = kata_todo.replace_tasks(original, "new\n")
        self.assertEqual(result, "notes\n" + kata_todo.START + "\nnew\n" +
                         kata_todo.END + "\nhistory\n")

    def test_replace_refuses_missing_duplicate_or_reversed_markers(self):
        for original in ("no markers", kata_todo.START + kata_todo.START + kata_todo.END,
                         kata_todo.END + kata_todo.START):
            with self.subTest(original=original), self.assertRaises(ValueError):
                kata_todo.replace_tasks(original, "new")

    def test_empty_queue_is_explicit(self):
        self.assertIn("No open tasks", kata_todo.render_tasks([]))

    def test_refresh_failure_preserves_existing_index(self):
        with tempfile.TemporaryDirectory(prefix="kata-index-", dir=kata_todo.ROOT / ".local") as directory:
            root = Path(directory)
            path = root / "TODO.md"
            original = "notes\n" + kata_todo.START + "\nold\n" + kata_todo.END + "\nhistory\n"
            path.write_text(original)
            with patch.object(kata_todo, "ROOT", root):
                with patch.object(kata_todo, "kata_launch", return_value=(["kata"], {})):
                    with patch.object(kata_todo.subprocess, "run", return_value=
                                      subprocess.CompletedProcess(["kata"], 7, "", "daemon unavailable")):
                        with self.assertRaisesRegex(RuntimeError, "daemon unavailable"):
                            kata_todo.refresh()
            self.assertEqual(path.read_text(), original)

    def test_refresh_refuses_concurrent_edit(self):
        with tempfile.TemporaryDirectory(prefix="kata-index-", dir=kata_todo.ROOT / ".local") as directory:
            root = Path(directory)
            path = root / "TODO.md"
            original = kata_todo.START + "\nold\n" + kata_todo.END
            path.write_text(original)

            def fetch(*args, **kwargs):
                path.write_text(original + "\nuser edit")
                return subprocess.CompletedProcess(["kata"], 0, '{"issues":[]}', "")

            with patch.object(kata_todo, "ROOT", root):
                with patch.object(kata_todo, "kata_launch", return_value=(["kata"], {})):
                    with patch.object(kata_todo.subprocess, "run", side_effect=fetch):
                        with self.assertRaisesRegex(RuntimeError, "changed during refresh"):
                            kata_todo.refresh()
            self.assertEqual(path.read_text(), original + "\nuser edit")

    def test_refresh_is_repeatable_and_preserves_completed_history(self):
        with tempfile.TemporaryDirectory(prefix="kata-index-", dir=kata_todo.ROOT / ".local") as directory:
            root = Path(directory)
            path = root / "TODO.md"
            path.write_text("notes\n" + kata_todo.START + "\nold\n" + kata_todo.END +
                            "\n- [x] historical completion\n")
            result = subprocess.CompletedProcess(["kata"], 0, json.dumps({"issues": [self.issue()]}), "")
            with patch.object(kata_todo, "ROOT", root):
                with patch.object(kata_todo, "kata_launch", return_value=(["kata"], {})):
                    with patch.object(kata_todo.subprocess, "run", return_value=result):
                        with contextlib.redirect_stdout(io.StringIO()):
                            kata_todo.refresh()
                            first = path.read_text()
                            kata_todo.refresh()
            self.assertEqual(path.read_text(), first)
            self.assertIn("- [x] historical completion", first)
            self.assertIn("engi-platform#g2tm", first)


if __name__ == "__main__":
    unittest.main()
