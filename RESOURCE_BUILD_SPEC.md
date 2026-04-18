# Specific Resources Build Spec

## Purpose

This document defines the first implementation pass for specific resources in Clashvergence.

The goal of this phase is not to model a full trade economy or industrial production chain. The goal is to replace the current abstract `region.resources` model with a more historically grounded production model that:

- distinguishes between spreadable and fixed resources
- makes geography materially meaningful
- gives factions reasons to expand beyond generic income gain
- preserves compatibility with the current simulation while the transition is underway

This is a simulation-first feature. It should be implemented for realism and causal depth, not for game balance.

## V1 Design Commitments

These points are treated as hard requirements for the first pass:

- `copper` is the first metal, not `iron`
- `grain` and `horses` are spreadable domestic resources
- `grain` and `horses` persist after ownership changes
- some resources are region-bound and cannot be replicated
- the current generic `resources` field will be phased out gradually, not deleted immediately

## Resource Taxonomy

V1 resources are divided into three categories.

### 1. Domesticable Resources

These can be introduced into a new owned region if the region is suitable and the faction already has access to an established source.

V1 domesticable resources:

- `grain`
- `horses`

Rules:

- They require local suitability.
- They do not appear automatically just because a region is suitable.
- A faction must spend development effort to establish them in a new region.
- Once established, they persist in the region even if the region changes owners.
- Their output can decline under low population, neglect, or severe unrest, but the established base should remain unless a later explicit collapse rule is added.

### 2. Wild Resources

These come from the local ecology rather than deliberate transplantation.

V1 wild resource:

- `wild_food`

`wild_food` is intentionally broader than fish alone. It should represent food gathered from the environment without organized agriculture, including:

- fish
- game animals such as deer
- trapping
- foraging

Rules:

- It is region-bound.
- It depends on terrain, climate, and local ecology.
- It should be strongest in coast, riverland, forest, marsh, and some hill/highland regions.
- It should matter most early and remain useful later as a supplement to grain rather than a full replacement for it.

### 3. Extractive Resources

These are fixed to specific regions and cannot be spread politically.

V1 extractive resources:

- `copper`
- `stone`

Rules:

- They are fixed endowments.
- They depend on terrain and map generation.
- They can only be controlled through ownership.
- Production depends on population, integration, and development, not just presence.

## Derived Capacities

The resource system should feed a small set of derived capacities used by the rest of the simulation.

V1 derived capacities:

- `food_security`
  From `grain + wild_food`
- `mobility_capacity`
  From `horses`
- `construction_capacity`
  From `timber + stone` if timber stays in scope, or `stone` alone in the narrowest V1
- `metal_capacity`
  From `copper`
- `taxable_value`
  From total usable production after modifiers

## Recommended V1 Resource Set

There are two acceptable V1 scope levels.

### Preferred V1

- `grain`
- `horses`
- `wild_food`
- `timber`
- `copper`
- `stone`

This gives a strong simulation foundation without being too large.

### Minimal V1

- `grain`
- `horses`
- `wild_food`
- `copper`
- `stone`

If implementation load needs to stay tighter, `timber` can be deferred. In that case, construction can temporarily be driven mostly by `stone` plus legacy abstract value.

## Data Model Changes

## Region

Update [src/models.py](C:/Users/Michael/Programs/python/Clashvergence/src/models.py) so each `Region` can hold resource state in a structured way.

Add fields:

```python
resource_fixed_endowments: dict[str, float] = field(default_factory=dict)
resource_wild_endowments: dict[str, float] = field(default_factory=dict)
resource_suitability: dict[str, float] = field(default_factory=dict)
resource_established: dict[str, float] = field(default_factory=dict)
resource_output: dict[str, float] = field(default_factory=dict)
infrastructure_level: float = 0.0
agriculture_level: float = 0.0
pastoral_level: float = 0.0
extractive_level: float = 0.0
```

Definitions:

- `resource_fixed_endowments`
  Permanent deposits such as `copper` and `stone`
- `resource_wild_endowments`
  Environmental food potential such as `wild_food`
- `resource_suitability`
  Suitability for domesticable resources such as `grain` and `horses`
- `resource_established`
  How established a domesticable resource currently is in the region
- `resource_output`
  Actual per-turn output after population and modifiers

Keep existing field:

