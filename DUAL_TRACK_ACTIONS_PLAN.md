# Dual-Track Actions + Bloc Competition for Action Selection

## Overview

Two changes are proposed together because they share a motivation: making faction
behaviour less monolithic and more structurally grounded.

**Dual-track actions** give developed factions the ability to act on a military track
(expand or attack) and an administrative track (develop) in the same turn. This removes
the false tradeoff where fighting a war means forgoing infrastructure, which is
historically inaccurate and produces the current early-game development-only pattern.

**Bloc competition** replaces the current pure-utility selection with a weighted vote
from elite blocs that biases the utility calculation. Military elites push for war and
expansion; merchant houses push for development; provincial governors prefer internal
investment. The faction still picks the highest resulting utility — it just isn't
omnisciently rational about what that means.

These are designed to be additive extensions to the existing system. `choose_action()`
stays intact. The new `choose_actions()` calls it internally and adds the second track.
No existing tests need to change in Phase 1.

---

## Key Architectural Facts (from codebase)

- `choose_action(faction_name, world)` in `agents.py` returns `(action_name, target)`.
  All utility logic is self-contained here.
- `_resolve_faction_action()` in `simulation.py` dispatches: `"expand"` → `expand()`,
  `"attack"` → `attack()`, `"develop"/"invest"` → `develop()`, `None` → skip.
- `action_provider` hook already exists in `run_turn()` for external overrides.
- Faction has `elite_blocs: list[EliteBloc]`, `strongest_elite_bloc: str`,
  `alienated_elite_bloc: str`, and `elite_balance: dict[str, float]`.
- `get_faction_elite_effects()` in `internal_politics.py` returns modifiers keyed by
  stat name. Blocs currently affect admin capacity, trade income, attack strength, etc.
  — but not action selection directly.
- Doctrine state tracks `doctrine_state.expansions`, `.attacks`, `.developments` as
  cumulative counts. Dual-track will increment both tracks' counts in the same turn,
  which is correct.

---

## 1. New Config Constants

Add to `src/config.py`:

```python
# ── Dual-track actions ─────────────────────────────────────────────────────────
# Minimum owned regions before the second track unlocks
DUAL_TRACK_MIN_REGIONS = 4

# Administrative efficiency floor required to use both tracks
DUAL_TRACK_ADMIN_EFFICIENCY_THRESHOLD = 0.55

# Proto-states and factions below min regions always use single track
# (no config needed — enforced in logic)

# ── Bloc competition ───────────────────────────────────────────────────────────
# Maximum utility bias applied by the winning bloc coalition
BLOC_COMPETITION_MAX_BIAS = 0.18

# Minimum effective bloc power (influence * loyalty) for a bloc to vote
BLOC_COMPETITION_MIN_EFFECTIVE_POWER = 0.06

# Penalty applied to an action type when the alienated bloc strongly opposes it
BLOC_COMPETITION_ALIENATION_PENALTY = 0.12

# Threshold below which a bloc is considered alienated for competition purposes
BLOC_ALIENATION_LOYALTY_THRESHOLD = 0.28
```

---

## 2. New Faction Fields

Add to `Faction` dataclass in `src/models.py`:

```python
# Dual-track: set each turn, not persisted between turns (ephemeral)
# These are cleared at the start of each faction's action resolution
military_track_used: bool = False
admin_track_used: bool = False
```

These do not need serialisation to save state — they are turn-local. Exclude them
from any `__post_init__` serialisation if the model uses one.

---

## 3. Track Capacity Gating

A new helper in `agents.py`:

```python
def get_available_tracks(faction_name: str, world: WorldState) -> tuple[bool, bool]:
    """
    Returns (military_track_available, admin_track_available).
    
    Single-track factions: only admin (develop) track is unlocked.
    Dual-track factions: both tracks available if institutional capacity is met.
    
    Track assignment:
      Military track: expand, attack
      Admin track:    develop
    """
    faction = world.factions[faction_name]

    # Proto-states and very small factions lack the institutional separation
    # to pursue military campaigns and domestic investment simultaneously
    if faction.proto_state:
        return (True, False)  # proto-states: military only (they want independence)

    owned_count = sum(1 for r in world.regions.values() if r.owner == faction_name)

    if owned_count < DUAL_TRACK_MIN_REGIONS:
        return (True, True)   # small faction: single combined track (choose one)
        # NOTE: both True but choose_actions() will only return 1 action for small factions

    admin_eff = float(faction.administrative_efficiency or 1.0)
    dual_available = admin_eff >= DUAL_TRACK_ADMIN_EFFICIENCY_THRESHOLD

    return (True, dual_available)
```

