# Territorial Cohesion Plan

## Feature Goal

Factions should struggle — and usually fail — to hold territory that is geographically cut off from their heartland. The difficulty of holding an exclave should vary sharply by government type: a nomadic band that loses physical contact with a region loses it almost immediately, while a maritime republic or a monarchy with sea-lane access can hold distant territory for generations. An active sea route should function as a genuine land-bridge substitute, but only if the faction has built up sufficient seafaring capacity to maintain it reliably.

---

## Why the Current System Does Not Achieve This

The infrastructure already exists but the pipeline is too attenuated to reliably cause secession.

**Current path from isolation to secession:**

```
capital_connection_mode == "isolated"
    → capital_disconnection_turns counter ticks up
    → capital isolation penalty added to admin distance (+0.06/turn, max +0.24)
    → increases region administrative burden
    → may increase overall overextension score
    → overextension is a narrative metric (ai_interpretation.py)
    → no direct per-region unrest increase
    → secession never triggers
```

The break is between overextension and unrest. Administrative overextension is tracked as a world-level metric but does not directly inject unrest into isolated regions. The capital isolation penalty to distance (max +0.24) is also too small — frontier regions already have a 1.8 distance cap, so the extra 0.24 is often irrelevant. The unrest threshold for secession (9.4) and the 3-consecutive-crisis-turn requirement are both calibrated for deliberately fomented rebellions, not passive geographic neglect.

The plan inserts two new levers directly into the unrest pipeline:
1. **Isolation unrest** — direct per-turn unrest added to isolated regions, scaled by how long they have been isolated and how far past their government's tolerance threshold they are
2. **Threshold reduction** — the effective secession threshold drops for regions that have been isolated too long, so that even modest unrest eventually reaches it

---

## Concepts

### Isolation Modes (extending existing `capital_connection_mode`)

The existing system already classifies each region per turn. This plan builds on those existing values:

| Mode | Meaning | Treated as |
|---|---|---|
| `"capital"` | This is the capital region | Fully connected |
| `"land"` | Reachable from capital via contiguous faction-owned land | Fully connected |
| `"sea"` | Reachable only via `world.sea_links` maritime route | Conditionally connected (see below) |
| `"isolated"` | Not reachable by land or sea | Disconnected — full isolation penalties apply |

A fifth state is introduced:

| Mode | Meaning |
|---|---|
| `"exclave"` | Reachable by sea (not land), but faction's seafaring level is below `COHESION_SEAFARING_THRESHOLD` — the route exists but cannot be reliably maintained |

`"exclave"` is set during the same connectivity pass that currently produces `capital_connection_mode`. The distinction: `"sea"` means connected and maintained; `"exclave"` means technically reachable but administratively unsustainable.

### Government Tolerance

Each government form has a **disconnection tolerance** — the number of consecutive turns a region may be in `"isolated"` or `"exclave"` status before isolation unrest begins accumulating. During the tolerance window the faction can theoretically re-establish connection (reconquer an intervening region, build up seafaring). After the window expires, unrest starts climbing.

| Government Form | Label | Tolerance (turns) | Rationale |
|---|---|---|---|
| `leader` | Band | 4 | A band leader's authority is personal presence; absence is desertion |
| `council` | Tribe | 10 | Council legitimacy requires representatives who can attend |
| `assembly` | Assembly | 16 | Assemblies need delegates; distant delegates cannot participate |
| `monarchy` | Kingdom | 40 | A crown claim is portable — legitimacy travels by letter and herald |
| `republic` | Republic | 28 | Civic institutions are durable but depend on active citizenship |
| `oligarchy` | Oligarchy | 34 | Merchant oligarchs maintain distant holdings via trade profit motive |

Sea-connected regions (`"sea"` mode, adequate seafaring) use these tolerances unmodified — the sea lane is treated as a genuine road. Exclave regions (`"exclave"` mode, inadequate seafaring) use half the tolerance, since the route exists in principle but cannot be relied upon.

---

## Isolation Unrest Accumulation

### Where it is applied

In `src/heartland.py`, within the per-turn region update loop (same section that applies famine, epidemic, and unrest crisis losses), add a call to `apply_isolation_unrest(world, region)` for every region where `capital_connection_mode in ("isolated", "exclave")`.

### Formula

```python
def apply_isolation_unrest(world, region):
    faction = world.factions.get(region.owner)
    if faction is None:
        return

    tolerance = get_government_disconnection_tolerance(faction.identity.government_form)

    if region.capital_connection_mode == "exclave":
        tolerance = tolerance // 2  # halved for unreliable sea connection

    turns_over = max(0, region.capital_disconnection_turns - tolerance)
    if turns_over == 0:
        return  # still within tolerance window

    base = COHESION_ISOLATION_UNREST_BASE
    escalation = turns_over * COHESION_ISOLATION_UNREST_ESCALATION
    unrest_addition = min(COHESION_ISOLATION_UNREST_CAP, base + escalation)

    # Homeland regions resist harder — people remember who founded them
    if region.homeland_faction_id == region.owner:
        unrest_addition *= COHESION_HOMELAND_UNREST_REDUCTION

    add_region_unrest(region, unrest_addition, source="isolation")
```

