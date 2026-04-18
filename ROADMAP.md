# Clashvergence Roadmap

## Core Premise

Clashvergence is being developed first and foremost as a simulation, not a game.

That means development decisions should prioritize:

- plausible interacting systems
- meaningful causal relationships
- historically recognizable dynamics
- interpretable emergent outcomes

Development should not prioritize:

- faction symmetry
- player fairness
- short-term fun optimization
- mechanics added mainly because they would make a future game mode more exciting

A future player-controlled mode can still exist, but it should emerge from the simulation after the core world model is strong enough to stand on its own.

## Design Principles

### 1. Simulation First

The central question is not "is this fun to play?" but "does this produce coherent geopolitical behavior?"

### 2. Material Foundations Before Abstractions

Add systems in dependency order. Material and logistical constraints should come before high-level ideological flavor systems.

### 3. Causality Over Balance

The goal is not perfectly equal win rates. The goal is that outcomes make sense given geography, institutions, demographics, and historical pressures.

### 4. Observe Before Tuning

When a new system is added, the first task is to observe how it behaves in repeated runs. Tuning comes after the system has proven it creates meaningful dynamics.

### 5. Protect Coherence, Not Perfection

Testing should guard against broken state, crashes, and nonsense outputs. It should not try to freeze the simulation into one ideal result.

## Current Baseline

The project already has a strong early foundation:

- map generation and multiple scenario layouts
- terrain and climate
- named factions with identities and governments
- doctrine adaptation
- expansion, attack, and investment behavior
- income, maintenance, and empire-scale penalties
- population, settlement, and integration
- ethnicity and ethnic claims
- unrest, secession, rebels, and proto-states
- diplomacy and relationship states
- polity advancement and government-form modifiers
- reporting, metrics, experiments, and an HTML viewer

This is enough to move beyond a simple map-control toy and start building a deeper historical simulation.

## Recommended Development Order

### Phase 1: Specific Resources And Production

Priority: highest

Why first:

- The economy is still too abstract.
- Later systems like trade, war, state formation, and technology need a real material base.
- Specific resources make geography matter for reasons other than flat resource counts.

Targets:

- Add resource classes such as grain, timber, iron, copper, horses, salt, stone, spices, and textiles.
- Let regions produce different baskets based on terrain and climate.
- Separate subsistence resources from prestige or strategic resources.
- Make some resources locally essential and others tradable luxuries or force multipliers.

Good outcomes:

- conquest becomes materially motivated
- chokepoints and productive zones become legible
- factions begin to differ structurally, not just doctrinally

### Phase 2: Trade, Transport, And Market Access

Priority: very high

Why next:

- Specific resources do not matter enough unless they can move.
- Trade is what turns geography into a networked system.
- This also creates interdependence, vulnerability, and non-military competition.

Targets:

- overland and coastal transport costs
- river and coast advantages
- route disruption from war or unrest
- local surplus and deficit
- market access modifiers
- strategic chokepoints

Good outcomes:

- factions can become rich without conquering everything
- wars can target routes rather than only territory
- isolated empires behave differently from connected ones

### Phase 3: State Capacity And Administrative Extraction

Priority: very high

Why here:

- Once wealth and trade exist, the next question is how much of that wealth states can actually extract.
- This is the missing bridge between owning territory and governing it effectively.

Targets:

- tax efficiency
- corruption or leakage
- communications distance
- frontier administrative burden
- local autonomy and delegated rule
- institutional capacity tied to polity tier and government form

Good outcomes:

- larger empires stop being powerful just because they are larger
- weak states can own land they do not truly control
- collapse becomes an administrative phenomenon, not just a military one

### Phase 4: Religion And Ideology

Priority: high

Why after state capacity:

- Religion and ideology are strongest when they sit on top of real demographic and political structures.
- If added too early, they risk becoming flavor modifiers instead of social forces.

Targets:

- belief systems with spread and persistence
- tolerance versus exclusivity
- legitimacy effects on rulers
- sectarian or ideological unrest
- alliance and rivalry patterns shaped by shared belief
- reform movements and heterodox splinters

Good outcomes:

- legitimacy becomes more than treasury and territory
- internal fragmentation becomes richer
- diplomacy gains cultural and ideological depth

