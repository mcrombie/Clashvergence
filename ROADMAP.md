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

The project has moved past the first economic and political scaffolding pass. It now includes:

- map generation and multiple scenario layouts
- terrain and climate
- named factions with identities and governments
- doctrine adaptation
- terrain/climate-shaped action selection
- expansion, attack, and development behavior
- specific regional resources and resource outputs
- food production, storage, spoilage, shortage, and seasonal consumption
- domesticable resource spread and resource development projects
- roads, markets, storehouses, granaries, irrigation, pastures, logging camps, mines, and quarries
- trade routing, bottlenecks, sea links, river links, foreign trade, trade warfare, and blockade losses
- income, maintenance, administrative penalties, tribute, and empire-scale pressure
- population, settlement, and integration
- migration, refugees, and frontier settler movement
- ethnicity and ethnic claims
- unrest, secession, rebels, and proto-states
- diplomacy, relationship states, tributaries, war objectives, and peace terms
- administrative capacity, tax capture, autonomy, reach, and overextension
- religion, sacred sites, religious legitimacy, conversion pressure, and reform pressure
- dynastic succession, rulers, heirs, regencies, claimant pressure, and succession crises
- polity advancement and government-form modifiers
- reporting, metrics, dead-system observation, experiments, and an HTML viewer

This is enough to treat the project less as a map-control toy and more as a layered historical simulation prototype. The next work should mostly deepen, connect, observe, and tune these systems before adding another large abstraction.

## Recommended Development Order

### Phase 1: Observation And Pressure Tuning

Priority: highest

Why now:

- Many major systems now exist, but not all of them fire visibly in ordinary runs.
- A simulation can look deep in code while behaving narrowly in practice.
- The current priority is to detect dead systems, runaway loops, and overly universal action incentives.

Targets:

- Use the balance dashboard's system-activity section to track active rate, dead-run rate, average event counts, metric signals, and first activation turn.
- Keep tuning action selection so terrain and climate strongly shape faction personality.
- Watch whether development, expansion, war, diplomacy, migration, religion, succession, unrest, and administration all matter at plausible horizons.
- Tune only after repeated runs show a clear behavioral pattern.

Good outcomes:

- plains, river, steppe, forest, highland, coast, and marsh societies behave differently
- observable systems activate for understandable reasons
- dead or near-silent systems are visible instead of hidden
- dashboard findings lead to targeted changes rather than broad balancing

### Phase 2: Economic Deepening

Priority: very high

Why here:

- The first resource/trade layer exists, but production chains are still shallow.
- Material causality should continue to ground war, settlement, administration, and technology.
- Existing resources should create sharper dependencies and strategic pressure.

Targets:

- Add additional resource classes only when they create new behavior, such as iron, spices, manufactured goods, or prestige materials.
- Build production-chain dependencies rather than only adding more resource names.
- Make shortages alter action choice, war aims, settlement growth, migration, and administrative stress.
- Make strategic resources affect military projection, logistics, and diplomacy more legibly.
- Use trade routes to create richer interdependence, vulnerability, and non-military competition.

Good outcomes:

- conquest is materially motivated
- productive zones and chokepoints are legible in reports and viewer state
- factions differ structurally, not just cosmetically
- trade dependence creates both wealth and risk

### Phase 3: Political And Legitimacy Deepening

Priority: very high

Why here:

- Administration, religion, succession, rebels, and migration exist but need stronger cross-pressure.
- Internal fragmentation should matter as much as external conquest.
- Legitimacy should become a visible political resource, not just a set of metrics.

Targets:

- Connect administrative overextension more strongly to unrest, tax capture, military projection, and integration.
- Make religious mismatch, sacred sites, reform pressure, and clergy support affect diplomacy and internal cohesion.
- Let succession crises, claimant pressure, and civil-war legitimacy shape war aims and secession patterns.
- Make migration and refugee movement alter ethnic, religious, economic, and political maps over time.
- Introduce urban specialization and city networks once migration and production pressure need them.

Good outcomes:

- weak states can own land they do not truly control
- collapse can be administrative, religious, dynastic, demographic, or military
- factions stop behaving like unitary rational actors
- internal events produce coherent external consequences

### Phase 4: Technology As Diffusion

Priority: high

Why now but not before:

- Technology should rest on resources, trade, density, stability, and institutions.
- The project now has enough material and political substrate for diffusion to be meaningful.
- A game-style tech tree would still pull the design toward strategy-game logic too early.

Targets:

- technology spread through contact, trade, density, and stability
- production and agricultural improvements
- military organization and logistics shifts
- administrative and record-keeping advances
- uneven adoption and regional lag
- practical adoption costs tied to resources, state capacity, and social disruption

Good outcomes:

- innovation clusters emerge naturally
- backward peripheries and advanced cores can coexist
- military and economic divergence becomes more believable

### Phase 5: Shocks And Long-Cycle Stressors

Priority: medium-high

Targets:

- famine
- disease
- ecological degradation
- climate anomalies
- trade collapse
- resource exhaustion or local environmental damage

Good outcomes:

- resilient versus brittle systems become clearer
- world history gains punctuated disruption
- complex recovery paths become possible

### Phase 6: Future Game-Facing Layer

Priority: deferred

Targets:

- player-facing controls that expose the same systems AI factions already use
- scenario goals that emerge from simulation pressures rather than abstract victory conditions
- UI affordances for inspection, forecasting, and constrained intervention

Good outcomes:

- player mode does not distort the simulation model
- choices feel political and logistical rather than board-game symmetric
- the same world model remains useful with or without a player

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

### Milestone A: Observation Harness

- keep the dead-system dashboard current as new systems are added
- add short, medium, and long seeded observation presets
- track activation rates for expansion, war, diplomacy, trade disruption, administration, unrest, rebellion, migration, religion, succession, technology, and shocks
- record whether terrain/climate personalities produce distinct strategies

### Milestone B: Action Pressure Passes

- tune action selection from observed behavior rather than flat target ratios
- keep terrain and climate as strong personality inputs
- make shortages, trade dependence, legitimacy, and overextension pull factions toward different choices
- verify that insular, frontier, martial, developmental, and adaptive polities remain meaningfully different

### Milestone C: Production Chains

- deepen resources from output baskets into dependencies
- add only resources that create new pressure or new interpretation
- connect strategic resources to military projection, trade leverage, and settlement development
- expose production dependencies in reports and viewer state

### Milestone D: Legitimacy And Internal Politics

- make religion, succession, and regime agitation more causally visible
- connect legitimacy to diplomacy, unrest, administrative capture, and civil-war claims
- support stronger religious schism, reform, suppression, and accommodation behavior
- introduce elite blocs only when current legitimacy systems need more internal actors

### Milestone E: Diffusion And Transformation

- add technology spread
- deepen migration and urban concentration
- let long-term world divergence emerge from the combined systems

### Milestone F: Shocks And Resilience

- add famine, disease, ecological, climate, and trade-collapse shocks
- distinguish resilient states from brittle ones
- let recovery paths differ by resources, state capacity, legitimacy, and trade access

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