- `resources: int`

For the transition period, this remains as a legacy abstract value derived from the new resource system.

## Faction

Add fields to `Faction` in [src/models.py](C:/Users/Michael/Programs/python/Clashvergence/src/models.py):

```python
resource_access: dict[str, float] = field(default_factory=dict)
resource_shortages: dict[str, float] = field(default_factory=dict)
derived_capacity: dict[str, float] = field(default_factory=dict)
```

Definitions:

- `resource_access`
  Total currently usable production across owned regions
- `resource_shortages`
  Demand minus access where access is insufficient
- `derived_capacity`
  Aggregate capacities such as `food_security` and `metal_capacity`

## New Module

Create:

- `src/resources.py`

This module should hold:

- resource category constants
- resource name constants
- terrain and climate seeding tables
- suitability tables
- production helper functions
- derived-capacity helper functions
- legacy conversion helper for temporary `region.resources` compatibility

## World Seeding

Update [src/world.py](C:/Users/Michael/Programs/python/Clashvergence/src/world.py) to initialize new resource fields on world creation.

### Seeding Rules

#### Domesticable Suitability

Assign suitability by terrain and climate:

- `grain`
  Strong in `plains`, `riverland`
  Moderate in `forest`, `coast`, `steppe`
  Weak in `hills`
  Poor in `marsh`, `highland`

- `horses`
  Strong in `steppe`, `plains`
  Moderate in `hills`
  Weak in `forest`
  Very poor in `marsh`, `riverland`, `highland`

#### Wild Endowments

Assign `wild_food` by terrain and climate:

- strong in `coast`, `riverland`, `forest`, `marsh`
- moderate in `hills`, `highland`
- lower in `plains`

This keeps `wild_food` as a broad ecological category rather than just fish.

#### Fixed Endowments

Assign:

- `copper`
  Mostly `hills` and `highland`, occasionally `forest hills`
- `stone`
  Common in `hills` and `highland`, moderate in some `forest` and `plains`

### Starting Established Resources

When a region begins owned by a faction, initialize:

- `grain` established if the region has meaningful grain suitability
- `horses` established only if suitability is good enough

This creates plausible starting agricultural bases without granting universal horse access.

## Production Model

Add production helpers in `src/resources.py`, then call them from [src/heartland.py](C:/Users/Michael/Programs/python/Clashvergence/src/heartland.py).

### Domesticable Production

For `grain` and `horses`:

```python
output = suitability
    * established_level
    * workforce_factor
    * development_factor
    * integration_factor
    * unrest_factor
```

Notes:

- `established_level` should grow over time after introduction rather than instantly jumping to full output.
- `grain` should scale faster than `horses`.
- `horses` should remain rarer and slower to mature.

### Wild Production

For `wild_food`:

```python
output = wild_endowment
    * local_ecology_factor
    * workforce_factor
    * unrest_factor
```

Notes:

- Wild output should not require prior establishment.
- It should not scale as aggressively with infrastructure as agriculture or extraction.
- It should remain available even in unowned or lightly settled regions, but at lower usable output.

### Extractive Production

For `copper` and `stone`:

```python
output = fixed_endowment
    * workforce_factor
    * extractive_development_factor
    * integration_factor
    * unrest_factor
```

Notes:

- A deposit without enough population or integration should underperform.
- Frontier conquest of a copper region should not instantly unlock full output.

## Spread Mechanics

Domesticable resources need explicit spread rules.

### New Concept: Introduction Projects

Keep the top-level action category `invest`, but let it eventually branch into project types.

V1 project types:

- `introduce_grain`
- `introduce_horses`
- `improve_agriculture`
- `improve_pastoralism`
- `improve_extraction`
- `improve_infrastructure`

### Rules For Introducing Grain

Requirements:

- region is owned by faction
- region has sufficient `grain` suitability
- region does not already have strong grain establishment
- faction controls at least one region with established grain
- ideally the target borders one of those source regions in V1

Effects:

- target region gains small initial `grain` establishment
- source region may take a one-turn small output hit or simply incur treasury cost
- grain establishment grows over later turns

### Rules For Introducing Horses

Requirements:

- owned region
- sufficient horse suitability
- faction controls a region with established horses
- higher cost than grain introduction

Effects:

