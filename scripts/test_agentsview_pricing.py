#!/usr/bin/env python3
"""Black-box tests for AgentsView's guarded-Sol pricing configuration.

AgentsView runs as plain upstream with no carried patches. Guarded-Sol
deployments are priced through upstream `custom_model_pricing.price_as`
(kenn-io/agentsview#2951); `local_env.py configure-agentsview-pricing` writes
the `gpt-*-sol-latest-guardrails-defaultv2` mappings. These tests run the built
binary against synthetic Pi sessions in a throwaway data directory with the
same mappings, so they survive upstream refactors of internal Go APIs.

After moving the agentsview pin, rebuild (`make build` in agentsview/) and run
`python3 -m unittest scripts/test_agentsview_pricing.py -v`
(AGENTSVIEW_BIN overrides the binary path).
"""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import local_env  # noqa: E402


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


@unittest.skipUnless(BINARY.is_file(), f"agentsview binary not built: {BINARY}")
class AgentsviewPricingTests(unittest.TestCase):
    def usage(self, pi_models=()):
        tmp = Path(tempfile.mkdtemp(prefix="avpricing-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(tmp)])
        (tmp / "home").mkdir()
        (tmp / "data").mkdir()
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
        (tmp / "data/config.toml").write_text("".join(
            f'[custom_model_pricing."{model}"]\nprice_as = "{target}"\n\n'
            for model, target in local_env.GUARDED_SOL_PRICE_AS.items()))
        env = dict(os.environ, HOME=str(tmp / "home"), AGENTSVIEW_DATA_DIR=str(tmp / "data"),
                   COPILOT_DIR=str(tmp / "copilot"), PI_DIR=str(tmp / "pi"),
                   AGENTSVIEW_NO_DAEMON="1")
        subprocess.run([str(BINARY), "source", "sync"], env=env, cwd=tmp, check=True,
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


if __name__ == "__main__":
    unittest.main()
