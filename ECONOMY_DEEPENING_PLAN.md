# Economy Deepening Plan

## Purpose

This document defines the next expansion of the Clashvergence economy beyond the V1 foundation.

V1 through V1.7 are complete. The specific-resource foundation is stable: nine resources, two produced goods, internal route distribution with bottleneck analysis, and inter-faction trade through diplomatic gateway matching. The legacy `region.resources` field has been subordinated to real resource output as the primary driver of simulation decisions.

This plan defines what comes next, organized into coherent phases rather than a single large expansion. Each phase should be completable independently and should deepen specific simulation behavior without requiring all subsequent phases to be in place.

The design philosophy does not change: simulation-first, not game-balance-first. The goal is more intelligible historical behavior, not optimal play or economic modeling accuracy.

---

## Current Foundation Summary

What V1 now includes, as the starting point for this plan:

- Nine resources across three categories: domesticable (grain, livestock, horses, textiles), wild (wild_food, timber), extractive (copper, stone, salt)
- Two produced goods: tools (from copper + materials) and urban_surplus (from food)
- Five derived capacities: food_security, mobility_capacity, metal_capacity, construction_capacity, taxable_value
- Internal route distribution with corridor bottlenecks
- Inter-faction trade through diplomatic gateway matching with blockade and disruption mechanics
- Resource growth and decay for domesticables
- Climate and terrain seeding for all nine resources

What remains intentionally deferred:

- Deeper production chains beyond tools and urban_surplus
- Market prices and supply-demand clearing
- Stockpiles and long-term inventory
- Resource depletion
- More metals: iron, gold
- Merchant actors and trade networks

---

## Phase 2: Completing the Existing Resource Set

The nine resources are seeded and tracked, but livestock, textiles, and salt are thinner than grain, copper, and timber in terms of what they actually do in the simulation.

### Goals

- Give livestock a proper production chain separate from grain
- Give salt a demand-side role that makes coastal and highland salt sources strategically meaningful
- Give textiles a role in faction economic sophistication beyond a component in suitability seeding

### Livestock

Livestock is currently defined as domesticable and contributes to food_security through a 0.9 multiplier, but it does not have its own production calculation path. It is partially collapsed into the grain logic.

Add a distinct livestock production calculation:

- separate output formula from grain
- contribution to food_security should remain, but also add a contribution to mobility_capacity (draft animals) at a reduced ratio compared to horses
- livestock should interact with pasture_level and pastoral_level as grain interacts with irrigation_level and agriculture_level
- introduce_livestock project alongside introduce_grain and introduce_horses
- livestock establishment decay should be faster than grain under neglect and slower than horses under crisis, reflecting the difference between field crops and animal herds

Livestock suitability is already seeded by terrain. The main work is completing the production calculation and giving factions reasons to develop it separately from grain.

### Salt

Salt currently exists as an extractive resource and contributes weakly to food_security (0.1 multiplier). It is the most historically important trade good of the ancient and medieval world but has almost no distinctive simulation behavior.

Deepening salt:

- add a salt demand derived from population and food_security level: polities that produce and store food at scale need salt for preservation, and this should translate into a shortage signal
- salt shortage should weakly increase food spoilage rate, representing reduced preservation capacity
- salt surplus should weakly reduce food spoilage, especially for factions with high food_storage_capacity
- salt should have a stronger export weight than its current resource value weight suggests, making salt-producing coast and highland regions more attractive for trade access
- gateway regions near salt sources should score higher in inter-faction trade routing calculations

These changes do not require a price system. Supply and demand can be approximated through shortage signals and output adjustments within the existing framework.

### Textiles

Textiles are currently seeded by terrain and climate and contribute to taxable_value, but they have no distinct demand signal and no meaningful feedback into other simulation systems.

Deepening textiles:

- add textiles as an input into urban_surplus calculation alongside food, representing the non-food component of city life and commerce
- textiles shortage should reduce urban_surplus output, making textile-producing regions more important to highly urbanized factions
- high textile access should weakly increase taxable_value beyond its current direct contribution, representing commercial sophistication
- textiles should be a preferred export in inter-faction trade for factions with surplus, creating a reason to develop textile production in suitable regions

---

## Phase 3: Iron and Gold

The V1 design committed to copper as the first metal. Iron and gold are the natural next additions. They are different from each other in almost every meaningful way, which makes them worth adding together as a design unit.

### Iron

