# Archived: Temporal Scale Migration: Season-Turns To Year-Turns

Status: implemented. Archived on 2026-06-05 after verification against the current codebase.

Implementation references:

- `src/calendar.py`: `TURNS_PER_YEAR = 1`, annual dominant-season selection, annual campaign modifiers, annual food variance, and year-only turn labels.
- `src/agents.py`, `src/actions.py`, `src/heartland.py`, and `src/resource_economy.py`: annual dominant-season mechanics threaded through action selection, combat, unrest, migration, and food economy.
- `src/config.py`: annualized population, unrest, rebel independence, diplomacy, and war-duration constants.
- `src/simulation_ui.py` and `src/metrics.py`: annual date labels and viewer/metric reporting.
- `tests/test_calendar.py`, `tests/test_climate.py`, and related system tests: focused annual cadence coverage.

Original plan retained below for historical context.

## Problem

Each turn currently represents one season (`TURNS_PER_YEAR = 4` in `calendar.py`). A
120-turn calibration run covers 30 years. Thirty years is not enough time for
macro-historical arcs to emerge: civilizational rise and fall, religious spread, the
obsolescence of technologies, and the development of successor state identities all
require centuries. The simulation generates episodes, not epochs.

Secondary effects of the seasonal timescale:

- Every per-turn rate constant was implicitly calibrated at seasonal frequency, meaning
  annual rates are 4× higher than intended (population growth at `0.035/turn` × 4
  seasons = 14%/year; historical agrarian range is 0.1–0.5%).
- One major strategic decision per season (every three months) is too granular for
  pre-modern state behavior. One per year is defensible.
- 1,800+ long-cycle shock events per 120-turn run — shocks fire at seasonal frequency
  across all regions simultaneously.

## Core Change

Change `TURNS_PER_YEAR` from `4` to `1` in `src/calendar.py`.

This single change cascades correctly through most of the codebase because the
seasonal abstraction is already well-centralised:

- `SEASONAL_TIME_STEP_YEARS = 1.0 / TURNS_PER_YEAR` becomes `1.0`, so all code that
  multiplies by this factor already expresses rates in per-year units and will behave
  correctly with no further changes.
- `is_year_end(turn)` returns `True` when `turn % TURNS_PER_YEAR == TURNS_PER_YEAR - 1`.
  With `TURNS_PER_YEAR = 1`, this fires every turn — which is correct, since every turn
  is now a year.
- `years_at_peace += SEASONAL_TIME_STEP_YEARS` in `diplomacy.py` will now accumulate
  1.0 year per turn instead of 0.25. Correct.
- `update_region_integration(time_step_years=SEASONAL_TIME_STEP_YEARS)` will integrate
  by 1.0 year per turn. Correct if integration constants are in per-year units.

## What Changes Automatically

These are handled by `SEASONAL_TIME_STEP_YEARS` and will be correct after the core
change with no further edits:

- `years_at_peace` accumulation in `diplomacy.py`
- `update_region_integration` time step
- Any other rate expressed as `value * SEASONAL_TIME_STEP_YEARS`

The year-end phase currently fires every 4 turns (once per year). After the change it
fires every turn — which is still once per year. No change required to year-end logic.

## What Needs Attention

### 1. Per-turn rates not scaled by `SEASONAL_TIME_STEP_YEARS`

These constants are currently applied once per season. After the change they fire once
per year, so each application must cover a full year's effect. Most will need to be
multiplied by 4 as a starting point, then recalibrated.

**Audit step first:** For each constant below, verify whether its application site
multiplies by `SEASONAL_TIME_STEP_YEARS`. If it does, it is already correct and does
not appear here. If it does not, it is in per-season units and needs rescaling.

| Constant | Current | ×4 implied | Recalibration target | Notes |
|---|---|---|---|---|
| `POPULATION_GROWTH_PER_TURN` | 0.035 | 0.14/yr | **0.005** | Historical: 0.1–0.5%/yr in good conditions |
| `POPULATION_FOOD_SURPLUS_BONUS_FACTOR` | 0.006 | 0.024 | **0.006** | Keep — this is a multiplier on surplus, not a base rate |
| `POPULATION_FOOD_DEFICIT_PENALTY_FACTOR` | 0.08 | 0.32 | **0.08** | Same — keep as annual sensitivity |
| `UNREST_DECAY_PER_TURN` | 0.6 | 2.4/yr | **1.8** | A freshly conquered region (unrest 6.0) should stabilise in 3–4 years |
| `REBEL_INDEPENDENCE_PER_TURN` | 0.55 | 2.2/yr | **1.0** | 1-region rebel should mature in ~2.5–3 years |
| `REBEL_FULL_INDEPENDENCE_THRESHOLD` | 3.5 | — | **2.5** | Adjusted together with the rate above |
| `DIPLOMACY_GRIEVANCE_DECAY` | 2.5 | 10/yr | **6.0** | A major war grievance (40 pts) should fade over 6–10 years |
| `SUCCESSION_PRESTIGE_GAIN_FACTOR` | 0.018 | — | verify | Applied at year-end? If yes, already per-year — no change |
| `SUCCESSION_UNREST_LEGITIMACY_PENALTY` | 0.018 | — | verify | Same — check application site |
| `RELIGION_CONVERSION_BASE` | 0.03 | 0.12/yr | verify | Check whether this fires per-turn or per-year-end |
| `MIGRATION_MAX_SHARE_PER_TURN` | 0.12 | 0.48/yr | **0.12** | Annual migration share should remain 12% of population |