**Rationale for thresholds:**
- `DUAL_TRACK_MIN_REGIONS = 4`: a faction needs at least four regions before it has
  distinct military and administrative institutional layers.
- `DUAL_TRACK_ADMIN_EFFICIENCY_THRESHOLD = 0.55`: administrative efficiency below 0.55
  means the bureaucracy is too strained to manage separate military and domestic
  operations simultaneously. This is already calculated and varies with overextension,
  unrest, and legitimacy — so it naturally degrades under stress, withdrawing the
  dual-track advantage at exactly the moment the faction is struggling.

---

## 4. Bloc Competition Bias

### 4a. Bloc preference tables

Add to `src/internal_politics.py` as module-level constants:

```python
# Which track does each bloc primarily prefer?
BLOC_PREFERRED_TRACK = {
    BLOC_MILITARY_ELITES:      "military",
    BLOC_NOBLES:               "military",
    BLOC_TRIBAL_LINEAGES:      "military",
    BLOC_MERCHANT_HOUSES:      "admin",
    BLOC_GUILDS:               "admin",
    BLOC_URBAN_COMMONS:        "admin",
    BLOC_PRIESTHOOD:           "admin",
    BLOC_PROVINCIAL_GOVERNORS: "admin",
}

# Within the military track: how strongly does each bloc prefer attack vs. expand?
# 0.0 = strongly prefer expand, 1.0 = strongly prefer attack
BLOC_MILITARY_ATTACK_BIAS = {
    BLOC_MILITARY_ELITES:  0.70,  # elites want glory in battle
    BLOC_NOBLES:           0.35,  # nobles prefer expansion (land grants)
    BLOC_TRIBAL_LINEAGES:  0.55,  # tribal: raid and expand equally
}

# Within the admin track: which develop targets does each bloc favour?
# Used in Phase 2 to bias region/project selection, not action selection
BLOC_ADMIN_PROJECT_BIAS = {
    BLOC_MERCHANT_HOUSES:      "trade",        # markets, roads, port access
    BLOC_GUILDS:               "production",   # copper mines, craft centers
    BLOC_PRIESTHOOD:           "religious",    # temples, shrines
    BLOC_PROVINCIAL_GOVERNORS: "frontier",     # frontier infrastructure
    BLOC_URBAN_COMMONS:        "food",         # granaries, irrigation
}
```

### 4b. Computing the competition bias

Add a new function to `src/internal_politics.py`:

```python
def get_bloc_action_biases(faction: Faction) -> dict[str, float]:
    """
    Returns utility biases for each action type, derived from bloc competition.
    
    Keys: "attack", "expand", "develop"
    Values: float bias to add to that action's utility (positive or negative)
    
    Mechanism:
    1. Each bloc casts a weighted vote for its preferred track based on
       effective power = influence * loyalty.
    2. The total military-track vote and admin-track vote are normalised.
    3. The military vote is split between attack and expand using BLOC_MILITARY_ATTACK_BIAS.
    4. Each action receives a bias proportional to its vote share * MAX_BIAS.
    5. If the faction's alienated_elite_bloc strongly opposes an action type,
       an additional penalty is applied.
    """
    biases = {"attack": 0.0, "expand": 0.0, "develop": 0.0}

    military_power = 0.0
    admin_power = 0.0
    attack_weight = 0.0
    expand_weight = 0.0

    for bloc in faction.elite_blocs:
        effective_power = bloc.influence * bloc.loyalty
        if effective_power < BLOC_COMPETITION_MIN_EFFECTIVE_POWER:
            continue

        preferred = BLOC_PREFERRED_TRACK.get(bloc.bloc_type)
        if preferred == "military":
            military_power += effective_power
            attack_bias = BLOC_MILITARY_ATTACK_BIAS.get(bloc.bloc_type, 0.5)
            attack_weight += effective_power * attack_bias
            expand_weight += effective_power * (1.0 - attack_bias)
        elif preferred == "admin":
            admin_power += effective_power

    total_power = military_power + admin_power
    if total_power < BLOC_COMPETITION_MIN_EFFECTIVE_POWER:
        return biases

    # Normalise vote shares
    military_share = military_power / total_power
    admin_share = admin_power / total_power

    # Apply biases
    if military_power > 0:
        attack_share = attack_weight / military_power
        expand_share = expand_weight / military_power
        biases["attack"] = military_share * attack_share * BLOC_COMPETITION_MAX_BIAS
        biases["expand"] = military_share * expand_share * BLOC_COMPETITION_MAX_BIAS

    biases["develop"] = admin_share * BLOC_COMPETITION_MAX_BIAS

    # Alienated bloc penalty
    alienated = faction.alienated_elite_bloc
    if alienated and faction.elite_blocs:
        alienated_blocs = [b for b in faction.elite_blocs if b.bloc_type == alienated]
        if alienated_blocs and alienated_blocs[0].loyalty < BLOC_ALIENATION_LOYALTY_THRESHOLD:
            preferred_track = BLOC_PREFERRED_TRACK.get(alienated, "")
            if preferred_track == "military":
                # Alienated military bloc: army is fractious, campaigns less effective
                biases["attack"] -= BLOC_COMPETITION_ALIENATION_PENALTY
                biases["expand"] -= BLOC_COMPETITION_ALIENATION_PENALTY * 0.6
            elif preferred_track == "admin":
                # Alienated admin bloc: internal investment is obstructed
                biases["develop"] -= BLOC_COMPETITION_ALIENATION_PENALTY

    return biases
```

