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
| `kata-binding`, `kata-daemon`, `kata-usage`, `git-identity`, `output-limit`, `missing-path`, `read-offset`, `edit-match`, `bad-arguments` | `recoveryHint` in `scripts/pi-extensions/forge-workspace.ts` appends one `Recovery:` line to the failed result | `scripts/pi-extensions/forge-workspace.test.mjs` (one test per cause) |
| Kata reachability, project binding, index freshness | `python3 scripts/tool-health.py` (read-only; PASS/FAIL/SKIP plus a `fix:` line; stale index exit 1 is reported, not crashed) | `scripts/test_tool_health.py` |
| Finding the next cause | `scripts/tool-failures.py` | `scripts/test_tool_failures.py` |

Not changed here: `web-fetch` (external sites), `write_agent`/`read_agent`
(agent lifecycle), and the Librarian reader messages (owned by
`GSA/the_librarian`, which already returns `fresh:false` as a result).

## Generated tables

### Pi

1123 failed of 20411 tool calls (5.5%).

#### Failures by cause

| Cause | Count | Top tools |
| --- | ---: | --- |
| nonzero-exit | 604 | bash 602, grep 1, subagent 1 |
| missing-path | 255 | read 112, bash 71, grep 51 |
| other | 101 | web_search 20, bash 17, edit 13 |
| edit-match | 46 | edit 46 |
| bad-arguments | 36 | edit 30, codemode 3, ask_user_question 3 |
| read-offset | 28 | read 27, codemode 1 |
| output-limit | 13 | bash 6, edit 4, write 3 |
| git-identity | 10 | bash 10 |
| command-not-found | 9 | bash 9 |
| human-gate | 8 | bash 8 |
| kata-usage | 6 | bash 6 |
| codemode-tool-name | 4 | codemode 4 |
| kata-binding | 1 | bash 1 |
| permission-denied | 1 | bash 1 |

#### Failures by tool

| Tool | Failed | Calls |
| --- | ---: | ---: |
| bash | 732 | 8522 |
| read | 145 | 6569 |
| edit | 93 | 1568 |
| grep | 55 | 1483 |
| codemode | 27 | 722 |
| web_search | 20 | 22 |
| ls | 14 | 370 |
| subagent | 11 | 80 |
| fetch_content | 6 | 12 |
| find | 4 | 315 |
| write | 3 | 307 |
| mcp__kenn_forge__kenn_forge_list_workspace_targets | 3 | 29 |
| ask_user_question | 3 | 35 |
| mcp__kenn_forge__kenn_forge_add_workspace_kata_target | 2 | 28 |

#### Most common messages

| Cause | Count | Message |
| --- | ---: | --- |
| missing-path | 112 | `ENOENT: no such file or directory, access '<path>'` |
| missing-path | 64 | `Path not found: <path>` |
| nonzero-exit | 37 | `Reviewing selected staged technical scope ONLY (N paths); snapshot: <path>` |
| bad-arguments | 30 | `Validation failed for tool "edit":` |
| read-offset | 27 | `Offset N is beyond end of file (N lines total)` |
| nonzero-exit | 26 | `Traceback (most recent call last):` |
| nonzero-exit | 25 | `(no output)` |
| nonzero-exit | 20 | `Enqueued dirty review job N (agent: pi)` |
| nonzero-exit | 14 | `test_limited_qualify_replaces_edited_item_selection_and_rejects_unsafe_paths (tests.test_intake_cohort.QualifyTests.test_limited_qualify_rep` |
| other | 12 | `Script failed` |
| nonzero-exit | 9 | `F                                                                        [N%]` |
| git-identity | 8 | `Author identity unknown` |
| nonzero-exit | 8 | `Waiting for review to complete... done!` |
| nonzero-exit | 8 | `test_every_file_gets_one_explicit_disposition (tests.test_intake_cohort.ClassifyTests.test_every_file_gets_one_explicit_disposition) ... ok` |

### Copilot

486 failed of 33106 tool calls (1.5%).

#### Failures by cause

| Cause | Count | Top tools |
| --- | ---: | --- |
| missing-path | 103 | view 68, glob 12, rg 12 |
| other | 85 | write_agent 19, falcon-context-review_events 12, read_agent 11 |
| edit-match | 81 | apply_patch 44, edit 37 |
| librarian-reader | 72 | falcon-context-review_events 23, falcon-context-catalog 20, falcon-context-get_many 10 |
| web-fetch | 48 | web_fetch 48 |
| read-offset | 45 | view 45 |
| bad-arguments | 18 | ask_user 12, create 4, edit 2 |
| permission-denied | 14 | glob 13, grep 1 |
| stale-index | 11 | falcon-context-search 5, falcon-context-status 4, falcon-context-get 2 |
| user-rejected | 7 | bash 4, web_fetch 3 |
| codemode-tool-name | 1 | hn_algolia_com 1 |
| kata-binding | 1 | kata-kata-list 1 |

#### Failures by tool

| Tool | Failed | Calls |
| --- | ---: | ---: |
| view | 116 | 11443 |
| web_fetch | 52 | 410 |
| apply_patch | 46 | 2027 |
| edit | 39 | 1304 |
| falcon-context-review_events | 35 | 77 |
| falcon-context-catalog | 27 | 45 |
| glob | 25 | 486 |
| write_agent | 19 | 167 |
| falcon-context-get_many | 18 | 40 |
| ask_user | 14 | 83 |
| create | 14 | 104 |
| rg | 13 | 2198 |
| falcon-context-search | 13 | 81 |
| bash | 12 | 12860 |

#### Most common messages

| Cause | Count | Message |
| --- | ---: | --- |
| missing-path | 68 | `Path does not exist` |
| read-offset | 45 | `view_range out of bounds` |
| edit-match | 37 | `No match found` |
| web-fetch | 30 | `Error: Failed to fetch https:/<path> - status code N` |
| edit-match | 25 | `Failed to apply patch: Error: Failed to find expected lines in <path>:` |
| edit-match | 19 | `Error: Failed to find expected lines in <path>:` |
| other | 11 | `Agent not found` |
| missing-path | 10 | `Search paths do not exist: <path>` |
| other | 9 | `Cancelled` |
| librarian-reader | 9 | `MCP server 'falcon-context': Error executing tool catalog: Reader failed (exit N): context-index: Invalid source ID` |
| permission-denied | 9 | `rg: <path>: Permission denied (os error N)` |
| librarian-reader | 8 | `MCP server 'falcon-context': Error executing tool catalog: Reader failed (exit N): context-index: Invalid receipt ID` |
| librarian-reader | 8 | `MCP server 'falcon-context': Error executing tool review_events: Reader failed (exit N): event-reader: receipt_id must be an exact D identif` |
| other | 8 | `MCP server 'falcon-context': Error executing tool review_events: Select a receipt, source or literal scope for bounded review events` |

