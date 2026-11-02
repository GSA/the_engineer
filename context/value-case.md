# Value case (template)

A short, honest case for what agent-assisted engineering is worth. Estimates
are fine if labeled; the aim is a credible mechanism plus checks that could
show it wrong, not exact statistics. Fill one copy per run in ignored
`.local/value-case/<run>.md`; keep ticket keys, rates and receipts there.

## 1. Estimates (label each: estimate / observed / unknown)

| Item | Value | Label | Who set it |
|---|---|---|---|
| Traditional-engineering hours for this ticket class | | | owner |
| Agent-assisted engineer hours (discovery, refinement, implementation, review/rework) | | | |
| Loaded hourly rate (USD) | | | owner |
| Model cost (USD, token estimate from AgentsView/roborev, not an invoice) | | | |
| Shared setup/ingestion cost and this run's share | | | owner |

Capacity released (hours) = baseline hours - assisted hours. Cost-equivalent =
hours released x rate - model/runtime cost - allocated setup. These are
capacity, not cash savings; cash needs a confirmed budget change. Unknown is
not zero. A replay of the same ticket by the agent is not an independent control.

## 2. Mechanism: why the saving should be true

- Refinement exposes unknowns before code is written, so less rework later.
- Independent review catches defects before merge.
- Engineer time shifts from producing to judging.

## 3. Checks for this run

Record what you saw; one run supports a hypothesis, never an organization-wide claim.

| Check | Source | Observed | Falsified if |
|---|---|---|---|
| Engineer minutes and human interventions | Kata/Forge timeline | | assisted hours >= baseline |
| Confirmed review findings (after reading the code) | `roborev list/show` | | review finds nothing real across runs |
| Tokens/cost by role, incl. review and retries | `agentsview usage daily --agent pi --breakdown --json`, `roborev cost --json` | | cost-equivalent <= 0 |
| Escaped defects after acceptance (state the window) | Kata/GitHub | | defects escape that review should have caught |

## 4. Second team (when replicated)

Approval/access lead time, clean install time, operator touch time, source
onboarding time and time to first reviewed accepted change. The pilot size and
success threshold are set with the owner; none is assumed here.

## 5. Lead message

Lead with time (capacity released), then cost-equivalent, then quality
(review findings, escaped defects). Say what is estimated and what would change the conclusion.