- target gains small horse establishment
- establishment grows slowly
- later contributes to mobility capacity

### Persistence Rule

When ownership changes, do not erase:

- `resource_established["grain"]`
- `resource_established["horses"]`

Ownership change may reduce effective output temporarily through:

- unrest
- low integration
- population loss

But the agricultural or pastoral base itself should remain.

## Economy Integration

This is the most important transition point.

Current economy in [src/simulation.py](C:/Users/Michael/Programs/python/Clashvergence/src/simulation.py) and [src/heartland.py](C:/Users/Michael/Programs/python/Clashvergence/src/heartland.py) relies heavily on `region.resources`.

V1 should migrate in two stages.

### Stage 1: Parallel Calculation

Add new production calculations without replacing the existing system yet.

Per region compute:

- `resource_output`
- `taxable_value`
- legacy-compatible derived abstract `resources`

Per faction compute:

- `resource_access`
- `resource_shortages`
- `derived_capacity`

Keep existing income rules running during this stage, but drive `region.resources` from the new model so old systems continue to function.

### Stage 2: Native Resource Economy

Replace direct dependence on raw `region.resources` in:

- income calculations
- surplus calculations
- settlement calculations
- population growth logic

At that point:

- `food_security` should affect growth and unrest
- `metal_capacity` should affect military and productive sophistication
- `mobility_capacity` should affect expansion and military projection

## Legacy Compatibility

To avoid breaking the whole project at once, define a compatibility function in `src/resources.py`:

```python
def get_legacy_region_resource_value(region, world) -> int:
    ...
```

This should translate specific outputs into a temporary abstract score for old systems and UI panels.

Suggested basis:

- grain and wild food contribute strongly
- copper contributes strongly
- horses contribute moderately
- stone contributes moderately
- timber contributes moderately if included

This compatibility value should eventually replace direct manual storage of `region.resources`.

## Changes To Existing Systems

## [src/heartland.py](C:/Users/Michael/Programs/python/Clashvergence/src/heartland.py)

Add:

- region production update helpers
- faction resource aggregation helpers
- derived capacity helpers
- shortage helpers

Refactor:

- `get_region_productive_capacity`
- `get_region_surplus`
- `get_region_effective_income`
- `update_region_populations`
- `get_faction_settlement_profile`

New logic should increasingly depend on real production and food security rather than generic region value.

## [src/actions.py](C:/Users/Michael/Programs/python/Clashvergence/src/actions.py)

Refactor:

- `invest` should become project-aware
- expansion scoring should consider specific resource needs
- attack scoring should consider fixed strategic resources such as copper

V1 can still keep one public `invest()` action, but it should internally choose a project type.

## [src/agents.py](C:/Users/Michael/Programs/python/Clashvergence/src/agents.py)

Update faction action logic so material needs influence behavior:

- food shortage biases toward grain introduction or fertile expansion
- horse shortage biases toward pastoral development or steppe/plains expansion
- copper shortage biases toward conquest of mineral regions

Doctrine should remain important, but it should stop being the only major explanation for strategic preference.

## [src/metrics.py](C:/Users/Michael/Programs/python/Clashvergence/src/metrics.py)

Add faction-level metrics:

- `food_security`
- `mobility_capacity`
- `metal_capacity`
- `taxable_value`
- `grain_access`
- `wild_food_access`
- `horse_access`
- `copper_access`
- `stone_access`
- shortage flags or shortage magnitudes

## [src/simulation_ui.py](C:/Users/Michael/Programs/python/Clashvergence/src/simulation_ui.py)

Add region display support for:

- fixed resources
- wild resources
- established domestic resources
- actual output

Add faction display support for:

- resource access
- shortages
- derived capacities

During transition, it is acceptable to keep the visible `R` shorthand if it is clearly acting as a compact legacy economic rating.

## [src/event_analysis.py](C:/Users/Michael/Programs/python/Clashvergence/src/event_analysis.py)

Update replay state and event interpretation so investments can report project type and so region economic importance can reference specific resources rather than only generic value.

## Build Sequence

Implement in the following order.

### Step 1: Resource Scaffolding

Create `src/resources.py`.

Add:

- resource constants
- category groupings
- terrain/climate seeding tables
- suitability helper functions
- legacy value helper

No gameplay changes yet.

### Step 2: Data Model Migration

