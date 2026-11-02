#!/usr/bin/env python3
"""Tests for value-scorecard.py using only generic, non-identifying values."""

import contextlib
import datetime
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import tomllib
import unittest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("value_scorecard", HERE / "value-scorecard.py")
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)

TODAY = datetime.date(2026, 12, 1)


def run_main(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = vs.main(list(args))
    return code, out.getvalue(), err.getvalue()


def metric(value, status="observed"):
    return {"status": status, "value": value, "source": "test"}


def complete_record(**over):
    """A fully known synthetic record; tests mutate copies of it."""
    rec = {
        "schema": vs.SCHEMA,
        "run": {"id": "run-1", "kind": "pilot", "task_class": "bounded-change", "task_type": "feature"},
        "baseline": {
            "kind": "historical-observed",
            "scope": "same class",
            "quality_bar": "reviewed and accepted",
            "source_access": "same",
            "approved_by": "owner",
            "approved_at": datetime.date(2026, 11, 3),
            "hours": metric(10),
            "elapsed_hours": metric(40),
        },
        "rate": {"status": "observed", "value": 100.0, "source": "test", "approved_by": "owner",
                 "approved_at": datetime.date(2026, 11, 3)},
        "active_minutes": {k: metric(30) for k in vs.PHASES},
        "elapsed": {"elapsed_minutes": metric(600), "wait_minutes": metric(300)},
        "interventions": metric(3),
        "route": [{"role": "implementation", "model": "m-a", "route": "usai", "recorded": "actual"}],
        "usage": [
            {"role": "implementation", "model": "m-a", "route": "usai", "status": "observed",
             "input": 1_000_000, "output": 100_000, "source": "agentsview", "pricing": "p1"},
            {"role": "review", "model": "m-b", "route": "usai", "status": "observed", "retry": True,
             "input": 500_000, "output": 50_000, "source": "roborev", "pricing": "p2"},
        ],
        "pricing": [
            {"id": "p1", "model": "m-a", "input_per_mtok": 4.0, "output_per_mtok": 20.0,
             "effective_date": datetime.date(2026, 11, 1), "basis": "approved sheet",
             "approved_by": "owner", "approved_at": datetime.date(2026, 11, 2)},
            {"id": "p2", "model": "m-b", "input_per_mtok": 2.0, "output_per_mtok": 10.0,
             "effective_date": datetime.date(2026, 11, 1), "basis": "approved sheet",
             "approved_by": "owner", "approved_at": datetime.date(2026, 11, 2)},
        ],
        "runtime_cost_usd": metric(1.0),
        "setup": {"status": "allocated"},
        "shared_cost": [{"id": "setup-1", "description": "ingestion", "amount_usd": metric(100.0),
                         "share": 0.25, "basis": "per run of four"}],
        "findings": {"status": "observed", "source": "roborev"},
        "finding": [{"id": "1", "source": "roborev", "disposition": "confirmed"},
                    {"id": "2", "source": "roborev", "disposition": "invalid"}],
        "escaped_defects": {"status": "observed", "value": 0, "source": "test",
                            "window_start": datetime.date(2026, 11, 10),
                            "window_end": datetime.date(2026, 11, 24)},
        "operating": {"accepted_tasks": metric(1), "escalations": metric(0), "rework_minutes": metric(10)},
        "cash_savings_usd": {"status": "unknown"},
        "replication": {k: {"status": "not-applicable"} for k in vs.REPLICATION},
        "pilot": {"status": "defined", "defined_by": "owner", "defined_at": datetime.date(2026, 11, 3),
                  "threshold": "owner text"},
    }
    rec.update(over)
    return rec


class MetricRules(unittest.TestCase):
    def test_unknown_with_value_is_an_error(self):
        rec = complete_record(interventions={"status": "unknown", "value": 0})
        errors, _ = vs.validate(rec)
        self.assertTrue(any("interventions" in e and "unknown" in e for e in errors), errors)

    def test_observed_needs_value_and_source(self):
        rec = complete_record(interventions={"status": "observed"})
        errors, _ = vs.validate(rec)
        self.assertTrue(any("interventions" in e for e in errors), errors)

    def test_negative_value_rejected(self):
        rec = complete_record(interventions=metric(-1))
        errors, _ = vs.validate(rec)
        self.assertTrue(any("interventions" in e for e in errors), errors)

    def test_missing_section_is_unknown_gap_not_zero(self):
        rec = complete_record()
        del rec["interventions"]
        errors, gaps = vs.validate(rec)
        self.assertEqual(errors, [])
        self.assertTrue(any("interventions" in g for g in gaps))
        self.assertIsNone(vs.build_report(rec, TODAY)["measures"]["interventions"])

    def test_unexpected_key_rejected(self):
        rec = complete_record()
        rec["active_minutes"]["discovry"] = metric(1)
        errors, _ = vs.validate(rec)
        self.assertTrue(any("discovry" in e for e in errors), errors)

    def test_complete_record_has_no_errors_or_gaps(self):
        errors, gaps = vs.validate(complete_record(), TODAY)
        self.assertEqual((errors, gaps), ([], []))


class Computation(unittest.TestCase):
    def test_capacity_and_cost_equivalent(self):
        rep = vs.build_report(complete_record(), TODAY)
        self.assertEqual(rep["active_minutes_total"], 120)
        self.assertEqual(rep["capacity_released_hours"], 8.0)
        # tokens: 4 + 2 (m-a) + 1 + 0.5 (m-b) = 7.5 ; + runtime 1 ; + setup 100*0.25
        self.assertAlmostEqual(rep["model_cost_usd"], 7.5 + 0.0, places=2)
        self.assertAlmostEqual(rep["incremental_cost_usd"], 7.5 + 1.0 + 25.0, places=2)
        self.assertAlmostEqual(rep["cost_equivalent_usd"], 800.0 - 33.5, places=2)
        self.assertIsNone(rep["cash_savings_usd"])
        self.assertEqual(rep["confirmed_findings"], 1)
        self.assertEqual(rep["tokens_by_role"]["review"]["input"], 500_000)
        self.assertEqual(rep["retry_tokens"]["input"], 500_000)

    def test_unknown_phase_blocks_capacity(self):
        rec = complete_record()
        rec["active_minutes"]["review_rework"] = {"status": "unknown"}
        rep = vs.build_report(rec, TODAY)
        self.assertIsNone(rep["capacity_released_hours"])
        self.assertIsNone(rep["cost_equivalent_usd"])
        self.assertEqual(rep["active_minutes_known_floor"], 90)

    def test_not_applicable_phase_counts_zero_minutes(self):
        rec = complete_record()
        rec["active_minutes"]["implementation"] = {"status": "not-applicable"}
        rep = vs.build_report(rec, TODAY)
        self.assertEqual(rep["active_minutes_total"], 90)
        self.assertEqual(rep["capacity_released_hours"], 10 - 1.5)

    def test_unapproved_pricing_leaves_cost_unknown(self):
        rec = complete_record()
        rec["pricing"][0].pop("approved_by")
        rep = vs.build_report(rec, TODAY)
        self.assertIsNone(rep["model_cost_usd"])
        self.assertIsNone(rep["cost_equivalent_usd"])
        self.assertEqual(rep["capacity_released_hours"], 8.0)

    def test_unknown_usage_status_has_no_tokens_counted_as_zero(self):
        rec = complete_record()
        rec["usage"].append({"role": "review", "model": "m-b", "route": "usai", "status": "unknown"})
        rep = vs.build_report(rec, TODAY)
        self.assertIsNone(rep["model_cost_usd"])
        self.assertEqual(rep["tokens_by_role"]["review"]["input"], 500_000)
        self.assertEqual(rep["usage_unknown_entries"], 1)

    def test_replay_baseline_is_not_a_control(self):
        rec = complete_record()
        rec["baseline"]["kind"] = "agent-first-replay"
        rep = vs.build_report(rec, TODAY)
        self.assertIsNone(rep["capacity_released_hours"])
        self.assertTrue(any("independent" in b for b in rep["claims"]["faster delivery"]["blockers"]))

    def test_setup_unknown_blocks_cost_equivalent_not_capacity(self):
        rec = complete_record(setup={"status": "unknown"}, shared_cost=[])
        rep = vs.build_report(rec, TODAY)
        self.assertEqual(rep["capacity_released_hours"], 8.0)
        self.assertIsNone(rep["cost_equivalent_usd"])

    def test_setup_none_counts_zero_allocation(self):
        rec = complete_record(setup={"status": "none"}, shared_cost=[])
        rep = vs.build_report(rec, TODAY)
        self.assertAlmostEqual(rep["cost_equivalent_usd"], 800.0 - 8.5, places=2)

    def test_accepted_tasks_per_engineer_hour(self):
        rep = vs.build_report(complete_record(), TODAY)
        self.assertEqual(rep["accepted_tasks_per_engineer_hour"], 0.5)


class Claims(unittest.TestCase):
    def test_complete_pilot_is_evaluable_not_proven(self):
        rep = vs.build_report(complete_record(), TODAY)
        for claim in rep["claims"].values():
            self.assertEqual(claim["blockers"], [])
            self.assertEqual(claim["status"], "evaluable against the owner threshold")

    def test_feasibility_run_never_supports_organization_claims(self):
        rec = complete_record()
        rec["run"]["kind"] = "feasibility"
        rep = vs.build_report(rec, TODAY)
        for claim in rep["claims"].values():
            self.assertTrue(any("feasibility" in b for b in claim["blockers"]))

    def test_missing_pilot_threshold_blocks_all(self):
        rec = complete_record(pilot={"status": "undefined"})
        rep = vs.build_report(rec, TODAY)
        for claim in rep["claims"].values():
            self.assertTrue(any("threshold" in b for b in claim["blockers"]))

    def test_open_defect_window_blocks_equal_quality(self):
        rep = vs.build_report(complete_record(), datetime.date(2026, 11, 15))
        self.assertTrue(any("window" in b for b in rep["claims"]["equal quality"]["blockers"]))
        self.assertEqual(rep["claims"]["faster delivery"]["blockers"], [])

    def test_unapproved_baseline_blocks(self):
        rec = complete_record()
        rec["baseline"].pop("approved_by")
        rep = vs.build_report(rec, TODAY)
        self.assertTrue(any("baseline" in b for b in rep["claims"]["faster delivery"]["blockers"]))

    def test_open_finding_is_a_gap(self):
        rec = complete_record()
        rec["finding"].append({"id": "3", "source": "roborev", "disposition": "open"})
        _, gaps = vs.validate(rec, TODAY)
        self.assertTrue(any("open" in g for g in gaps))


class ReviewFixes(unittest.TestCase):
    def test_usage_needs_input_and_output(self):
        rec = complete_record()
        del rec["usage"][0]["output"]
        errors, _ = vs.validate(rec, TODAY)
        self.assertTrue(any("output" in e for e in errors), errors)

    def test_open_finding_blocks_equal_quality_in_report(self):
        rec = complete_record()
        rec["finding"].append({"id": "3", "source": "roborev", "disposition": "open"})
        rep = vs.build_report(rec, TODAY)
        self.assertEqual(rep["claims"]["equal quality"]["status"], vs.NOT_CLAIMABLE)

    def test_baseline_without_comparability_fields_is_not_usable(self):
        rec = complete_record()
        del rec["baseline"]["scope"]
        del rec["baseline"]["source_access"]
        rep = vs.build_report(rec, TODAY)
        self.assertIsNone(rep["capacity_released_hours"])
        self.assertTrue(any("scope" in b for b in rep["claims"]["faster delivery"]["blockers"]))

    def test_wrong_section_types_are_errors_not_crashes(self):
        for section in ("baseline", "run", "active_minutes", "pilot"):
            rec = complete_record()
            rec[section] = "missing"
            errors, _ = vs.validate(rec, TODAY)
            self.assertTrue(any(section in e for e in errors), (section, errors))

    def test_allocated_without_entries_and_undefined_pilot_are_gaps(self):
        rec = complete_record(shared_cost=[])
        _, gaps = vs.validate(rec, TODAY)
        self.assertTrue(any("shared_cost" in g for g in gaps), gaps)
        _, gaps = vs.validate(complete_record(pilot={"status": "undefined"}), TODAY)
        self.assertTrue(any("pilot" in g for g in gaps), gaps)


class Structure(unittest.TestCase):
    def test_unknown_findings_forbid_entries(self):
        rec = complete_record(findings={"status": "unknown"})
        errors, _ = vs.validate(rec, TODAY)
        self.assertTrue(any("finding" in e for e in errors), errors)

    def test_duplicate_pricing_and_dangling_reference(self):
        rec = complete_record()
        rec["usage"][0]["pricing"] = "nope"
        errors, _ = vs.validate(rec, TODAY)
        self.assertTrue(any("nope" in e for e in errors), errors)

    def test_share_out_of_range(self):
        rec = complete_record()
        rec["shared_cost"][0]["share"] = 1.5
        errors, _ = vs.validate(rec, TODAY)
        self.assertTrue(any("share" in e for e in errors), errors)

    def test_observed_defects_require_window(self):
        rec = complete_record()
        del rec["escaped_defects"]["window_end"]
        errors, _ = vs.validate(rec, TODAY)
        self.assertTrue(any("window" in e for e in errors), errors)

    def test_bad_role_and_disposition(self):
        rec = complete_record()
        rec["usage"][0]["role"] = "bogus"
        rec["finding"][0]["disposition"] = "bogus"
        errors, _ = vs.validate(rec, TODAY)
        self.assertEqual(len([e for e in errors if "bogus" in e]), 2, errors)


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".gitignore").write_text("private/\n")
        self.private = self.root / "private"

    def init(self, run_id, *extra):
        return run_main("init", run_id, "--root", str(self.private), *extra)

    def test_init_writes_private_template_that_validates_with_gaps(self):
        code, out, err = self.init("run-a", "--task-class", "bounded-change")
        self.assertEqual(code, 0, err)
        card = self.private / "run-a" / "scorecard.toml"
        self.assertEqual(stat.S_IMODE(card.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(card.parent.stat().st_mode), 0o700)
        self.assertTrue((card.parent / "COLLECT.md").exists())
        data = tomllib.loads(card.read_text())
        self.assertEqual(data["schema"], vs.SCHEMA)
        code, out, err = run_main("check", str(card))
        self.assertEqual(code, 0, err)
        self.assertIn("unknown", out)
        code, _, _ = run_main("check", str(card), "--require-complete")
        self.assertEqual(code, 1)

    def test_init_refuses_tracked_destination_and_existing_run(self):
        code, _, err = run_main("init", "run-a", "--root", str(self.root / "tracked"))
        self.assertEqual(code, 1)
        self.assertIn("not ignored", err)
        self.assertEqual(self.init("run-a")[0], 0)
        self.assertEqual(self.init("run-a")[0], 1)

    def test_init_round_trips_special_characters(self):
        text = 'owner "approved" \\ change'
        self.assertEqual(self.init("run-q", "--task-class", text, "--task-type", "t\u00e9")[0], 0)
        data = tomllib.loads((self.private / "run-q" / "scorecard.toml").read_text())
        self.assertEqual(data["run"]["task_class"], text)

    def test_wrong_section_type_exits_with_diagnostic(self):
        self.private.mkdir()
        bad = self.private / "bad.toml"
        bad.write_text('schema = "%s"\nbaseline = "missing"\n' % vs.SCHEMA)
        code, _, err = run_main("check", str(bad))
        self.assertEqual(code, 1)
        self.assertIn("baseline", err)

    def test_init_rejects_path_like_run_id(self):
        self.assertEqual(self.init("../x")[0], 1)

    def test_report_json_and_text(self):
        self.init("run-a")
        card = str(self.private / "run-a" / "scorecard.toml")
        code, out, _ = run_main("report", card, "--json")
        self.assertEqual(code, 0)
        rep = json.loads(out)
        self.assertIsNone(rep["capacity_released_hours"])
        code, out, _ = run_main("report", card)
        self.assertEqual(code, 0)
        self.assertIn("unknown", out)
        self.assertIn("not an invoice", out)

    def test_check_reports_invalid_toml_and_wrong_schema(self):
        bad = self.private / "bad.toml"
        self.private.mkdir()
        bad.write_text('schema = "other"\n')
        code, _, err = run_main("check", str(bad))
        self.assertEqual(code, 1)
        self.assertIn("schema", err)

    def test_rollup_flags_double_counted_shared_cost(self):
        for name, share in (("a", 0.6), ("b", 0.6)):
            self.init(name)
            card = self.private / name / "scorecard.toml"
            card.write_text(card.read_text() + f"""
[setup]
status = "allocated"
[[shared_cost]]
id = "setup-1"
description = "x"
share = {share}
basis = "test"
[shared_cost.amount_usd]
status = "observed"
value = 100.0
source = "test"
""".replace("[setup]\nstatus = \"allocated\"\n", ""))
        # replace the template's setup status
        for name in ("a", "b"):
            card = self.private / name / "scorecard.toml"
            text = card.read_text().replace('[setup]\nstatus = "unknown"', '[setup]\nstatus = "allocated"')
            card.write_text(text)
        code, out, err = run_main("rollup", str(self.private))
        self.assertEqual(code, 1)
        self.assertIn("setup-1", err)

    def test_rollup_counts_runs_and_stratifies(self):
        self.init("a", "--task-type", "feature")
        self.init("b", "--task-type", "refinement")
        code, out, _ = run_main("rollup", str(self.private), "--json")
        self.assertEqual(code, 0)
        roll = json.loads(out)
        self.assertEqual(roll["runs"], 2)
        self.assertIsNone(roll["by_task_type"]["feature"]["accepted_tasks"])
        self.assertEqual(roll["by_task_type"]["feature"]["accepted_task_runs"], 0)
        self.assertEqual(sorted(roll["by_task_type"]), ["feature", "refinement"])
        self.assertIn("not an organization-wide", roll["caveat"])


if __name__ == "__main__":
    unittest.main()
