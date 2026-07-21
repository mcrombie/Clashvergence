# Language Drift Plan

## Feature Goal

Every ~100 turns, languages spoken by geographically separated populations diverge into regional subfamilies. A Grassic-speaking population that ends up under Lond cultural influence gradually becomes "Lond-Grassic"; another branch living in Mithala territory becomes "Mithala-Grassic". The parent tongue ("Grassic") survives as a shared ancestor but the living branches are distinct, have slightly different phonetics, and generate subtly different place names and culture names going forward.

This is a complement to the existing **succession sound changes** (which apply immediately when a faction splits) and **contact borrowing** (which blends profiles without creating a new entity). Drift is slower, geographically conditioned, and creates a phylogenetic tree of subfamilies rather than immediate schisms.

---

## What Already Exists (Do Not Duplicate)

| Mechanism | Location | What it does |
|---|---|---|
| `SUCCESSOR_SOUND_CHANGE_SETS` | `src/heartland.py:2973-2982` | 8 phoneme substitution rules applied on rebellion/split |
| `_build_successor_language_profile()` | `src/heartland.py:3122-3183` | Creates child LanguageProfile with 2-3 sound changes |
| `apply_language_contact_borrowing()` | `src/heartland.py:1741-1817` | Blends phonemes from neighbours into a profile |
| `Ethnicity.parent_ethnicity` | `src/models.py:212` | Already tracks lineage |
| `Ethnicity.language_family` | `src/models.py:211` | Tracks proto-family |
| `region.ethnic_composition` | `src/models.py:229+` | Population-weighted ethnicity map per region |

Drift reuses the sound-change infrastructure but drives it on a timer and geographic signal rather than a political event.

---

## New Concepts

### Branch

A **branch** is a population of ethnicity E concentrated in regions owned by a single faction (or a contiguous bloc of politically allied factions). Branches are not persisted between turns — they are computed on demand during drift evaluation.

```python
@dataclass
class EthnicBranch:
    ethnicity: str
    owning_faction: str           # majority owner of regions containing this branch
    population: int               # total population of this ethnicity in these regions
    region_ids: list[str]         # regions making up this branch
    dominant_contact: str | None  # the external culture most present in these regions
    separation_start_turn: int    # first turn this group was politically separate
```

Branches are ephemeral — computed, evaluated, then discarded. A new subfamily is created only when the split crosses the configured thresholds.

### Subfamily

A **subfamily** is a new `Ethnicity` record whose `parent_ethnicity` is the origin tongue. It has:
- A modified `LanguageProfile` (phoneme shifts and borrowed roots)
- A compound name following the `"{influence}-{parent}"` convention
- Its own entry in `world.ethnicities`
- Its own entry in `world.culture_roots` (integrates with name uniqueness plan)

The parent ethnicity is not deleted. It persists, either held by the other branch or marked as the "archaic" ancestor if all living speakers have drifted into subfamilies.

---

## Data Model Changes

### Ethnicity (`src/models.py:206-215`)

Add three fields:

```python
@dataclass
class Ethnicity:
    name: str = ""
    language_family: str = ""
    parent_ethnicity: str | None = None
    language_profile: LanguageProfile = field(default_factory=LanguageProfile)
    origin_faction: str = ""
    # NEW:
    child_ethnicities: list[str] = field(default_factory=list)
    divergence_turn: int | None = None        # turn this ethnicity split from parent
    archaic: bool = False                      # True when no living speakers remain as primary
```

`child_ethnicities` allows narrative generation to reconstruct the family tree ("Grassic → [Lond-Grassic, Mithala-Grassic]").

`archaic` marks an ethnicity that still appears in `ethnic_composition` maps (population inertia) but no longer has any faction claiming it as `primary_ethnicity` — equivalent to a dead proto-language.

### WorldState (`src/models.py` or wherever WorldState lives)

Add:

```python
language_split_history: list[LanguageSplitRecord] = field(default_factory=list)
```

```python
@dataclass
class LanguageSplitRecord:
    turn: int
    parent_ethnicity: str
    child_ethnicity: str
    trigger_faction: str        # faction whose territory held the diverging branch
    contact_influence: str      # the external culture that shaped the new branch
    sound_changes_applied: list[str]
```

This feeds the narrative system (the living chronicle and the AI interpretation summary both need language history).

---

## Algorithm

### Step 1: Drift Trigger (`src/heartland.py` — turn loop)

