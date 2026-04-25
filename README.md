# Clashvergence

Clashvergence is a simulation-first project about how polities grow, compete, consolidate, fragment, and adapt across a map. The goal is not to build a fair strategy game and then layer realism on top. The goal is to model interacting geopolitical and economic pressures first, then see what kinds of stories emerge and generate stylized histories.

At its current stage, the simulation already supports territory expansion, war, development projects, specific resources, trade routing, food storage, population movement, settlement growth, climate and terrain effects, faction doctrine, diplomacy, ethnicity, unrest, secession, rebel proto-states, government forms, administrative capacity, religion, dynastic succession, polity advancement, narrative reporting, experiment dashboards, and an HTML turn-by-turn viewer.

This `README.md` describes the current project state.

## Project Direction

The long-term direction is:

- Build a simulation of political, economic, and social dynamics.
- Prefer plausible causal systems over game balance or player fun.
- Treat any future player-controlled mode as secondary.
- Use experiments and metrics to study behavior, not to force symmetry.

## Current Simulation Model

Each run creates a world containing regions and factions. Regions track ownership, resource endowments, output, trade route state, food storage, population, terrain, climate, ethnic and religious composition, integration, settlement level, administrative state, migration pressure, and unrest. Factions track treasury, identity, doctrine, ethnicity, diplomacy, political structure, resource access, trade income, administrative capacity, religion, succession, and population movement.

Each turn currently follows a rough loop like this:

1. Each faction chooses an action based on its doctrine and current opportunities.
2. Actions resolve as `expand`, `attack`, or `develop`.
3. Resource production, trade routing, food storage, and administrative state are refreshed.
4. Unrest events, secessions, rebel maturation, and migration are resolved.
5. Income, empire-scale penalties, administrative penalties, tribute, and maintenance are applied.
6. Integration, population, settlement levels, polity tiers, diplomacy, religion, succession, language contact, and doctrine are updated.
7. Metrics and region history are recorded for analysis and visualization.

## Implemented Systems

- Terrain-aware and climate-aware regions.
- Multiple hand-authored and generated map layouts.
- Faction naming, identity, language, and government structure.
- Doctrine profiles that adapt from homeland, climate, terrain, and lived experience.
- Expansion, attack, and development decision logic, with terrain/climate personality shaping strategy.
- Specific resources including grain, livestock, horses, wild food, timber, copper, stone, salt, and textiles.
- Resource production, shortages, domesticable resource spread, extraction sites, roads, storehouses, markets, irrigation, pastures, logging camps, mines, and quarries.
- Internal trade routing, route bottlenecks, sea and river links, foreign trade, trade income, import reliance, trade warfare, and blockade losses.
- Seasonal food production, consumption, storage, spoilage, shortages, and salt preservation effects.
- Population growth and transfer during expansion and conflict.
- Population migration, refugee movement, frontier settlement, and seasonal migration modifiers.
- Homeland, core, and frontier integration.
- Ethnicity, ethnic claims, and same-people regime tension.
- Unrest, crises, secession, restoration, and rebel proto-states.
- Diplomacy including rivalry, pacts, alliances, truces, tributary relationships, war objectives, peace terms, and diplomatic breakdown.
- Administrative capacity, administrative reach, tax capture, autonomy, overextension, and administrative maintenance pressure.
- Religion, sacred sites, religious legitimacy, religious unrest, conversion pressure, clergy support, tolerance, zeal, and reform pressure.
- Dynastic succession, rulers, heirs, regencies, legitimacy, prestige, claimant pressure, and succession crises.
- Polity tiers and government forms that affect income, stability, and integration.
- Event logs, chronicles, AI-assisted interpretive narrative input/output, metrics snapshots, balance dashboards, and dead-system observation.
- HTML simulation viewer with turn playback, region/faction detail panels, trade overlays, migration/admin/religion/succession data, and doctrine timeline support.

## What Still Needs Work

These areas are still intentionally incomplete, shallow, or mostly observational:

- Resource chains beyond the current regional-output and project system, such as iron, spices, manufactured goods, and stronger production dependencies.
- Technology diffusion and production methods.
- Ideology beyond religion and legitimacy politics.
- Urban specialization, city networks, and more explicit labor or craft roles.
- Elite internal politics beyond succession, claimants, clergy support, and regime agitation.
- Large shocks such as famine, disease, ecological degradation, climate anomalies, and trade collapse.
- A player game mode.

## Repository Layout

- `main.py`: CLI entry point for a single simulation run.
- `src/`: Core simulation logic and viewer generation.
- `tests/`: Focused tests for core systems and invariants.
- `experiments/`: Repeated-run analysis and dashboard scripts.
- `reports/`: Generated reports, chronicles, viewers, and experiment output.

## Running A Simulation

From the project root:

```powershell
python main.py
```

Example with explicit parameters:

```powershell
python main.py --map thirty_seven_region_ring --turns 20 --num-factions 4
```

This writes output to:

- `reports/results.txt`
- `reports/chronicle.txt`
- `reports/simulation_view.html`

## Running Experiments

Example balance-dashboard run:

```powershell
python experiments/experiment_balance_dashboard.py --maps thirty_seven_region_ring --turns 20 --runs 10 --num-factions 4
```

The dashboard is best thought of as a research tool. For this project, it is more useful for spotting pathological behavior, runaway collapse, or dead systems than for forcing strict competitive balance.

## Running Tests

Use `python -m pytest`, since `pytest` may not be on `PATH` in every shell:

```powershell
python -m pytest
```

Example:

```powershell
python -m pytest tests\test_metrics.py -q
```

Current tests are most valuable when they protect simulation coherence:

- invalid state transitions
- broken event serialization
- diplomacy and doctrine regressions
- metric/reporting failures
- crash-level failures in core turn processing

## Current Development Philosophy

This project should move faster than a typical productized game, but not so fast that the simulation becomes unreadable or internally inconsistent.

The most useful test philosophy here is:

- keep strong invariant tests
- keep a few seeded smoke runs
- use experiment scripts for observation
- avoid heavy regression gates for every new feature

That fits a simulation where the interesting question is often, "what does this system do when combined with the others?" rather than, "is this perfectly balanced for players?"

## Recommended Near-Term Focus

The next major priorities are:

1. Observe existing systems across repeated runs, especially with the dead-system dashboard.
2. Tune pressure and action mix so terrain, climate, resources, trade, and legitimacy produce distinct strategies without flattening faction personality.
3. Deepen production chains, strategic resources, and trade dependencies now that the first resource/trade layer exists.
4. Deepen state capacity, legitimacy, religion, migration, and succession so they create more visible causal pressure.
5. Add technology as diffusion through resources, trade, density, stability, and institutions rather than as a game-like tech tree.

More detailed sequencing and rationale live in [ROADMAP.md](./ROADMAP.md).
