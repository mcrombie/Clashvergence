# Release Checklist

Use this checklist before publishing `v0.9.0 - Historical Simulation Prototype` on GitHub.

## Pre-Release Review

- Confirm `README.md` describes the project as a simulation-first prototype.
- Confirm the documented Python version matches the version actually verified for the release.
- Confirm `RELEASE_NOTES.md` includes the current version title, highlights, known limitations, and suggested demo command.
- Confirm `examples/README.md` includes the public demo command.
- Confirm `requirements.txt` documents the standard-library core honestly.
- Confirm `requirements-optional.txt` lists optional AI/debug visualizer dependencies.
- Confirm `.gitignore` excludes generated reports, local env files, caches, generated GIFs, and temporary output.
- Confirm no generated `reports/` artifacts are staged.
- Confirm no `.env` or `.env.local` file is staged.
- Attach selected atlas-map screenshots from `release-assets/v0.9.0/` to the GitHub release page instead of committing generated assets.
- Do not use node-map, graph-view, or map-generator visuals as public release imagery.

## Suggested Verification

Before tagging, run whichever checks you want for the release bar:

```powershell
python main.py --map thirty_seven_region_ring --turns 20 --num-factions 4 --seed release-smoke --ai-narrative off
```

```powershell
python -m pytest
```

The smoke run checks the public command path and output generation. The test run checks core invariants and regressions. Generated output should remain untracked.

## GitHub Release Draft

Tag:

```text
v0.9.0
```

Title:

```text
v0.9.0 - Historical Simulation Prototype
```

Suggested opening:

```text
This release marks Clashvergence's first substantial public prototype: a simulation-first model of factions, regions, resources, diplomacy, unrest, technology, religion, succession, and emergent historical reporting. It is not yet a stable v1.0 release; systems are still being tuned and several mechanics remain intentionally experimental.
```

Suggested demo command:

```powershell
python main.py --map thirty_seven_region_ring --turns 80 --num-factions 4 --seed v0.9.0-demo --ai-narrative off
```

## After Publishing

- Confirm the release page links to the README.
- Confirm the source archive does not include `reports/` output.
- Consider adding atlas-map screenshots to the GitHub release body, not as generated files committed to the repository.
- Keep post-release tuning on the roadmap rather than patching the release unless there is a crash-level issue or documentation error.
