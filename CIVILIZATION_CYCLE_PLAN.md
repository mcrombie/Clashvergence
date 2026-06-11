# Civilization Cycle System — Glubb's Seven Ages

## Theoretical Basis

This system combines Sir John Glubb's *Fate of Empires* (1977) with Brooks Adams' *Law of
Civilization and Decay* (1895) to create a macro-scale civilizational lifecycle for factions.
Both thinkers independently observed that civilizations follow a roughly 250-year arc driven by
the rise and exhaustion of "vital energy" — fear, faith, and martial spirit in youth; comfort,
skepticism, and centralization in maturity.

**Glubb's seven stages** provide the implementation structure because they are more granular
than Adams' four phases and map cleanly to observable simulation variables:

| # | Stage | Character |
|---|---|---|
| 1 | Age of Pioneers (Outburst) | Small, fierce, driven by survival and raw faith |
| 2 | Age of Conquests | Military success becomes organized expansion |
| 3 | Age of Commerce | Trade replaces conquest; merchants rise |
| 4 | Age of Affluence | Wealth breeds luxury and cultural brilliance |
| 5 | Age of Intellect | Surplus creates scholars who critique and debate |
| 6 | Age of Decadence | Cynicism and pleasure-seeking replace civic virtue |
| 7 | Age of Decline and Collapse | Vital energy exhausted; collapse or revival |

**Religion is the engine of the cycle.** Glubb and Adams both observed that genuine faith —
born of real fear and uncertainty — is the primary vehicle of social cohesion and martial energy.
As prosperity removes the conditions that created that faith, religion becomes ceremonial and
political. The spiritual vacuum is why the final stages are so vulnerable: there is no cohering
force to rally the population when crisis arrives.

**The revival mechanic:** When a declining faction is struck hard by famine, invasion, or
epidemic, the material desperation can reignite genuine faith from below. This grassroots
spiritual surge — mirroring historical cases like the early Islamic expansion, the Mongol
outburst, or the Protestant Reformation — gives survivors a narrow chance to restart the
cycle rather than dissolve entirely.

**Target cycle length:** 160–300 years per full arc, averaging ~220 years. The existing 15–80
year succession micro-cycles operate within each phase, so a succession crisis in a declining
faction is catastrophic while the same crisis in a pioneering faction is routine.

---

## New Data Fields

### Add to `Faction` dataclass (`src/models.py`, after the `trade_collapse_exposure` line)

```python
# Civilizational cycle (Glubb / Brooks Adams system)
civilizational_phase: str = "pioneers"     # see stage names below
civilizational_phase_turns: int = 0        # turns spent in current phase
social_energy: float = 0.80               # Adams' vital/fear energy (0.0–1.0)
religious_vitality: float = 0.70          # genuine popular spiritual energy (0.0–1.0)
material_accumulation: float = 0.10       # rolling prosperity index (0.0–1.0)
intellectual_activity: float = 0.10       # scholarship, criticism, ideological ferment (0.0–1.0)
revival_surge_turns: int = 0              # consecutive turns qualifying for revival in decline
```

`social_energy` and `religious_vitality` are intentionally separate from the existing
`FactionReligionState` fields. They represent the *popular* spiritual and martial energy, not
the institution's health. A faction can have high `religious_legitimacy` (powerful, well-funded
clergy) while having near-zero `religious_vitality` (nobody actually believes anymore).

`intellectual_activity` is unique to Glubb: the Intellect age is one where surplus and stability
create scholars and critics. High intellectual activity drives ideological and religious reform
pressure but also accelerates the transition toward Decadence if religious vitality is low.

---

## New Module: `src/civilization_cycle.py`

Create this file. It exports one public function: `update_civilization_cycle(world)`, called
once per year-end from `_run_year_end_phase` in `simulation.py`.

---

### Constants