Update `Region` and `Faction` dataclasses in `src/models.py`.

Initialize empty resource fields safely so old saves and tests do not immediately fail.

### Step 3: World Seeding

Update `src/world.py` to seed:

- fixed endowments
- wild endowments
- domesticable suitability
- initial established grain and horses for owned starts

At this point, viewer and reports can begin exposing the raw seeded data.

### Step 4: Regional Production

Add functions to calculate:

- domesticable output
- wild output
- extractive output
- derived legacy `resources`

Run these during world initialization and per-turn updates.

### Step 5: Faction Aggregation

Add per-faction aggregation of:

- access
- shortages
- derived capacities

Use these only for reporting at first.

### Step 6: Economy Refactor

Change income and productive capacity calculations so they rely on real output and `taxable_value`.

This is the point where the resource system begins affecting core simulation outcomes.

### Step 7: Investment Projects

Refactor `invest()` to choose specific project types.

V1 priority:

- grain introduction
- horse introduction
- agriculture improvement
- extraction improvement

### Step 8: Strategic AI Integration

Update action scoring to care about:

- shortage relief
- spreadable resource establishment opportunities
- fixed strategic resource capture

### Step 9: Metrics And Viewer Integration

Expose resources clearly in metrics, reports, and HTML viewer.

### Step 10: Cleanup

Reduce direct use of legacy `region.resources` throughout the codebase.

It can remain as a compatibility field until the trade/logistics phase is ready.

## Testing Plan

Testing should protect coherence, not freeze exact outcomes.

### Unit Tests

Add tests for:

- deterministic seeding by terrain/climate
- suitability generation
- production formulas for each resource category
- grain persistence after conquest
- horse persistence after conquest
- introduction project legality
- shortage calculation

### Invariant Tests

Assert:

- outputs never go negative
- no unknown resource keys appear
- fixed resources do not spread
- domesticable resources cannot be introduced without a valid source
- region ownership change does not erase established grain or horses

### Smoke Tests

Run a small seeded simulation and verify:

- economy completes without crash
- factions can produce food
- at least some regions retain distinct resource profiles
- metrics and viewer serialization still work

## Out Of Scope For This Phase

Do not include in this build:

- inter-faction trade
- market prices
- stockpiles
- depletion
- afforestation mechanics
- livestock categories beyond horses
- iron
- gold

These should wait until the specific-resource foundation is stable.

## Success Criteria

This phase is successful if:

- regions now differ materially in believable ways
- factions can spread grain and horses but not copper or stone
- conquest of mineral regions matters strategically
- wild food matters early and remains a meaningful supplement later
- existing systems still run during the transition
- the simulation tells more plausible stories about why factions expand

## Next Iteration: V1.5 Resource Refinement

The preferred V1 foundation is now in place. The next iteration should improve realism and behavioral quality without yet moving into full trade networks or market simulation.

This next phase should be treated as a refinement pass on top of V1, not a replacement for it.

### Primary Goals

- make resource distribution inside a polity more realistic
- make demand and shortage logic less abstract
- make agricultural and pastoral spread feel more physically grounded
- make established resources more persistent but also more vulnerable to neglect and collapse
- improve AI reasoning so factions pursue resource goals more coherently

### What This Phase Is

This phase should add:

- internal distribution limits
- better per-resource demand logic
- source-linked spread and transfer friction
- gradual decline rules for neglected domestic resources
- more meaningful differences between frontier, core, and homeland production

### What This Phase Is Not

This phase should not yet add:

- inter-faction trade
- price systems
- market-clearing logic
- stockpiles with long-term inventory behavior
- merchant actors
- depletion of mineral resources

Those belong in the later trade and logistics phase.

## V1.5 Design Commitments

- keep `grain` and `horses` persistent after conquest
- do not erase established resources because of flag changes alone
- do allow domestic resources to decay under low population, neglect, severe unrest, or repeated devastation
- keep `copper` and `stone` fixed to the land
- keep `wild_food` as a regional ecological resource, not something factions can transplant
- make access depend more on whether a polity can actually connect and use a region, not just whether it owns it

## V1.5 Feature Areas

### 1. Internal Distribution And Effective Access

V1 currently aggregates all owned output into faction-wide access too cleanly.

The next step should distinguish between:

- `gross_output`
  Total raw production in owned regions
- `effective_access`
  Production the polity can actually coordinate and use
- `isolated_output`
  Production trapped behind weak integration, unrest, or separation

This can be modeled without full trade by using a simple internal-distribution factor based on:

- adjacency to homeland or core regions
- integration level
- unrest
- settlement level
- whether the region is cut off by hostile borders or rebel breakaway

This preserves simplicity while making distant frontiers less perfectly efficient.

### 2. Better Demand Logic

V1 demand is intentionally broad. The next phase should make it more grounded.

Demand should be broken into at least:

- `food_demand`
  tied mostly to population
- `mobility_demand`
  tied to territory size, doctrine, and military posture
- `construction_demand`
  tied to settlement growth, infrastructure, and polity tier
- `metal_demand`
  tied to extraction, warfare, and political sophistication

This should reduce the number of arbitrary shortage values and make faction behavior easier to interpret.

### 3. Resource Decline And Maintenance

Domesticable resources should persist, but they should not be permanently self-sustaining at full strength under any condition.

Add gradual decline rules for `grain` and `horses` when:

- population collapses
- unrest remains severe
- the region is owned for many turns without adequate development
- repeated warfare damages the local base

The key rule is:

- conquest does not erase the resource base
- neglect can erode it over time

This is a more realistic persistence model than either total permanence or instant disappearance.

### 4. Source-Linked Spread

V1 spread should become more physically grounded.

When introducing `grain` or `horses`, the simulation should consider:

- nearest valid source region
- whether the source is adjacent or reachable through owned territory
- how developed the source is
- whether the source takes a temporary cost or slowdown from sending seed stock or breeding stock outward

This does not need full route simulation yet. A simple owned-path or adjacency check is enough for this iteration.

### 5. Frontier Friction

Resource output should increasingly reflect how difficult it is to use a frontier region.

Add stronger penalties for frontier regions in:

- effective access
- extractive output
- settlement-supporting production
- ability to support introduction projects

This should make mineral conquest and marginal agricultural expansion feel more historically constrained.

### 6. Richer Investment Projects

The V1 project model should be refined into a clearer development hierarchy.

Keep the same project family, but make their effects more distinct:

- `introduce_grain`
  starts local grain establishment
- `introduce_horses`
  starts local herd base
- `improve_agriculture`
  raises grain efficiency and food resilience
- `improve_pastoralism`
  raises horse output and persistence
- `improve_extraction`
  raises copper and stone output
- `improve_infrastructure`
  raises internal distribution and taxable extraction

This phase should also add stronger project prerequisites so development feels path-dependent rather than interchangeable.

### 7. AI Goal Coherence

The AI should move from “shortage-aware” to “resource-strategy-aware.”

Examples:

- food-poor factions should prioritize fertile corridors and internal grain spread
- horse-poor factions should value steppe and plains more strongly
- copper-poor factions should target mineral regions more aggressively
- factions with strong but isolated output should invest in integration or infrastructure before overexpanding

The desired result is not optimal play. The desired result is more intelligible historical behavior.

## Data Model Additions For V1.5

If needed, add the following fields.

### Region

Possible additions to [src/models.py](C:/Users/Michael/Programs/python/Clashvergence/src/models.py):

```python
resource_effective_output: dict[str, float] = field(default_factory=dict)
resource_damage: dict[str, float] = field(default_factory=dict)
resource_isolation_factor: float = 0.0
last_resource_project_turn: int | None = None
```

Definitions:

- `resource_effective_output`
  output actually reaching faction-wide use after local friction
- `resource_damage`
  accumulated disruption from war, unrest, or neglect
- `resource_isolation_factor`
  simple measure of how poorly connected the region is to the polity
- `last_resource_project_turn`
  recent development timestamp for project pacing or decay rules

### Faction

Possible additions:

```python
resource_gross_output: dict[str, float] = field(default_factory=dict)
resource_effective_access: dict[str, float] = field(default_factory=dict)
resource_isolated_output: dict[str, float] = field(default_factory=dict)
```

This would let reports distinguish what the polity owns from what it can actually exploit.

## V1.5 Mechanical Changes

### Effective Access Formula

For each region:

```python
effective_output = raw_output
    * integration_factor
    * internal_distribution_factor
    * unrest_factor
```

