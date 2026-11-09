#!/usr/bin/env python3
"""Tests for tool-failures.py using synthetic session files."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tool_failures", HERE / "tool-failures.py")
tf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tf)


def pi_lines(*calls):
    """Pi JSONL: (tool, arguments, text, is_error) -> call + result lines."""
    out = []
    for index, (tool, args, text, is_error) in enumerate(calls):
        out.append({"message": {"role": "assistant", "content": [
            {"type": "toolCall", "id": f"c{index}", "name": tool, "arguments": args}]}})
        out.append({"message": {"role": "toolResult", "toolCallId": f"c{index}", "toolName": tool,
                                "isError": is_error, "content": [{"type": "text", "text": text}]}})
    return "\n".join(json.dumps(line) for line in out) + "\n"


class NormalizeTests(unittest.TestCase):
    def test_paths_ids_and_numbers_collapse(self):
        a = tf.normalize("ENOENT: no such file or directory, access '/home/u/wt/abc12345/context/x.md'")
        b = tf.normalize("ENOENT: no such file or directory, access '/home/u/other/ff00ee11/context/y.md'")
        self.assertEqual(a, b)
        self.assertNotIn("/home", a)

    def test_only_first_meaningful_line_is_kept(self):
        self.assertEqual(tf.normalize("\n\nboom 12\nsecond line"), "boom N")


class ClassifyTests(unittest.TestCase):
    def cause(self, tool, args, text):
        return tf.classify(tool, args, text)

    def test_known_causes(self):
        cases = [
            ("read", {"path": "a"}, "ENOENT: no such file or directory, access '/x/a'", "missing-path"),
            ("read", {"path": "a"}, "Offset 200 is beyond end of file (199 lines total)", "read-offset"),
            ("edit", {}, "Found 3 occurrences of edits[0] in f", "edit-match"),
            ("edit", {}, "Could not find the exact text in f.", "edit-match"),
            ("edit", {}, "Validation failed for tool \"edit\":\n  - edits.0: must be object", "bad-arguments"),
            ("bash", {"command": "kata comment x y"}, "kata: accepts 1 arg(s), received 2\n\nCommand exited with code 2", "kata-usage"),
            ("bash", {"command": "kata list"}, "ERR list not_found: no .kata.toml ancestor and no git ancestor", "kata-binding"),
            ("bash", {"command": "kata list"}, 'kata: alias github.com/GSA/x is not registered', "kata-binding"),
            ("bash", {"command": "kata list"}, "daemon_unavailable: connection refused", "kata-daemon"),
            ("bash", {"command": "kata x"}, "kata: command not found", "command-not-found"),
            ("bash", {"command": "git commit"}, "Author identity unknown\nfatal: empty ident name", "git-identity"),
            ("bash", {"command": "git push"}, "push_main is human-controlled", "human-gate"),
            ("bash", {"command": "ls"}, 'Tool call "bash" was not executed: the response hit the output token limit', "output-limit"),
            ("bash", {"command": "pytest"}, "FAILED\nCommand exited with code 1", "nonzero-exit"),
            ("mcp__falcon_context", {}, "context-index: Index is stale; run build", "stale-index"),
            ("codemode", {}, "TypeError: tools.kata.show does not exist. Did you mean", "codemode-tool-name"),
            ("codemode", {}, 'Validation failed for tool "x":\n  - ref: must have', "bad-arguments"),
            ("ls", {}, "Path not found: /x/y", "missing-path"),
            ("glob", {}, "rg: /x: Permission denied (os error 13)", "permission-denied"),
            ("web_fetch", {}, "Error: Failed to fetch https://x - status code 404", "web-fetch"),
            ("falcon-context-search", {}, "MCP server 'falcon-context': Error executing tool search: Reader failed (exit 2): bad", "librarian-reader"),
            ("falcon-context-status", {}, "MCP server 'falcon-context': Error executing tool status: Reader failed (exit 1): context-index: Index is stale", "stale-index"),
            ("web_search", {}, "weird", "other"),
        ]
        for tool, args, text, expected in cases:
            with self.subTest(text=text[:40]):
                self.assertEqual(self.cause(tool, args, text), expected)


class MiningTests(unittest.TestCase):
    def test_pi_errors_counted_by_tool_and_cause(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "s1.jsonl"
            session.write_text(pi_lines(
                ("read", {"path": "a"}, "ENOENT: no such file or directory, access '/w/1/a'", True),
                ("read", {"path": "b"}, "ENOENT: no such file or directory, access '/w/2/b'", True),
                ("read", {"path": "c"}, "fine", False),
                ("bash", {"command": "pytest"}, "boom\n\nCommand exited with code 1", True),
            ))
            stats = tf.mine_pi([Path(tmp)])
        self.assertEqual(stats.total, 4)
        self.assertEqual(stats.failed, 3)
        self.assertEqual(stats.by_tool["read"], (3, 2))
        self.assertEqual(stats.by_cause["missing-path"], 2)

    def test_copilot_failures_use_start_event_for_tool_name(self):
        events = [
            {"type": "tool.execution_start", "data": {"toolCallId": "t1", "toolName": "view", "arguments": {}}},
            {"type": "tool.execution_complete", "data": {"toolCallId": "t1", "success": False,
                                                          "error": {"message": "Path does not exist"}}},
            {"type": "tool.execution_start", "data": {"toolCallId": "t2", "toolName": "view", "arguments": {}}},
            {"type": "tool.execution_complete", "data": {"toolCallId": "t2", "success": True}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "abc"
            run.mkdir()
            (run / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
            stats = tf.mine_copilot([Path(tmp)])
        self.assertEqual((stats.total, stats.failed), (2, 1))
        self.assertEqual(stats.by_tool["view"], (2, 1))
        self.assertEqual(stats.by_cause["missing-path"], 1)

    def test_bad_json_lines_are_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "s.jsonl").write_text("{not json\n" + pi_lines(("ls", {}, "x", True)))
            stats = tf.mine_pi([Path(tmp)])
        self.assertEqual(stats.failed, 1)


class ReportTests(unittest.TestCase):
    def test_report_lists_causes_with_counts_and_no_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "s.jsonl").write_text(pi_lines(
                ("read", {}, "ENOENT: no such file or directory, access '/home/secret/a'", True)))
            stats = tf.mine_pi([Path(tmp)])
        text = tf.render_report({"Pi": stats}, top=5)
        self.assertIn("missing-path", text)
        self.assertIn("| 1 |", text)
        self.assertNotIn("/home/secret", text)


if __name__ == "__main__":
    unittest.main()
