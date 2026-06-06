# Pressure Diagnostics Plan

## Purpose

The current codebase has enough systems active that the next question is not whether
features fire at all. The next question is why a run becomes dominated, why late wars
spike, and which pressures actually changed faction behavior.

This plan adds diagnostics before tuning constants. It should make repeated runs explain
runaway formation, war cadence, shock volume, action incentives, and pressure propagation
without forcing symmetric balance.

## Implementation Status

Pressure diagnostics are implemented in `experiments/experiment_balance_dashboard.py`.
The dashboard now emits a `Pressure Diagnostics` section and structured result fields
for:

- runaway context around the start turn and final turn
- diplomacy pressure and active-war counts
- early/mid/late war cadence
- shock event volume and faction exposure
- pressure propagation checks
- dashboard-only action utility samples

The simulation also supports an optional `action_diagnostics_callback` so experiment
runs can collect candidate utilities without adding debug payloads to normal runs.

This document is retained as a calibration reference until the baseline and tuning
passes below are complete.

## Current Signal

A 5-run, 150-turn dashboard on `thirty_seven_region_ring` with seed `20260605`
showed:

- all tracked systems active
- runaway rate: 100 percent
- average runaway turn: 119.40
- late attacks: 81.60 per run, up from 27.40 early and 35.00 mid
- long-cycle shock events: 890.00 per run
- dual-track activation: 29.19 percent of qualifying faction-turns
- military-action dominant-bloc alignment: 36.72 percent

The report is generated output under `reports/next_steps_balance_dashboard.md` and is
not part of the repository.

## Diagnostic Questions

1. When does a winner become structurally dominant?
2. Which pressure made that dominance durable: treasury, regions, force projection,
   administration, trade, diplomacy, technology, shock resilience, or dual-track action
   capacity?
3. Are late attacks purposeful war pursuit, rivalry churn, opportunistic target picking,
   or lack of a military-track abstention threshold?
4. Do overextension, autonomy, unrest, succession, elite blocs, and shocks punish large
   states enough to create plausible plateau and fragmentation?
5. Are shock systems creating meaningful stress arcs, or mostly producing event noise?
6. Are bloc biases shifting decisions in legible cases, or are they averaged away by
   stronger utility terms?

## Phase 1: Extend Dashboard Runaway Context

Add a `build_pressure_diagnostics(world)` helper to
`experiments/experiment_balance_dashboard.py`.

For each run, capture:

- runaway winner and runaway start turn from `analyze_competition_metrics`
- snapshots at `runaway_turn - 10`, `runaway_turn`, `runaway_turn + 10`, and final turn
- winner versus runner-up margins for treasury, regions, population, effective income,
  net income, force projection, manpower pool, military readiness, administrative
  efficiency, administrative overextension, shock exposure, and average institutional
  technology
- active war count, rivalry count, pact/alliance count, and tributary/vassal pressure
- dual-track qualified state, both-track usage, military/admin track usage, and bloc
  bias magnitude

Output a `Pressure Diagnostics` section in the text report and matching structured
fields in any JSON report path that already exists.

## Phase 2: Explain Action Incentives

Add lightweight per-turn action-choice sampling for AI factions.

For each faction-turn, record the chosen action plus the strongest available utility
components:

- selected action and target
- raw action utilities for attack, expand, and develop
- whether the faction was dual-track qualified
- best attack target score, success chance, active war bonus, diplomacy status,
  resource need bonus, trade chokepoint bonus, foreign gateway bonus, supply risk,
  manpower commitment, readiness, and force projection
- best expansion score and frontier pressure
- best development score, acute development need, production shortage indicators, and
  dominant admin bloc agenda
- bloc action biases by action

Keep this sampling optional or dashboard-only so normal simulation runs do not carry
heavy debug payloads.

## Phase 3: Late-War Cadence Report

Add a war cadence summary by early/mid/late phase:

- attack count
- successful attack count
- attacks inside an active war
- attacks against rivals
- attacks against pact/tributary/overlord targets, if any
- attacks with active war objective bonus
- attacks with negative or near-zero final utility
- repeated same-pair attacks
- average attacker manpower ratio and readiness
- average target value and success chance

This will distinguish "the world is at war" from "the military track attacks because
something is attackable."

## Phase 4: Shock Volume And Exposure Report

Split shock diagnostics into event volume and state exposure.

Track per run:

- shock event count by event type
- unique active shock count by kind
- average duration and affected region count by kind
- population-loss event count and total population loss
- average and peak faction shock exposure
- average and peak faction shock resilience
- fraction of turns where a faction has active famine, epidemic, or trade-collapse
  exposure
- recovery event count versus onset event count

This should support tuning shock systems toward readable long-cycle arcs instead of raw
event frequency.

## Phase 5: Pressure Propagation Checks

After diagnostics exist, add targeted derived indicators:

- overextension bite: correlation of region count with administrative efficiency,
  autonomy, tax capture, unrest, secession, and dual-track loss
- military exhaustion bite: correlation of attack frequency with manpower ratio,
  readiness, military upkeep, and attack success
- shock bite: correlation of shock exposure with food deficit, migration outflow,
  unrest, income loss, and development choice
- bloc bite: faction-turns where bloc bias changed the selected action or target
- trade bite: import dependency, corridor exposure, blockade losses, and trade-collapse
  exposure versus action choice and treasury trend

These can start as aggregate report fields rather than formal statistical tooling.

## Phase 6: Calibration Baseline

Use the same commands before and after any tuning patch:

```powershell
python experiments/experiment_balance_dashboard.py --maps thirty_seven_region_ring --turns 80 150 250 --runs 10 --num-factions 4 --seed 20260605 --output reports/pressure_baseline.txt
```

```powershell
python experiments/experiment_azhora_calibration.py --runs 25 --turns 150 --seed pressure-baseline
```

Use `reports/` for generated outputs and keep them untracked.

## Implementation Order

1. Add `build_pressure_diagnostics(world)` and text-report output.
2. Add optional action utility sampling, scoped to experiment runs.
3. Add late-war cadence diagnostics.
4. Add shock volume/exposure diagnostics.
5. Run the baseline commands and record the summarized findings in a short tracked
   note only if the findings become design guidance.
6. Tune one pressure family at a time, validating after each patch.

## Tuning Candidates After Diagnostics

Do not apply these until the diagnostics identify the failure mode:

- add a military-track utility floor so low-value attacks can abstain
- make manpower/readiness and war exhaustion reduce attack utility more strongly
- make overextension reduce dual-track qualification, military projection, tax capture,
  or frontier control more visibly
- increase the political cost of repeated late wars through elite unrest, legitimacy,
  or coalition formation
- reduce shock onset/recovery event spam while preserving ongoing shock exposure in
  metrics and viewer state
- strengthen production shortage and trade-dependency pulls on development and
  diplomacy

## Validation

For diagnostics-only patches:

```powershell
python -m unittest tests.test_balance_dashboard tests.test_metrics
python -m unittest discover -s tests
python experiments/experiment_balance_dashboard.py --maps thirty_seven_region_ring --turns 80 150 --runs 3 --num-factions 4 --seed 20260605 --output reports/pressure_diagnostics_smoke.txt
```

For tuning patches, add focused tests around the changed pressure and then rerun the
full suite plus the 10-run dashboard baseline.
