# Economy Deepening: Further Development Plan

## Assessment of Phase 1 Implementation

The seven-phase plan from `ECONOMY_DEEPENING_PLAN.md` was implemented with high fidelity. The following is a summary of what was completed, what was partially done, and what remains unwired.

### What Was Completed (Phases 2–6)

**Phase 2 — Resource Completion:** Livestock has its own production formula separate from grain, with `pasture_level` as its primary development input and a contribution to `mobility_capacity` at 0.18 per unit. Salt generates a demand signal from population and food security and modulates food spoilage through `get_faction_salt_preservation_modifier()`. Textiles feed into `urban_surplus` and boost `taxable_value` through a dedicated access factor.

**Phase 3 — Iron and Gold:** Iron is seeded as an extractive resource in hills and highland terrain, gated by a copper development threshold before it can be exploited, and processes into `iron_goods` through a timber-fuel dependency. Gold is seeded at low concentrations in hills and riverlandterrain, contributes heavily to `taxable_value`, and raises trade gateway attractiveness by the highest bonus of any resource.

**Phase 4 — Deeper Production Chains:** All four planned produced goods are implemented. Weapons require copper or iron_goods, timber, and tools, with demand scaling against active wars and military doctrine. Provisions require food and salt with a storehouse factor, contributing to logistics mobility. Crafted goods require textiles, stone, and tools with an urban population cap. Ships require timber, tools, and coastal or river settlements with a market-level bonus. Seven total produced goods now exist.

**Phase 5 — Stockpiles:** Raw stockpiles are active for grain, copper, iron, and salt. Produced good stockpiles are active for provisions and weapons. Stockpile capacity is tied to `storehouse_level`. Spoilage applies each turn, fill occurs at a 0.38 rate from surplus, and draw activates at 0.65 rate when access falls below demand.

**Phase 6 — Depletion:** All four extractive resources (copper, iron, gold, stone) accumulate `resource_depletion_by_resource` per region based on output intensity and mine level, with maintenance investment through `extractive_level` slowing the rate. Recovery is possible up to 18% of the original endowment.

### What Was Partially Done

**Phase 3 — Gold administrative effects:** The `RESOURCE_GOLD_ADMIN_CAPACITY_FACTOR` constant (0.06) and `RESOURCE_GOLD_TRADE_BONUS_FACTOR` (0.08) are defined. The trade value bonus is implicit in the `taxable_value` calculation. The explicit administrative cost reduction for large polities and the disruption effect when gold sources are cut off are not wired into the simulation.

**Phase 7 — Prices and trade flows:** `resource_prices` fields exist on Region, `_estimate_resource_price()` is defined, price constants are in place (`MARKET_PRICE_SHORTAGE_FACTOR = 0.65`, `MARKET_PRICE_SURPLUS_FACTOR = 0.22`), and `_refresh_faction_market_state()` calculates merchant capacity. None of this is connected to the actual trade routing loop. Inter-faction trade still uses shortage-matching rather than price-gradient matching.

### What Was Not Implemented

The plan listed three behavioral effects that remain absent from the simulation:

- Weapons shortage affecting campaign casualty rate or campaign cost
- Iron goods access giving attack effectiveness bonus
- Depletion-aware expansion targeting (depleted copper regions should score lower)

These are the most important gaps because they are the places where the new economic depth would feed back into core simulation behavior. The economy is richer but not yet fully connected to the outcomes it is supposed to drive.

---

## Purpose of This Plan

The first deepening plan expanded what the economy contains. This plan is about what the economy does.

The core problem is that eleven resources, seven produced goods, stockpiles, and depletion now exist, but much of this depth is not yet visible in military outcomes, faction behavior, or the long-run trajectory of the simulation. A faction with superior iron_goods and a full weapons stockpile should fight and campaign differently from one without. A faction relying on gold access for its administrative coherence should be in a qualitatively different political situation when that gold is cut off. These connections are the point.

This plan is organized around what the economy should drive rather than what it should contain.

---

## Part 1: Closing the Behavioral Gaps

These items are missing connections between the existing economy and existing simulation outcomes. They should be implemented before any new feature additions.

