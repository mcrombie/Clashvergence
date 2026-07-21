# Polity Name Uniqueness Plan

## Problem

Multiple factions can share the same base word — e.g. several polities all called some variant of "Lond". This is both a readability problem in the narrative and a signal that the name system has gaps in its collision handling.

---

## Root Causes

There are four distinct mechanisms that produce name redundancy. Each needs its own fix.

---

### Cause 1: Directional region prefixes are stripped for rebel names, collapsing siblings

**Location:** `src/heartland.py:3258` (`_get_rebel_region_name_root`)

When a region called "East Lond" secedes, the directional prefix is stripped to produce root `"Lond"`. A second secession from "West Lond" independently produces the same root `"Lond"` — resulting in "Lond Rebels" and "Lond Rebels 2". The numeric suffix is the only guard, and it does not prevent the conceptual collision; both polities still *are* Lond.

**This is the primary source of the "multiple Londs" problem.**

---

### Cause 2: Named-group rebels inherit the parent's full culture name

**Location:** `src/heartland.py:3229-3243`

Sixteen hardcoded named groups (grassic, boueni, mittoli, etc.) cause rebels to inherit the parent's `culture_name` instead of deriving a new one from the region. So a "Grassic Kin Tribe" civil war produces "Grassic Rebels", leaving two active factions sharing the root "Grassic".

---

### Cause 3: The similarity check (`_is_too_similar`, threshold 0.8) only runs at world generation

**Location:** `src/faction_naming.py:272-285`

Initial factions are deduplicated against each other at creation time. Rebel and civil-war factions created later do not pass through this check at all — only the basic `while candidate in world.factions` loop runs, which only catches exact `display_name` collisions, not near-matches on root words.

---

### Cause 4: Polity tier upgrades are not checked for display_name collisions

When a faction upgrades from Band → Tribe → Chiefdom, its `display_name` changes (e.g., "Lond Band" → "Lond Tribe"). If another "Lond Tribe" already exists, there is no guard — the upgrade proceeds silently and two factions share the same display_name.

**Location:** Faction tier upgrade logic (faction display_name reassignment in `src/factions.py` and `src/heartland.py`).

---

## Fix Plan

### Fix 1: Culture Root Registry

Introduce a `world.culture_roots: set[str]` that tracks the **normalised base word** of every active faction's culture name. This is the single source of truth for collision detection.

**What counts as a "root":** lowercase of the longest token in `culture_name` after stripping directional prefixes ("East", "West", "North", "South", "Upper", "Lower", "Inner", "Outer", "Old", "New", "Greater", "Lesser") and government-type suffixes ("Band", "Tribe", "Kingdom", etc.).

Examples:
- "Lond Band" → root `"lond"`
- "East Lond" (region) → root `"lond"`
- "Grassic Kin Tribe" → root `"grassic"` (or `"grassic kin"` as compound — see below)

**Implementation sketch:**

```python
def extract_culture_root(name: str) -> str:
    DIRECTIONAL = {"east", "west", "north", "south", "upper", "lower",
                   "inner", "outer", "old", "new", "greater", "lesser"}
    GOV_TYPES   = {"band", "tribe", "chiefdom", "kingdom", "republic",
                   "assembly", "council", "rising", "rebels"}
    tokens = name.lower().split()
    tokens = [t for t in tokens if t not in DIRECTIONAL and t not in GOV_TYPES]
    return " ".join(tokens)
```

Add `culture_roots` to `WorldState` (`src/models.py`), populate it during world initialisation (`src/world.py`), and update it whenever a faction is created or destroyed.

---

### Fix 2: Rebel Naming — Retain the Directional Qualifier When Root Is Taken

**Location:** `src/heartland.py:3246-3280` (`_build_rebel_faction_name`, `_get_rebel_region_name_root`)

Current logic strips "East" from "East Lond" and produces root `"Lond"`. Change it to:

1. Compute the bare root (stripped).
2. Check `world.culture_roots` for a collision.
3. **If the root is already in use**, keep the directional prefix: root becomes `"East Lond"` → display_name "East Lond Rebels" (and culture_name "East Lond").
4. If *that* is also taken, try terrain qualifiers derived from the region's terrain type ("Mountain Lond", "River Lond", "Coast Lond").
5. If all qualifiers are exhausted, generate a fresh culture name from the region's language family via the existing `_generate_family_scoped_culture_name()` pipeline.

This preserves meaningful geography in the name rather than falling back to ugly numeric suffixes.

---

### Fix 3: Named-Group Rebels — Add a Geographic Qualifier

**Location:** `src/heartland.py:3229-3243`, `create_rebel_faction()` (line 3469)

