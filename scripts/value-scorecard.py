#!/usr/bin/env python3
"""Per-run value scorecard: private records, validation and reports.

  init    create a private scorecard.toml and COLLECT.md for one run
  check   validate a scorecard and list what is still unknown
  report  compute capacity released, cost-equivalent and claim blockers
  rollup  combine private runs, stratified by task type

A measure is observed, estimated, unknown or not-applicable. Unknown is never
zero. Records hold run data and live under an ignored private directory; this
tool carries no ticket, rate or receipt. See context/value-scorecard.md.
"""

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib


SCHEMA = "engineer.value-scorecard/v1"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = REPO_ROOT / ".local" / "value-scorecard"
PHASES = ("discovery", "refinement", "implementation", "review_rework")
ROLES = ("discovery", "refinement", "implementation", "review", "rework", "other")
REPLICATION = (
    "approval_lead_time_minutes",
    "clean_install_minutes",
    "operator_touch_minutes",
    "source_onboarding_minutes",
    "first_accepted_change_minutes",
)
STATUSES = ("observed", "estimated", "unknown", "not-applicable")
RUN_KINDS = ("feasibility", "pilot", "replication")
BASELINE_KINDS = ("historical-observed", "estimate", "agent-first-replay", "missing")
DISPOSITIONS = ("confirmed", "invalid", "stale", "out-of-scope", "open")
TOKEN_FIELDS = ("input", "output", "cache_read", "cache_write")
RATE_FIELDS = {"input": "input_per_mtok", "output": "output_per_mtok",
               "cache_read": "cache_read_per_mtok", "cache_write": "cache_write_per_mtok"}
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
CLAIMS = ("faster delivery", "equal quality", "positive ROI")
EVALUABLE = "evaluable against the owner threshold"
NOT_CLAIMABLE = "not claimable"


class ScorecardError(Exception):
    pass


# -- validation ---------------------------------------------------------------

def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _keys(d, allowed, path, errors):
    for key in d:
        if key not in allowed:
            errors.append(f"{path}: unexpected key {key!r}")


def _metric(m, path, errors, gaps, extra=()):
    """Validate one measure; return its number when observed/estimated."""
    if m is None:
        gaps.append(f"{path}: unknown (not recorded)")
        return None
    if not isinstance(m, dict):
        errors.append(f"{path}: must be a table with status")
        return None
    _keys(m, {"status", "value", "source", "note", *extra}, path, errors)
    status = m.get("status")
    if status not in STATUSES:
        errors.append(f"{path}: status must be one of {', '.join(STATUSES)}")
        return None
    if status in ("unknown", "not-applicable"):
        if "value" in m:
            errors.append(f"{path}: {status} must not carry a value (unknown is not zero)")
        if status == "unknown":
            gaps.append(f"{path}: unknown")
        return None
    value = m.get("value")
    if not _num(value) or value < 0:
        errors.append(f"{path}: {status} needs a non-negative numeric value")
        return None
    if not (isinstance(m.get("source"), str) and m["source"].strip()):
        errors.append(f"{path}: {status} needs a source")
        return None
    return value


def _baseline_blockers(base):
    kind = base.get("kind", "missing")
    if kind == "agent-first-replay":
        return ["baseline is an agent-first replay, not an independent control"]
    if kind not in ("historical-observed", "estimate"):
        return ["baseline: no comparable baseline agreed"]
    out = [] if _approved(base) else ["baseline: not approved by the owner"]
    out += [f"baseline.{f}: not recorded" for f in ("scope", "quality_bar", "source_access") if not base.get(f)]
    return out


def _approved(d):
    return bool(d and d.get("approved_by") and d.get("approved_at"))


def _list(rec, name, errors):
    value = rec.get(name, [])
    if not isinstance(value, list) or not all(isinstance(x, dict) for x in value):
        errors.append(f"{name}: must be an array of tables")
        return []
    return value