**Note on war duration:** `DIPLOMACY_WAR_MAX_TURNS = 4` currently means 4 seasons = 1
year. After the migration, 4 turns = 4 years, which is too long. Change to `2` (2-year
maximum war duration). `DIPLOMACY_WAR_WHITE_PEACE_TRUCE = 2` and
`DIPLOMACY_WAR_SETTLEMENT_TRUCE = 3` similarly become 2-year and 3-year truces, which
are reasonable and need no change.

### 2. Seasonal modifier dictionaries

`calendar.py` contains eight seasonal modifier dictionaries — for action utility,
attack strength, attack score, unrest pressure, migration pressure, migration
attraction, migration capacity, and migration flow. With a single annual turn, these
lose their direct meaning.

**Recommended approach: retain seasons as narrative, replace modifiers with annual
variance.**

Keep `SEASON_NAMES` and `get_turn_season_name` for display and report purposes. Each
year can be labelled with a "dominant season character" (a weighted random draw from
the four seasons, biased by regional climate — more spring/autumn dominance in
temperate climates, more winter dominance in cold climates, no winter in tropical).

Replace the four per-season modifier dictionaries with two annual modifier functions:

```python
# New in calendar.py:
def get_annual_campaign_modifier(dominant_season: str) -> float:
    """Military campaign effectiveness for this year."""
    return {
        "Spring": 0.5,   # average — some good, some bad months
        "Summer": 1.0,   # good campaign year
        "Autumn": 0.2,   # harvest season limits mobilisation
        "Winter": -0.5,  # harsh campaign conditions dominate
    }.get(dominant_season, 0.0)

def get_annual_food_variance(dominant_season: str) -> float:
    """Fractional adjustment to annual food production."""
    return {
        "Spring": 0.0,    # average
        "Summer": 0.05,   # slightly above average
        "Autumn": 0.10,   # good harvest year
        "Winter": -0.18,  # cold year, reduced yields
    }.get(dominant_season, 0.0)
```

The food production and consumption share dictionaries
(`SEASONAL_FOOD_PRODUCTION_SHARES`, `SEASONAL_FOOD_CONSUMPTION_SHARES`) can be
removed — they are sub-annual detail that is no longer meaningful at annual resolution.
Their effect is absorbed into `get_annual_food_variance`.

`SEASONAL_ECONOMY_SHARE = 1.0 / TURNS_PER_YEAR` becomes `1.0`, meaning the full
annual economy is applied each turn. This is correct.

### 3. Long-cycle shock frequency

Shocks currently fire at seasonal frequency across all regions. With annual turns the
raw event count will drop by 4× automatically. However, the per-event probability
settings may also need recalibration. Target: ~400–600 shock events per 120-turn
(120-year) run. Run calibration after the core change and adjust shock base
probabilities if the count is still too high.

### 4. Calibration run lengths

| Run type | Old turns | Old span | New turns | New span |
|---|---|---|---|---|
| Quick smoke test | 20 | 5 years | 20 | 20 years |
| Short calibration | 40 | 10 years | 60 | 60 years |
| Standard calibration | 120 | 30 years | 150 | 150 years |
| Long calibration | 400 | 100 years | 400 | 400 years |

The 150-turn standard run is sufficient to observe the rise and decline of at least one
major power, multi-generational technology diffusion, and multiple succession cycles
within a dynasty. The 400-turn run begins to approach the timescale of a proper
historical period (the Han dynasty, the Roman Principate, the Abbasid Caliphate).

---

## Implementation Phases

### Phase 0 — Audit (no code changes)

Before touching any code, establish a complete inventory of what will break.

1. Grep for every reference to `SEASONAL_TIME_STEP_YEARS` across `src/`. Record which
   rate applications are already in per-year units (safe) vs. which are bare per-turn
   values (need rescaling).

2. Grep for `get_turn_season_name`, `get_seasonal_*`, and `season_name` parameter
   usage. These are every site that will need to transition to the annual dominant-season
   model.

3. Run the current test suite and record the baseline pass/fail state. Note which tests
   assert specific state at specific turn numbers — these will need updating.

4. Run a 120-turn calibration and record baseline metrics as the comparison target:
   development events, expansion events, war events, rebel independence rate, runaway
   rate, faction count.

### Phase 1 — Isolate seasonal mechanics in `calendar.py`

Add the annual variance functions described above (`get_annual_campaign_modifier`,
`get_annual_food_variance`) alongside the existing dictionaries. Do not remove the
existing dictionaries yet. Add a `get_annual_dominant_season(region, world)` function
that draws a dominant season for a region based on climate weighting.