```python
# Internal phase names — these are the values stored in faction.civilizational_phase
PHASE_PIONEERS   = "pioneers"
PHASE_CONQUESTS  = "conquests"
PHASE_COMMERCE   = "commerce"
PHASE_AFFLUENCE  = "affluence"
PHASE_INTELLECT  = "intellect"
PHASE_DECADENCE  = "decadence"
PHASE_DECLINE    = "decline"

PHASE_ORDER = [
    PHASE_PIONEERS, PHASE_CONQUESTS, PHASE_COMMERCE,
    PHASE_AFFLUENCE, PHASE_INTELLECT, PHASE_DECADENCE, PHASE_DECLINE,
]

# ---- Social energy ----
# Each phase has an equilibrium social_energy pulls toward
SOCIAL_ENERGY_EQUILIBRIUM = {
    PHASE_PIONEERS:  0.85,
    PHASE_CONQUESTS: 0.72,
    PHASE_COMMERCE:  0.52,
    PHASE_AFFLUENCE: 0.38,
    PHASE_INTELLECT: 0.28,
    PHASE_DECADENCE: 0.18,
    PHASE_DECLINE:   0.12,
}

SOCIAL_ENERGY_HARDSHIP_GAIN  = 0.05   # per turn when hardship signal is maxed
SOCIAL_ENERGY_PROSPERITY_LOSS = 0.04  # per turn when prosperity signal is maxed
SOCIAL_ENERGY_MEAN_REVERSION  = 0.015 # pull toward phase equilibrium each turn

# ---- Religious vitality ----
RELIGIOUS_VITALITY_REVERSION_RATE = 0.08  # how fast vitality tracks its target
VITALITY_REFORM_PRESSURE_RATE     = 0.04  # extra reform_pressure per unit vitality above 0.60

# ---- Intellectual activity ----
INTELLECTUAL_REVERSION_RATE       = 0.06
INTELLECTUAL_IDEOLOGY_PRESSURE    = 0.03  # ideology.reform_pressure boost per unit above 0.50
INTELLECTUAL_RELIGION_PRESSURE    = 0.025 # religion.reform_pressure boost per unit above 0.50

# ---- Material accumulation ----
MATERIAL_ACCUMULATION_SMOOTHING   = 0.10  # rolling average weight (~10-turn lag)

# ---- Phase transitions ----
# Base probability per turn once conditions are met.
# Scales +1% for each turn beyond the minimum, preventing eternal stagnation.
PHASE_BASE_CHANCE = {
    PHASE_PIONEERS:  0.07,
    PHASE_CONQUESTS: 0.06,
    PHASE_COMMERCE:  0.05,
    PHASE_AFFLUENCE: 0.05,
    PHASE_INTELLECT: 0.05,
    PHASE_DECADENCE: 0.04,
    PHASE_DECLINE:   0.09,   # revival window; higher chance once conditions met
}

# Minimum turns in phase before transition can fire
PHASE_MIN_TURNS = {
    PHASE_PIONEERS:  8,
    PHASE_CONQUESTS: 12,
    PHASE_COMMERCE:  18,
    PHASE_AFFLUENCE: 20,
    PHASE_INTELLECT: 15,
    PHASE_DECADENCE: 12,
    PHASE_DECLINE:   8,
}

# Revival
REVIVAL_HARDSHIP_THRESHOLD = 0.50   # famine + epidemic + shock must exceed this
REVIVAL_VITALITY_THRESHOLD = 0.65   # religious_vitality must exceed this
REVIVAL_SURGE_REQUIRED     = 5      # consecutive qualifying turns to unlock revival
```

---

### `_update_material_accumulation(faction)`

Rolling prosperity index built from food balance, trade income, and treasury, minus active
hardship signals.

```python
def _update_material_accumulation(faction: Faction) -> None:
    food_consumption = max(faction.food_consumption, 1.0)
    food_signal  = clamp(faction.food_balance / food_consumption * 0.5 + 0.5, 0.0, 1.0)
    trade_signal = clamp(faction.trade_income / 30.0, 0.0, 1.0)
    treasury_sig = clamp(faction.treasury / 200.0, 0.0, 1.0)

    hardship_drag = clamp(
        faction.famine_pressure   * 0.40
        + faction.epidemic_pressure * 0.25
        + faction.shock_exposure    * 0.20
        + clamp(faction.food_deficit / food_consumption, 0.0, 1.0) * 0.15,
        0.0, 1.0
    )

    raw = clamp(
        food_signal  * 0.30
        + trade_signal * 0.30
        + treasury_sig * 0.25
        + (1.0 - hardship_drag) * 0.15,
        0.0, 1.0
    )

    faction.material_accumulation = (
        faction.material_accumulation * (1.0 - MATERIAL_ACCUMULATION_SMOOTHING)
        + raw * MATERIAL_ACCUMULATION_SMOOTHING
    )
```