For the 16 hardcoded named groups, when the parent's `culture_name` would be inherited as-is:

1. Check if `culture_name` root is already in `world.culture_roots` (it will be — the parent holds it).
2. Prepend a geographic qualifier from the rebel region: `f"{direction_or_terrain} {culture_name}"`.
   - Direction: derived from region's map position relative to the parent's capital.
   - Terrain: from the region's terrain type if no clear direction.
3. If the compound is still colliding (because parent already controls "East Grassic" too), fall through to the terrain qualifier, then to a fresh generated name.

**Example output:** instead of "Grassic Rebels 2", produce "Mountain Grassic Rebels" or "River Grassic Rebels".

---

### Fix 4: Apply Similarity Check to All New Factions, Not Just World Gen

**Location:** `src/faction_naming.py:272-285`, `src/heartland.py:_build_rebel_faction_name`

The existing `_is_too_similar(candidate, existing, threshold=0.8)` function uses `SequenceMatcher` and already does the right thing — it just isn't called for rebels.

After computing the candidate culture name for any new faction (rebel, civil-war, restoration), run it through `_is_too_similar()` against all current `world.culture_roots`. If similarity ≥ 0.75 (slightly looser than the 0.8 generation-time threshold, to catch root-sharing more aggressively), treat it as a collision and apply the qualifier logic from Fix 2/3.

---

### Fix 5: Guard Polity Tier Upgrades Against Display Name Collisions

**Location:** wherever `faction.identity.display_name` and `faction.name` are updated on tier change

Before writing the new display_name on upgrade:

```python
new_display = f"{faction.identity.culture_name} {new_gov_type}"
if new_display in world.factions and world.factions[new_display] is not faction:
    # append geographic qualifier to culture_name before building display_name
    qualifier = _derive_geographic_qualifier(world, faction)
    faction.identity.culture_name = f"{qualifier} {faction.identity.culture_name}"
    new_display = f"{faction.identity.culture_name} {new_gov_type}"
world.factions[new_display] = faction
```

Also update `world.culture_roots` at this point to reflect the (possibly modified) culture_name.

---

### Fix 6: Civil-War Factions — Differentiate From Parent by Default

**Location:** `src/heartland.py:3503-3522` (civil war path in `create_rebel_faction`)

Civil war currently inherits the parent's `culture_name` unconditionally. The fix: treat civil war the same as named-group secession — inherit culture_name only if no collision, otherwise apply geographic qualifier. The faction split is still clearly a child of the parent (via `origin_faction` field), so narrative lineage is preserved without the display name being identical.

---

## Summary of Changes

| Fix | File | Lines |
|---|---|---|
| Add `culture_roots` to WorldState | `src/models.py` | FactionIdentity / WorldState fields |
| Populate roots at world init | `src/world.py` | faction creation loop |
| `extract_culture_root()` helper | `src/faction_naming.py` | new function |
| Retain directional qualifier when root taken | `src/heartland.py` | 3258, `_get_rebel_region_name_root` |
| Named-group qualifier logic | `src/heartland.py` | 3229–3243, `create_rebel_faction` |
| Apply similarity check to rebels | `src/heartland.py` | `_build_rebel_faction_name` |
| Guard tier-upgrade display_name | `src/factions.py` + `src/heartland.py` | tier-change code paths |
| Civil-war differentiation | `src/heartland.py` | 3503–3522 |
| Update `world.culture_roots` on faction death | `src/heartland.py` | faction removal code |

---

## Qualifier Derivation Logic (`_derive_geographic_qualifier`)

Central helper used by Fixes 2, 3, 5, 6:

```
Priority order:
1. Directional: if rebel capital is N/S/E/W of disputed name's largest region → "North", "South", etc.
2. Terrain: region.terrain_type → "Mountain", "River", "Coast", "Forest", "Plain", "Highland"
3. Descriptor from culture: pick one of the faction's lexical roots for a meaningful suffix ("Old", "New")
4. Fallback: generate a fresh 4-7 character culture name from the language family
```

The function should be deterministic given `(world, faction)` so that a replay with the same seed produces the same qualifier.

---

## Test Coverage

The existing `tests/test_faction_naming.py` (308 lines) already tests culture name similarity. Extend it with:

- Test: two rebel factions from "East Lond" and "West Lond" receive different culture_roots
- Test: named-group rebel (e.g. "Grassic") gets qualifier when parent still active
- Test: civil-war child differs from parent display_name
- Test: polity tier upgrade does not produce duplicate display_name in world.factions
- Test: `extract_culture_root()` correctly strips directional and government-type tokens
