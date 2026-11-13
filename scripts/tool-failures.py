#!/usr/bin/env python3
"""Mine agent session history for failed tool calls and report the top causes.

Read-only and stdlib-only. Sources: Pi session JSONL (`--pi DIR`, repeatable)
and Copilot `session-state/*/events.jsonl` (`--copilot DIR`). AgentsView's
database records errored tool results without their text, so it cannot be
grouped by cause and is not read.

  tool-failures.py [--pi DIR ...] [--copilot DIR ...] [--top N] [--out FILE]

Output groups failures by tool and by cause with counts. Error text is
normalised (paths, ids and numbers collapsed) and never copied verbatim beyond
one short line, so the report carries no file contents.
"""

import argparse
import collections
import json
from pathlib import Path
import re
import sys

# (cause, pattern over the full error text). First match wins; the order puts
# the specific causes ahead of the generic "nonzero-exit".
CAUSES = (
    ("output-limit", r"hit the output token limit"),
    ("human-gate", r"is human-controlled"),
    ("git-identity", r"Author identity unknown|empty ident name"),
    ("kata-binding", r"no \.kata\.toml ancestor|kata: alias .* is not registered|project \S+ is not registered|outside the MCP startup scope"),
    ("kata-daemon", r"daemon_unavailable|kata: .*connection refused|cannot reach (the )?kata"),
    ("kata-usage", r"kata: accepts \d+ arg|kata: unknown flag|kata: if any flags in the group|kata: evidence not allowed|X-Kata-Confirm"),
    ("stale-index", r"Index is stale"),
    ("librarian-reader", r"MCP server 'falcon-(librarian|context)': .*Reader (failed|timed out)"),
    ("codemode-tool-name", r"tools\.\S+ does not exist|Tool '\S+' does not exist"),
    ("bad-arguments", r"Validation failed for tool|must have required propert|\"path\": Required|Expected property name|Multiple validation errors|Invalid input"),
    ("edit-match", r"Could not find the exact text|No match found|Found \d+ occurrences|Failed to apply patch|Failed to find expected lines"),
    ("read-offset", r"Offset \d+ is beyond|view_range out of bounds"),
    ("missing-path", r"ENOENT|No such file or directory|Path does not exist|Path not found|Search paths do not exist|Parent directory does not exist|cannot access"),
    ("permission-denied", r"Permission denied"),
    ("web-fetch", r"Failed to fetch|web_fetch could not retrieve|Invalid URL"),
    ("command-not-found", r"command not found"),
    ("user-rejected", r"user rejected this tool call"),
    ("nonzero-exit", r"Command exited with code [1-9]"),
)


def classify(tool, arguments, text):
    for cause, pattern in CAUSES:
        if re.search(pattern, text):
            return cause
    return "other"


def normalize(text):
    """First non-empty line with paths, hashes and numbers collapsed."""
    line = next((item.strip() for item in text.splitlines() if item.strip()), "")
    line = re.sub(r"(?:/[\w.@+~-]+){2,}/?", "<path>", line)
    line = re.sub(r"\b[0-9a-f]{7,}\b", "<id>", line)
    return re.sub(r"\d+", "N", line)[:140]


class Stats:
    def __init__(self):
        self.total = 0
        self.failed = 0
        self.by_tool = {}          # tool -> (calls, failures)
        self.by_cause = collections.Counter()
        self.by_message = collections.Counter()   # (cause, normalised line)
        self.cause_tools = collections.defaultdict(collections.Counter)

    def call(self, tool, failed, text="", arguments=None):
        calls, failures = self.by_tool.get(tool, (0, 0))
        self.by_tool[tool] = (calls + 1, failures + bool(failed))
        self.total += 1
        if not failed:
            return
        self.failed += 1
        cause = classify(tool, arguments or {}, text)
        self.by_cause[cause] += 1
        self.cause_tools[cause][tool] += 1
        self.by_message[(cause, normalize(text))] += 1