def validate(rec, today=None):
    """Return (errors, gaps). Errors are malformed data; gaps are unknowns."""
    errors, gaps = [], []
    tables = ("run", "baseline", "rate", "active_minutes", "elapsed", "interventions", "runtime_cost_usd",
              "setup", "findings", "escaped_defects", "operating", "cash_savings_usd", "replication", "pilot")
    for name in tables:
        if name in rec and not isinstance(rec[name], dict):
            errors.append(f"{name}: must be a table")
    if errors:
        return errors, gaps
    _keys(rec, {"schema", "run", "baseline", "rate", "active_minutes", "elapsed", "interventions",
                "route", "usage", "pricing", "runtime_cost_usd", "setup", "shared_cost",
                "findings", "finding", "escaped_defects", "operating", "cash_savings_usd",
                "replication", "pilot"}, "record", errors)
    if rec.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    run = rec.get("run") or {}
    _keys(run, {"id", "kind", "task_class", "task_type", "observation_note"}, "run", errors)
    if not RUN_ID_RE.match(str(run.get("id", ""))):
        errors.append("run.id must be a generic identifier (letters, digits, . _ -)")
    if run.get("kind") not in RUN_KINDS:
        errors.append(f"run.kind must be one of {', '.join(RUN_KINDS)}")
    for field in ("task_class", "task_type"):
        if not run.get(field):
            errors.append(f"run.{field} is required")

    base = rec.get("baseline")
    if base is None or base.get("kind", "missing") == "missing":
        gaps.append("baseline: missing (no comparable baseline agreed)")
    if base:
        _keys(base, {"kind", "scope", "quality_bar", "source_access", "approved_by", "approved_at",
                     "hours", "elapsed_hours", "note"}, "baseline", errors)
        if base.get("kind") not in BASELINE_KINDS:
            errors.append(f"baseline.kind must be one of {', '.join(BASELINE_KINDS)}")
        if base.get("kind") not in (None, "missing"):
            if not _approved(base):
                gaps.append("baseline: not approved by the owner")
            for field in ("scope", "quality_bar", "source_access"):
                if not base.get(field):
                    gaps.append(f"baseline.{field}: unknown")
            for field in ("hours", "elapsed_hours"):
                _metric(base.get(field), f"baseline.{field}", errors, gaps)
    rate = rec.get("rate")
    _metric(rate, "rate", errors, gaps, ("approved_by", "approved_at"))
    if rate and rate.get("status") in ("observed", "estimated") and not _approved(rate):
        gaps.append("rate: not approved by the owner")

    active = rec.get("active_minutes") or {}
    _keys(active, set(PHASES), "active_minutes", errors)
    for phase in PHASES:
        _metric(active.get(phase), f"active_minutes.{phase}", errors, gaps)
    elapsed = rec.get("elapsed") or {}
    _keys(elapsed, {"elapsed_minutes", "wait_minutes"}, "elapsed", errors)
    for field in ("elapsed_minutes", "wait_minutes"):
        _metric(elapsed.get(field), f"elapsed.{field}", errors, gaps)
    _metric(rec.get("interventions"), "interventions", errors, gaps)

    _validate_usage(rec, errors, gaps)
    _metric(rec.get("runtime_cost_usd"), "runtime_cost_usd", errors, gaps)
    _validate_setup(rec, errors, gaps)
    _validate_quality(rec, errors, gaps, today)

    op = rec.get("operating") or {}
    _keys(op, {"accepted_tasks", "escalations", "rework_minutes"}, "operating", errors)
    for field in ("accepted_tasks", "escalations", "rework_minutes"):
        _metric(op.get(field), f"operating.{field}", errors, gaps)
    _metric(rec.get("cash_savings_usd"), "cash_savings_usd", errors, [])
    repl = rec.get("replication") or {}
    _keys(repl, set(REPLICATION), "replication", errors)
    for field in REPLICATION:
        sink = gaps if run.get("kind") == "replication" else []
        _metric(repl.get(field), f"replication.{field}", errors, sink)
    pilot = rec.get("pilot") or {}
    _keys(pilot, {"status", "defined_by", "defined_at", "threshold"}, "pilot", errors)
    if pilot.get("status") not in (None, "defined", "undefined"):
        errors.append("pilot.status must be defined or undefined")
    if not (pilot.get("status") == "defined" and pilot.get("defined_by") and pilot.get("defined_at")
            and pilot.get("threshold")):
        gaps.append("pilot: success threshold not defined with the owner")
    return errors, gaps