**Example trajectories** (monarchy, tolerance = 40 turns):
- Turn 41: +0.08 unrest/turn
- Turn 50: +0.08 + (10 × 0.015) = +0.23 unrest/turn
- Turn 60: +0.08 + (20 × 0.015) = +0.38 unrest/turn

At +0.38/turn, a region starting at 4.0 unrest reaches crisis (8.25) in ~11 turns and secession threshold (9.4) in ~14 turns — a total of ~74 turns after disconnection for a monarchy. A band (tolerance = 4) reaches the same unrest trajectory at turn 5 and hits secession in ~25 turns total. This feels right for the simulation's pacing.

---

## Secession Threshold Reduction

The existing secession check (`src/heartland.py:4570-4584`) uses a fixed effective threshold (normally 9.4). For isolated regions past their tolerance, lower it:

```python
def get_effective_secession_threshold(region, faction):
    base = UNREST_SECESSION_THRESHOLD  # 9.4
    tolerance = get_government_disconnection_tolerance(faction.identity.government_form)

    if region.capital_connection_mode == "exclave":
        tolerance = tolerance // 2

    turns_over = max(0, region.capital_disconnection_turns - tolerance)
    if turns_over == 0:
        return base

    reduction = min(
        COHESION_THRESHOLD_REDUCTION_MAX,
        turns_over * COHESION_THRESHOLD_REDUCTION_PER_TURN
    )
    return base - reduction
```

This means a deeply isolated region needs progressively less unrest to secede. After 60 turns over tolerance, the threshold might drop to 7.9 — reachable from moderate crisis conditions without needing a famine or a succession collapse to push it over.

The crisis-streak requirement (3 consecutive turns) is **not** reduced. The isolated region still needs to spend time in sustained crisis, not just touch the threshold once. This prevents instantaneous splits from a single bad turn.

---

## Sea Route Rules

### When a sea route counts as "connected"

`capital_connection_mode = "sea"` requires both:
1. A path in `world.sea_links` from the region to any capital-connected region the faction owns
2. `get_faction_seafaring_level(faction) >= COHESION_SEAFARING_THRESHOLD`

If condition 1 is met but condition 2 is not → `capital_connection_mode = "exclave"` (half tolerance, not fully connected).

`COHESION_SEAFARING_THRESHOLD` should be set to `SEAFARING_EXPANSION_THRESHOLD` or slightly above — the same level required to actively expand by sea. A faction that can expand by sea can maintain sea lanes; a faction that cannot expand cannot maintain them.

### Sea connection does not eliminate isolation unrest entirely

Even with `"sea"` mode and adequate seafaring, a region that is a pure exclave (no land-connected faction region for several hops) accumulates a small background unrest representing the friction of remote governance:

```python
COHESION_EXCLAVE_BACKGROUND_UNREST = 0.02  # per turn, always applies to sea-only regions
```

This is very mild (a sea-connected exclave that has been stable for years still accumulates ~2 unrest over 100 turns) but it ensures that maritime empires feel some pressure on their distant holdings over very long simulations, without making sea lanes useless.

### River links

`world.river_links` are treated identically to `world.sea_links` for connectivity purposes but require no seafaring threshold — rivers are navigable by any faction. A region connected only by river is `"sea"` mode (existing naming) and gets no penalty if the route exists. This is already implicit in the current system and requires no change.

---

## Homeland Protection

