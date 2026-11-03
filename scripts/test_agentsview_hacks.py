#!/usr/bin/env python3
"""Black-box regression tests for the carried agentsview patches.

These run the built agentsview binary against synthetic Copilot and Pi session
files in a throwaway data directory, so they survive upstream refactors of
internal Go APIs. After rebasing the agentsview pin onto a newer upstream:

  1. rebuild (`make pricing-snapshot && make build` in agentsview/);
  2. run `python3 -m unittest scripts/test_agentsview_hacks.py -v`
     (AGENTSVIEW_BIN overrides the binary path);
  3. a failing test names the hack to re-apply. Once upstream covers a hack,
     the test keeps passing and the carried commit can be dropped.

Carried hacks (agentsview fork biggestbinary/agentsview, local/usage-accuracy-v2):
  * 13e93147 guarded-Sol pricing: USAi/Pi deployment names such as
    gpt-6.1-sol-latest-guardrails-defaultv2 must price like their base model
    instead of $0.00 (fixedPricingAliases in internal/pricing/supplemental.go).
  * ec06909c checkpoint credit: Copilot sessions with no session.shutdown and
    no session.usage_record still carry spend in session.usage_checkpoint
    totalNanoAiu; it is a last resort that never overrides shutdown totals or
    per-request receipts (applyCheckpointCredit in internal/parser/copilot.go).
Dropped upstream-covered hack: usage_record fallback (upstream #2537).
Optional/not carried: Pi claude- dot-to-dash model normalization.
"""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def find_binary():
    explicit = os.environ.get("AGENTSVIEW_BIN")
    if explicit:
        return Path(explicit).expanduser().resolve()
    for base in (ROOT, ROOT.parent):
        candidate = base / "agentsview/agentsview"
        if candidate.is_file():
            return candidate
    common = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        text=True, capture_output=True, check=False).stdout.strip()
    return Path(common).parent / "agentsview/agentsview" if common else ROOT / "agentsview/agentsview"


BINARY = find_binary()
START = '{"type":"session.start","data":{"sessionId":"%s"},"timestamp":"2026-09-04T17:00:00Z"}'
USER = '{"type":"user.message","data":{"content":"Hello"},"timestamp":"2026-09-04T17:00:01Z"}'
CHECKPOINT = '{"type":"session.usage_checkpoint","data":{"totalNanoAiu":%d},"timestamp":"2026-09-04T17:00:02Z"}'
SHUTDOWN = ('{"type":"session.shutdown","data":{"totalNanoAiu":100000000,"modelMetrics":'
            '{"gpt-5.6-sol":{"usage":{"inputTokens":10,"outputTokens":3}}}},'
            '"timestamp":"2026-09-04T17:00:03Z"}')
RECEIPT = ('{"type":"session.usage_record","timestamp":"2026-09-04T17:00:05Z","data":'
           '{"usage":{"model":"gpt-5.6-sol","inputTokens":20,"outputTokens":9}}}')