---

### `_update_social_energy(faction)`

Adams' "vital energy" / "fear." Rises under material hardship; falls under prosperity.
Each phase has a natural equilibrium it slowly pulls toward.

```python
def _update_social_energy(faction: Faction) -> None:
    food_consumption = max(faction.food_consumption, 1.0)

    hardship = clamp(
        faction.famine_pressure     * 0.35
        + faction.epidemic_pressure * 0.25
        + faction.shock_exposure    * 0.20
        + clamp(faction.food_deficit / food_consumption, 0.0, 1.0) * 0.20,
        0.0, 1.0
    )

    prosperity = clamp(
        clamp(faction.food_balance / food_consumption, 0.0, 1.0) * 0.35
        + clamp(faction.trade_income / 30.0, 0.0, 1.0)           * 0.30
        + clamp(faction.treasury / 200.0, 0.0, 1.0)              * 0.20
        + faction.material_accumulation                           * 0.15,
        0.0, 1.0
    )

    equilibrium = SOCIAL_ENERGY_EQUILIBRIUM[faction.civilizational_phase]

    delta = (
        hardship   * SOCIAL_ENERGY_HARDSHIP_GAIN
        - prosperity * SOCIAL_ENERGY_PROSPERITY_LOSS
        - (faction.social_energy - equilibrium) * SOCIAL_ENERGY_MEAN_REVERSION
    )

    faction.social_energy = clamp(faction.social_energy + delta, 0.05, 1.0)
```

---

### `_update_religious_vitality(faction)`

Genuine popular faith, not institutional legitimacy. Tracks social energy but is suppressed
when `state_cult_strength` is high (religion-as-politics crowds out authentic belief). Feeds
the existing `reform_pressure` when high.

```python
def _update_religious_vitality(faction: Faction) -> None:
    target = clamp(
        faction.social_energy                          * 0.55
        + (1.0 - faction.material_accumulation)       * 0.30
        + (1.0 - faction.religion.state_cult_strength) * 0.15,
        0.05, 0.95
    )

    delta = (target - faction.religious_vitality) * RELIGIOUS_VITALITY_REVERSION_RATE
    faction.religious_vitality = clamp(faction.religious_vitality + delta, 0.05, 1.0)

    # Genuine faith creates pressure for real reform (not top-down state reform)
    if faction.religious_vitality > 0.60:
        boost = (faction.religious_vitality - 0.60) * VITALITY_REFORM_PRESSURE_RATE
        faction.religion.reform_pressure = min(1.0, faction.religion.reform_pressure + boost)
```

---

### `_update_intellectual_activity(faction)`

Glubb's Intellect age originates in surplus and administrative complexity. This metric rises as
wealth and bureaucracy grow; it feeds ideological and religious reform pressure and accelerates
the Decadence transition if religious vitality is low.

```python
def _update_intellectual_activity(faction: Faction) -> None:
    # Wealth and administrative depth fund scholarship
    wealth_driver = clamp(
        faction.material_accumulation * 0.60
        + clamp(faction.trade_income / 50.0, 0.0, 1.0) * 0.40,
        0.0, 1.0
    )
    # Cap at faction's administrative capacity (proxy for bureaucratic complexity)
    admin_cap = clamp(faction.administrative_capacity / 5.0, 0.0, 1.0)

    target = clamp(
        wealth_driver * 0.60
        + admin_cap   * 0.25
        + faction.intellectual_activity * 0.15,  # mild self-reinforcement
        0.05, 0.90
    )

    delta = (target - faction.intellectual_activity) * INTELLECTUAL_REVERSION_RATE
    faction.intellectual_activity = clamp(faction.intellectual_activity + delta, 0.05, 1.0)

    if faction.intellectual_activity > 0.50:
        over = faction.intellectual_activity - 0.50
        faction.ideology.reform_pressure = min(
            1.0, faction.ideology.reform_pressure + over * INTELLECTUAL_IDEOLOGY_PRESSURE
        )
        faction.religion.reform_pressure = min(
            1.0, faction.religion.reform_pressure + over * INTELLECTUAL_RELIGION_PRESSURE
        )
```

---

### `_check_revival_surge(faction)`