Where `internal_distribution_factor` should be reduced by:

- frontier status
- low settlement
- distance from homeland or core
- ongoing rebellion pressure

### Domestic Resource Decay Formula

For `grain` and `horses`:

```python
established_next = established_now
    + growth_from_projects
    - decay_from_neglect
    - decay_from_devastation
```

Decay should usually be mild, but sustained crisis should matter.

### Project Reach Rule

An introduction project should require either:

- adjacency to a valid source region, or
- a contiguous owned path to a valid source region

The first implementation can use adjacency only if path logic feels too expensive right now.

## V1.5 Build Sequence

Implement in this order.

### Step 11: Separate Gross Output From Effective Access

Refactor faction aggregation in [src/heartland.py](C:/Users/Michael/Programs/python/Clashvergence/src/heartland.py) so raw output and usable output are not the same thing.

### Step 12: Add Region Isolation Logic

Compute a simple isolation factor using:

- homeland distance or owned-path depth
- frontier/core status
- unrest

### Step 13: Refine Demand

Replace coarse shortage estimates with clearer food, mobility, construction, and metal demand components.

### Step 14: Add Domestic Resource Decay

Implement slow decay for `grain` and `horses` under:

- depopulation
- neglect
- crisis unrest
- repeated conflict

### Step 15: Tighten Project Prerequisites

Require valid source linkage and make source regions pay a small cost or temporary output penalty when spreading domestic resources.

### Step 16: Update AI Priorities

Teach factions to respond to:

- isolated production
- failed food security
- frontier extraction bottlenecks
- path-dependent agricultural and pastoral development opportunities

### Step 17: Improve Reporting

Update [src/metrics.py](C:/Users/Michael/Programs/python/Clashvergence/src/metrics.py) and [src/simulation_ui.py](C:/Users/Michael/Programs/python/Clashvergence/src/simulation_ui.py) to show:

- gross output
- effective access
- isolated output
- shortage type
- resource decay or damage state

## V1.5 Testing Plan

Add focused tests for:

- effective access being lower than gross output for isolated frontier regions
- grain and horse persistence after conquest
- grain and horse decay under prolonged neglect or crisis
- inability to introduce domestic resources without a valid source
- improved AI target scoring for food-poor or copper-poor factions

Keep smoke testing bounded:

- 1 short map
- 1 medium map
- 10 to 20 turns each
- a few fixed seeds

This should be enough to catch obvious incoherence without turning the test pass into a large experiment run.

## V1.5 Success Criteria

This iteration is successful if:

- owning a distant region is not the same as fully exploiting it
- grain and horses remain persistent but not magically maintenance-free
- frontier extraction feels weaker and slower than homeland extraction
- factions pursue more intelligible material strategies
- reports can explain not only what a polity owns, but what it can actually use

## Next Iteration: V1.6 Explicit Internal Route Distribution

The next refinement should treat internal distribution less like a generic isolation penalty and more like a simple political-logistical network.

This phase should not add full trade or merchant behavior. It should make the existing resource economy more explicit about how goods move from productive regions into usable state capacity.

### Primary Goals

- reduce behavior-critical dependence on legacy `region.resources`
- represent internal resource access through explicit owned routes
- distinguish good corridors from degraded corridors
- make route quality visible in reports and the viewer

### Core Model

Each owned region should have a route relationship to the nearest viable internal anchor.

Anchor priority:

- homeland regions first
- then core regions if no homeland route exists
- then any owned region only as a fallback for fragmented polities

Per-region route state should include:

- `resource_route_anchor`
- `resource_route_depth`
- `resource_route_cost`
- `resource_isolation_factor`

### Route Cost Logic

Route cost should be based on the actual owned path, not just straight distance.

Each step along a route should become more expensive when the traversed region has:

- frontier status
- low settlement
- severe unrest
- crisis events
- low population
- accumulated resource damage

Each step should become less expensive when the traversed region has:

- stronger infrastructure
- better integration
- more settled internal support

This should allow two equally distant regions to behave differently if one sits behind a coherent core corridor and the other sits behind a damaged frontier chain.

### Legacy Cleanup Focus

In this phase, replace behavior-critical remaining uses of legacy `region.resources` in:

- faction economy snapshots
- expansion scoring
- attack scoring
- rebellion and collapse effects
- event interpretation where taxable value is the more truthful signal