def _validate_usage(rec, errors, gaps):
    pricing = {}
    for i, p in enumerate(_list(rec, "pricing", errors)):
        path = f"pricing[{i}]"
        _keys(p, {"id", "model", "input_per_mtok", "output_per_mtok", "cache_read_per_mtok",
                  "cache_write_per_mtok", "effective_date", "basis", "approved_by", "approved_at"},
              path, errors)
        if not p.get("id") or p["id"] in pricing:
            errors.append(f"{path}: id is required and unique")
        pricing[p.get("id")] = p
        for field in ("model", "basis"):
            if not p.get(field):
                errors.append(f"{path}.{field} is required")
        if not isinstance(p.get("effective_date"), datetime.date):
            errors.append(f"{path}.effective_date must be a TOML date")
        for field in RATE_FIELDS.values():
            if field in p and (not _num(p[field]) or p[field] < 0):
                errors.append(f"{path}.{field} must be a non-negative number")
        if bool(p.get("approved_by")) != bool(p.get("approved_at")):
            errors.append(f"{path}: approved_by and approved_at go together")
    route = _list(rec, "route", errors)
    if not route:
        gaps.append("route: no actual USAi route/model recorded")
    for i, r in enumerate(route):
        _keys(r, {"role", "model", "route", "recorded"}, f"route[{i}]", errors)
        if r.get("role") not in ROLES:
            errors.append(f"route[{i}].role {r.get('role')!r} must be one of {', '.join(ROLES)}")
        if r.get("recorded") not in ("actual", "planned"):
            errors.append(f"route[{i}].recorded must be actual or planned")
    usage = _list(rec, "usage", errors)
    if not usage:
        gaps.append("usage: no attributable token entries")
    for i, u in enumerate(usage):
        path = f"usage[{i}]"
        _keys(u, {"role", "model", "route", "status", "retry", "source", "pricing", *TOKEN_FIELDS}, path, errors)
        if u.get("role") not in ROLES:
            errors.append(f"{path}.role {u.get('role')!r} must be one of {', '.join(ROLES)}")
        if u.get("status") not in ("observed", "estimated", "unknown"):
            errors.append(f"{path}.status must be observed, estimated or unknown")
            continue
        if u["status"] == "unknown":
            gaps.append(f"{path}: unknown tokens for {u.get('role')}")
            if any(f in u for f in TOKEN_FIELDS):
                errors.append(f"{path}: unknown must not carry token counts (unknown is not zero)")
            continue
        for field in ("model", "source"):
            if not u.get(field):
                errors.append(f"{path}.{field} is required")
        for field in TOKEN_FIELDS:
            if field in u and (not isinstance(u[field], int) or isinstance(u[field], bool) or u[field] < 0):
                errors.append(f"{path}.{field} must be a non-negative integer")
        for field in ("input", "output"):
            if field not in u:
                errors.append(f"{path}.{field} is required (cache counts default to 0; use status unknown otherwise)")
        ref = u.get("pricing")
        if ref is None:
            gaps.append(f"{path}: no pricing basis")
        elif ref not in pricing:
            errors.append(f"{path}.pricing {ref!r} matches no pricing entry")
        elif pricing[ref].get("model") != u.get("model"):
            errors.append(f"{path}.pricing {ref!r} is for a different model")
        elif not _approved(pricing[ref]):
            gaps.append(f"{path}: pricing {ref!r} not approved")


def _validate_setup(rec, errors, gaps):
    setup = rec.get("setup") or {}
    _keys(setup, {"status"}, "setup", errors)
    status = setup.get("status", "unknown")
    if status not in ("unknown", "none", "allocated"):
        errors.append("setup.status must be unknown, none or allocated")
    if status == "unknown":
        gaps.append("setup: unknown (shared setup/ingestion allocation not decided)")
    shared = _list(rec, "shared_cost", errors)
    if status == "allocated" and not shared:
        gaps.append("setup: allocated but no shared_cost entries")
    if status != "allocated" and shared:
        errors.append("shared_cost entries require setup.status = allocated")
    ids = set()
    for i, s in enumerate(shared):
        path = f"shared_cost[{i}]"
        _keys(s, {"id", "description", "amount_usd", "share", "basis"}, path, errors)
        if not s.get("id") or s["id"] in ids:
            errors.append(f"{path}.id is required and unique")
        ids.add(s.get("id"))
        if not (_num(s.get("share")) and 0 < s["share"] <= 1):
            errors.append(f"{path}.share must be a fraction above 0 and at most 1")
        if not s.get("basis"):
            errors.append(f"{path}.basis is required (state the allocation rule)")
        _metric(s.get("amount_usd"), f"{path}.amount_usd", errors, gaps)