Tracks whether a Decline-phase faction is accumulating the hardship + spiritual awakening
conditions required to unlock revival. Also applies in late Decadence.

```python
def _check_revival_surge(faction: Faction) -> None:
    if faction.civilizational_phase not in (PHASE_DECADENCE, PHASE_DECLINE):
        faction.revival_surge_turns = 0
        return

    hardship_total = (
        faction.famine_pressure
        + faction.epidemic_pressure
        + faction.shock_exposure
    )
    qualifying = (
        hardship_total > REVIVAL_HARDSHIP_THRESHOLD
        and faction.religious_vitality > 0.50
    )

    if qualifying:
        faction.revival_surge_turns += 1
        # Extreme hardship directly pushes religious vitality upward (spiritual awakening)
        faction.religious_vitality = min(1.0, faction.religious_vitality + 0.025)
    else:
        faction.revival_surge_turns = max(0, faction.revival_surge_turns - 1)
```

---

### `_check_phase_transitions(faction, world)`

Tests conditions for the next phase. Base probability scales up +1% per turn beyond the
minimum, preventing any phase from becoming permanent.

```python
def _check_phase_transitions(faction: Faction, world: WorldState) -> None:
    faction.civilizational_phase_turns += 1
    phase     = faction.civilizational_phase
    min_turns = PHASE_MIN_TURNS[phase]

    if faction.civilizational_phase_turns < min_turns:
        return

    overage = faction.civilizational_phase_turns - min_turns
    chance  = PHASE_BASE_CHANCE[phase] + overage * 0.01

    if phase == PHASE_PIONEERS:
        # Growth and early military success signal readiness for organized conquest
        if (faction.material_accumulation > 0.30
                and faction.social_energy > 0.65
                and random.random() < chance):
            _transition_to(faction, PHASE_CONQUESTS, world)

    elif phase == PHASE_CONQUESTS:
        # Conquest wealth flows back; merchants begin to displace warriors
        if (faction.material_accumulation > 0.42
                and faction.social_energy < 0.70
                and faction.trade_income > 5.0
                and random.random() < chance):
            _transition_to(faction, PHASE_COMMERCE, world)

    elif phase == PHASE_COMMERCE:
        # Sustained wealth and intellectual confidence signal affluence
        if (faction.material_accumulation > 0.56
                and faction.social_energy < 0.52
                and faction.intellectual_activity > 0.22
                and random.random() < chance):
            _transition_to(faction, PHASE_AFFLUENCE, world)

    elif phase == PHASE_AFFLUENCE:
        # Scholars flourish when material comfort is established
        if (faction.material_accumulation > 0.65
                and faction.intellectual_activity > 0.45
                and faction.social_energy < 0.40
                and random.random() < chance):
            _transition_to(faction, PHASE_INTELLECT, world)

    elif phase == PHASE_INTELLECT:
        # Two possible exits:

        # Path A (Decadence): skepticism destroys remaining faith
        if (faction.religious_vitality < 0.32
                and faction.social_energy < 0.28
                and random.random() < chance):
            _transition_to(faction, PHASE_DECADENCE, world)

        # Path B (Intellectual Revival — rare Protestant Reformation analogy):
        # High intellectual ferment + surging vitality = reformation → restart at Commerce
        elif (faction.religious_vitality > 0.68
                and faction.intellectual_activity > 0.55
                and random.random() < chance * 0.4):
            _transition_to(faction, PHASE_COMMERCE, world)

    elif phase == PHASE_DECADENCE:
        # Overextension, low legitimacy, and atrophy signal collapse onset
        if (faction.administrative_overextension > 0.32
                and faction.social_energy < 0.20
                and faction.succession.claimant_pressure > 0.55
                and random.random() < chance):
            _transition_to(faction, PHASE_DECLINE, world)

        # Revival can also begin in decadence if hardship is severe enough
        elif (faction.religious_vitality > REVIVAL_VITALITY_THRESHOLD
                and faction.revival_surge_turns >= REVIVAL_SURGE_REQUIRED
                and random.random() < chance * 0.6):
            _transition_to(faction, PHASE_CONQUESTS, world)

    elif phase == PHASE_DECLINE:
        # Revival: hardship has relit genuine faith; faction rebuilds from scratch
        if (faction.religious_vitality > REVIVAL_VITALITY_THRESHOLD
                and faction.revival_surge_turns >= REVIVAL_SURGE_REQUIRED
                and random.random() < chance):
            _transition_to(faction, PHASE_CONQUESTS, world)
        # Note: actual collapse/dissolution is handled by the existing succession and
        # rebel systems — this module just makes those events far more likely in Decline.
```

