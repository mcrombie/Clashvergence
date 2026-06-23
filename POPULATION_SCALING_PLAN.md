# Population Scaling Plan

## Problem

Population numbers never reach realistic scales. After 250 years, a dominant faction sits at
500–900 population units (the "state" threshold), while a real chiefdom should represent tens of
thousands of people, and a continent of 37 regions should reach into the millions over a few
centuries. Two bugs combine to cause this:

1. **The ceiling is too low.** `SURPLUS_POPULATION_PRESSURE = 90` means a region with
   productive capacity 4 hits equilibrium at 360 units. Starting populations (~250 units) are
   already 70% of ceiling — growth stalls within 40–50 years.

2. **The surplus growth bonus is too large relative to the base rate.** `SURPLUS_GROWTH_FACTOR`
   adds up to 1.8%/year bonus on top of the 0.5%/year base, meaning near-empty regions grow at
   2.3%/year — far above any pre-industrial historical rate.

---

## The Formula

Population growth follows **P(t) = P₀eʳᵗ**, where t is years (1 turn = 1 year) and r is the
annual growth rate. Real pre-industrial rates:

| Condition | r |
|---|---|
| Hunter-gatherer | 0.01%/year |
| Early agriculture / chiefdom | 0.1–0.3%/year |
| Favourable medieval period | 0.2–0.4%/year |
| 17th–18th century Europe (exceptional) | 0.5%/year |

Target: **r = 0.003/year** (0.3%) as the base in stable, food-sufficient conditions. In abundant
surplus the rate may rise to 0.7%; in crisis it goes negative.

---

## Deriving Starting Population

Two targets must be simultaneously satisfied:

1. A chiefdom faction (~3 regions) should total ≈ 50,000 at year 100.
2. Azhora total (37 regions) should reach ≈ 1,000,000 at year 250.

Converting to per-region:
- Target 1: 50,000 / 3 = **16,667** per region at year 100
- Target 2: 1,000,000 / 37 = **27,027** per region at year 250

Solving for r using P(t₂) = P(t₁) × e^(r × Δt):

```
27,027 = 16,667 × e^(r × 150)
e^(150r) = 1.622
r = ln(1.622) / 150 ≈ 0.00323 ≈ 0.003/year  ✓
```

Solving for P₀:

```
P₀ = 16,667 / e^(0.003 × 100) = 16,667 / 1.350 ≈ 12,350 per region
```

A typical region (3 resources, 4 neighbours) currently starts at ≈ 247 units.
**Scale factor ≈ 50×.**

### Verification

| Year | Per region (r = 0.003) | Chiefdom total (3 regions) | Azhora total (37 regions) |
|---|---|---|---|
| 0 | 12,350 | 37,050 | 456,950 |
| 50 | 14,373 | 43,119 | 531,801 |
| 100 | 16,736 | 50,208 | 619,232 ✓ ≈ 50k chiefdom |
| 200 | 22,680 | 68,040 | 839,160 |
| 250 | 26,399 | 79,197 | 976,763 ✓ ≈ 1M total |
| 350 | 35,776 | 107,328 | 1,323,712 |

*(These assume uniform growth at base r with no wars, shocks, or unrest — actual values will be
lower in contested regions and higher in peaceful, food-rich ones.)*

---

## Parameter Changes

### `src/config.py` — Starting population (×50)

| Constant | Old | New |
|---|---|---|
| `POPULATION_BASE` | 90 | 4,500 |
| `POPULATION_PER_RESOURCE` | 35 | 1,750 |
| `POPULATION_PER_CONNECTION` | 8 | 400 |
| `POPULATION_STARTING_OWNER_BONUS` | 20 | 1,000 |
| `POPULATION_MINIMUM` | 25 | 1,250 |
| `POPULATION_EXPANSION_TRANSFER_MIN` | 30 | 1,500 |
| `MIGRATION_MIN_SOURCE_POPULATION` | 55 | 2,750 |
| `MIGRATION_EVENT_MINIMUM` | 18 | 900 |
| `SUCCESSION_CLAIMANT_REGION_MIN_POPULATION` | 70 | 3,500 |

**Leave unchanged** (percentages/ratios unaffected by scale):
`POPULATION_GROWTH_PER_TURN` (see below), `POPULATION_UNOWNED_GROWTH_FACTOR`,
`POPULATION_UNREST_GROWTH_PENALTY`, `POPULATION_ATTACK_SUCCESS_LOSS`,
`POPULATION_ATTACK_FAILURE_LOSS`, `POPULATION_UNREST_CRISIS_LOSS`,
`POPULATION_SECESSION_LOSS`, `POPULATION_EXPANSION_TRANSFER_RATIO`,
`MIGRATION_MAX_SHARE_PER_TURN`, `ADMIN_POPULATION_BURDEN_FACTOR`
(already saturates at `ADMIN_POPULATION_BURDEN_MAX` under both scales).

---

### `src/heartland.py` — Growth rate and ceiling

**Base growth rate (historically calibrated):**

| Constant | Old | New | Reason |
|---|---|---|---|
| `POPULATION_GROWTH_PER_TURN` | 0.005 | **0.003** | 0.3%/year matches pre-industrial r |
| `SURPLUS_GROWTH_FACTOR` | 0.003 | **0.001** | Smaller surplus effect per unit |
| `SURPLUS_MAX_GROWTH_BONUS` | 0.018 | **0.004** | Max total r = 0.3% + 0.4% = 0.7%/year |
| `SURPLUS_MIN_GROWTH_PENALTY` | -0.012 | **-0.004** | Proportionally smaller penalty |

