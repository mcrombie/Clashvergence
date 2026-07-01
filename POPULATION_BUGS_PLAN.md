# Population Bugs Fix Plan

## Issues

1. **Grassic Kin population zeroes out in early game**
2. **Population grows shockingly fast per year**
3. **Simulation should start with 100 initial Grassic settlers, not 50**

---

## Bug 1 & 3: Grassic Kin Drops to Zero / Starting Population Too Low

### Root Cause

Grassic Kin initialises as a band polity at `BAND_STARTING_POPULATION = 50` (`src/config.py:130`).

At 50 people, percentage-based early-game losses are lethal:

| Event | Rate | Loss on 50 pop |
|---|---|---|
| Successful conquest | −12% (`POPULATION_ATTACK_SUCCESS_LOSS`) | −6 people |
| Failed conquest | −5% (`POPULATION_ATTACK_FAILURE_LOSS`) | −3 people |
| Unrest crisis (per turn) | −4% (`POPULATION_UNREST_CRISIS_LOSS`) | −2 people |
| Food deficit (per turn) | up to −12.15% | −6 people |

Once zeroed, recovery is **impossible**: `update_region_populations()` (`src/heartland.py:2448`) skips regions with `population <= 0`, and `change_region_population()` (`src/heartland.py:2038-2052`) floors at 0 via `max(0, population + amount)`.

### Fixes Needed

**A. Raise starting population to 100** (`src/config.py:130`)

```
BAND_STARTING_POPULATION = 50  →  100
```

This directly addresses issue #3 and gives the band a larger buffer against early losses.

**B. Add a population floor to prevent permanent zero** (`src/heartland.py:2038-2052`)

Currently `change_region_population()` uses `max(0, ...)`. Change it to use a small floor constant (e.g. `POPULATION_FLOOR = 10`) so a region can never be completely eliminated by attrition alone — it stabilises at the floor and can recover when conditions improve. Conquest/destruction events that intentionally eliminate a polity can bypass the floor explicitly.

**C. (Optional) Dampen percentage losses at very low populations**

The `max(1, ...)` floor in loss calculations means a 50-person band always loses at least 1 person per battle, which is proportionally brutal. Consider a low-population dampening factor: if `population < POPULATION_LOW_THRESHOLD` (e.g. 150), scale loss ratios down proportionally. This is secondary if fixes A and B are applied.

---

## Bug 2: Population Grows Too Fast

### Root Cause

The growth formula in `update_region_populations()` (`src/heartland.py:2446-2496`) stacks multiple bonuses:

| Component | Max contribution |
|---|---|
| Base rate (`POPULATION_GROWTH_PER_TURN`) | +0.30%/turn |
| Food surplus bonus | +1.00%/turn |
| Surplus modifier | +0.40%/turn |
| **Combined best case** | **~+1.70%/turn** |

At +1.7%/turn compounded, a population of 10,000 doubles in roughly 41 turns — far faster than plausible for a historical-era simulation. Even the food surplus bonus ceiling alone (`min(0.008 * 1.25, ...)` → up to +1.0%) can triple the effective growth rate over baseline.

**Files:** `src/heartland.py:2464-2490`, `src/config.py:112-119`

### Fixes Needed

**A. Cap total positive growth factor** (`src/heartland.py`, after all adjustments are summed)

Add a `POPULATION_GROWTH_MAX` constant (e.g. `0.007` or `0.008`) in `src/config.py` and clamp `growth_factor = min(POPULATION_GROWTH_MAX, growth_factor)` before computing the population change. This is the simplest single change that prevents runaway stacking.

**B. Reduce food surplus bonus ceiling** (`src/heartland.py:2476-2480`)

The current ceiling of `0.008 * 1.25 = 0.01` (+1.0%) is very high. Consider reducing the multiplier so the maximum food surplus bonus is ~+0.2–0.3%, keeping it meaningful but not dominant.

**C. Verify turn-to-year mapping**

Confirm how many simulation turns correspond to one in-game year. If turns are more granular than assumed (e.g. 4 turns/year), the base rate of 0.003/turn may need to be halved or quartered to match realistic annual growth rates (~0.5–1.5% per year historically).

---

## File Reference

| What | File | Lines |
|---|---|---|
| `BAND_STARTING_POPULATION` | `src/config.py` | 130 |
| `POPULATION_GROWTH_PER_TURN` and other rates | `src/config.py` | 112–132 |
| `change_region_population()` (floor logic) | `src/heartland.py` | 2038–2052 |
| `update_region_populations()` (growth formula) | `src/heartland.py` | 2446–2496 |
| Unrest crisis population loss | `src/heartland.py` | 4507–4513 |
| Secession population loss | `src/heartland.py` | 3600–3637 |
| Combat population loss | `src/actions.py` | 2452–2498 |
| World / band initialisation | `src/world.py` | 32–281, 244–266 |