def lines(path):
    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for raw in handle:
            try:
                value = json.loads(raw)
            except ValueError:
                continue
            if isinstance(value, dict):
                yield value


def result_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(item.get("text", "") for item in content if isinstance(item, dict))
    return ""


def mine_pi(roots):
    stats = Stats()
    for root in roots:
        for path in sorted(Path(root).rglob("*.jsonl")):
            calls = {}
            for entry in lines(path):
                message = entry.get("message")
                if not isinstance(message, dict):
                    continue
                content = message.get("content")
                if message.get("role") == "assistant" and isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "toolCall":
                            calls[part.get("id")] = part.get("arguments") or {}
                elif message.get("role") == "toolResult":
                    text = result_text(content)
                    failed = bool(message.get("isError")) or bool(re.search(r"Command exited with code [1-9]", text))
                    stats.call(message.get("toolName") or "?", failed, text, calls.get(message.get("toolCallId")))
    return stats


def mine_copilot(roots):
    stats = Stats()
    for root in roots:
        for path in sorted(Path(root).glob("*/events.jsonl")):
            started = {}
            for entry in lines(path):
                data = entry.get("data") if isinstance(entry.get("data"), dict) else {}
                if entry.get("type") == "tool.execution_start":
                    started[data.get("toolCallId")] = (data.get("toolName") or "?", data.get("arguments"))
                elif entry.get("type") == "tool.execution_complete":
                    tool, arguments = started.get(data.get("toolCallId"), ("?", None))
                    failed = data.get("success") is False
                    detail = data.get("error") or {}
                    text = detail.get("message", "") if isinstance(detail, dict) else str(detail)
                    stats.call(tool, failed, text, arguments if isinstance(arguments, dict) else {})
    return stats


def render_report(sources, top=10):
    out = ["# Agent tool-call failures", "",
           "Generated by `scripts/tool-failures.py`. Messages are normalised: paths, ids and",
           "numbers are collapsed and only the first line is kept.", ""]
    for name, stats in sources.items():
        rate = f"{100 * stats.failed / stats.total:.1f}%" if stats.total else "n/a"
        out += [f"## {name}", "", f"{stats.failed} failed of {stats.total} tool calls ({rate}).", "",
                "### Failures by cause", "", "| Cause | Count | Top tools |", "| --- | ---: | --- |"]
        for cause, count in stats.by_cause.most_common(top):
            tools = ", ".join(f"{tool} {n}" for tool, n in stats.cause_tools[cause].most_common(3))
            out.append(f"| {cause} | {count} | {tools} |")
        out += ["", "### Failures by tool", "", "| Tool | Failed | Calls |", "| --- | ---: | ---: |"]
        ranked = sorted(stats.by_tool.items(), key=lambda item: -item[1][1])
        out += [f"| {tool} | {failed} | {calls} |" for tool, (calls, failed) in ranked[:top] if failed]
        out += ["", "### Most common messages", "", "| Cause | Count | Message |", "| --- | ---: | --- |"]
        for (cause, message), count in stats.by_message.most_common(top):
            out.append(f"| {cause} | {count} | `{message.replace('|', '/').replace('`', '')}` |")
        out.append("")
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pi", action="append", default=[], metavar="DIR", help="Pi sessions directory")
    parser.add_argument("--copilot", action="append", default=[], metavar="DIR", help="Copilot session-state directory")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--out", type=Path, help="write the Markdown report here instead of stdout")
    args = parser.parse_args(argv)
    if not args.pi and not args.copilot:
        parser.error("give at least one --pi or --copilot directory")
    sources = {}
    if args.pi:
        sources["Pi"] = mine_pi(args.pi)
    if args.copilot:
        sources["Copilot"] = mine_copilot(args.copilot)
    report = render_report(sources, args.top)
    if args.out:
        args.out.write_text(report + "\n")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
