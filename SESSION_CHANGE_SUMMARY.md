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

## Validation Notes

- Validation commands for this implementation pass are listed in the final Codex response.
