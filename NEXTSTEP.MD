Worked for 4h 55m 45s
I ran two things:

Full automated suite: 126 passed, 6 failed in about 49 minutes
Broad balance audit: 330 simulation runs across 7 maps, 3 turn horizons (10/20/35), and both valid player-count buckets (3-player and 4-player)
I wrote the detailed outputs to simulation_state_audit_2026_04_21.txt and simulation_state_audit_2026_04_21.json.

Main Findings

The sim is overwhelmingly development-led. In my audit, winners were development_led in 330/330 runs. Even on violent maps, winners still developed much more than they fought.
The development meta is very clear:
build_granary dominates early, then expand_market and expand_storehouse take over mid/late.
Mines and quarries are present but still strategically minor.
Winner doctrine by end-state:
Developmental won 42.4%
Insular won 40.6%
Adaptive won 17.0%
By player count:
3-player maps strongly favored Insular end states (74% of wins)
4-player maps favored Developmental end states (54% of wins)
Map Balance

Most balanced map in this sweep: seventeen_region_ring
Top winner share ranged from 37.5% to 50%, with multiple factions winning across runs.
Moderate competition: seven_region_ring
Still biased, but not fully deterministic.
Highly deterministic / position-biased:
ten_region_ring
asymmetric_frontier
multi_ring_symmetry
thirty_seven_region_ring at 10 and 20 turns
thirteen_region_ring was also heavily biased, especially at short horizons.
multi_ring_symmetry looks especially suspicious:
no attack wins, fixed winners, and unrest/secession dominates late behavior.
Economy / New Mechanics

Food mechanics are present, but winners usually stay food-positive.
Food deficits stayed near zero on most maps until longer horizons.
The clearest food-pressure problem map was asymmetric_frontier at 35 turns:
winner average food deficit 0.375, food balance nearly flat.
Storage/logistics mechanics are definitely shaping play:
markets and storehouses become the dominant economic upgrade path once granaries are in place.
Roads matter, but they are still secondary compared with storage/market scaling.
Extraction is under-adopted:
copper/stone projects were rare compared with food/storage/trade projects.
Unrest / Rebellion

Long-run instability is real on some maps.
thirty_seven_region_ring at 35 turns produced heavy unrest:
52 secessions and 10 rebel-independence events across 10 runs.
A rebel polity won 6/10 runs there.
multi_ring_symmetry produced repeated secession/independence loops despite low direct warfare, which suggests an instability feedback problem rather than a military one.
Test Caveats
The current branch is not fully green. The failing tests matter:

1 stale UI test still expects the removed doctrine timeline panel.
3 heartland/economy tests no longer match current population/income behavior.
2 region-naming tests are failing, including one failed conquest expectation.
My read on the current strategy meta is:

Best general strategy: develop first, fight selectively
Best 3-player outcome pattern: Insular
Best 4-player / larger-map outcome pattern: Developmental
Biggest systemic issues: opening doctrine homogenization, strong map/start-position bias, over-centrality of granary -> market/storehouse progression, and late unrest/rebel spikes on some maps
The next best step is probably not adding more mechanics immediately. I’d first fix the red tests and then rebalance:

opening doctrine diversity
deterministic map bias on ten_region_ring, asymmetric_frontier, multi_ring_symmetry
overperformance of market/storehouse follow-up relative to extractive development
unrest/rebel escalation on long 4-player runs