# Release Notes

## v0.9.0 - Historical Simulation Prototype

Clashvergence v0.9.0 is the first substantial public prototype milestone. It presents the project as a simulation-first model of factions, regions, resources, diplomacy, unrest, technology, religion, succession, and emergent historical reporting.

This is not a stable v1.0 release. The simulation is usable and inspectable, but the systems are still experimental, outputs are still being tuned, and several mechanics remain intentionally shallow or observational.

## Suggested Demo

Use this command for the recommended public demo:

```powershell
python main.py --map thirty_seven_region_ring --turns 80 --num-factions 4 --seed v0.9.0-demo --ai-narrative off
```

Open the generated viewer:

```text
reports/simulation_view.html
```

For a longer showcase run:

```powershell
python main.py --map thirty_seven_region_ring --turns 250 --num-factions 4 --seed showcase --ai-narrative off
```

Longer runs can generate very large report files. `reports/` is ignored by Git.

## Highlights

- Turn-based historical simulation with region ownership, faction actions, and emergent event logs.
- Terrain, climate, resources, trade, food, migration, administration, and settlement growth.
- Faction identity, language/culture, government forms, polity tiers, and doctrine adaptation.
- Diplomacy with rivalry, pacts, alliances, truces, tributaries, wars, objectives, and settlements.
- Unrest, crises, secession, rebel proto-states, and successor polities.
- Religion, sacred sites, legitimacy, conversion pressure, reform pressure, and clergy support.
- Dynastic succession with rulers, heirs, regencies, claimants, prestige, and crises.
- Elite blocs and internal political pressure.
- Practical technology diffusion through regional exposure, local adoption, and faction institutionalization.
- Urban specialization, capital selection, and urban network value.
- HTML turn-by-turn viewer with map playback, region/faction inspection, metrics, trade overlays, migration/admin/religion/succession data, and doctrine timelines.
- Text reports, chronicles, metrics logs, experiment dashboards, and optional AI-assisted interpretive narrative generation.
- Generated map support and a standalone map generator UI.

## Known Limitations

- This is a simulation prototype, not a player-facing game.
- The simulation is not balanced for faction fairness or strategic-game symmetry.
- Long runs can create large HTML viewer files.
- Event logs and reports can be noisy.
- Production chains are still shallow relative to the resource/trade substrate.
- Technology is still a V1 practical-method diffusion layer.
- Ideology beyond religion and legitimacy politics is not yet modeled.
- Urban specialization exists, but deeper city networks, labor roles, and craft specialization remain future work.
- Large shocks such as famine, disease, ecological degradation, climate anomalies, and trade collapse are not yet fully modeled.
- Internal politics exists but needs stronger feedback into diplomacy, revolt, administration, and collapse.

## Optional AI Narrative

AI interpretation is optional. By default, runs write structured narrative input to:

```text
reports/interpretive_narrative_input.json
```

API-backed interpretive narrative generation requires:

- the optional dependencies in `requirements-optional.txt`
- `OPENAI_API_KEY`
- `CLASHVERGENCE_ENABLE_AI_INTERPRETATION=1` or `--ai-narrative on`

## Upgrade Notes

There are no stable APIs promised before v1.0. Internal data structures, event formats, metrics, and viewer payloads may change as the simulation model develops.

## Next Direction

After v0.9.0, the highest-value work is:

1. Observe system activity across repeated runs.
2. Tune terrain/climate/resource pressures.
3. Deepen production chains and strategic resources.
4. Strengthen legitimacy, administration, migration, succession, religion, and elite politics.
5. Continue refining technology diffusion without turning it into a game-style tech tree.
