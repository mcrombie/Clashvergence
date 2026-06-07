# Session Change Summary

## Pending Documentation Cleanup

- Archived implemented plans under `archive/implemented/`.
- Updated `README.md`, `ROADMAP.md`, and `RELEASE_NOTES.md` to match implemented systems.
- Added `PRESSURE_DIAGNOSTICS_PLAN.md` as the next balance investigation plan.

## Pressure Diagnostics Implementation

- Added optional dashboard-only action utility diagnostics to the AI action path.
- Added pressure diagnostics to the balance dashboard covering runaway margins, diplomacy pressure, late-war cadence, shock volume, pressure propagation, and action incentives.
- Updated `README.md`, `ROADMAP.md`, `RELEASE_NOTES.md`, and `PRESSURE_DIAGNOSTICS_PLAN.md` to describe pressure diagnostics as implemented tooling and calibration guidance.
- Added focused dashboard tests for action incentives, pressure diagnostics, and report output.

## Capital Connectivity Mechanics

- Added capital-to-region connectivity checks to administration.
- Regions cut off from the faction capital now accumulate fragment penalties over consecutive turns.
- Owned sea links can preserve capital connectivity when a faction has enough practical seafaring.
- Exposed capital connectivity state in metrics, player view data, and simulation viewer snapshots.
- Added focused tests for isolated enclaves, maritime mitigation, stable capitals, and observability fields.

## Capital Fragmentation Diagnostics

- Added capital isolation, fragment count, and connectivity penalty fields to pressure dashboard runaway context.
- Added pressure-propagation checks for capital-fracture effects on administration, overextension, and net income.
- Updated pressure dashboard report text with capital fracture and capital bite summaries.
- Added focused balance-dashboard assertions for structured capital-fragment diagnostics and report output.

## Post-Capital Baseline Runs

- Ran a 10-run, 150-turn pressure dashboard baseline on `thirty_seven_region_ring`; the generated report is ignored under `reports/post_capital_pressure_baseline.txt`.
- Ran a 25-run, 150-turn Azhora calibration baseline; generated text and JSON reports are ignored under `reports/azhora_post_capital_baseline.*`.
- Baseline signal: runaways remain common, Azhora still strongly favors successor-state and Ibnael outcomes, shock volume remains high, and capital-fragment pressure now shows up as a measurable administrative bite in the pressure dashboard.

## Validation Notes

- Validation commands for this implementation pass are listed in the final Codex response.
