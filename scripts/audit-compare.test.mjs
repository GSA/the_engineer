import assert from "node:assert/strict";
import { test } from "node:test";
import { compareAudit } from "./audit-compare.mjs";

const line = (tool, outcome, sha, label = "pi-forge") =>
  JSON.stringify({ agent_label: label, tool, outcome, returned_sha256: sha });
const calls = [{ tool: "status", error: false, sha256: "aa" }, { tool: "get", error: true, sha256: "bb" }];
const fresh = [line("status", "ok", "aa"), line("get", "error", "bb")];

test("accepts exactly the records appended by this run", () => {
  assert.equal(compareAudit(["{}"], ["{}", ...fresh], calls, "pi-forge"), 2);
});
test("older matching records do not satisfy an unaudited run", () => {
  assert.throws(() => compareAudit(fresh, fresh, calls, "pi-forge"), /expected 2 new audit records/);
});
test("rejects a wrong label, outcome or hash", () => {
  assert.throws(() => compareAudit([], [fresh[0], line("get", "error", "bb", "other")], calls, "pi-forge"), /label/);
  assert.throws(() => compareAudit([], [fresh[0], line("get", "ok", "bb")], calls, "pi-forge"), /outcome/);
  assert.throws(() => compareAudit([], [fresh[0], line("get", "error", "zz")], calls, "pi-forge"), /hash/);
});
