# Per-run value scorecard

`scripts/value-scorecard.py` holds the generic contract (`engineer.value-scorecard/v1`),
validator and reports for the MVP value baseline. It reads existing evidence
(Kata, Forge, AgentsView, roborev, private run receipts) and adds no daemon,
dashboard or telemetry. Tickets, rates, baselines and receipts stay in ignored
`.local/value-scorecard/<run>/scorecard.toml` (`0700`/`0600`); `init` refuses a
destination Git would track.

```sh
scripts/value-scorecard.py init RUN --kind feasibility --task-class CLASS --task-type TYPE
scripts/value-scorecard.py check  .local/value-scorecard/RUN/scorecard.toml [--require-complete]
scripts/value-scorecard.py report .local/value-scorecard/RUN/scorecard.toml [--json]
scripts/value-scorecard.py rollup .local/value-scorecard   # stratified by task type
```

## Measures

Each measure is `observed` or `estimated` (value and source), `unknown`
(no value) or `not-applicable`. Unknown is never zero; a missing section is a
reported gap. The record covers:

- Baseline: kind (`historical-observed`, `estimate`, `agent-first-replay`,
  `missing`), scope, quality bar, source access, owner approval, human hours and
  elapsed hours. An agent-first replay is never an independent control.
- Active engineer minutes: discovery, refinement, implementation, review/rework;
  elapsed and wait minutes; interventions; escalations and rework minutes;
  accepted tasks (tasks per engineer hour, stratified by task type).
- Route/model per role (actual vs planned) and tokens per model, role and
  retry, including review, each pointing to a dated, owner-approved `[[pricing]]`
  basis. Token cost is an estimate, not an invoice.
- Review findings with dispositions (`confirmed`, `invalid`, `stale`,
  `out-of-scope`, `open`) and escaped defects with a stated observation window.
- Shared setup/ingestion: `setup.status` is `unknown`, `none` or `allocated`;
  each `[[shared_cost]]` has an amount, this run's `share` and a `basis`.
  `rollup` fails when shares of one id exceed 1, so cost is never counted twice.
- Replication (second team, `--kind replication`): approval/access lead time,
  clean install, operator touch, source onboarding and first reviewed accepted
  change minutes.

## Computation

- Capacity released (hours) = baseline hours - agent-assisted active hours;
  needs a comparable baseline and all four phases (`not-applicable` counts 0).
- Cost-equivalent = capacity released x approved loaded rate - incremental cost
  (approved-price model cost + runtime + allocated shared cost). Cash savings
  are a separate field, filled only after a confirmed budget change.
- Anything unknown makes the dependent figure unknown, never zero.

## Claims

`report` lists blockers for "faster delivery", "equal quality" and "positive
ROI": feasibility runs, undefined pilot/threshold (defined with the owner; no
multiplier is invented), missing or unapproved baseline, replay baselines,
uncollected findings, open defect windows and unknown cost inputs. A claim
becomes at most "evaluable against the owner threshold"; one run never
establishes organization-wide results. Reduced rework from refinement is a
measured pilot hypothesis, not an avoided-cost figure.

## Collection

`init` writes `COLLECT.md` beside the record. Evidence commands:
`agentsview usage daily --agent pi --breakdown --json --since DATE`,
`roborev cost --repo REPO --since WINDOW --json` (a lower bound), `roborev list
--json`, `kata events`. Missing client metrics (`3c2c`) and no-session review
usage (`fjyf`) are recorded as unknown. Fill the record during the run.