Export this function from `internal_politics.py`.

---

## 5. New Action Selection Function

Add to `src/agents.py`:

```python
from src.internal_politics import get_bloc_action_biases

def choose_actions(faction_name: str, world: WorldState) -> list[tuple[str, str]]:
    """
    Dual-track action selection.
    
    Returns a list of 0–2 (action_name, target_region_name) tuples.
    
    - Small factions (< DUAL_TRACK_MIN_REGIONS) or low admin efficiency:
      returns at most 1 action (military OR admin, same as before).
    - Qualifying factions: returns at most 2 actions, one per track.
    
    Bloc competition is applied to both tracks' utility calculations.
    """
    faction = world.factions[faction_name]
    military_available, admin_available = get_available_tracks(faction_name, world)
    is_dual = military_available and admin_available and (
        sum(1 for r in world.regions.values() if r.owner == faction_name)
        >= DUAL_TRACK_MIN_REGIONS
    )

    bloc_biases = get_bloc_action_biases(faction)
    actions: list[tuple[str, str]] = []

    # ── Military track ─────────────────────────────────────────────────────────
    military_action = _choose_military_action(
        faction_name, world, bloc_biases
    )
    if military_action[0] is not None:
        actions.append(military_action)

    # ── Admin track ────────────────────────────────────────────────────────────
    if is_dual:
        admin_action = _choose_admin_action(
            faction_name, world, bloc_biases
        )
        if admin_action[0] is not None:
            actions.append(admin_action)
    elif not actions:
        # Single-track fallback: if no military action chosen, try admin
        admin_action = _choose_admin_action(
            faction_name, world, bloc_biases
        )
        if admin_action[0] is not None:
            actions.append(admin_action)

    return actions


def _choose_military_action(
    faction_name: str,
    world: WorldState,
    bloc_biases: dict[str, float],
) -> tuple[str | None, str | None]:
    """
    Selects the best action on the military track: expand or attack.
    Returns (action_name, target) or (None, None) if no military action is warranted.
    """
    # Reuse existing utility helpers from choose_action()
    # Extract only the expand and attack utility calculations
    faction = world.factions[faction_name]
    doctrine = faction.doctrine_profile
    season_name = get_turn_season_name(world.turn)
    campaign_modifier = get_seasonal_action_modifier("attack", season_name)

    expand_utility = None
    attack_utility = None
    best_expand_target = None
    best_attack_target = None

    expandable = get_expandable_regions(faction_name, world)
    if expandable and faction.treasury >= EXPANSION_COST:
        best_score, best_expand_target = _score_expandable_regions(
            faction_name, expandable, world
        )
        expansion_personality = _get_expansion_personality(faction)
        frontier_pressure = _get_frontier_pressure(faction, expandable)
        expand_utility = (
            _normalize_expand_score(best_score)
            * (0.72 + doctrine.expansion_posture * 0.42)
            * expansion_personality
            + (1.0 - doctrine.insularity) * 0.08
            + frontier_pressure
            + (0.05 if faction.treasury >= EXPANSION_COST * 2 else 0.0)
            + get_seasonal_action_modifier("expand", season_name) * 0.12
            + bloc_biases.get("expand", 0.0)
        )

    attackable = get_attackable_regions(faction_name, world)
    if attackable and faction.treasury >= ATTACK_COST:
        best_score, best_attack_target = _score_attackable_regions(
            faction_name, attackable, world
        )
        attack_utility = (
            _normalize_attack_score(best_score)
            * (0.72 + doctrine.war_posture * 0.42)
            + doctrine.expansion_posture * 0.08
            - doctrine.insularity * 0.10
            + campaign_modifier * 0.7
            + bloc_biases.get("attack", 0.0)
        )
        if faction.treasury <= ATTACK_COST:
            attack_utility -= 0.04
        if faction.proto_state:
            attack_utility -= REBEL_PROTO_ATTACK_UTILITY_PENALTY

    # Add diplomacy modifiers (same as in choose_action())
    if attack_utility is not None and best_attack_target:
        attack_utility += _get_diplomacy_attack_modifier(
            faction_name, best_attack_target, world
        )

    # Neither action is worthwhile
    if expand_utility is None and attack_utility is None:
        return (None, None)

    # Pick better of the two
    if expand_utility is None:
        return ("attack", best_attack_target)
    if attack_utility is None:
        return ("expand", best_expand_target)
    if attack_utility >= expand_utility:
        return ("attack", best_attack_target)
    return ("expand", best_expand_target)


def _choose_admin_action(
    faction_name: str,
    world: WorldState,
    bloc_biases: dict[str, float],
) -> tuple[str | None, str | None]:
    """
    Selects the best action on the admin track: develop.
    Returns ("develop", target_region) or (None, None).
    """
    faction = world.factions[faction_name]
    doctrine = faction.doctrine_profile
    season_name = get_turn_season_name(world.turn)

    developable = get_developable_regions(faction_name, world)
    if not developable:
        return (None, None)

    acute_need = _get_acute_development_need(faction)
    best_score, best_dev_target = _score_developable_regions(
        faction_name, developable, world, bloc_biases
    )

    develop_utility = (
        (acute_need + _normalize_develop_score(best_score))
        * (0.4 + doctrine.development_posture * 0.32)
        + doctrine.insularity * 0.14
        - doctrine.expansion_posture * 0.06
        + get_seasonal_action_modifier("develop", season_name)
        + bloc_biases.get("develop", 0.0)
    )
    if faction.proto_state:
        develop_utility += REBEL_PROTO_INVEST_UTILITY_BONUS

    # Only take the admin action if it clears a minimum threshold
    # (prevents trivial develop actions when nothing is needed)
    if develop_utility < 0.10:
        return (None, None)

    return ("develop", best_dev_target)
```