### Phase 5: Technology As Diffusion

Priority: high

Why not earlier:

- Technology should rest on resources, trade, and institutions.
- A game-style tech tree would pull the project toward strategy-game logic too early.

Targets:

- technology spread through contact, trade, density, and stability
- production and agricultural improvements
- military organization and logistics shifts
- administrative and record-keeping advances
- uneven adoption and regional lag

Good outcomes:

- innovation clusters emerge naturally
- backward peripheries and advanced cores can coexist
- military and economic divergence becomes more believable

### Phase 6: Migration, Assimilation, And Urbanization

Priority: medium-high

Why here:

- Once resources, trade, and legitimacy are stronger, population movement becomes much more meaningful.

Targets:

- refugee flight
- settler expansion
- labor migration toward productive regions
- assimilation versus persistence
- city attraction and regional specialization

Good outcomes:

- conquest has long-tail demographic consequences
- urban centers become engines of change
- ethnic maps evolve over time rather than staying mostly static

### Phase 7: Elite Politics And Internal Power Blocs

Priority: medium

Why later:

- Internal politics becomes more interesting once the economy, legitimacy, and state machinery are stronger.

Targets:

- court, army, clergy, merchant, and provincial elite blocs
- succession pressure
- reform coalitions
- coups, palace struggles, and military autonomy

Good outcomes:

- factions stop behaving like unitary rational actors
- policy instability becomes endogenous
- civil conflict gains clearer internal causes

### Phase 8: Shocks And Long-Cycle Stressors

Priority: medium

Targets:

- famine
- disease
- ecological degradation
- climate anomalies
- trade collapse

Good outcomes:

- resilient versus brittle systems become clearer
- world history gains punctuated disruption
- complex recovery paths become possible

## Features To Defer On Purpose

These should stay secondary until the simulation core is deeper:

- player abilities designed around fun
- asymmetric faction powers built for replayability
- explicit victory conditions
- highly game-like tech trees
- UI systems aimed mainly at tactical control

If a future game mode is added, it should mostly expose and constrain the same systems the AI factions already use.

## Testing Strategy

The project should not rely on heavy full-regression testing before every feature. That is too slow for the current stage and too rigid for a simulation whose behavior is still being discovered.

Instead, use a lighter but disciplined stack:

- Invariant tests
  Ensure treasury, population, ownership, integration, and unrest stay in valid ranges and transitions remain legal.

- Seeded smoke simulations
  Run a few fixed seeds for short and medium turn counts to catch crashes and obvious nonsense.

- Experiment dashboards
  Use repeated-run reports to study behavior, detect dead systems, and flag pathological outcomes.

- Focused unit tests for fragile systems
  Keep tests around doctrine, diplomacy, rebellion, serialization, and metrics where small changes can silently break observability.

This keeps development fast while still protecting simulation coherence.

## Practical Milestones

### Milestone A: Economic Grounding

- introduce specific resources
- make regional output depend on terrain and climate
- update reports and viewer to expose resource composition

### Milestone B: Networked Geography

- add trade routes and transport friction
- make route control economically meaningful
- expose trade dependency in metrics

### Milestone C: Governing Capacity

- model taxation, leakage, and administrative reach
- connect unrest and integration more tightly to extractive capacity
- make overextension a structural pressure

### Milestone D: Legitimacy Systems

- add religion and ideology
- tie them into unrest, diplomacy, and faction cohesion
- support schism, reform, and suppression behavior

### Milestone E: Diffusion And Transformation

- add technology spread
- add migration and urban concentration
- let long-term world divergence emerge from the combined systems

## Ongoing Questions To Revisit

- What level of abstraction feels rich without becoming unmanageably detailed?
- Which outputs are genuinely informative versus just noisy?
- Which systems create new behavior and which only add modifiers?
- Where does realism improve understanding, and where does it overcomplicate the model?

## Success Criteria

The roadmap is working if the simulation increasingly produces outcomes like these:

- geography shapes wealth and conflict in recognizable ways
- states differ in capacity, not just color and doctrine
- internal fragmentation matters as much as border war
- trade and legitimacy affect power as much as raw territory
- plausible historical stories emerge without being scripted

If those outcomes appear, then a future game mode can be built on top of the simulation rather than distorting it.
