# Clashvergence

Clashvergence is a simulation-first project about how polities grow, compete, consolidate, fragment, and adapt across a map. The goal is not to build a fair strategy game and then layer realism on top. The goal is to model interacting geopolitical, economic, social, and environmental pressures first, then see what kinds of histories emerge.

## Release Status

Current target release:

```text
v0.9.0 - Historical Simulation Prototype
```

This milestone is intended as a substantial public prototype, not a stable v1.0 release. The simulation is usable, inspectable, and capable of generating rich turn-by-turn histories, but systems are still being tuned and several mechanics remain intentionally experimental.

## What It Simulates

Each run creates a world containing regions and factions. Regions track ownership, resource endowments, output, trade route state, food storage, population, terrain, climate, ethnic and religious composition, technology presence and adoption, integration, settlement level, administrative state, migration pressure, and unrest. Factions track treasury, identity, doctrine, ethnicity, diplomacy, political structure, resource access, trade income, administrative capacity, religion, succession, institutionalized technologies, elite blocs, and population movement.

Each turn roughly follows this loop:

1. Each faction chooses an action based on doctrine, opportunities, resources, diplomacy, and geography.
2. Actions resolve as `expand`, `attack`, or `develop`.
3. Resource production, trade routing, food storage, and administrative state are refreshed.
4. Unrest events, secessions, rebel maturation, and migration are resolved.
5. Income, empire-scale penalties, administrative penalties, tribute, and maintenance are applied.
6. Integration, technology diffusion, population, settlement levels, polity tiers, diplomacy, religion, succession, language contact, and doctrine are updated.
7. Metrics and region history are recorded for analysis and visualization.

## Implemented Systems

- Terrain-aware and climate-aware regions.
- Multiple hand-authored and generated map layouts.
- Faction naming, identity, language, government forms, and polity tiers.
- Doctrine profiles that adapt from homeland, climate, terrain, and lived experience.
- Expansion, attack, and development decision logic, with terrain/climate personality shaping strategy.
- Specific resources including grain, livestock, horses, wild food, timber, copper, stone, salt, and textiles.
- Resource production, shortages, domesticable resource spread, extraction sites, roads, storehouses, markets, irrigation, pastures, logging camps, mines, and quarries.
- Internal trade routing, route bottlenecks, sea and river links, foreign trade, trade income, import reliance, trade warfare, and blockade losses.
- Seasonal food production, consumption, storage, spoilage, shortages, and salt preservation effects.
- Population growth, population transfer, migration, refugees, frontier settlement, and seasonal migration modifiers.
- Homeland, core, and frontier integration.
- Ethnicity, ethnic claims, language contact, and same-people regime tension.
- Unrest, crises, secession, restoration, rebel proto-states, and rebel independence.
- Diplomacy including rivalry, pacts, alliances, truces, tributary relationships, war objectives, peace terms, and diplomatic breakdown.
- Administrative capacity, administrative reach, tax capture, autonomy, overextension, and administrative maintenance pressure.
- Religion, sacred sites, religious legitimacy, religious unrest, conversion pressure, clergy support, tolerance, zeal, and reform pressure.
- Dynastic succession, rulers, heirs, regencies, legitimacy, prestige, claimant pressure, and succession crises.
- Elite blocs and internal political pressure.
- Practical technology diffusion through regional exposure, local adoption, and faction institutionalization.
- Urban specialization, capital selection, and urban network value.
- Event logs, chronicles, metrics snapshots, balance dashboards, dead-system observation, and an HTML turn-by-turn viewer.
- Optional AI-assisted interpretive narrative generation.

## Installation

The current verified development environment uses Python 3.14.3. Use Python 3.14 for the v0.9.0 release unless you separately verify another version. Python 3.10+ is likely compatible based on the syntax used by the codebase, but it has not been separately verified for this release.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The core simulation currently uses the Python standard library. Optional AI and debug-visualizer dependencies are listed in `requirements-optional.txt`.

## Quick Start

From the project root:

```powershell
python main.py --map thirty_seven_region_ring --turns 80 --num-factions 4 --seed v0.9.0-demo --ai-narrative off
```

This writes output to:

- `reports/results.txt`
- `reports/chronicle.txt`
- `reports/interpretive_narrative_input.json`
- `reports/simulation_view.html`

Open `reports/simulation_view.html` in a browser to inspect the turn-by-turn viewer.

For a shorter smoke-style run:

```powershell
python main.py --map thirty_seven_region_ring --turns 20 --num-factions 4 --seed quick-demo --ai-narrative off
```

For a longer showcase run:

```powershell
python main.py --map thirty_seven_region_ring --turns 250 --num-factions 4 --seed showcase --ai-narrative off
```

Long runs can create very large HTML viewer files. Generated reports are intentionally ignored by Git.

## Map Generator

To write the standalone map generator UI:

```powershell
python main.py --map-lab
```

This writes:

```text
reports/map_generator.html
```

The generated UI can preview map settings and produce a command for running the selected generated world.

## Optional AI Narrative

AI narrative generation is optional and disabled by default. The simulation always writes `reports/interpretive_narrative_input.json`, which can be inspected without making an API call.

To enable API-backed narrative generation:

1. Install the optional dependencies listed in `requirements-optional.txt`.
2. Set `OPENAI_API_KEY`.
3. Set `CLASHVERGENCE_ENABLE_AI_INTERPRETATION=1` or pass `--ai-narrative on`.

Example:

```powershell
python -m pip install -r requirements-optional.txt
python main.py --map thirty_seven_region_ring --turns 80 --num-factions 4 --seed narrative-demo --ai-narrative on
```

When enabled, the interpretive narrative is written to:

```text
reports/interpretive_narrative.txt
```

## Running Experiments

The experiment scripts are observation tools. They are useful for spotting pathological behavior, runaway collapse, underused systems, and dead systems. They are not meant to force symmetric game balance.

Example balance dashboard run:

```powershell
python experiments/experiment_balance_dashboard.py --maps thirty_seven_region_ring --turns 20 --runs 10 --num-factions 4
```

## Running Tests

Use `python -m pytest`, since `pytest` may not be on `PATH` in every shell:

```powershell
python -m pytest
```

Current tests are most valuable when they protect simulation coherence:

- invalid state transitions
- broken event serialization
- diplomacy and doctrine regressions
- metric/reporting failures
- crash-level failures in core turn processing

## Repository Layout

- `main.py`: CLI entry point for a single simulation run.
- `src/`: Core simulation logic and viewer generation.
- `tests/`: Focused tests for core systems and invariants.
- `experiments/`: Repeated-run analysis and dashboard scripts.
- `examples/`: Suggested public demo commands and release examples.
- `reports/`: Generated reports, chronicles, viewers, and experiment output. This directory is ignored by Git.
- `ROADMAP.md`: Development direction after the prototype milestone.
- `RELEASE_NOTES.md`: Public release notes.

## Known Limitations

These limitations are expected for v0.9.0:

- Clashvergence is not a player-facing game yet.
- The simulation is not tuned for faction symmetry, fairness, or short-term fun.
- Output can be noisy, especially in long runs with many events.
- The HTML viewer can become very large for long simulations.
- Production chains are still shallow relative to the resource/trade framework.
- Technology is a V1 practical-method diffusion layer, not a deep transformational history model.
- Ideology beyond religion and legitimacy politics is not yet modeled.
- Urban specialization exists, but deeper city networks and labor/craft roles remain future work.
- Large shocks such as famine, disease, ecological degradation, climate anomalies, and trade collapse are not yet fully modeled.
- Internal politics exists through succession, religion, claimants, and elite blocs, but still needs stronger causal feedback into diplomacy, revolt, and state capacity.

## Development Philosophy

This project should move faster than a typical productized game, but not so fast that the simulation becomes unreadable or internally inconsistent.

The useful test philosophy here is:

- keep strong invariant tests
- keep a few seeded smoke runs
- use experiment scripts for observation
- avoid heavy regression gates for every new feature

That fits a simulation where the interesting question is often, "what does this system do when combined with the others?" rather than, "is this perfectly balanced for players?"

## Recommended Near-Term Focus

The next major priorities after v0.9.0 are:

1. Observe existing systems across repeated runs, especially with the dead-system dashboard.
2. Tune pressure and action mix so terrain, climate, resources, trade, and legitimacy produce distinct strategies without flattening faction personality.
3. Deepen production chains, strategic resources, and trade dependencies now that the first resource/trade layer exists.
4. Deepen state capacity, legitimacy, religion, migration, succession, and elite politics so they create more visible causal pressure.
5. Observe and tune technology diffusion so trade, density, stability, resources, and institutions create visible divergence without becoming a game-like tech tree.

More detailed sequencing and rationale live in [ROADMAP.md](./ROADMAP.md).