Every `LANGUAGE_DRIFT_INTERVAL = 100` turns, call `evaluate_language_drift(world)`.

Also check on every turn if `world.turn % LANGUAGE_DRIFT_INTERVAL == 0` (not just every 100th — allow this to be configurable so test runs can set it to 10).

### Step 2: Branch Detection (`src/language_drift.py` — new module)

For each ethnicity E in `world.ethnicities`:
1. Collect all regions where `ethnic_composition[E.name] >= BRANCH_MIN_POPULATION` (e.g. 50).
2. Group regions by their `owner`. Each distinct owner = one candidate branch.
3. Discard branches below `BRANCH_MIN_POPULATION` total.
4. If fewer than 2 branches remain → no drift possible, skip.

For each pair of branches (A, B):
- Compute `separation_turns`: how long these two owning factions have had no alliance/tributary relationship. Use `world.metrics` snapshots or a dedicated tracking field (see below).
- If `separation_turns < DRIFT_MIN_SEPARATION` (default 50 turns) → skip, too recent.

### Step 3: Separation Tracking

The algorithm needs to know how long two factions have been politically separate. Add a lightweight structure:

```python
# WorldState addition
faction_separation_start: dict[frozenset[str], int] = field(default_factory=dict)
```

Updated each turn: when two factions that were previously allied/tributary enter rivalry or neutrality, record `world.turn` as the separation start. Cleared when they re-align.

This is a small dict keyed by frozenset pairs — at most O(N²) entries for N factions, manageable.

### Step 4: Drift Intensity

For branch pair (A, B) of ethnicity E:

```python
separation_turns = world.turn - faction_separation_start.get(frozenset({A.owner, B.owner}), world.turn)
contact_intensity = get_contact_intensity(world, A.owning_faction, B.owning_faction)
# contact_intensity: 0.0 (no contact) to 1.0 (heavy trade/alliance)

drift_score = (separation_turns / DRIFT_FULL_DIVERGENCE_TURNS) * (1.0 - contact_intensity * CONTACT_DRIFT_DAMPENING)
# DRIFT_FULL_DIVERGENCE_TURNS = 200, CONTACT_DRIFT_DAMPENING = 0.4
```

If `drift_score < DRIFT_THRESHOLD` (default 0.35) → not enough divergence, skip this pair.

If `drift_score >= DRIFT_THRESHOLD` → proceed to create a subfamily for the **smaller** branch (the one with fewer speakers, who are more exposed to external influence).

### Step 5: Dominant Contact Detection

For the branch being spun off (the smaller one), identify the `dominant_contact`:
1. Collect all factions that border any region in this branch's `region_ids`.
2. Exclude the branch's own `owning_faction`.
3. Weight each candidate by: (shared border length as region count) × (trade intensity).
4. The highest-weighted external faction is `dominant_contact`.

If no dominant contact exists (isolated population) → use the terrain type as a naming hook instead ("Highland-Grassic", "Coast-Grassic").

### Step 6: Subfamily Naming

```python
def _build_subfamily_name(parent_ethnicity: str, dominant_contact: str | None, world: WorldState) -> str:
    if dominant_contact is None:
        prefix = _derive_terrain_prefix(branch_regions, world)
    else:
        contact_faction = world.factions.get(dominant_contact)
        prefix = _extract_culture_prefix(contact_faction.identity.culture_name)
    return f"{prefix}-{parent_ethnicity}"
```

`_extract_culture_prefix`: Takes the first meaningful token of the contact culture name, stripped of government-type suffixes. Examples:
- "Lond Band" → "Lond"
- "Mithala Reed Tribe" → "Mithala"
- "East Ibenwood Kingdom" → "Ibenwood"

The compound name is checked against `world.culture_roots` (name uniqueness plan). If already taken, append a directional qualifier ("North-Lond-Grassic").

### Step 7: Sound Change Selection (Contact-Weighted)

Rather than the existing random 2-3 rule selection, drift uses a **contact-weighted** selection:

1. Get the dominant contact's `language_profile`.
2. For each of the 8 `SUCCESSOR_SOUND_CHANGE_SETS` rules, score how well that rule moves the parent profile toward the contact profile:
   - If the contact profile has more "e" sounds than "a" → weight `a_to_e` higher
   - If the contact has "h" where parent has "k" → weight `k_to_h` higher
   - etc.
3. Select the top 1-2 highest-weighted rules (not random) — this makes phoneme drift directional toward the dominant contact culture, so "Lond-Grassic" genuinely sounds more Lond-like.