Iron is the historically significant successor to copper and bronze, but it should not arrive as a simple upgrade. Iron ore is more common than copper but requires more processing infrastructure to use. The simulation should reflect this.

Iron as a resource:

- extractive, like copper, with fixed deposits in hills and highland terrain
- seeded at lower per-region concentrations than copper but in a broader terrain range
- adds to metal_capacity when extracted, but at a lower per-unit rate than copper until smelting infrastructure is in place

Iron as a production chain input:

- raw iron ore has low direct value; the value emerges from processing
- add a produced good: iron_goods (or metalwork), which requires iron + fuel (represented by timber) + adequate extractive infrastructure
- iron_goods contributes to metal_capacity at a higher rate than raw iron alone
- factions with copper but no iron can still produce tools; factions with iron but no processing are leaving most of the value trapped
- this creates a two-step extraction-and-processing pattern that mirrors the copper → tools chain but with a harder fuel dependency

Iron demand:

- iron_goods shortages should increase military campaign cost (representing equipment quality)
- factions with high iron_goods access should get a small attack effectiveness bonus, representing better-equipped forces
- construction projects should prefer iron_goods over raw stone + timber when available, representing more durable infrastructure

Iron introduction timing:

- iron should not be available at game start; it should unlock through a technology or development threshold
- the simplest approach: iron extraction requires copper_mine_level to be above a threshold in at least one faction-held region, representing the metallurgical knowledge base that historically preceded iron use
- this ties iron availability to faction development rather than just terrain, which is more historically accurate

### Gold

Gold is not a production metal. It is a strategic resource with a different function: it amplifies trade value and later, if a currency system is added, it becomes the basis for monetary expansion.

Gold as a resource:

- extractive, found in hills and riverland terrain (alluvial gold in river valleys, vein gold in hills)
- rare and concentrated; most maps should have only a few meaningful gold deposits
- does not contribute to any capacity directly; its value is through taxable_value at a high per-unit rate

Gold and trade:

- factions with gold access should have higher gateway attractiveness for inter-faction trade, representing the historical role of gold-producing regions as trade hubs
- gold surplus should increase trade_value_bonus for the owning faction
- gold shortage in a faction that previously had gold access should reduce its trade attractiveness, representing the historical disruption of trade networks when gold sources were cut off

Gold and political capacity:

- gold access should weakly increase a faction's administrative capacity or reduce the cost of keeping distant regions integrated
- this represents the historical use of precious metal as a means of paying administrators, soldiers, and tribute recipients
- the effect should be modest: gold should not substitute for territory or population, but it should make large polities slightly more manageable

---

## Phase 4: Deeper Production Chains

The current production chain has two tiers: raw resources and produced goods (tools, urban_surplus). Deepening the chain means adding goods that either require produced goods as inputs, or that open new economic roles.

This phase should not become a full industrial model. Three or four additional produced goods is the right scope.

### Weapons

The most direct extension of metal production into military outcomes.

Weapons as a produced good:

- input: copper or iron_goods + timber (hafting, handles) + tools
- output: weapons stock that affects military effectiveness
- weapons production should be limited by metal_capacity, not just metal access — this distinguishes raw material access from actual productive industrial capacity
- weapons shortage should increase campaign casualties or reduce attack effectiveness
- weapons surplus should be available for export and should be a valued trade good for non-producing factions

Weapons demand:

- weapons demand should scale with faction military posture and active conflicts
- a faction at peace with stable borders should have lower weapons demand than one conducting aggressive expansion
- this creates a self-regulating effect: overextended factions face rising weapons demand and potential shortage

### Preserved Food (or Provisions)

A produced good representing the processed, transportable form of food: dried grain, salt fish, cured meat.

Preserved food:

- input: grain or wild_food + salt + storehouse_level
- output: provisions that contribute to military campaign supply and reduce food spoilage
- provisions shortage should limit campaign range or increase campaign cost, representing historical supply chain constraints on military projection
- provisions surplus should increase campaign range, representing the ability to campaign far from the homeland
- provisions production should require storehouse infrastructure, giving storehouses a clearer simulation function than their current role

This links the salt deepening in Phase 2 directly into military behavior, which is historically accurate (armies marched on salt-preserved food) and mechanically clean.

### Crafted Goods

A broad category representing pottery, glass, fine cloth, and other skilled manufactures.

Crafted goods:

- input: stone or textiles + tools + urban population factor (craftsmen require urban concentration)
- output: a trade-value good with no direct military application but high export demand
- crafted goods should contribute heavily to urban_surplus when produced locally
- crafted goods surplus should increase a faction's taxable_value significantly, representing the premium that skilled manufactures command
- crafted goods production should be limited by city and town population, making urbanization directly relevant to economic sophistication

Crafted goods and trade:

- crafted goods should be among the highest-value trade exports a faction can offer
- this gives highly urbanized, textile-producing factions a distinct economic identity from agricultural or pastoral ones
- factions with only basic resources and no urban production will have lower trade leverage

### Ships (optional, coastal-only)

If the simulation has meaningful coastal and maritime regions, ships as a produced good creates a feedback loop from timber and coastal geography into naval and trade capacity.

Ships:

- input: timber + tools + coastal region with settlement
- output: maritime capacity that reduces sea route cost and increases trade gateway quality for sea-connected regions
- ships production should require a coastal or river settlement above a minimum level
- ships shortage should reduce sea route efficiency, representing degraded naval infrastructure

This is the most optional item in Phase 4. Include it only if maritime geography plays a significant enough role in the simulation to justify the additional complexity.

---

## Phase 5: Stockpiles and Strategic Reserves

V1 implemented food storage with spoilage and overflow mechanics. The next step is extending stockpile logic to strategic resources.

### What Stockpiles Add

Stockpiles give factions the ability to buffer against resource shocks. Without stockpiles, any disruption to supply immediately affects derived capacities and military effectiveness. With stockpiles, factions can absorb a bad year or a blocked trade route without immediate crisis — but they pay for this in storage costs and the risk of spoilage.

Stockpiles are historically significant. Empires with deep granaries and copper reserves outlasted factions that consumed everything as produced.

### Resource Stockpile Mechanics

Add a stockpile for each strategic resource: copper, iron (when available), salt, and grain (already partially implemented through food_stored).

Per-faction stockpile state:

- stockpile_capacity: maximum reserve, scaled by storehouse_level across owned regions
- stockpile_level: current reserve
- stockpile_draw: amount drawn from reserve per turn when access falls short of demand
- stockpile_spoilage: per-turn loss based on storage quality

Stockpile filling logic:

- surplus production above demand flows into the stockpile up to capacity
- stockpile_draw activates when current access falls below a threshold (shortage condition)
- if the stockpile is drawn to zero and shortage persists, the shortage propagates normally into derived capacities and behavior

Stockpile investment:

- storehouse_level already exists; its primary effect should shift to stockpile_capacity
- a faction that invests in storehouses should be able to hold reserves for longer campaigns and longer disruption periods
- this makes storehouse investment more meaningful than its current role in urban_surplus calculation

### Faction-Level Behavior

Factions with deep stockpiles should be harder to defeat through isolation or blockade alone. They should be able to wait out a blockade that a stockpile-poor faction cannot survive.

This is already partially implied by the food storage system. Extending it to copper and provisions creates a richer strategic picture: a blockaded faction faces not one countdown but several, based on which stockpiles run out first.

---

## Phase 6: Resource Depletion

Fixed extractive resources — copper, stone, and eventually iron and gold — should degrade over time under intensive extraction.

### Why Depletion Matters

Depletion adds long-run historical pressure to civilizations built on mineral wealth. The Bronze Age Collapse is partly a story of copper supply disruption. The exhaustion of Athenian silver mines changed Greek history. The Roman Empire's silver depletion contributed to its economic crises.

Depletion does not make the game unwinnable; it makes geography change its significance over time, which is historically authentic.

### Depletion Mechanics

For each extractive resource, track depletion_level per region.

depletion_level starts at 0.0 and increases as extraction occurs:

- depletion accumulates faster with high copper_mine_level and high extraction output
- depletion accumulates slower with moderate extraction and investment in mine maintenance
- depletion reduces the effective endowment multiplicatively: effective_endowment = fixed_endowment × (1.0 - depletion_level)
- depletion is slow; a heavily mined region should take many turns to reach significant degradation

Depletion is not reversible. Some recovery is possible through investment (representing deeper shaft mining, improved techniques) but the ceiling on recovery should be below the original endowment.

Depletion visibility:

- depletion_level should be visible in region reports
- regions near high depletion should score lower in expansion targeting, representing the reduced long-run value of the deposit
- factions holding a depleting copper region should receive early warning through output decline before the region becomes unproductive

Depletion and trade:

- as local copper deposits deplete, factions face stronger incentive to import copper through trade
- this is historically accurate (late Bronze Age trade in copper) and creates economic interdependence between producing and consuming factions
- the inter-faction trade system already supports this; depletion simply generates the demand signal

---

## Phase 7: Market Prices and Trade Flows

This is the most complex phase and should not be attempted until Phases 2 through 5 are stable.

### What a Price System Adds

Prices allow the simulation to capture the historical reality that the same resource is worth more where it is scarce than where it is plentiful. Without prices, a grain surplus in a fertile faction and a grain famine in a dry faction exist independently; with prices, trade naturally flows toward the price gradient.

The goal is not a general equilibrium model. The goal is price signals that make trade behavior more intelligible and that give factions reasons to protect and develop specific trade relationships.

### Simplified Price Model

Track a regional price for each resource at major markets (towns and cities with market_level above a threshold).

Price formation:

- base price derived from regional output vs. local demand ratio
- price increases as local access falls below demand
- price decreases as surplus grows
- prices revert toward a baseline (representing long-run supply response) with a slow time constant

Price gradients and trade:

- inter-faction trade should route goods toward higher-price destinations, replacing the current shortage-matching logic with a price-differential matching logic
- merchants (simplified, not actor-level) follow price gradients
- the existing gateway and diplomacy framework constrains trade routes; prices determine which goods flow through those routes

Price visibility:

- market prices should be visible in region reports for market-level regions
- faction economic reports should show average price levels for strategic resources
- price spikes should be visible as events when a resource price exceeds a threshold

### Merchant Actors

The simplest implementation does not require individual merchant agents. A faction-level merchant capacity can abstract the behavior:

- merchant_capacity is a derived value from market_level, urban_surplus, and roads across owned regions
- merchant_capacity determines how much trade volume a faction can conduct per turn
- higher merchant_capacity means the faction can exploit more price differentials, not just fill shortages
- factions with low merchant_capacity leave price differentials unexploited, representing underdeveloped commercial infrastructure

Full merchant agents — individual actors with capital, routes, and preferences — are beyond the scope of this plan and should be treated as a V3 feature.

---

## Phase Order and Dependencies

The phases are ordered by dependency, not arbitrary priority.

**Phase 2** (completing the existing resource set) has no dependencies and should come first. Livestock, salt, and textiles are already seeded and tracked; the work is adding demand logic and production completeness.

**Phase 3** (iron and gold) depends on Phase 2 being stable. Iron's fuel dependency on timber works better after timber's role in the production chain is clearer. Gold's trade function works better after trade behavior is more finely tuned.

**Phase 4** (deeper production chains) depends on Phase 3. Weapons require iron_goods or copper. Preserved food requires salt being meaningful. Crafted goods require textiles being meaningful.

**Phase 5** (stockpiles) depends on Phase 4. Provisions as a produced good and weapons as a produced good both interact with stockpile mechanics. The stockpile system is most useful after the production chain is deeper.

**Phase 6** (depletion) depends on Phase 3. Depletion makes most sense for copper, iron, and gold. It can be implemented in parallel with Phase 5, but it is most impactful after iron and gold are in place.

**Phase 7** (prices and trade) depends on all preceding phases. Prices require stable supply and demand signals. Supply signals require the production chain. Demand signals require depletion and stockpile draw to generate real shortage pressure.

---

## Out Of Scope For This Plan

Do not include in this expansion:

- full merchant agent actors with individual capital and route preferences (V3)
- coinage and monetary systems (V3)
- diplomatic trade agreements as distinct treaty types (may belong in diplomacy system)
- population specialization (craftsmen, merchants, miners as distinct population categories) — this requires population model changes that are out of scope here
- ecological regeneration of wild resources (timber regrowth, wild food recovery) — potentially valuable but changes the wild resource category significantly
- afforestation or land improvement mechanics

---

## Success Criteria

This plan is successful if:

- livestock, salt, and textiles each have a distinct simulation role that players can observe in faction behavior
- iron and gold exist as meaningfully different resources from copper, with different terrain distributions and different downstream effects
- the production chain has enough depth that urbanized commercial factions and pastoral military factions feel economically different, not just geographically different
- stockpiles make it possible to survive a short disruption without immediate crisis
- depletion adds long-run pressure to mineral-dependent factions without making the simulation unplayable
- prices create legible trade incentives that explain why goods move between factions, rather than trade being purely a shortage-filling mechanism