def _validate_quality(rec, errors, gaps, today):
    findings = rec.get("findings") or {}
    _keys(findings, {"status", "source"}, "findings", errors)
    fstatus = findings.get("status", "unknown")
    entries = _list(rec, "finding", errors)
    if fstatus not in ("observed", "unknown"):
        errors.append("findings.status must be observed or unknown")
    if fstatus == "unknown":
        gaps.append("findings: unknown (review findings not yet collected)")
        if entries:
            errors.append("findings is unknown but finding entries exist")
    elif fstatus == "observed" and not findings.get("source"):
        errors.append("findings: observed needs a source")
    for i, f in enumerate(entries):
        path = f"finding[{i}]"
        _keys(f, {"id", "source", "disposition", "role"}, path, errors)
        if f.get("disposition") not in DISPOSITIONS:
            errors.append(f"{path}.disposition {f.get('disposition')!r} must be one of {', '.join(DISPOSITIONS)}")
        elif f["disposition"] == "open":
            gaps.append(f"{path}: disposition open (confirm, invalidate or defer it)")
    esc = rec.get("escaped_defects")
    value = _metric(esc, "escaped_defects", errors, gaps, ("window_start", "window_end"))
    if esc and esc.get("status") in ("observed", "estimated"):
        ws, we = esc.get("window_start"), esc.get("window_end")
        if not (isinstance(ws, datetime.date) and isinstance(we, datetime.date) and ws <= we):
            errors.append("escaped_defects: a stated observation window (window_start <= window_end) is required")
        elif today and today < we:
            gaps.append(f"escaped_defects: observation window open until {we}")


# -- report -------------------------------------------------------------------

def _val(m):
    if isinstance(m, dict) and m.get("status") in ("observed", "estimated"):
        v = m.get("value")
        if _num(v) and v >= 0:
            return v
    return None


def _usage_cost(rec):
    """Model cost in USD from approved pricing, or None when anything is unknown."""
    usage = rec.get("usage") or []
    if not usage:
        return None
    pricing = {p.get("id"): p for p in rec.get("pricing") or []}
    total = 0.0
    for u in usage:
        p = pricing.get(u.get("pricing"))
        if u.get("status") not in ("observed", "estimated") or not _approved(p):
            return None
        for field, rate in RATE_FIELDS.items():
            if u.get(field):
                if not _num(p.get(rate)):
                    return None
                total += u[field] * p[rate] / 1_000_000
    return total


def _shared_cost(rec):
    status = (rec.get("setup") or {}).get("status", "unknown")
    if status == "none":
        return 0.0
    if status != "allocated":
        return None
    entries = rec.get("shared_cost") or []
    if not entries:
        return None
    total = 0.0
    for s in entries:
        amount = _val(s.get("amount_usd"))
        if amount is None or not _num(s.get("share")):
            return None
        total += amount * s["share"]
    return total


def _tokens(rec):
    by_role, retry = {}, dict.fromkeys(TOKEN_FIELDS, 0)
    unknown = 0
    for u in rec.get("usage") or []:
        if u.get("status") == "unknown":
            unknown += 1
            continue
        bucket = by_role.setdefault(u.get("role"), dict.fromkeys(TOKEN_FIELDS, 0))
        for field in TOKEN_FIELDS:
            bucket[field] += u.get(field, 0)
            if u.get("retry"):
                retry[field] += u.get(field, 0)
    return by_role, retry, unknown