Apply these rules to a copy of the parent's LanguageProfile via the existing transformation logic in `_build_successor_language_profile()`.

Additionally, borrow 2-3 lexical roots from the contact profile for the semantic domains most relevant to political life: `ruler`, `dynasty`, `ancestor`, `settlement`. This represents administrative vocabulary borrowing — conquered peoples adopt the ruling class's words for governance.

### Step 8: Subfamily Creation

```python
new_ethnicity = Ethnicity(
    name=subfamily_name,
    language_family=parent.language_family,
    parent_ethnicity=parent.name,
    language_profile=drifted_profile,
    origin_faction=branch.owning_faction,
    divergence_turn=world.turn,
)
world.ethnicities[subfamily_name] = new_ethnicity
parent.child_ethnicities.append(subfamily_name)
```

Update `region.ethnic_composition` for all regions in the branch: replace `parent.name` population counts with `subfamily_name` counts (the branch's speakers now "are" Lond-Grassic, not plain Grassic).

Record a `LanguageSplitRecord` in `world.language_split_history`.

Update `world.culture_roots` (name uniqueness plan integration).

### Step 9: Parent Ethnicity Fate

The parent ethnicity keeps its population in the *other* branch (the one not spinning off). It is **not** renamed or altered. Over time:
- If all branches eventually spin off and no faction holds the parent as `primary_ethnicity` → set `parent.archaic = True`
- Archaic ethnicities still appear in `ethnic_composition` maps (historical population) but no new factions generate from them and no new place names are coined in the parent's phonetics

This mirrors how Proto-Indo-European works — the ancestor exists only in the record books while the daughters are the living tongues.

---

## Place Name Generation Impact

Place names are generated from the region's dominant ethnicity's `language_profile` (via `region_naming.py`). Once a region's ethnic composition shifts to "Lond-Grassic", new place names coined in that region will use the drifted profile — subtly different onsets and suffixes. Old names (coined under the parent Grassic profile) remain unchanged, creating a visible stratigraphy of naming eras exactly like the narrative describes ("a Marosh stone recut by Dinelv hands").

This happens automatically because `region_naming.py` reads from `world.ethnicities[dominant_ethnicity].language_profile` — no additional changes needed there.

---

## Config Constants (`src/config.py`)

```python
LANGUAGE_DRIFT_INTERVAL         = 100    # turns between drift evaluations
LANGUAGE_DRIFT_MIN_SEPARATION   = 50     # turns of political separation before drift eligible
LANGUAGE_DRIFT_FULL_TURNS       = 200    # turns at which drift_score reaches 1.0
LANGUAGE_DRIFT_THRESHOLD        = 0.35   # minimum drift_score to trigger subfamily
LANGUAGE_DRIFT_CONTACT_DAMPEN   = 0.40   # how much active contact slows drift
LANGUAGE_DRIFT_BRANCH_MIN_POP   = 50     # minimum population for a branch to count
LANGUAGE_DRIFT_SOUND_CHANGES    = 2      # number of sound-change rules applied per drift
LANGUAGE_DRIFT_LEXICAL_BORROWS  = 3      # number of lexical roots borrowed from contact
```

---

## New Module: `src/language_drift.py`

| Function | Purpose |
|---|---|
| `evaluate_language_drift(world)` | Main entry point; calls detect → score → split pipeline |
| `detect_ethnic_branches(world, ethnicity)` | Returns list of EthnicBranch for a given ethnicity |
| `compute_drift_score(world, branch_a, branch_b)` | Returns float 0.0–1.0 |
| `find_dominant_contact(world, branch)` | Returns contact faction name or None |
| `build_subfamily_name(parent, contact, world)` | Returns unique compound name string |
| `select_contact_weighted_sound_changes(parent_profile, contact_profile, n)` | Returns list of change rule names |
| `build_drifted_profile(parent_profile, rules, contact_profile)` | Returns new LanguageProfile |
| `create_subfamily(world, branch, parent, subfamily_name, drifted_profile)` | Mutates world state |
| `update_separation_tracking(world)` | Called each turn to maintain faction_separation_start dict |

---

## Modified Files

| File | Change |
|---|---|
| `src/models.py` | Add `child_ethnicities`, `divergence_turn`, `archaic` to Ethnicity; add `faction_separation_start`, `language_split_history` to WorldState |
| `src/config.py` | Add 8 new constants |
| `src/heartland.py` | Call `update_separation_tracking(world)` each turn; call `evaluate_language_drift(world)` every LANGUAGE_DRIFT_INTERVAL turns |
| `src/ai_interpretation.py` | Add `language_split_history` to summary JSON (new "language_evolution" digest section) |
| `src/narrative.py` | Include language subfamilies in place-name strata section of chronicle |
| `src/faction_naming.py` | Call `_extract_culture_root()` for subfamilies on creation (name uniqueness integration) |
| `src/language_drift.py` | **New file** — full drift pipeline |

---

## Narrative Integration

### AI Interpretation Summary

Add a `language_evolution` block to the summary JSON built in `src/ai_interpretation.py`:

```json
"language_evolution": [
  {
    "turn": 100,
    "parent": "Grassic",
    "child": "Lond-Grassic",
    "contact_influence": "Lond Band",
    "sound_changes": ["a_to_e", "k_to_h"],
    "branch_population": 3200
  }
]
```

The narrator can then say things like "In those years, the Grassic speech of the river valleys had already begun to sound different from the Grassic of the uplands — the vowels were shifting toward the Lond manner."

### Living Chronicle (LIVING_CHRONICLE_PLAN.md integration)

When a drift event occurs within the current epoch window, `build_epoch_summary()` should include it in `epoch_events`. The `compute_epoch_narrator()` function should check whether the narrator's region speaks a subfamily that diverged *during the narrator's lifetime* — if so, the narrator is aware of the shift and can reference the old forms as "the speech of our grandparents."

The `narrator_speech_note` derivation (from the Living Chronicle plan) gains a new case:
- If dominant ethnicity in narrator's region is a subfamily with `divergence_turn` within the last 150 turns: "where the old Grassic stems are still intelligible but the vowels have taken the Lond shape"
- If `divergence_turn` is more than 150 turns ago: "where the old Grassic is now a learned tongue, and the living speech is Lond-Grassic"

### Place-Name Strata in Chronicle

The existing `build_chronicle()` function (`src/narrative.py:1185-1210`) includes a "Place-Name Strata" section for 5 regions. Extend this to note when a region's place names span multiple language eras — e.g. "East Lond: oldest names in Grassic phonetics (ridges, rivers); later settlements in Lond-Grassic (administrative centres, markets)."

---

## Test Coverage

- Test: two branches of "Grassic" separated for 100 turns with drift_score ≥ threshold → produces one new subfamily
- Test: two branches with heavy trade contact (high contact_intensity) → drift suppressed below threshold
- Test: subfamily name uses dominant contact's culture prefix
- Test: subfamily name falls back to terrain prefix when no external contact
- Test: subfamily name avoids collision with existing culture_roots
- Test: drifted LanguageProfile shares parent's family_name but differs in at least 2 onsets or suffixes
- Test: parent ethnicity marked archaic only when no faction holds it as primary_ethnicity
- Test: `region.ethnic_composition` correctly transfers population from parent to child ethnicity after split
- Test: `language_split_history` records the event with correct turn and factions
- Test: `update_separation_tracking` correctly records and clears separation start turns

---

## Open Questions

1. **Multiple simultaneous drift events.** If "Grassic" splits into "Lond-Grassic" at turn 100 and then "Lond-Grassic" itself splits into "Old-Lond-Grassic" at turn 200, the compound names grow long. Cap depth at 2 levels of compounding — after that, generate a fresh coined name (the historical process by which speakers lose conscious connection to their origins).

2. **Drift for non-band ethnicities.** The initial simulation has Grassic Kin as the focus, but the same drift logic should apply to Mithala, Boueni, and other ethnicities. Any ethnicity distributed across ≥2 politically separate owners for ≥50 turns is eligible. This may generate many subfamilies. Should there be a world-level cap on simultaneous drift evaluations per cycle?

3. **Reverse convergence.** If two subfamilies end up reunited under one political roof, should their profiles slowly converge back? The existing contact borrowing mechanism (`apply_language_contact_borrowing()`) already handles this passively — subfamilies that are reunited will borrow from each other over time. No new mechanism needed, but the narrative should note this ("the two branches of Grassic began to resemble each other again under Lond administration").

4. **AI-assisted naming.** The existing pipeline has an optional GPT-based name generation path. Subfamily names via `"{contact}-{parent}"` are deterministic and don't need AI, but there could be an optional mode where the AI suggests more natural-sounding compound names ("Londric" instead of "Lond-Grassic"). Worth flagging as a future option.