---

### `_transition_to(faction, new_phase, world)`

Applies the phase change and any one-time stat perturbations.

```python
def _transition_to(faction: Faction, new_phase: str, world: WorldState) -> None:
    world.events.append({
        "turn":    world.current_turn,
        "faction": faction.name,
        "type":    "civilizational_phase_transition",
        "from":    faction.civilizational_phase,
        "to":      new_phase,
    })

    faction.civilizational_phase       = new_phase
    faction.civilizational_phase_turns = 0

    if new_phase == PHASE_CONQUESTS:
        faction.military_tradition = min(1.0, faction.military_tradition + 0.05)

    elif new_phase == PHASE_COMMERCE:
        faction.religion.religious_tolerance = min(0.95, faction.religion.religious_tolerance + 0.08)

    elif new_phase == PHASE_AFFLUENCE:
        faction.religion.state_cult_strength = min(0.95, faction.religion.state_cult_strength + 0.10)

    elif new_phase == PHASE_INTELLECT:
        # Ideology becomes volatile
        faction.ideology.radicalism = min(1.0, faction.ideology.radicalism + 0.10)

    elif new_phase == PHASE_DECADENCE:
        faction.military_tradition        = max(0.0, faction.military_tradition - 0.12)
        faction.succession.claimant_pressure = min(1.0, faction.succession.claimant_pressure + 0.18)
        faction.shock_resilience          = max(0.0, faction.shock_resilience - 0.12)

    elif new_phase == PHASE_DECLINE:
        faction.military_tradition        = max(0.0, faction.military_tradition - 0.10)
        faction.succession.claimant_pressure = min(1.0, faction.succession.claimant_pressure + 0.20)
        faction.shock_resilience          = max(0.0, faction.shock_resilience - 0.15)
        faction.administrative_overextension = min(1.0, faction.administrative_overextension + 0.08)

    # Revival (back to Conquests from Decadence or Decline)
    if new_phase == PHASE_CONQUESTS and faction.revival_surge_turns > 0:
        faction.social_energy            = min(1.0, faction.social_energy + 0.25)
        faction.religious_vitality       = min(1.0, faction.religious_vitality + 0.20)
        faction.religion.religious_zeal  = min(0.95, faction.religion.religious_zeal + 0.20)
        faction.religion.state_cult_strength = max(0.10, faction.religion.state_cult_strength - 0.25)
        faction.religion.reform_pressure = min(1.0, faction.religion.reform_pressure + 0.45)
        faction.revival_surge_turns      = 0
```

---

### `_apply_phase_effects(faction)`

Per-turn nudges. Small enough that no single year matters, but over decades they shape
the faction toward the character of its current age.