def _claims(rec, today, derived):
    run, base, pilot = rec.get("run") or {}, rec.get("baseline") or {}, rec.get("pilot") or {}
    common = []
    if run.get("kind") == "feasibility":
        common.append("feasibility run: one ticket does not establish an organization-wide result")
    if pilot.get("status") != "defined" or not (pilot.get("defined_by") and pilot.get("threshold")):
        common.append("pilot and success threshold not defined with the owner")
    common += _baseline_blockers(base)
    claims = {name: list(common) for name in CLAIMS}
    if derived["active_minutes_total"] is None or _val((rec.get("elapsed") or {}).get("elapsed_minutes")) is None:
        claims["faster delivery"].append("agent-assisted active or elapsed time unknown")
    if _val(base.get("elapsed_hours")) is None:
        claims["faster delivery"].append("baseline elapsed time unknown")
    quality = claims["equal quality"]
    if (rec.get("findings") or {}).get("status") != "observed":
        quality.append("review findings not collected")
    esc = rec.get("escaped_defects") or {}
    if _val(esc) is None:
        quality.append("escaped defects unknown")
    elif isinstance(esc.get("window_end"), datetime.date) and today and today < esc["window_end"]:
        quality.append(f"escaped-defect observation window open until {esc['window_end']}")
    if any(f.get("disposition") == "open" for f in rec.get("finding") or []):
        quality.append("review findings still open")
    roi = claims["positive ROI"]
    if derived["cost_equivalent_usd"] is None:
        roi.append("cost-equivalent unknown (hours, approved rate, pricing or setup allocation missing)")
    return {
        name: {"status": EVALUABLE if not blockers else NOT_CLAIMABLE, "blockers": blockers}
        for name, blockers in claims.items()
    }


def build_report(rec, today=None):
    today = today or datetime.date.today()
    active = rec.get("active_minutes") or {}
    known = [0 if (active.get(p) or {}).get("status") == "not-applicable" else _val(active.get(p))
             for p in PHASES]
    total = sum(known) if all(v is not None for v in known) else None
    floor = sum(v for v in known if v is not None)  # not-applicable phases count as 0
    base = rec.get("baseline") or {}
    base_hours = _val(base.get("hours")) if not _baseline_blockers(base) else None
    capacity = base_hours - total / 60 if base_hours is not None and total is not None else None
    model_cost = _usage_cost(rec)
    runtime = _val(rec.get("runtime_cost_usd"))
    shared = _shared_cost(rec)
    parts = (model_cost, runtime, shared)
    incremental = sum(parts) if all(p is not None for p in parts) else None
    rate = rec.get("rate") or {}
    rate_value = _val(rate) if _approved(rate) else None
    equivalent = None
    if capacity is not None and rate_value is not None and incremental is not None:
        equivalent = capacity * rate_value - incremental
    by_role, retry, unknown = _tokens(rec)
    op = rec.get("operating") or {}
    accepted = _val(op.get("accepted_tasks"))
    findings = rec.get("finding") or []
    observed = (rec.get("findings") or {}).get("status") == "observed"
    elapsed = rec.get("elapsed") or {}
    derived = {
        "schema": SCHEMA,
        "run": rec.get("run"),
        "baseline_kind": base.get("kind", "missing"),
        "active_minutes_total": total,
        "active_minutes_known_floor": floor,
        "active_minutes": {p: _val(active.get(p)) for p in PHASES},
        "capacity_released_hours": capacity,
        "model_cost_usd": model_cost,
        "runtime_cost_usd": runtime,
        "shared_cost_allocated_usd": shared,
        "incremental_cost_usd": incremental,
        "cost_equivalent_usd": equivalent,
        "cash_savings_usd": _val(rec.get("cash_savings_usd")),
        "tokens_by_role": by_role,
        "retry_tokens": retry,
        "usage_unknown_entries": unknown,
        "confirmed_findings": sum(f.get("disposition") == "confirmed" for f in findings) if observed else None,
        "accepted_tasks_per_engineer_hour": accepted / (total / 60) if accepted is not None and total else None,
        "measures": {
            "interventions": _val(rec.get("interventions")),
            "elapsed_minutes": _val(elapsed.get("elapsed_minutes")),
            "wait_minutes": _val(elapsed.get("wait_minutes")),
            "escaped_defects": _val(rec.get("escaped_defects")),
            "escalations": _val(op.get("escalations")),
            "rework_minutes": _val(op.get("rework_minutes")),
            **{k: _val((rec.get("replication") or {}).get(k)) for k in REPLICATION},
        },
    }
    derived["claims"] = _claims(rec, today, derived)
    return derived


def _fmt(value, unit=""):
    if value is None:
        return "unknown"
    return f"{value:,.2f}{unit}" if isinstance(value, float) else f"{value:,}{unit}"