At this stage, both the seasonal and annual functions exist. No simulation behaviour
changes.

### Phase 2 — Thread annual season through the simulation

In `simulation.py`, compute `dominant_season` for each region (or a single world-level
dominant season as a simplification) at the start of each turn. Pass this to the
post-action phase alongside or instead of `season_name`.

In `agents.py`, replace `get_seasonal_action_modifier(action_name, season_name)` with
`get_annual_campaign_modifier(dominant_season)` for the attack and expand modifiers. The
develop modifier (which was positive in winter, negative in summer, reflecting campaign
off-season development) can be folded into a single annual develop baseline or dropped —
it was always a small effect.

In `heartland.py` and `resource_economy.py`, replace seasonal food share calculations
with the annual food yield using `get_annual_food_variance`.

Run the test suite. At this stage the simulation still uses `TURNS_PER_YEAR = 4` — this
is a pure refactor confirming that the seasonal modifier logic has been cleanly
abstracted before the clock change.

### Phase 3 — Change the clock

In `calendar.py`, change `TURNS_PER_YEAR = 4` to `TURNS_PER_YEAR = 1`.

Remove the now-meaningless seasonal distribution dictionaries
(`SEASONAL_FOOD_PRODUCTION_SHARES`, `SEASONAL_FOOD_CONSUMPTION_SHARES`,
`SEASONAL_ECONOMY_SHARES`, `SEASONAL_ACTION_UTILITY_MODIFIERS`,
`SEASONAL_ATTACK_STRENGTH_BONUSES`, `SEASONAL_ATTACK_SCORE_BONUSES`,
`SEASONAL_UNREST_PRESSURE_MODIFIERS`, and the four migration modifier dictionaries).
Keep `SEASON_NAMES` for narrative labelling.

Update `format_turn_span` to replace "seasons" language with "years":
```python
# Old output: "2 years and 3 seasons"
# New output: "5 years"
```

Run a 20-turn smoke test. The simulation should run to completion without crashing.
Output will be miscalibrated but structurally coherent.

### Phase 4 — Recalibrate rate constants

Work through the recalibration table above, one system at a time. After each system,
run a 150-turn calibration and check the target metric.

**Order of operations:**

1. **Population** — Set `POPULATION_GROWTH_PER_TURN = 0.005`. Verify: a well-fed,
   low-unrest region should roughly double its population over 120–150 years.

2. **Unrest** — Set `UNREST_DECAY_PER_TURN = 1.8`. Verify: a freshly conquered region
   (unrest 6.0) stabilises in 3–5 years without additional pressure.

3. **Rebel independence** — Set `REBEL_INDEPENDENCE_PER_TURN = 1.0` and
   `REBEL_FULL_INDEPENDENCE_THRESHOLD = 2.5`. Verify: a 1-region rebel proto-state
   matures in 2–3 years; a 2-region rebel in ~1.7 years.

4. **War duration** — Set `DIPLOMACY_WAR_MAX_TURNS = 2`. Verify: wars resolve in 1–2
   years and leave a multi-year truce.

5. **Diplomacy rates** — Set `DIPLOMACY_GRIEVANCE_DECAY = 6.0`. Verify: a major
   post-war grievance (40 pts) fades over 6–10 years of peace.

6. **Shock frequency** — Check total shock events in the 150-turn calibration. Adjust
   base shock probabilities until the count is in the 400–600 range.

7. **Technology adoption** — Check that a major technology spreads across a continent
   over 40–80 years. Adjust adoption probability constants if diffusion is too fast or
   too slow.

### Phase 5 — Validate and update calibration baseline

Run 25 calibration runs at 150 turns (150 years) on the Azhora map. Record the new
baseline metrics. Compare against the old 120-turn (30-year) baseline as a sanity check
on what has shifted vs. what is structural.

Target indicators that the migration succeeded:

- At least one major faction rises, plateaus, and begins fragmenting within a single run.
- Successor states persist long enough (10–20+ years) to develop distinct doctrine
  profiles.
- Technology has a visible early/late-era character: early runs dominated by expansion
  and basic development; later runs showing complex trade networks and mature
  administrative states.
- Shock events no longer dominate event logs.

Update test fixtures to reflect the new turn-count semantics.

---

## Risk Notes

**Biggest risk:** Some rate constants may be applied at year-end (every 4 turns under
the old system) rather than per-turn. After the migration, year-end fires every turn,
which means these constants fire 4× more often in absolute terms. They will need to be
divided by 4, not multiplied. The Phase 0 audit is essential for identifying these.

**Second risk:** `MIGRATION_MAX_SHARE_PER_TURN = 0.12` — if migration currently fires
every season, annual migration totals 48% of population per year, which is
already implausible. If it fires per-turn scaled by some internal factor, annual total
may be reasonable. Verify the application site before recalibrating.

**Saved world compatibility:** World serialisation stores `world.turn` as an integer.
Existing saved worlds at turn 120 represent 30 years under the old system. After the
migration, turn 120 represents 120 years. Treat saved-world compatibility as out of
scope; this is a new simulation epoch, not a patch.