```python
def _apply_phase_effects(faction: Faction) -> None:
    phase = faction.civilizational_phase

    if phase == PHASE_PIONEERS:
        faction.military_tradition = min(1.0, faction.military_tradition + 0.012)
        faction.shock_resilience   = min(1.0, faction.shock_resilience + 0.008)
        if faction.religion.religious_zeal < 0.78:
            faction.religion.religious_zeal += 0.007
        if faction.religion.state_cult_strength > 0.35:
            faction.religion.state_cult_strength -= 0.006

    elif phase == PHASE_CONQUESTS:
        faction.military_tradition = min(1.0, faction.military_tradition + 0.008)
        faction.shock_resilience   = min(1.0, faction.shock_resilience + 0.004)
        if faction.religion.state_cult_strength < 0.55:
            faction.religion.state_cult_strength += 0.003  # state adopts victorious faith

    elif phase == PHASE_COMMERCE:
        faction.merchant_capacity = min(1.0, faction.merchant_capacity + 0.005)
        if faction.religion.religious_tolerance < 0.65:
            faction.religion.religious_tolerance += 0.005
        if faction.religion.religious_zeal > 0.35:
            faction.religion.religious_zeal -= 0.005
        if faction.religion.state_cult_strength < 0.65:
            faction.religion.state_cult_strength += 0.003

    elif phase == PHASE_AFFLUENCE:
        faction.merchant_capacity  = min(1.0, faction.merchant_capacity + 0.003)
        faction.military_tradition = max(0.05, faction.military_tradition - 0.004)
        if faction.religion.religious_zeal > 0.25:
            faction.religion.religious_zeal -= 0.006
        if faction.religion.state_cult_strength < 0.80:
            faction.religion.state_cult_strength += 0.004
        faction.administrative_overextension = min(
            1.0, faction.administrative_overextension + 0.003
        )

    elif phase == PHASE_INTELLECT:
        faction.military_tradition = max(0.05, faction.military_tradition - 0.006)
        faction.shock_resilience   = max(0.0,  faction.shock_resilience - 0.005)
        # Intellectual debate breeds political factionalism
        faction.succession.claimant_pressure = min(
            1.0, faction.succession.claimant_pressure + 0.006
        )

    elif phase == PHASE_DECADENCE:
        faction.shock_resilience   = max(0.0, faction.shock_resilience - 0.008)
        faction.military_tradition = max(0.0, faction.military_tradition - 0.007)
        faction.succession.claimant_pressure = min(
            1.0, faction.succession.claimant_pressure + 0.010
        )
        faction.administrative_overextension = min(
            1.0, faction.administrative_overextension + 0.005
        )
        # Even the pretense of state religion hollows out
        if faction.religion.state_cult_strength > 0.30:
            faction.religion.state_cult_strength -= 0.004

    elif phase == PHASE_DECLINE:
        faction.shock_resilience   = max(0.0, faction.shock_resilience - 0.012)
        faction.military_tradition = max(0.0, faction.military_tradition - 0.010)
        faction.succession.claimant_pressure = min(
            1.0, faction.succession.claimant_pressure + 0.015
        )
        faction.administrative_overextension = min(
            1.0, faction.administrative_overextension + 0.008
        )
        # Desperate populations naturally turn toward faith — passive vitality boost
        if faction.religious_vitality < 0.50:
            faction.religious_vitality = min(1.0, faction.religious_vitality + 0.004)
```

---

### `update_civilization_cycle(world)` — public entry point

```python
def update_civilization_cycle(world: WorldState) -> None:
    for faction in world.factions.values():
        if faction.is_rebel and faction.rebel_age < 3:
            # New rebels start martial; don't run cycle until stabilized
            continue
        _update_material_accumulation(faction)
        _update_social_energy(faction)
        _update_religious_vitality(faction)
        _update_intellectual_activity(faction)
        _check_revival_surge(faction)
        _check_phase_transitions(faction, world)
        _apply_phase_effects(faction)
```

---

## Integration: `src/simulation.py`

### Import

```python
from src.civilization_cycle import update_civilization_cycle
```

### `_run_year_end_phase`

Add at the **end**, after all other updates have settled.

```python
def _run_year_end_phase(world):
    advance_long_run_economic_dynamics(world)
    update_religious_legitimacy(world)
    resolve_dynastic_succession(world)
    update_region_populations(world)
    update_region_settlement_levels(world)
    update_urban_specializations(world)
    update_elite_blocs(world)
    update_ideologies(world)
    update_rebel_faction_status(world)
    update_faction_polity_tiers(world)
    update_civilization_cycle(world)   # ← add here
```

---

## Initialization: `src/factions.py`

**New rebel factions** — always start as pioneers:

```python
new_faction.civilizational_phase    = "pioneers"
new_faction.social_energy           = 0.82
new_faction.religious_vitality      = 0.72
new_faction.material_accumulation   = 0.12
new_faction.intellectual_activity   = 0.08
```

**Established factions spawned mid-simulation** — infer starting phase from existing state.
Add a helper at the end of the faction initialization that calls:

```python
def _infer_initial_phase(faction: Faction) -> str:
    if faction.administrative_overextension > 0.30:
        return "decadence"
    if faction.material_accumulation > 0.60:
        return "affluence"
    if faction.material_accumulation > 0.42:
        return "commerce"
    return "conquests"
```

---

## Snapshot: `src/simulation_ui.py`

The HTML UI is generated by Python. The faction snapshot dictionary (wherever it is built for
embedding in the HTML data blob) needs these new fields added so the JavaScript can read them.

### In the faction snapshot builder, add:

```python
"civilizational_phase":       faction.civilizational_phase,
"civilizational_phase_turns": faction.civilizational_phase_turns,
"social_energy":              round(faction.social_energy, 3),
"religious_vitality":         round(faction.religious_vitality, 3),
"material_accumulation":      round(faction.material_accumulation, 3),
"intellectual_activity":      round(faction.intellectual_activity, 3),
```

---

## UI: Civilizational Stage Display

### Stage metadata (embed as a JavaScript constant in the generated HTML)

Add the following lookup object in the `<script>` block near the other constant definitions:

```javascript
const CIVI_STAGES = {
  pioneers:  {
    label: "Age of Pioneers",
    color: "#c0392b",
    summary: "A fierce, desperate people burst from obscurity on pure martial and spiritual energy."
  },
  conquests: {
    label: "Age of Conquests",
    color: "#e67e22",
    summary: "Military success becomes systematic; expansion and dominion define the generation."
  },
  commerce:  {
    label: "Age of Commerce",
    color: "#d4ac0d",
    summary: "Conquest yields to trade; wealth grows and merchants displace warriors in prestige."
  },
  affluence: {
    label: "Age of Affluence",
    color: "#27ae60",
    summary: "Accumulated wealth fosters luxury, grandeur, and the arts — but softens the martial spirit."
  },
  intellect: {
    label: "Age of Intellect",
    color: "#2980b9",
    summary: "Surplus and stability breed scholars and critics who question faith and the foundations of order."
  },
  decadence: {
    label: "Age of Decadence",
    color: "#8e44ad",
    summary: "Cynicism and pleasure-seeking replace civic virtue; the state buys loyalty it can no longer inspire."
  },
  decline:   {
    label: "Age of Decline",
    color: "#7f8c8d",
    summary: "Vital energy is exhausted; the realm fractures under its own weight — or endures long enough to revive."
  },
};
```

---

### Civilizational Stage card in `renderSelectedFactionView`

In the `renderSelectedFactionView(snapshot)` function, insert a new card **before** the existing
"Realm Snapshot" card (i.e., as the first card in the inspector grid). The card should follow
the same HTML structure and CSS class conventions used by the other cards in that function.

The card must render:

1. **Stage badge** — A colored pill/badge using `CIVI_STAGES[phase].color` as the background,
   displaying `CIVI_STAGES[phase].label`.

2. **Stage summary** — One sentence of flavour text: `CIVI_STAGES[phase].summary`.

3. **Years in stage** — `faction.civilizational_phase_turns` formatted as "Year N of this age".

4. **Four metric bars** — Horizontal progress bars (0–100%) for:
   - Social Energy (`faction.social_energy`)
   - Religious Vitality (`faction.religious_vitality`)
   - Material Wealth (`faction.material_accumulation`)
   - Intellectual Activity (`faction.intellectual_activity`)
   
   Each bar shows the label, the bar itself, and the numeric value (e.g. `0.42`).
   Color the bar fills consistently with the stage color or a neutral accent color.

5. **Revival note** (only shown when phase is `"decadence"` or `"decline"` AND
   `revival_surge_turns > 0`) — A short line such as:
   *"Spiritual awakening stirring — revival surge: N / 5 turns"*
   rendered in the `CIVI_STAGES.pioneers.color` (red) to signal urgency.

The card title should read **"Civilizational Age"**.

---

### Phase indicator in `renderStandings`

In `renderStandings(snapshot)`, for each faction card rendered in the standings bar,
add a small colored dot and short label immediately after the faction name.

The dot should:
- Be a small circle (`width: 8px; height: 8px; border-radius: 50%`) using
  `CIVI_STAGES[phase].color` as `background-color`.
- Be followed by a short text label in a muted style (e.g. `font-size: 0.7em; opacity: 0.75`)
  showing only the stage keyword (e.g. "Commerce", "Decline") — not the full "Age of" prefix,
  since space is limited.

Wrap the dot and label together in a `<span>` with `display: inline-flex; align-items: center;
gap: 3px;` and place it on its own line below the faction name using `display: block`.

---

## Interaction Map

No existing functions need internal changes. The new module writes to existing fields through
per-turn nudges and spike values on transition. Existing crisis systems then fire naturally.

