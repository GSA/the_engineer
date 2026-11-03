// Compares the audit lines appended during one client run with what that
// client received. Only lines past `before` count, so older matching records
// cannot satisfy the check when auditing is off.
import assert from "node:assert/strict";

export function compareAudit(beforeLines, afterLines, calls, label) {
  assert.ok(afterLines.length >= beforeLines.length, "audit log shrank during the run");
  const added = afterLines.slice(beforeLines.length).map((line) => JSON.parse(line));
  assert.equal(added.length, calls.length, `expected ${calls.length} new audit records, found ${added.length}`);
  calls.forEach((call, index) => {
    const record = added[index];
    assert.equal(record.agent_label, label, `${call.tool} label`);
    assert.equal(record.tool, call.tool);
    assert.equal(record.outcome, call.error ? "error" : "ok", `${call.tool} outcome`);
    assert.equal(record.returned_sha256, call.sha256, `${call.tool} returned hash`);
  });
  return added.length;
}
