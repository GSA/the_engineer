# Agent tool-call failures

Snapshot of failed tool calls mined from Pi (this checkout's private sessions
and the user-level store) and Copilot session history, with the fixes made for
the recurring causes (Kata `the_engineer#eynt`).

Reproduce with:

```sh
python3 scripts/tool-failures.py --pi .local/environment/pi/sessions \
  --pi ~/.pi/agent/sessions --copilot ~/.copilot/session-state --out report.md
```

AgentsView is not a source: its `tool_result_events` hold 486 `errored` rows
(all Copilot) with empty content, so they cannot be grouped by cause.

## Reading the numbers

- Tool failure rate is 5.5% of Pi calls and 1.5% of Copilot calls. Most Pi
  failures are `bash` exiting nonzero (failing tests, `roborev` exit 1, `grep`
  with no match). Those are task outcomes, not tool misuse, and need no fix.
- Kata itself is a small share (7 Pi failures and 1 Copilot failure), but each
  one is a wasted turn and the messages did not always say how to recover.
- The largest agent-recoverable causes are path errors (`missing-path`, mostly
  `read`/`view` of a file in a different or removed worktree), `edit-match` /
  `read-offset` (stale file contents), `bad-arguments` (`edit` called with
  `edits` as a JSON string), and `git-identity` (a sandboxed `HOME`).
- Librarian reader failures (72 Copilot) include `stale-index` (a reported
  state that the MCP surfaced as a tool error; fixed in `GSA/the_librarian#29`).

## What changed

| Cause | Change | Test |
| --- | --- | --- |
| `kata-binding`, `kata-daemon`, `kata-usage`, `git-identity`, `output-limit`, `missing-path`, `read-offset`, `edit-match`, `bad-arguments` | `recoveryHint` in `scripts/pi-extensions/forge-workspace/recovery.ts` appends one `Recovery:` line to the failed result | `scripts/pi-extensions/forge-workspace/forge-workspace.test.mjs` (one test per cause) |
| Kata reachability, project binding, index freshness | `python3 scripts/tool-health.py` (read-only; PASS/FAIL/SKIP plus a `fix:` line; stale index exit 1 is reported, not crashed) | `scripts/test_tool_health.py` |
| Finding the next cause | `scripts/tool-failures.py` | `scripts/test_tool_failures.py` |
