#!/usr/bin/env python3
"""Refresh the generated open-task index in TODO.md from the private Kata daemon."""

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import urllib.parse

from local_env import ROOT, kata_launch


START = "<!-- kata-open-tasks:start -->"
END = "<!-- kata-open-tasks:end -->"


def render_tasks(issues):
    sections = {}
    for issue in issues:
        if (issue["status"] != "open"
                or not re.fullmatch(r"[a-z0-9]+", issue["short_id"])
                or not issue["uid"] or not issue["title"].strip()
                or not isinstance(issue["metadata"], dict)
                or not isinstance(issue["labels"], list)):
            raise ValueError("expected open Kata issues with valid identity, title, metadata and labels")
        section = issue["metadata"].get("migration.section", "New work")
        if not isinstance(section, str) or not section.strip():
            raise ValueError("expected a nonempty task section")
        sections.setdefault(section, []).append(issue)
    output = ["## Open Kata tasks", ""]
    if not issues:
        output.extend(["No open tasks.", ""])
    for section, members in sections.items():
        output.extend(["### " + " ".join(section.split()), ""])
        for issue in members:
            url = "http://127.0.0.1:17777/kata?" + urllib.parse.urlencode({"issue": issue["uid"]})
            flags = " ".join(f"**{flag}**" for flag in ("blocked", "deferred")
                             if flag in issue["labels"])
            title = " ".join(issue["title"].split())
            output.append(f"- [ ] [`engi-platform#{issue['short_id']}`]({url}) {title}" +
                          (f" {flags}" if flags else ""))
        output.append("")
    return "\n".join(output)


def replace_tasks(original, rendered):
    if original.count(START) != 1 or original.count(END) != 1:
        raise ValueError("TODO.md must contain exactly one generated Kata task block")
    prefix, _, remaining = original.partition(START)
    if END in prefix or END not in remaining:
        raise ValueError("TODO.md task markers are out of order")
    _, _, suffix = remaining.partition(END)
    return prefix + START + "\n" + rendered.rstrip() + "\n" + END + suffix


def refresh():
    path = ROOT / "TODO.md"
    if path.is_symlink():
        raise RuntimeError("refusing to replace a symlinked TODO.md")
    original = path.read_text()
    replace_tasks(original, "")
    command, environment = kata_launch(["list", "--status", "open", "--sort", "oldest",
                                        "--limit", "0", "--json"])
    result = subprocess.run(command, env=environment, cwd=ROOT, capture_output=True,
                            text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(f"Kata task read failed: {result.stderr.strip() or result.stdout.strip()}")
    issues = json.loads(result.stdout)["issues"]
    updated = replace_tasks(original, render_tasks(issues))
    if path.read_text() != original:
        raise RuntimeError("TODO.md changed during refresh; no snapshot was written")
    if updated != original:
        fd, temporary = tempfile.mkstemp(prefix=".TODO.md-", dir=ROOT)
        try:
            with os.fdopen(fd, "w") as stream:
                os.fchmod(stream.fileno(), stat.S_IMODE(path.stat().st_mode))
                stream.write(updated)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    print(f"TODO.md indexes {len(issues)} open Kata tasks; completed history preserved.")


if __name__ == "__main__":
    try:
        refresh()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