@unittest.skipUnless(BINARY.is_file(), f"agentsview binary not built: {BINARY}")
class AgentsviewHackTests(unittest.TestCase):
    def usage(self, copilot_lines=None, pi_models=()):
        tmp = Path(tempfile.mkdtemp(prefix="avhack-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(tmp)])
        (tmp / "home").mkdir()
        (tmp / "data").mkdir()
        if copilot_lines:
            session = tmp / "copilot/session-state/s1"
            session.mkdir(parents=True)
            (session / "events.jsonl").write_text("\n".join(copilot_lines) + "\n")
        (tmp / "pi/--tmp-x--").mkdir(parents=True)
        for index, model in enumerate(pi_models):
            lines = [
                {"type": "session", "version": 3, "id": f"pi-{index}",
                 "timestamp": "2026-10-01T12:00:00Z", "cwd": "/tmp/x"},
                {"type": "message", "id": "m1", "parentId": None,
                 "timestamp": "2026-10-01T12:00:01Z",
                 "message": {"role": "user", "content": "hi"}},
                {"type": "message", "id": "m2", "parentId": "m1",
                 "timestamp": "2026-10-01T12:00:02Z",
                 "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}],
                             "model": model, "usage": {"input": 100000, "output": 1000}}},
            ]
            (tmp / f"pi/--tmp-x--/s{index}.jsonl").write_text(
                "\n".join(json.dumps(line) for line in lines) + "\n")
        env = dict(os.environ, HOME=str(tmp / "home"), AGENTSVIEW_DATA_DIR=str(tmp / "data"),
                   COPILOT_DIR=str(tmp / "copilot"), PI_DIR=str(tmp / "pi"),
                   AGENTSVIEW_NO_DAEMON="1")
        for command in (["source", "sync"],):
            subprocess.run([str(BINARY), *command], env=env, cwd=tmp, check=True,
                           capture_output=True, timeout=120)
        out = subprocess.run(
            [str(BINARY), "usage", "daily", "--json", "--all", "--offline", "--breakdown",
             "--no-sync"], env=env, cwd=tmp, check=True, capture_output=True, text=True,
            timeout=120).stdout
        report = json.loads(out)
        models = {}
        for day in report["daily"]:
            for item in day["modelBreakdowns"]:
                entry = models.setdefault(item["modelName"], 0)
                models[item["modelName"]] = entry + item["cost"]["microdollars"]
        return report["totals"]["totalCost"]["microdollars"], models

    def test_guarded_sol_deployments_price_like_base_model(self):
        # Hack 13e93147. Includes gpt-6-sol, which the first attempt missed.
        for base in ("gpt-5.6-sol", "gpt-6-sol", "gpt-6.1-sol"):
            with self.subTest(base=base):
                guarded = base + "-latest-guardrails-defaultv2"
                # One model per run: Pi sessions with identical content collapse.
                _, base_models = self.usage(pi_models=(base,))
                _, guarded_models = self.usage(pi_models=(guarded,))
                self.assertGreater(base_models[base], 0, "base model must be priced")
                self.assertEqual(guarded_models[guarded], base_models[base],
                                 f"{guarded} must price exactly like {base}")

    def test_unknown_guardrails_suffix_stays_unpriced(self):
        # Aliases are exact; an unrecognised suffix must not be silently guessed.
        _, models = self.usage(pi_models=("gpt-6.1-sol-latest-guardrails-defaultv3",))
        self.assertEqual(models["gpt-6.1-sol-latest-guardrails-defaultv3"], 0)

    def test_checkpoint_credit_for_session_without_other_usage(self):
        # Hack ec06909c: 250,000,000 nanoAIU = $0.0025 = 2500 microdollars.
        total, models = self.usage([START % "cp-only", USER, CHECKPOINT % 100000000,
                                    CHECKPOINT % 250000000])
        self.assertEqual(total, 2500, "largest checkpoint total is the session credit")
        self.assertEqual(models, {"copilot": 2500})

    def test_checkpoint_never_overrides_shutdown_total(self):
        total, _ = self.usage([START % "cp-sd", USER, CHECKPOINT % 900000000, SHUTDOWN])
        self.assertEqual(total, 1000, "shutdown totalNanoAiu is authoritative")

    def test_checkpoint_never_overrides_per_request_receipts(self):
        # The checkpoint must change nothing: compare with the same session
        # minus the checkpoint, and require receipt tokens to be priced.
        for name, tail in (("receipt only", [RECEIPT]),
                           ("receipt after shutdown", [SHUTDOWN, RECEIPT])):
            with self.subTest(name):
                head = [START % "cp-rc", USER]
                baseline_total, baseline = self.usage([*head, *tail])
                self.assertGreater(baseline.get("gpt-5.6-sol", 0), 0,
                                   "receipt usage must be counted and priced")
                total, models = self.usage([*head, CHECKPOINT % 900000000, *tail])
                self.assertNotIn("copilot", models, "no synthesized checkpoint row")
                self.assertEqual((total, models), (baseline_total, baseline))


if __name__ == "__main__":
    unittest.main()