def render_report(rep):
    claims = rep["claims"]
    lines = [
        f"Run {rep['run'].get('id')} ({rep['run'].get('kind')}, {rep['run'].get('task_type')})",
        f"  baseline kind: {rep['baseline_kind']}",
        f"  active engineer minutes: {_fmt(rep['active_minutes_total'])}"
        f" (known floor {rep['active_minutes_known_floor']})",
    ]
    lines += [f"    {p}: {_fmt(v)}" for p, v in rep["active_minutes"].items()]
    lines += [
        f"  capacity released (hours, not cash): {_fmt(rep['capacity_released_hours'])}",
        f"  model cost, estimate not an invoice (USD): {_fmt(rep['model_cost_usd'])}",
        f"  incremental cost incl. runtime and allocated setup (USD): {_fmt(rep['incremental_cost_usd'])}",
        f"  cost-equivalent (USD): {_fmt(rep['cost_equivalent_usd'])}",
        f"  cash savings (USD): {_fmt(rep['cash_savings_usd'])}",
        f"  confirmed review findings: {_fmt(rep['confirmed_findings'])}",
        f"  accepted tasks per engineer hour: {_fmt(rep['accepted_tasks_per_engineer_hour'])}",
        f"  usage entries with unknown tokens: {rep['usage_unknown_entries']}",
    ]
    lines += [f"  {k}: {_fmt(v)}" for k, v in rep["measures"].items()]
    for role, t in sorted(rep["tokens_by_role"].items()):
        lines.append(f"  tokens[{role}]: " + ", ".join(f"{k}={v:,}" for k, v in t.items() if v))
    lines.append("  claims:")
    for name, claim in claims.items():
        lines.append(f"    {name}: {claim['status']}")
        lines += [f"      - {b}" for b in claim["blockers"]]
    lines.append("  Capacity released is hours, not cash. Token costs are estimates, not an invoice.")
    return "\n".join(lines)


# -- files and templates ------------------------------------------------------

TEMPLATE = '''schema = "engineer.value-scorecard/v1"
# Private run record. Every measure is observed, estimated, unknown or
# not-applicable. Unknown is never zero. Keep ticket keys, rates and receipts here only.

[run]
id = {run_id}
kind = {kind}                  # feasibility | pilot | replication
task_class = {task_class}
task_type = {task_type}

[baseline]
kind = "missing"                 # historical-observed | estimate | agent-first-replay | missing
# scope = ""                     # same ticket class and scope
# quality_bar = ""               # definition of reviewed and accepted change
# source_access = ""             # same source access as the agent-assisted run
# approved_by = "owner"
# approved_at = 2026-01-01
# [baseline.hours]               # comparable human hours
# status = "estimated"
# value = 0
# source = "owner baseline"
# [baseline.elapsed_hours]
# status = "estimated"
# value = 0
# source = "owner baseline"

[rate]                           # approved loaded hourly rate (USD)
status = "unknown"
# approved_by = "owner"
# approved_at = 2026-01-01

[active_minutes.discovery]
status = "unknown"
[active_minutes.refinement]
status = "unknown"
[active_minutes.implementation]
status = "unknown"
[active_minutes.review_rework]
status = "unknown"

[elapsed.elapsed_minutes]
status = "unknown"
[elapsed.wait_minutes]
status = "unknown"

[interventions]                  # human interventions during the run
status = "unknown"

# [[route]]                      # actual USAi route/model per role
# role = "implementation"        # discovery | refinement | implementation | review | rework | other
# model = ""
# route = ""
# recorded = "actual"            # actual | planned

# [[pricing]]                    # dated, owner-approved pricing basis (USD per million tokens)
# id = "p1"
# model = ""
# input_per_mtok = 0.0
# output_per_mtok = 0.0
# effective_date = 2026-01-01
# basis = ""
# approved_by = "owner"
# approved_at = 2026-01-01

# [[usage]]                      # one entry per model, role and retry; include review and retries
# role = "implementation"
# model = ""
# route = ""
# status = "observed"            # observed | estimated | unknown (omit counts when unknown)
# retry = false
# input = 0
# output = 0
# source = "agentsview"
# pricing = "p1"

[runtime_cost_usd]               # incremental runtime cost other than tokens
status = "unknown"

[setup]
status = "unknown"               # unknown | none | allocated
# [[shared_cost]]                # allocate shared setup/ingestion once across runs
# id = "setup-1"
# description = ""
# share = 0.25                   # this run's fraction; shares of one id sum to at most 1
# basis = ""
# [shared_cost.amount_usd]
# status = "observed"
# value = 0.0
# source = ""

[findings]
status = "unknown"               # observed once review results were read
# source = "roborev"
# [[finding]]
# id = ""
# source = "roborev"
# disposition = "confirmed"      # confirmed | invalid | stale | out-of-scope | open

[escaped_defects]                # defects found after acceptance within a stated window
status = "unknown"
# window_start = 2026-01-01
# window_end = 2026-01-15

[operating]
[operating.accepted_tasks]
status = "unknown"
[operating.escalations]
status = "unknown"
[operating.rework_minutes]
status = "unknown"

[cash_savings_usd]               # only with a confirmed budget change; otherwise leave unknown
status = "unknown"

[replication]                    # second-team runs only
{replication}
[pilot]
status = "undefined"             # defined with the owner: threshold text, never invented here
# defined_by = "owner"
# defined_at = 2026-01-01
# threshold = ""
'''