A region where `homeland_faction_id == region.owner` (the region's founding faction still owns it) resists isolation unrest by `COHESION_HOMELAND_UNREST_REDUCTION = 0.5`. This represents the deep loyalty of a heartland population even when cut off — they are the people who named the valley, they are not going to secede from themselves easily.

This protection is removed (factor = 1.0) once the homeland region's ethnic composition no longer has the owner's primary ethnicity as the dominant group — the cultural anchor is gone.

---

## Narrative Events

Two new event types should be added to make isolation legible in the chronicle and live lore output:

### `"region_isolation_warning"` (informational, no gameplay effect)

Fired when a region first exceeds its government's tolerance window. Fields:
- `region`, `owner`, `turns_isolated`, `government_form`, `connection_mode`

Used by the live lore system to display "Outpost X has been unreachable from the capital for N turns" and by the narrative digest to set up a secession as foreseeable rather than sudden.

### `"region_isolation_crisis"` (triggers visual/narrative escalation)

Fired when isolation unrest pushes a region into crisis (unrest ≥ 8.25) for the first time. Fields:
- `region`, `owner`, `turns_isolated`, `current_unrest`

The living chronicle plan should include this in `epoch_events` — an epoch that includes `region_isolation_crisis` events gives the narrator material to describe a disintegrating periphery.

---

## Config Constants (`src/config.py`)

```python
# Territorial cohesion — disconnection tolerances (turns)
COHESION_TOLERANCE_BAND        = 4
COHESION_TOLERANCE_TRIBE       = 10
COHESION_TOLERANCE_ASSEMBLY    = 16
COHESION_TOLERANCE_REPUBLIC    = 28
COHESION_TOLERANCE_OLIGARCHY   = 34
COHESION_TOLERANCE_MONARCHY    = 40

# Isolation unrest accumulation
COHESION_ISOLATION_UNREST_BASE        = 0.08   # unrest/turn when first past tolerance
COHESION_ISOLATION_UNREST_ESCALATION  = 0.015  # additional unrest per extra turn
COHESION_ISOLATION_UNREST_CAP         = 0.60   # maximum unrest/turn from isolation alone
COHESION_HOMELAND_UNREST_REDUCTION    = 0.50   # multiplier for homeland regions

# Secession threshold reduction
COHESION_THRESHOLD_REDUCTION_PER_TURN = 0.04   # threshold reduction per turn over tolerance
COHESION_THRESHOLD_REDUCTION_MAX      = 1.80   # max total reduction (floor: 9.4 - 1.8 = 7.6)

# Sea connection
COHESION_SEAFARING_THRESHOLD          = 0.40   # seafaring level required for sea to count as connected
COHESION_EXCLAVE_BACKGROUND_UNREST    = 0.02   # unrest/turn for sea-connected exclaves (always on)
```

---

## Modified Files

| File | Change |
|---|---|
| `src/config.py` | Add all constants above |
| `src/models.py` | Add `"exclave"` as valid `capital_connection_mode` value; document in Region field |
| `src/administration.py` | In connectivity pass (`_walk_capital_connections`): classify `"exclave"` when sea link exists but seafaring below threshold |
| `src/heartland.py` | Add `apply_isolation_unrest()` to per-turn region loop; modify secession check to call `get_effective_secession_threshold()` |
| `src/region_state.py` | Expose `get_government_disconnection_tolerance(government_form)` helper |
| `src/events.py` (or equivalent) | Add `"region_isolation_warning"` and `"region_isolation_crisis"` event types |
| `src/live_lore.py` | Display isolation warning events in the real-time lore feed |
| `src/ai_interpretation.py` | Include isolation crisis events in `key_event_digest` and flag prolonged exclave status in faction epilogues |

---

## Interaction With Other Plans

### Name Uniqueness Plan

When an isolated pocket secedes, it currently inherits a name derived from its region root (e.g. "Lond Rebels"). The name uniqueness plan's `culture_roots` registry must be checked at this point — if the parent faction still exists and holds "Lond" as its root, the seceding exclave should get a qualifier ("East Lond Rebels", "Coast Lond Rebels") per Fix 2 of that plan.

### Language Drift Plan

A region that spends 100+ turns as an isolated exclave is precisely the scenario where a new language subfamily should form (the branch detection algorithm will find it as politically separated). Isolation events should therefore increment `faction_separation_start` for the exclave region's owner pair, accelerating the drift clock. A region that breaks free as an independent polity will very likely drift linguistically within a generation.

### Living Chronicle Plan

The epoch narrator computing `narrator_disposition` should check for active isolation crises in the epoch. A faction with multiple isolation crises maps to `"fragmenting"` disposition — the narrator writes from a disintegrating periphery, hedging which name is authoritative, uncertain whether messages from the capital are still arriving.

---

## Open Questions

1. **Reconnection cooldown.** If a faction reconquers the connecting region (restoring land contact), the `capital_disconnection_turns` counter should reset immediately. But should there be a "trust recovery" period where isolation unrest drains slowly rather than stopping instantly? Otherwise factions could game this by briefly reconnecting then losing contact again.

2. **Multi-hop sea routes.** Current sea connectivity checks direct `world.sea_links` pairs. Should a faction be allowed to chain sea links through intermediate sea-connected regions it owns (A → sea → B → sea → C)? This would matter for archipelago-style factions. Probably yes, using the existing BFS in `_walk_capital_connections`, but worth confirming that it already handles chained sea links.

3. **Capital relocation.** A faction that loses land connection to its capital but still has a strong population centre in the isolated bloc could arguably move its capital there. Should isolation trigger a capital relocation option (player-facing or AI-driven) that resets the disconnection counter for the isolated bloc at the cost of declaring the original capital region "frontier"?

4. **Band and tribe grace period.** A band (tolerance = 4 turns) could lose an exclave very quickly if the connection is severed mid-war and restored after 5 turns. Consider whether bands should have a "war exemption" — tolerance doesn't tick during active war (when `conflict_type` is ongoing) — since a band leader might physically be travelling rather than permanently absent.