### 5a. Refactoring `choose_action()` to use the new helpers

`choose_action()` currently contains the full utility calculation inline. To avoid
duplication, refactor it to call `_choose_military_action()` and `_choose_admin_action()`
with no bloc biases, then pick the single winner — preserving identical behaviour for
the single-track case:

```python
def choose_action(faction_name: str, world: WorldState) -> tuple[str | None, str | None]:
    """Retained for backwards compatibility. Returns single best action."""
    no_biases = {"attack": 0.0, "expand": 0.0, "develop": 0.0}
    military = _choose_military_action(faction_name, world, no_biases)
    admin = _choose_admin_action(faction_name, world, no_biases)

    m_action, m_target = military
    a_action, a_target = admin

    # Compare across tracks using the same utility helpers to pick one winner
    m_util = _get_military_utility(faction_name, m_action, m_target, world, no_biases)
    a_util = _get_admin_utility(faction_name, a_action, a_target, world, no_biases)

    if m_action is None and a_action is None:
        return (None, None)
    if m_action is None:
        return (a_action, a_target)
    if a_action is None:
        return (m_action, m_target)
    if m_util >= a_util:
        return (m_action, m_target)
    return (a_action, a_target)
```

This means the existing test suite continues to pass because `choose_action()`
produces identical results to today (no bloc biases, single track).

---

## 6. Bloc Agenda → Region Selection (Phase 2)

In `_score_developable_regions()`, add a secondary bias so that the winning admin-track
bloc's agenda shifts the region scoring:

```python
def _score_developable_regions(
    faction_name: str,
    developable: list[str],
    world: WorldState,
    bloc_biases: dict[str, float],
) -> tuple[float, str]:
    """Returns (best_score, best_region_name), adjusted for dominant admin bloc agenda."""
    faction = world.factions[faction_name]

    # Determine dominant admin-track bloc agenda
    admin_blocs = [
        b for b in faction.elite_blocs
        if BLOC_PREFERRED_TRACK.get(b.bloc_type) == "admin"
    ]
    dominant_agenda = ""
    if admin_blocs:
        dominant = max(admin_blocs, key=lambda b: b.influence * b.loyalty)
        dominant_agenda = BLOC_ADMIN_PROJECT_BIAS.get(dominant.bloc_type, "")

    best_score = -999.0
    best_region = developable[0]

    for region_name in developable:
        components = get_development_target_score_components(
            faction_name, region_name, world
        )
        if not components:
            continue
        score = components["score"]

        # Apply agenda bonus: +2 to score if region matches dominant bloc's preference
        if dominant_agenda:
            score += _get_agenda_region_bonus(region_name, dominant_agenda, world)

        if score > best_score:
            best_score = score
            best_region = region_name

    return (best_score, best_region)


def _get_agenda_region_bonus(region_name: str, agenda: str, world: WorldState) -> float:
    """Returns a score bonus for a region based on bloc agenda alignment."""
    region = world.regions[region_name]
    if agenda == "trade":
        # Merchant houses: prefer regions with market access or port adjacency
        return 2.0 if (region.market_level or 0) >= 1 else 0.0
    if agenda == "production":
        # Guilds: prefer regions with copper or stone
        return 2.0 if any(r in (region.resources or []) for r in ["copper", "stone"]) else 0.0
    if agenda == "frontier":
        # Provincial governors: prefer frontier regions
        from src.resource_economy import get_region_core_status
        return 2.0 if get_region_core_status(region) == "frontier" else 0.0
    if agenda == "food":
        # Urban commons: prefer regions needing food infrastructure
        return 2.0 if (region.irrigation_level or 0) < 1 and "grain" in (region.resources or []) else 0.0
    if agenda == "religious":
        # Priesthood: prefer regions with no shrine yet
        return 2.0 if not (region.has_shrine or False) else 0.0
    return 0.0
```

This is a lightweight secondary effect. The dominant admin-bloc's agenda shifts which
region gets developed, not whether development happens. The bias value of `+2.0` is
small relative to typical development scores, so it nudges rather than overrides.

---

## 7. Simulation Loop Changes

In `src/simulation.py`, update `_resolve_faction_action()` and
`_run_faction_action_phase()`:

```python
def _run_faction_action_phase(world, turn_order, *, verbose=True, action_provider=None):
    for faction_name in turn_order:
        update_faction_resource_economy(world, advance_resources=False)
        refresh_administrative_state(world)
        refresh_military_state(world)
        refresh_faction_visibility(world, faction_name)

        # Clear ephemeral track flags
        faction = world.factions[faction_name]
        faction.military_track_used = False
        faction.admin_track_used = False

        if action_provider is not None:
            selected_action = action_provider(faction_name, world)
            _resolve_faction_action(
                world, faction_name, verbose=verbose,
                selected_action=selected_action
            )
        else:
            # DUAL-TRACK PATH
            actions = choose_actions(faction_name, world)
            for action_name, target_region_name in actions:
                _execute_single_action(
                    world, faction_name, action_name, target_region_name,
                    verbose=verbose
                )
                # Mark track as used
                if action_name in {"expand", "attack"}:
                    faction.military_track_used = True
                elif action_name in {"develop", "invest"}:
                    faction.admin_track_used = True

        refresh_faction_visibility(world, faction_name)
        refresh_administrative_state(world)
        refresh_military_state(world)
```

Extract the action dispatch into `_execute_single_action()`:

```python
def _execute_single_action(
    world, faction_name, action_name, target_region_name, *, verbose=True
):
    """Executes one action and handles verbose output. Extracted from _resolve_faction_action."""
    if action_name == "expand":
        success = expand(faction_name, target_region_name, world)
        if verbose:
            _print_expand_result(faction_name, target_region_name, success)
    elif action_name == "attack":
        success = attack(faction_name, target_region_name, world)
        if verbose:
            _print_attack_result(faction_name, target_region_name, success)
    elif action_name in {"develop", "invest"}:
        success = develop(faction_name, target_region_name, world)
        if verbose:
            _print_develop_result(faction_name, target_region_name, success)
```