### 1.1 Military Economy Integration

The weapons and iron goods systems need downstream effects in the military simulation.

**Attack effectiveness bonus:**

Factions with high weapons access and adequate iron_goods should receive a small attack effectiveness multiplier. The intent is not dramatic — this is not a morale or leadership bonus, it is material quality. A factor in the range of 0.04 to 0.12 is appropriate, scaling smoothly with weapons access relative to demand rather than as a binary threshold.

The multiplier should apply to the attack roll or to the effective attacker strength calculation, not to campaign cost. Better weapons means more effective combat, not cheaper logistics.

**Weapons shortage and campaign cost:**

When a faction's weapons access falls significantly below weapons demand, campaigns should become more costly. The mechanism should be a campaign maintenance multiplier: shortage increases the treasury drain of active military operations, representing the need to field underequipped forces longer to achieve the same result.

This connects the production chain directly to strategic behavior. Factions that overextend without maintaining weapons production will face escalating campaign costs, which historically is accurate.

**Provisions shortage and campaign range:**

Provisions already contribute to `mobility_capacity` through a logistics factor, but this is not the same as limiting campaign range. A faction with provisions shortage should have a ceiling on how far it can sustain an active campaign from its core. The implementation should add a maximum effective campaign depth that decreases as provisions access falls below demand.

This is the most historically grounded of the three effects. Armies in the ancient and medieval world were limited not by troops but by supply lines. A simulation that models this is telling truer stories.

### 1.2 Depletion-Aware Targeting

Expansion and attack targeting should account for resource depletion.

When a faction scores candidate regions for conquest, extractive regions with high depletion levels should score lower. The adjustment does not need to be large — depletion is slow and even a partially depleted copper region is valuable — but the simulation should not treat a 70% depleted gold mine as equivalent to a fresh one.

The implementation should modify the resource value contribution in expansion and attack scoring by multiplying it against `(1.0 - depletion_level)`. This is a one-line change per scoring function but meaningfully improves strategic coherence.

### 1.3 Gold Administrative Effects

Gold's administrative capacity effect is defined but not active.

When a faction has strong gold access, its integration costs for distant regions should be slightly reduced. The mechanism: add a small integration bonus to distant owned regions when faction gold access exceeds a threshold, representing the ability to pay administrators, garrison soldiers, and tribute recipients in hard currency.

When gold access drops significantly (due to conquest of the gold source, trade blockade, or depletion), the bonus disappears and the previous integration costs return. This creates a meaningful political consequence for gold loss that does not currently exist.

---

## Part 2: Military Supply Chains

The provisions and weapons systems are in place. The next step is making military operations consume them.

### 2.1 Campaign Supply Draw

Active military campaigns should draw from provisions stockpiles each turn.

Supply draw mechanics:

- Each active campaign consumes provisions at a base rate scaled by campaign size (number of regions attacked or defended)
- Draw comes first from provisions stockpiles; if stockpiles are empty, provisions access is consumed directly
- When provisions access falls to zero and stockpiles are empty, a supply crisis condition activates
- Supply crisis increases campaign cost, increases casualty rate slightly, and eventually forces campaign suspension if it persists

This does not need to be complex. Supply draw as a flat amount per active campaign turn, checked against stockpile and current provisions access, is sufficient for V2.

### 2.2 Siege and Supply

Sieges are a specific military operation with a distinct supply dynamic. A besieging faction draws provisions continuously while the besieged faction draws from its internal stockpiles.

The besieged faction's provisions stockpile should determine how long it can hold out against a siege before a surrender or sortie condition is reached. This creates a direct connection between the economic investment in provisions storage and military defensive outcomes.

The besieging faction's provisions access determines how long it can sustain the siege. A faction with deep provisions stockpiles can outlast a siege that a provisions-poor faction cannot.

This models the historical reality that sieges were won and lost on logistics more often than on assault.

### 2.3 Logistics and Campaign Range

Codify the campaign range limit from provisions shortage as a formal mechanic rather than an implicit effect.

Each faction should have a logistics radius: the maximum campaign depth from its nearest supply-capable core region. Logistics radius is derived from:

- provisions access relative to demand
- ships production (for sea transport, extending coastal campaign range)
- roads infrastructure (reducing campaign cost along connected routes)

A faction with high provisions access, a fleet, and developed roads should be able to project power further than one without. This is not a gamey resource — it is a direct representation of historical capability differences between organized imperial logistics and frontier raiding.

---

## Part 3: Faction Economic Identity

The simulation now has enough economic variety that factions can have genuinely distinct economic characters. The missing piece is making those differences legible and behaviorally meaningful.

### 3.1 Economic Identity Classification

Add a faction-level economic identity tag derived from the dominant pattern in resource access and produced goods.

Identity types:

- **Agricultural** — high grain, livestock, provisions; large food surplus; slow expansion but high resilience
- **Pastoral** — high horses, livestock; strong mobility capacity; mobile expansion, weaker on fixed infrastructure
- **Commercial** — high textiles, crafted goods, trade throughput; high taxable value; prefers diplomatic expansion and trade leverage
- **Industrial** — high copper and iron, tools, weapons; strong metal capacity; prefers conquest of resource-rich terrain
- **Maritime** — high ships, coastal trade flow, timber; extended campaign range by sea; depends on trade access for non-coastal goods
- **Imperial** — no single dominant resource; balanced access with strong integration and gold; derives power from administrative depth rather than resource specialization

Identity is not binary. A faction can lean toward two types. The identity should be recalculated each turn from the composition of access and production output.

### 3.2 Identity-Driven AI Priorities

Faction AI should read its economic identity and adjust strategic priorities accordingly.

Current AI behavior reasons from resource shortages. Identity-driven behavior reasons from economic strengths as well as weaknesses.

An Agricultural faction should:
- prioritize expansion into fertile riverland and plains
- invest more heavily in food security before military expansion
- treat disruption of its grain base as an existential threat

A Maritime faction should:
- prioritize coastal regions and sea route control
- invest in ships and coastal trade infrastructure
- treat naval blockade as the primary military threat

An Industrial faction should:
- pursue copper and iron aggressively even at high campaign cost
- accept poor-terrain conquests that Agricultural factions would not
- prioritize tools and weapons production over food surplus

This does not require complex AI changes. It requires the existing action-scoring system to read faction identity and apply biases to terrain type, resource type, and investment type preferences.

### 3.3 Economic Identity Reporting

Economic identity should be visible in faction reports and event analysis.

The event log should be able to describe faction behavior in economic terms: "Marosh, an Industrial faction, launched an attack on copper-rich highland territory despite poor grain access." This makes simulation output more readable as historical narrative.

---

## Part 4: Economic Shocks and Resilience

The shock system (`src/shocks.py`) exists and affects resource output. The deeper question is what the economy does when shocked — both how it fails and how it recovers.

### 4.1 Production Chain Cascades

When a key input is disrupted, downstream production chains should fail in order.

Current behavior: shocks reduce raw resource output. They do not propagate through the production chain.

