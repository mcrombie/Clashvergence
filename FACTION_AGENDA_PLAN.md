# Faction Agenda System — Azhora Scenario 3

Each of the ten named factions in Scenario 3 carries a single behavioral agenda that steers their AI toward a culturally appropriate outcome. Agendas are a scenario-level feature only: they are declared in the scenario config, not in the simulation engine, and they are never inherited by factions spawned during play (rebel states, successor factions).

---

## Scope Rules

- Agendas live in the scenario config (`faction_agendas` block in `azhora3.cmap.json`).
- The simulation engine has no agenda logic. `agents.py` checks `faction.agenda` and applies modifiers only when that field is set.
- `faction.is_rebel == True` → agenda is always `None`, regardless of what the config says.
- Factions that split off from an agenda faction start clean, with no agenda.

---

## Data Structure

```json
"faction_agendas": {
  "Faction1": {
    "agenda_type": "explore"
  },
  "Faction2": {
    "agenda_type": "contiguous_terrain",
    "params": { "terrain": "plains" }
  },
  "Faction3": {
    "agenda_type": "hold_regions",
    "params": { "regions": ["West Pyros", "East Pyros"] }
  },
  "Faction4": {
    "agenda_type": "settle_region",
    "params": { "target_region": "Marosh" }
  },
  "Faction5": {
    "agenda_type": "expand_territory"
  },
  "Faction6": {
    "agenda_type": "contiguous_terrain",
    "params": { "terrain": "forest" }
  },
  "Faction7": {
    "agenda_type": "trade"
  },
  "Faction8": {
    "agenda_type": "imperial",
    "params": { "region_target": 15, "prefer_tributaries": true }
  },
  "Faction9": {
    "agenda_type": "defend_region",
    "params": { "region": "Telemonia" }
  },
  "Faction10": {
    "agenda_type": "conquer"
  }
}
```

---

## Agenda Definitions

### `explore` — Bouéni (Faction 1)
Prioritize moving into regions the faction has never owned. Score all expansion moves toward uncontrolled territory higher than moves that recapture or consolidate. Treat adjacency to the unknown coast as a pull factor in region selection.

**AI effect:** When selecting a target region, add a bonus proportional to how far the region is from the faction's current territory extent. Reduce the value of staying put or consolidating when unexplored coast is reachable.

---

### `settle_region` — Moreshi (Faction 4)
Drive toward a specific named target region. Until that region is held, weight all expansion decisions that move the faction closer to it. Once the target is held, switch to a defensive-hold posture for it.

**AI effect:** Each candidate expansion region receives a bonus inversely proportional to its graph distance from `target_region`. After `target_region` is controlled, apply a strong defensive multiplier to that region (treat it like a core region for action scoring).

---

### `expand_territory` — Grassic (Faction 5)
Maximize total region count at all times. Always prefer attacking or settling empty regions over diplomatic actions. Never voluntarily cede territory.

**AI effect:** Increase the action score for any attack or settlement move. Reduce weight on economic and diplomatic actions unless they directly enable expansion.

---

### `hold_regions` — Pyrosi (Faction 3)
Maintain simultaneous control of a fixed set of named regions. If any are currently lost, treat recapture as the highest-priority action. If all are held, shift to a consolidation posture.

**AI effect:** When any target region is unowned or enemy-held, apply a strong aggression multiplier toward recapturing it. When all target regions are held, reduce overall military aggression.

---

### `contiguous_terrain` (plains) — Mittoli (Faction 2)
Build and maintain a contiguous block of regions sharing the specified terrain tag. Prefer expansion moves that extend contiguity over isolated grabs. Avoid moves that leave plains enclaves disconnected from the main bloc.

**AI effect:** Score each candidate expansion region by whether it shares the terrain tag AND is adjacent to an already-owned region of that terrain. Penalize non-contiguous grabs. If the bloc is fragmented, weight reconnection moves above new expansion.

---

### `contiguous_terrain` (forest) — Ibnael (Faction 6)
Same mechanic as Mittoli but for forest terrain. The Ibnael are drawn to the Ibenwood and its corridor; their AI should seek and maintain a connected forest holding.

**AI effect:** Identical to Mittoli's contiguous_terrain but with `terrain = "forest"`.

---

### `trade` — Elodi (Faction 7)
Maximize diplomatic relationships and trade income. Prefer forming alliances, pacts, and tributary arrangements over military expansion. Avoid wars unless directly attacked.

**AI effect:** Increase the score for diplomatic track actions (pacts, alliances, trade arrangements). Reduce military aggression significantly. When attacked, favor defensive action and peace offers over escalation.

---

### `imperial` — Elagosi (Faction 8)
Expand aggressively toward a numeric region target and, where the option exists, prefer establishing tributary relationships over direct annexation. Ambron has done this before; the empire is a known pattern, not an experiment.

**AI effect:** Apply a strong expansion bonus until `region_target` regions are held. When a candidate target is held by a weaker faction, score a tributary-offer action higher than an outright attack (if the diplomacy system supports it). Once `region_target` is reached, maintain rather than contract, but the expansion drive eases. Tributaries count toward the region target.

---

### `defend_region` — Telemon (Faction 9)
A single named region must never fall. Treat any threat to it as the highest-priority situation in the game. All other strategy is secondary.

**AI effect:** When `region` is under threat (enemy adjacent or at war with a faction adjacent to it), override normal action selection and maximize defensive response. Apply an extreme defense multiplier (e.g. 5×) to actions that protect the region. When not threatened, behave normally.

---

### `conquer` — Crefs (Faction 10)
Maximize the total number of regions taken by force. Prefer attacking over settling empty territory. Prefer war over diplomacy.

**AI effect:** Apply a persistent bonus to attack actions. Reduce diplomatic action weights. Among valid targets, prefer the weakest neighbor. The faction arrives last (turn 225) and needs to act aggressively to matter.

---

## Implementation

### Models (`src/models.py`)
Add a minimal `FactionAgenda` dataclass:

```python
@dataclass
class FactionAgenda:
    agenda_type: str          # one of the types above
    params: dict = field(default_factory=dict)
```

Add `agenda: FactionAgenda | None = None` to the `Faction` dataclass.

### World / scenario loading (`src/world.py`)
When loading a scenario config that contains `faction_agendas`, attach the corresponding `FactionAgenda` to each named `Faction`. Do not attach agendas to factions not listed in the block.

### Faction arrivals (`src/faction_arrivals.py`)
No changes needed. Agendas are attached at world-load time by faction ID. Arriving factions already have their agenda set when they activate.

### AI scoring (`src/agents.py`)
Add a single helper, `apply_agenda_modifiers(faction, candidate_action, world) -> float`, that returns a score multiplier. The main action-selection loop multiplies each candidate's base score by this value. If `faction.agenda is None` or `faction.is_rebel`, the function returns `1.0` immediately.

Each `agenda_type` branch inside that function implements the logic described in the Agenda Definitions above.

### Spawned factions
Rebel and successor factions are created with `is_rebel = True` and no `agenda` field. The `apply_agenda_modifiers` guard (`faction.is_rebel → return 1.0`) ensures they are never affected.

---

## What This Does NOT Include

- Victory scoring or point systems (agendas are behavioral, not scored)
- Stability hooks or core-region penalties
- Historical goal tracking or end-of-run reports
- Any change to the simulation engine outside of the AI scoring multiplier
