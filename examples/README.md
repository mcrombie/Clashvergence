# Examples

This directory records recommended public demo commands for Clashvergence. Generated outputs are written to `reports/`, which is ignored by Git. A couple images from the UI are also included.

## v0.9.0 Demo

Recommended first run:

```powershell
python main.py --map thirty_seven_region_ring --turns 80 --num-factions 4 --seed v0.9.0-demo --ai-narrative off
```

Generated outputs:

- `reports/results.txt`
- `reports/chronicle.txt`
- `reports/interpretive_narrative_input.json`
- `reports/simulation_view.html`

Open `reports/simulation_view.html` in a browser to inspect the timeline and map state.

## Quick Demo

Use this when you only want to confirm the simulation produces output quickly:

```powershell
python main.py --map thirty_seven_region_ring --turns 20 --num-factions 4 --seed quick-demo --ai-narrative off
```

## Long Showcase

Use this when you want a longer history with more succession, rebellion, diplomacy, and system interaction:

```powershell
python main.py --map thirty_seven_region_ring --turns 250 --num-factions 4 --seed showcase --ai-narrative off
```

Long showcase runs can generate very large HTML files.

## Generated Map Demo

Generate the map lab:

```powershell
python main.py --map-lab
```

Then open:

```text
reports/map_generator.html
```

The map lab generates commands for dynamic worlds. A representative generated-world run looks like:

```powershell
python main.py --map generated_world --num-factions 4 --turns 80 --map-style continent --map-seed v0.9.0-generated --map-regions 56 --map-landmasses 2 --map-water 0.42 --map-rivers 5 --map-mountains 3 --map-climate varied --map-richness 1 --map-chokepoints 0.55 --map-diversity 0.7 --map-starts balanced --ai-narrative off
```

## Optional AI Narrative Demo

Only use this if `OPENAI_API_KEY` is configured and the optional `openai` package is installed:

```powershell
python main.py --map thirty_seven_region_ring --turns 80 --num-factions 4 --seed narrative-demo --ai-narrative on
```