The legacy field can still remain for compact display and compatibility, but it should stop being a primary driver of simulation decisions.

### Viewer And Reporting

Expose route information so the simulation is easier to read:

- route anchor
- route depth
- route cost
- isolation percentage
- taxable value alongside legacy value where both are still shown

### V1.6 Testing Plan

Add focused tests for:

- route quality changing effective output even at similar depth
- route anchor and route depth being populated for connected owned regions
- disconnected pockets showing higher isolation than coherent corridors
- attack and expansion scoring using taxable value rather than raw legacy resource score

Keep testing bounded:

- targeted unit tests for route computation
- the existing resource test slice
- one short smoke run through the CLI

### V1.6 Success Criteria

This iteration is successful if:

- the simulation can explain why some frontier output is usable and some is trapped
- connected interior corridors outperform equally distant but degraded frontiers
- legacy `region.resources` still exists, but no longer drives the important strategic decisions
- the viewer makes internal distribution legible instead of hiding it inside a single isolation number

## Next Iteration: V1.7 Corridor Throughput And Bottlenecks

The next refinement should treat not all routes as equally capable corridors. A polity may technically own a path, but that path can still be fragile, undersupplied, or too degraded to move much usable output.

This phase is still pre-trade. It is about internal coordination capacity, not markets.

### Primary Goals

- distinguish route cost from route quality
- model internal corridor bottlenecks explicitly
- make infrastructure more important as a way to unlock trapped production
- surface bottlenecks clearly in simulation outputs

### Core Model

Each owned route should track not only:

- `resource_route_anchor`
- `resource_route_depth`
- `resource_route_cost`

but also:

- `resource_route_bottleneck`

The bottleneck is the weakest corridor-support value along the best owned route back to an anchor.

### Corridor Support Logic

Each traversed region should contribute to corridor quality based on:

- settlement level
- infrastructure
- integration
- population
- unrest
- crisis events
- accumulated resource damage
- frontier versus core versus homeland status

This means a route can be:

- cheap but fragile
- long but still workable
- short but badly bottlenecked by one weak link

That distinction is important for a simulation-first economy.

### Mechanical Effects

Route bottlenecks should reduce effective access on top of route cost.

Effects should be stronger for:

- extractive output
- distant frontier production
- low-infrastructure corridors

This should make copper and stone regions feel materially trapped if the state has not built the administrative and infrastructural depth needed to use them.

### AI And Investment Effects

Infrastructure projects should become more attractive when a region:

- sits on a weak corridor
- has high isolation
- blocks access to downstream production
- connects frontier extraction or food production back to the core

The desired result is that factions sometimes consolidate a corridor instead of only chasing new territory or local yield.

### Reporting

Expose corridor bottlenecks in region reporting:

- bottleneck percentage
- route cost
- route depth
- anchor

This should make it easier to diagnose why a region underperforms.

### V1.7 Testing Plan

Add focused tests for:

- route bottleneck values dropping on weak corridors
- two similar-depth routes performing differently because of corridor quality
- infrastructure becoming a preferred investment on badly bottlenecked owned corridors

Keep testing bounded:

- targeted resource tests
- metrics/resource regression slice
- one short smoke sim

### V1.7 Success Criteria

This iteration is successful if:

- route cost and route bottleneck capture different failures
- weak corridors visibly choke usable output
- infrastructure matters more as a way to unlock existing holdings
- the viewer can show not just that a region is isolated, but why its corridor is weak

## V1 Completion

With V1 through V1.7 implemented, the specific-resource foundation should now be treated as functionally complete.

What V1 now includes:

- specific resource seeding by terrain and climate
- domesticable, wild, and extractive resource categories
- persistence of grain and horses through ownership change
- native production and taxable-value calculations
- faction-level access, shortage, and derived-capacity tracking
- project-based investment
- source-linked domestic spread
- explicit internal route distribution
- corridor bottlenecks and infrastructure-sensitive throughput
- viewer and reporting support for route state and effective access

What remains intentionally post-V1:

- inter-faction trade
- prices and market behavior
- stockpiles and inventory persistence
- depletion
- more metals and deeper production chains

From this point forward, new resource work should be treated as V2-facing expansion rather than unfinished V1 migration.