Desired behavior: a salt shortage that reduces provisions output should subsequently increase food spoilage (salt's preservation function), which reduces food security, which increases unrest, which reduces grain output in the following turn. This cascade is historically accurate — supply chain failures compound — and makes the shock system dramatically more impactful without requiring any new event types.

Implementation: after computing produced goods output, check each produced good for shortage against its own demand signal. If shortage is significant, apply a secondary modifier to the downstream capacity it feeds. This is an additive modifier to the existing shortage feedback loop, not a new system.

### 4.2 Recovery Time

Currently the economy responds to shocks immediately in the same turn they are resolved. Recovery should take time.

Add a `resource_recovery_rate` per resource per region, representing how quickly established production returns to pre-shock levels after the disrupting condition ends. Domesticable resources (grain, horses) should recover slowly, reflecting the time needed to replant, restock, and rebuild. Wild resources should recover faster. Extractive resources should recover at a rate determined by investment since the shock.

This creates a more realistic post-conflict economic picture. A faction that wins a war but loses four grain regions to devastation during the campaign should face a multi-turn recovery period, not an immediate return to normal.

### 4.3 Drought and Famine Dynamics

Food shocks currently reduce grain output uniformly. A more realistic model:

- Drought affects grain and livestock simultaneously, compounding the food security impact
- Flood may reduce grain but increase wild_food in riverland and marsh regions, creating uneven regional effects
- Famine (sustained food deficit) should progressively reduce population, which reduces labor for all production, extending the crisis beyond the immediate food shortage

Famine as a cascading condition: food_deficit crosses a threshold, population begins declining, grain output declines further (fewer workers), which deepens the deficit. Recovery requires either external food access (trade) or restoring grain production faster than population can decline.

This is historically the most common path to civilizational collapse in agricultural societies. The simulation should be able to tell that story.

---

## Part 5: Long-Run Economic Dynamics

The simulation currently runs on a turn-by-turn basis without strong long-run economic feedback. Adding a few mechanisms that operate on longer timescales would make the simulation more historically textured.

### 5.1 Economic Development as a Path

Currently, development investments (irrigation_level, copper_mine_level, etc.) affect output directly. They do not interact with each other in ways that create development paths.

A few simple interactions would add depth:

- High `agriculture_level` should increase the benefit of `irrigation_level` (they reinforce each other; a sophisticated agricultural administration can operate more complex irrigation)
- High `extractive_level` should slow depletion (more skilled extraction leaves less waste and reaches deeper deposits)
- High `infrastructure_level` should reduce the cost of all other investments in the region (better administration makes all improvement projects more efficient)

These are multiplicative adjustments to existing factors, not new systems. They reward sustained investment in a region and penalize development-by-conquest (taking a well-developed region and immediately extracting without maintaining it).

### 5.2 Urbanization Feedback

Urban surplus and crafted goods production currently depend on urban population as a cap. The other direction of causality — economic activity driving urbanization — is not modeled.

Add a slow urbanization feedback: high crafted_goods output and high taxable_value in a region weakly accelerate its settlement advancement over time. Conversely, trade_value_denied (due to blockade or warfare pressure) weakly retards settlement growth.

This creates a long-run dynamic where commercial regions become more commercially capable over time, and economically disrupted regions stagnate. The effect should be slow enough that it is a decades-long phenomenon in simulation time rather than a year-by-year fluctuation.

### 5.3 Population-Economy Coupling

Food security already affects population growth weakly. This coupling should be more explicit and more consequential in both directions.

Additions:

- Sustained food security above demand should accelerate population growth more aggressively than currently
- Sustained food deficit should reduce population, with the reduction rate scaling with deficit severity
- Population loss should reduce workforce across all resource categories, creating a compounding effect

The goal is for the simulation to be able to represent the historical pattern of demographic boom and bust that accompanies agricultural expansion, conquest, famine, and plague. A faction that conquers a large fertile plain and develops it heavily should eventually have a much larger population than it started with. A faction that wars continuously without maintaining food production should face demographic pressure.

---

## Part 6: Completing Phase 7 (Prices)

The price infrastructure is in place. This section describes what is needed to activate it.

### 6.1 Price Calculation in the Economy Loop

`_estimate_resource_price()` should be called during the main economy update for all regions with a market above the minimum threshold (`market_level >= 0.5`).

Price calculation:

- Base price starts at 1.0
- Adjusts upward by `MARKET_PRICE_SHORTAGE_FACTOR` times the severity of local shortage
- Adjusts downward by `MARKET_PRICE_SURPLUS_FACTOR` times the magnitude of local surplus
- Blends toward the faction average price at `MARKET_PRICE_BLEND` weight, preventing extreme local volatility
- Trade disruption adds upward pressure by `MARKET_PRICE_TRADE_DISRUPTION_FACTOR` times disruption level

Prices update every turn but move slowly (the blend factor prevents single-turn spikes).

### 6.2 Price-Gradient Trade Routing

Replace the current shortage-matching logic in inter-faction trade with price-gradient matching.

Current system: match resource shortages between factions through diplomatic gateways.
New system: match price differentials between factions through diplomatic gateways, weighted by merchant capacity.

The practical difference: currently a faction with no shortage will not import a resource even if it would benefit from it. Under price-gradient matching, a faction with low prices can export to a faction with high prices even if the exporter has no formal shortage. This is the historically accurate driver of inter-regional trade.

The merchant capacity field already calculated by `_refresh_faction_market_state()` becomes the volume constraint on how much price-gradient trade a faction can conduct per turn. Commercial factions with high merchant capacity can exploit price differentials that subsistence-agrarian factions cannot.

### 6.3 Price Spikes as Events

When a resource price in a market region exceeds a threshold (1.8× baseline) or drops below a floor (0.4× baseline), generate a narrative event.

Events should be interpretable: "Grain prices in the Lizeem delta spiked following the Ambronite blockade of the Ros estuary." This gives the simulation output more legible economic narrative.

Price spikes should also function as signals in the AI targeting system: factions with high merchant capacity should be attracted to trade with regions experiencing price spikes.

---

## Build Sequence

The phases above should be implemented in the following order.

### Step 1: Close the Behavioral Gaps (Part 1)

Highest priority. These are one- to five-line additions that make existing systems meaningful.

- Attack effectiveness multiplier from weapons and iron_goods access
- Campaign cost scaling from weapons shortage
- Provisions shortage → campaign range ceiling
- Depletion adjustment in expansion and attack scoring
- Gold administrative integration bonus

### Step 2: Military Supply Chains (Part 2)

Medium complexity. Requires extending the campaign system to draw provisions and check supply state per turn.

- Campaign supply draw from provisions stockpiles
- Siege duration based on besieged faction's provisions stockpile
- Logistics radius calculation

### Step 3: Economic Identity (Part 3)

Low implementation cost, high interpretive value.

- Identity classification function from resource access composition
- AI priority biases from identity
- Identity tag in faction reports

### Step 4: Production Chain Cascades (Part 4.1)

Medium complexity within the existing shock framework.

- Propagate produced good shortages into downstream capacity modifiers
- Add `resource_recovery_rate` per resource per region

### Step 5: Activate Phase 7 Prices (Part 6)

Medium complexity. Infrastructure is ready; needs wiring into the economy loop and trade routing.

- Call price calculation in economy update for market regions
- Replace shortage matching with price-gradient matching in inter-faction trade
- Add price spike events

### Step 6: Long-Run Dynamics (Part 5)

Low urgency, high historical authenticity. Can be done after Steps 1–5 are stable.

- Development interaction bonuses
- Urbanization feedback from commercial activity
- Tighter population-food security coupling (both directions)

### Step 7: Famine and Cascade Dynamics (Part 4.2–4.3)

Final pass on the shock system. Most impactful for long simulation runs.

- Drought compounding grain and livestock together
- Famine as a compounding population-food feedback loop

---

## Out Of Scope For This Plan

The following remain deferred:

- Individual merchant agents with capital, routes, and preferences (this is a V3 architectural change)
- Coinage and monetary systems (requires price system to be stable first)
- Trade treaty mechanics as distinct diplomatic contract types (belongs in the diplomacy system)
- Population specialization (craftsmen, merchants, miners as distinct population categories) — requires population model changes beyond the economy
- Ecological regeneration of wild resources — changes the wild resource category significantly
- Diplomatic economic sanctions as a formal action type — implied by the price and trade systems but not yet scoped

---

## Success Criteria

This plan is successful if:

- A faction's weapons and iron_goods access visibly affects its military campaign outcomes
- Provisions shortage limits how far and how long campaigns can be sustained
- Gold loss creates an observable administrative disruption, not just a taxable_value drop
- The production chain cascades — salt disruption reduces provisions, which limits campaigns, which reduces territory under stable production
- Faction economic identity is readable from reports and explains strategic behavior without requiring the player to audit resource tables
- Price differentials drive trade in a way that looks like historical trade rather than a shortage-clearinghouse
- The simulation can plausibly represent famine: food deficit → population decline → labor decline → deeper deficit → crisis
- A long-running simulation shows meaningful economic differentiation between factions based on their geography, development choices, and political stability