`_resolve_faction_action()` is retained unchanged for the `action_provider` path and
for any direct callers in tests.

---

## 8. Metrics and Observability

Add to the calibration report and balance dashboard:

- **Dual-track activation rate**: percentage of qualifying turns where both tracks fired.
- **Bloc competition delta**: average absolute utility bias applied by bloc competition
  (measures how much blocs are actually shifting decisions vs. being noise).
- **Track split by faction size**: average military/admin track usage broken out by
  faction region count — verifies that larger factions genuinely act on both tracks more.
- **Dominant bloc action alignment**: for each run, what fraction of military actions
  were taken by factions with military-track dominant blocs? Should be >50% if the
  competition is working.

---

## 9. Implementation Phases

### Phase 1 — Refactor `choose_action()` (no behaviour change)

Extract `_choose_military_action()`, `_choose_admin_action()`,
`_score_expandable_regions()`, `_score_attackable_regions()`, `_score_developable_regions()`
from the existing inline logic in `choose_action()`. Refactor `choose_action()` to call
them with zero biases. Run the full test suite — it should pass unchanged.

This is pure refactoring. No calibration run is needed; the output is identical.

### Phase 2 — Bloc competition biases (single-track)

Add `get_bloc_action_biases()` to `internal_politics.py`. Add the new config constants.
Update `choose_action()` to pass real bloc biases instead of zero biases.

Run 25-run calibration. Compare action distribution against baseline. The bloc biases
should be visible but not dominant — development events should decrease slightly for
factions with strong military-elite blocs; attack events should increase. If the shift
is larger than ~10% of baseline counts, reduce `BLOC_COMPETITION_MAX_BIAS`.

### Phase 3 — Dual-track activation

Add `get_available_tracks()` to `agents.py`. Add `choose_actions()`. Update
`_run_faction_action_phase()` in `simulation.py` to use `choose_actions()` for the
non-provider path.

Run 25-run calibration. Key metrics to watch:
- Development events should increase (previously crowded out by military priority).
- War events should not decrease — military actions still happen, they just no longer
  preclude development.
- Runaway victory rate should decrease slightly: large developed empires now develop
  AND expand simultaneously, but so do their rivals. The balance pressure comes from
  the admin efficiency gate — overextended empires lose the dual-track advantage.

### Phase 4 — Bloc agenda → region selection

Add `_get_agenda_region_bonus()` and update `_score_developable_regions()`. This is
a secondary effect and requires calibration only to verify it produces legible
development patterns — dominant merchant-house factions should visibly prefer
market-adjacent development, etc. Check this in a single long run against the event
log before running full calibration.

---

## 10. Risk Notes

**Doctrinal inflation:** If `BLOC_COMPETITION_MAX_BIAS = 0.18` is too high relative
to existing utility ranges, bloc competition will override doctrine entirely — a
highly insular faction with a strong military-elite bloc will start attacking anyway.
The bias should be a nudge, not a determinant. Start at `0.18` and reduce if doctrine
identity becomes less legible in runs.

**Dual-track treasury drain:** Factions acting on both tracks can spend treasury on
expand (cost 3) and attack (cost 2) in the same turn. The existing treasury gate still
applies — `_choose_military_action()` checks `treasury >= EXPANSION_COST` before
scoring — so factions cannot overspend. No additional treasury guard is needed.

**Admin efficiency as the gate:** The dual-track gate relies on `administrative_efficiency`.
This value is already stressed by overextension, unrest, and poor integration. If
it degrades too easily, large empires will rarely achieve dual-track status and the
feature will be invisible. Verify that a stable 8-region empire in normal conditions
has `administrative_efficiency >= 0.55`. If not, lower the threshold to `0.48` or
investigate whether admin efficiency is being calculated correctly for large stable
factions.

**Bloc competition in proto-states:** Proto-states currently route through the
single-track path (`is_dual = False`). Their bloc composition is sparse and their
`elite_blocs` list may be empty or contain only tribal lineages. The `get_bloc_action_biases()`
function handles empty bloc lists gracefully (returns zero biases). No special case needed.