With these values:
- Abundant surplus: r = 0.003 + 0.004 = **0.7%/year** (near-ideal farming conditions)
- Stable surplus: r ≈ **0.4%/year**
- Strained/deficit: r ≈ **0.1–0.2%/year** or negative

**Ceiling constant (×556):**

| Constant | Old | New |
|---|---|---|
| `SURPLUS_POPULATION_PRESSURE` | 90 | **50,000** |

Typical ceiling: productive capacity 4 × 50,000 = **200,000 per region**. Starting populations
(~12,000) begin at 6% of ceiling — growth runs as near-exponential for centuries before slowing.

Band-scale exception: generated bands and unowned wild regions start around **50 people**.
The regional 50× estimator applies once a society is no longer operating as a mobile band.

**Settlement level thresholds** (calibrated to expected gameplay populations):

| Level | Old | New | Reached at (r=0.003) |
|---|---|---|---|
| rural | ≥ 35 | **≥ 8,000** | Game start (regions already rural) |
| town | ≥ 160 | **≥ 40,000** | ~Year 110 |
| city | ≥ 320 | **≥ 100,000** | ~Year 230 |

**Polity tier population thresholds** (faction total, in `_qualifies_for_tribe/chiefdom/state`):

| Tier | Old | New | Reached at (3-region faction, r=0.003) |
|---|---|---|---|
| band → tribe | 120 | **125** | Around 100–150 people (gated by `tribalization_progress`) |
| tribe → chiefdom | 360 | **50,000** | ~Year 100 ✓ |
| chiefdom → state | 900 | **250,000** | ~Year 250 (also requires city, infrastructure) |

---

### `src/resource_economy.py` — Normalizers and guards (×50)

These divide absolute population into dimensioned scores. Scaling ×50 preserves starting-game
ratios exactly; scores then grow proportionally as populations increase over centuries, which is
correct (larger populations demand more food, produce more economic output, etc.).

| Location | Expression | Old divisor/threshold | New |
|---|---|---|---|
| `get_region_resource_workforce_factor` | `population / X` | 180.0 | 9,000 |
| `_get_domestic_resource_decay` | `population < X` | 90 | 4,500 |
| `_get_region_corridor_step_cost` (line ~1794) | `population < X` | 90 | 4,500 |
| `_get_region_corridor_support_factor` | `population < X` | 60 | 3,000 |
| `_get_region_corridor_support_factor` | `population >= X` | 180 | 9,000 |
| trade quality bonus (line ~1078) | `population >= X` | 180 | 9,000 |
| food-suitability thresholds (lines ~1865, ~1884) | `population >= X` | 125 / 95 | 6,250 / 4,750 |
| `get_region_food_demand` | `population / X` | 138.0 | 6,900 |
| faction food demand (line ~3108) | `total_population / X` | 138.0 | 6,900 |
| urban surplus food calc (line ~3505) | `sum(population) / X` | 180.0 | 9,000 |

---

### `src/urban.py` — Population factor (×50)

`_urban_population_factor`: `/ 420.0` → `/ 21,000.0`

Currently saturates at pop 525; should saturate at ~26,000 (mid-game city scale).

---

### `src/military.py` — Manpower (×50)

`_population_manpower`: `/ 28.0` → `/ 1,400.0`

Starting manpower unchanged (12,000/1,400 ≈ 8.6, same as 250/28 ≈ 8.9). Scales proportionally
as populations grow.

---

### `src/diplomacy.py` — Power score (×50)

`get_faction_power_score`: `population / 110.0` → `population / 5,500.0`

---

### `src/movement.py` — Movement capacity (×50)

Line ~87: `/ 500.0` → `/ 25,000.0`

---

### `src/internal_politics.py` — Urban population (×50)

Line ~263: `/ 2200.0` → `/ 110,000.0`

---

### `src/actions.py` — Draw probability (×50)

Line ~1182: `/ 5200.0` → `/ 260,000.0`

---

### `src/ai_interpretation.py` — Migration significance (×50)

Line ~390: `/ 80.0` → `/ 4,000.0`

---

### `src/narrative.py` — Migration significance (×50)

Line ~453: `/ 40.0` → `/ 2,000.0`

---

## What Does NOT Change

- `SURPLUS_RESOURCE_YIELD`, `SURPLUS_CONNECTION_YIELD`, `SURPLUS_TERRAIN_PRODUCTIVITY` — resource system unchanged
- All unrest constants, war outcome ratios, diplomacy relationship scores (other than power score normalizer)
- `ADMIN_POPULATION_BURDEN_FACTOR` / `ADMIN_POPULATION_BURDEN_MAX` — already saturates under both scales
- Food production constants — food supply doesn't scale with population; food demand scales via the normalizer changes above, preserving starting-game food balance

---

## Verification Steps

After implementation:

1. Run a 250-turn simulation. Check that:
   - A chiefdom-tier faction has total population in the 40,000–80,000 range around turn 100.
   - Azhora total population exceeds 800,000 by turn 250.
   - At least one region has a city by turn 200–250.

2. Confirm early-game food balance is not broken:
   - At turn 1, `get_region_food_demand` for a typical region should return ≈ 1.7–1.9
     (same as current: 12,000 / 6,900 ≈ 1.74 vs. 250 / 138 ≈ 1.81).

3. Confirm settlement levels advance naturally:
   - Starting band camps remain `wild`; settled non-band regions should be `rural` from turn 1.
   - First `town` regions should appear around turn 80–120.
   - First `city` should appear around turn 200–250.

4. Run the balance dashboard (`reports/`) and compare:
   - Win-rate spread and runaway rate should be similar to pre-change baselines.
   - Elimination turn averages may shift (larger populations make conquest harder).
