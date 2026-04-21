# Clashvergence

Clashvergence is a simulation-first project about how polities grow, compete, consolidate, fragment, and adapt across a map. The goal is not to build a fair strategy game and then layer realism on top. The goal is to model interacting geopolitical and economic pressures first, then see what kinds of stories emerge and generate stylized histories.

At its current stage, the simulation already supports territory expansion, war, investment, population, settlement growth, climate and terrain effects, faction doctrine, diplomacy, ethnicity, unrest, secession, rebel proto-states, government forms, polity advancement, narrative reporting, and an HTML turn-by-turn viewer.

This `README.md` describes the current project state.

## Project Direction

The long-term direction is:

- Build a simulation of political, economic, and social dynamics.
- Prefer plausible causal systems over game balance or player fun.
- Treat any future player-controlled mode as secondary.
- Use experiments and metrics to study behavior, not to force symmetry.

## Current Simulation Model

Each run creates a world containing regions and factions. Regions track ownership, resources, population, terrain, climate, ethnic composition, integration, settlement level, and unrest. Factions track treasury, identity, doctrine, ethnicity, diplomacy, and political structure.

Each turn currently follows a rough loop like this:

1. Each faction chooses an action based on its doctrine and current opportunities.
2. Actions resolve as `expand`, `attack`, or `invest`.
3. Unrest events and secessions are resolved.
4. Income, empire-scale penalties, and maintenance are applied.
5. Integration, population, settlement levels, rebel status, polity tiers, diplomacy, and doctrine are updated.
6. Metrics and region history are recorded for analysis and visualization.

## Implemented Systems

- Terrain-aware and climate-aware regions.
- Multiple hand-authored and generated map layouts.
- Faction naming, identity, language, and government structure.
- Doctrine profiles that adapt from homeland and lived experience.
- Expansion, attack, and investment decision logic.
- Population growth and transfer during expansion and conflict.
- Homeland, core, and frontier integration.
- Ethnicity, ethnic claims, and same-people regime tension.
- Unrest, crises, secession, restoration, and rebel proto-states.
- Diplomacy including rivalry, pacts, alliances, truces, and diplomatic breakdown.
- Polity tiers and government forms that affect income, stability, and integration.
- Event logs, chronicles, metrics snapshots, and balance dashboards.
- HTML simulation viewer with turn playback and doctrine timeline.

## What The Project Is Not Yet

These areas are still intentionally incomplete or missing:

- Specific resources such as iron, grain, timber, salt, horses, or spices.
- Trade networks, transport friction, and market access.
- State capacity and administrative extraction as a first-class system.
- Religion and ideology.
- Technology diffusion and production methods.
- Migration, urban specialization, and elite internal politics.
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

1. Specific resources and production chains.
2. Trade, transport, and market access.
3. State capacity, extraction, and administrative limits.
4. Religion and ideology as legitimacy and cohesion systems.
5. Technology as diffusion rather than a game-like tech tree.

More detailed sequencing and rationale live in [ROADMAP.md](./ROADMAP.md).