| New field / action | Writes to existing field | Consumed by |
|---|---|---|
| `religious_vitality > 0.60` | `religion.reform_pressure` ↑ | `update_religious_legitimacy` → reformations |
| Pioneers/Conquests effects | `military_tradition`, `shock_resilience` ↑ | `refresh_military_state`, `shocks.py` |
| Commerce effects | `merchant_capacity`, `religious_tolerance` ↑ | trade functions in `resource_economy.py` |
| Affluence/Intellect effects | `administrative_overextension` ↑, `military_tradition` ↓ | heartland.py succession, shocks |
| Decadence/Decline effects | `succession.claimant_pressure` ↑, `shock_resilience` ↓ | succession crisis logic, shocks |
| `intellectual_activity > 0.50` | `ideology.reform_pressure` ↑, `religion.reform_pressure` ↑ | `update_ideologies`, `update_religious_legitimacy` |
| Revival transition | `religion.reform_pressure` +0.45 spike | Triggers reformation within ~1–5 turns |
| Decline transition | `succession.claimant_pressure` +0.20 spike | May immediately trigger succession crisis |

---

## Expected Emergent Behavior

**Nominal cycle (no extreme shocks):**

| Phase | Duration | Observable signals |
|---|---|---|
| Pioneers | 15–35 yr | Peak military tradition; fervent zeal; rapid territorial growth |
| Conquests | 20–45 yr | Sustained expansion; state adopts religion; legitimacy high |
| Commerce | 30–55 yr | Rising trade income; tolerance grows; zeal softens |
| Affluence | 35–65 yr | Luxury goods; grand monuments; mercenary armies |
| Intellect | 20–45 yr | High reform pressure; ideological schisms; military declining |
| Decadence | 20–40 yr | Succession crises; overextension worsening; shock vulnerability up |
| Decline | 15–35 yr | Either collapses (existing mechanics) or revival fires |
| **Total** | **155–320 yr** | **Average ~230 yr** |

**Revival dynamics:**
- A faction must survive to decline to revive. Factions that collapse before accumulating 5
  revival surge turns simply dissolve — a common outcome.
- Successful revival always returns to **Conquests** (not Pioneers), representing a
  reinvigorated but not entirely new society. The old culture does not fully die.
- Intellect → Commerce revival (rare reformation path) represents the Reformation analogy:
  intellectual ferment produces genuine renewed faith rather than skepticism.

**Conquest dynamics:**
- A martial faction absorbing a centralized one gains wealth that accelerates its own
  transition to Commerce. Conquerors frequently inherit the rot of the conquered.
- Factions in Decline are significantly more vulnerable: lower `shock_resilience`, higher
  `claimant_pressure`, weaker military — all compounding the existing crisis triggers.

---

## What This Does NOT Change

- Succession trigger ages (58/73), crisis scoring, and dynasty rotation logic are unchanged.
- Religious legitimacy calculation in `update_religious_legitimacy` is unchanged.
- Elite bloc mechanics are unchanged.
- Shock generation and decay rates are unchanged.
- The existing collapse/dissolution mechanics (rebel secession, faction death) are unchanged.

The civilizational cycle is purely additive: it adjusts the *likelihood* of events the existing
systems already handle. Decadent factions don't die from a new death rule — they die because
`claimant_pressure` built for 40 years until a succession crisis finally spiraled into civil war.

---

## Testing

Run the simulation for 600+ turns with event logging enabled and verify:

1. At least one faction completes a full Pioneers → Conquests → Commerce → Affluence →
   Intellect → Decadence → Decline arc without external intervention.
2. At least one Decline-phase faction achieves revival if it survives long enough under hardship.
3. `religious_vitality` and `social_energy` move in the opposite direction to
   `material_accumulation` and `intellectual_activity`.
4. Phase transitions appear correctly in the event stream.
5. `reform_pressure` spikes after a revival transition (should trigger reformation in ~1–5 turns).
6. Succession crises are visibly more frequent in Decadence and Decline phases.
7. The "Civilizational Age" card renders in the faction panel for all factions.
8. The standings bar shows a colored dot and short stage label for each faction.

**Diagnostic plot:** for a single long-lived faction, plot `social_energy`, `religious_vitality`,
`material_accumulation`, and `intellectual_activity` over time. You should see accumulation and
intellectual activity lead the cycle while social energy and vitality lag in inverse relationship
to them.