COLLECT = """# Collection instructions (generic)

Fill scorecard.toml while the run happens; do not reconstruct afterwards.
Missing data stays unknown. Keep this directory private (ignored by Git).

1. Baseline: agree a comparable traditional-engineering baseline and quality
   bar with the owner before the run. Label it historical-observed, estimate or
   missing. An agent-first replay is not an independent control.
2. Clock: note start/end and every wait (approval, access, review, CI) as
   elapsed and wait minutes. Record active engineer minutes per phase:
   discovery, refinement, implementation, review/rework.
3. Interventions: count each time a human corrected, unblocked or redirected
   the agent; escalations and rework minutes go under [operating].
4. Tokens: per model, role and retry (including review).
     agentsview usage daily --agent pi --breakdown --json --since YYYY-MM-DD
     roborev cost --repo <repo> --since <window> --json   # lower bound only
   Record the actual route/model per role, and a dated owner-approved pricing
   basis. Token cost is an estimate, not an invoice.
5. Findings: `roborev list --json`, `roborev show <job>`; record each finding's
   disposition after reading the code. Escaped defects: state the window and
   check at its end.
6. Setup and ingestion: record shared costs once with an explicit share per run.
7. Check and report:
     scripts/value-scorecard.py check  scorecard.toml
     scripts/value-scorecard.py report scorecard.toml
"""


def _toml_string(text):
    return json.dumps(text, ensure_ascii=False)


def _replication_block():
    return "\n".join(f"[replication.{k}]\nstatus = \"not-applicable\"" for k in REPLICATION)


def ensure_private(directory):
    probe = directory
    while not probe.exists():
        probe = probe.parent
    result = subprocess.run(
        ["git", "-C", str(probe), "check-ignore", "-q", "--no-index", str(directory)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if result.returncode == 1:
        raise ScorecardError(f"{directory} is inside a Git checkout and not ignored by Git")


def _write_private(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(text)


def load(path):
    with open(path, "rb") as handle:
        return tomllib.load(handle)


def cmd_init(args):
    if not RUN_ID_RE.match(args.run_id):
        raise ScorecardError("run id must be a generic identifier (letters, digits, . _ -)")
    root = Path(args.root).expanduser()
    run_dir = root / args.run_id
    ensure_private(run_dir)
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    run_dir.mkdir(mode=0o700)
    replication = _replication_block() if args.kind != "replication" else "\n".join(
        f"[replication.{k}]\nstatus = \"unknown\"" for k in REPLICATION)
    text = TEMPLATE.format(run_id=_toml_string(args.run_id), kind=_toml_string(args.kind),
                           task_class=_toml_string(args.task_class), task_type=_toml_string(args.task_type),
                           replication=replication)
    _write_private(run_dir / "scorecard.toml", text)
    _write_private(run_dir / "COLLECT.md", COLLECT)
    print(f"created {run_dir / 'scorecard.toml'}")
    return 0


def cmd_check(args):
    rec = load(args.scorecard)
    errors, gaps = validate(rec, datetime.date.today())
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    for g in gaps:
        print(f"unknown: {g}")
    if errors:
        return 1
    print(f"{len(gaps)} unknown measure(s)")
    return 1 if gaps and args.require_complete else 0


def _checked(path):
    rec = load(path)
    errors, _ = validate(rec, datetime.date.today())
    if errors:
        raise ScorecardError("; ".join(errors))
    return rec


def cmd_report(args):
    rep = build_report(_checked(args.scorecard), datetime.date.today())
    print(json.dumps(rep, indent=2) if args.json else render_report(rep))
    return 0


def _cards(root):
    root = Path(root).expanduser()
    return sorted(root.glob("*/scorecard.toml")) if root.is_dir() else []


def rollup(records, today=None):
    shares = {}
    problems = []
    types = {}
    for rec in records:
        for s in rec.get("shared_cost") or []:
            if (rec.get("setup") or {}).get("status") == "allocated" and _num(s.get("share")):
                shares.setdefault(s.get("id"), []).append(s["share"])
        rep = build_report(rec, today)
        t = types.setdefault((rec.get("run") or {}).get("task_type", "unknown"), {
            "runs": 0, "complete_active_runs": 0, "active_minutes": None,
            "capacity_runs": 0, "capacity_released_hours": None,
            "accepted_task_runs": 0, "accepted_tasks": None,
            "escalation_runs": 0, "escalations": None})
        t["runs"] += 1
        for key, runs_key, value in (
                ("accepted_tasks", "accepted_task_runs", _val((rec.get("operating") or {}).get("accepted_tasks"))),
                ("escalations", "escalation_runs", rep["measures"]["escalations"])):
            if value is not None:
                t[runs_key] += 1
                t[key] = (t[key] or 0) + value
        if rep["active_minutes_total"] is not None:
            t["complete_active_runs"] += 1
            t["active_minutes"] = (t["active_minutes"] or 0) + rep["active_minutes_total"]
        if rep["capacity_released_hours"] is not None:
            t["capacity_runs"] += 1
            t["capacity_released_hours"] = (t["capacity_released_hours"] or 0) + rep["capacity_released_hours"]
    for ident, values in shares.items():
        if sum(values) > 1 + 1e-9:
            problems.append(f"shared cost {ident!r}: shares sum to {sum(values):g}, above 1 (double counted)")
    return {
        "runs": len(records),
        "by_task_type": types,
        "caveat": "Totals sum only runs with known values (see the *_runs counts) and are null when none are known; "
                  "unknown is not zero. "
                  "This is not an organization-wide or statistically powered result.",
    }, problems


def cmd_rollup(args):
    cards = _cards(args.root)
    records = []
    for card in cards:
        errors, _ = validate(load(card), datetime.date.today())
        if errors:
            raise ScorecardError(f"{card}: " + "; ".join(errors))
        records.append(load(card))
    result, problems = rollup(records, datetime.date.today())
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['runs']} run(s)")
        for name, t in sorted(result["by_task_type"].items()):
            print(f"  {name}: " + ", ".join(f"{k}={v}" for k, v in t.items()))
        print(result["caveat"])
    for p in problems:
        print(f"error: {p}", file=sys.stderr)
    return 1 if problems else 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="create a private scorecard for one run")
    init.add_argument("run_id")
    init.add_argument("--root", default=str(DEFAULT_ROOT), help=f"private root (default {DEFAULT_ROOT})")
    init.add_argument("--kind", choices=RUN_KINDS, default="feasibility")
    init.add_argument("--task-class", default="unclassified")
    init.add_argument("--task-type", default="unclassified")
    init.set_defaults(func=cmd_init)
    check = sub.add_parser("check", help="validate a scorecard and list unknowns")
    check.add_argument("scorecard")
    check.add_argument("--require-complete", action="store_true", help="exit 1 while any measure is unknown")
    check.set_defaults(func=cmd_check)
    report = sub.add_parser("report", help="compute capacity, cost-equivalent and claim blockers")
    report.add_argument("scorecard")
    report.add_argument("--json", action="store_true")
    report.set_defaults(func=cmd_report)
    roll = sub.add_parser("rollup", help="combine private runs by task type")
    roll.add_argument("root", nargs="?", default=str(DEFAULT_ROOT))
    roll.add_argument("--json", action="store_true")
    roll.set_defaults(func=cmd_rollup)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ScorecardError, OSError, tomllib.TOMLDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
