from dataclasses import asdict, dataclass, field
from typing import Any


POLITY_TIERS = ("band", "tribe", "chiefdom", "state")
GOVERNMENT_FORMS_BY_TIER = {
    "band": ("leader", "council"),
    "tribe": ("leader", "council", "assembly"),
    "chiefdom": ("leader", "council", "monarchy"),
    "state": ("council", "assembly", "monarchy", "republic", "oligarchy"),
}
DEFAULT_GOVERNMENT_FORM_BY_TIER = {
    "band": "leader",
    "tribe": "council",
    "chiefdom": "leader",
    "state": "council",
}
GOVERNMENT_TYPE_LABELS = {
    ("band", "leader"): "Band",
    ("band", "council"): "Band",
    ("tribe", "leader"): "Tribe",
    ("tribe", "council"): "Tribe",
    ("tribe", "assembly"): "Tribe",
    ("chiefdom", "leader"): "Chiefdom",
    ("chiefdom", "council"): "Chiefdom",
    ("chiefdom", "monarchy"): "Chiefdom",
    ("state", "council"): "Council Realm",
    ("state", "assembly"): "Commonwealth",
    ("state", "monarchy"): "Kingdom",
    ("state", "republic"): "Republic",
    ("state", "oligarchy"): "Oligarchy",
}
LEGACY_GOVERNMENT_TYPE_TO_STRUCTURE = {
    "Band": ("band", "leader"),
    "Tribe": ("tribe", "council"),
    "Chiefdom": ("chiefdom", "leader"),
    "State": ("state", "council"),
    "Kingdom": ("state", "monarchy"),
    "Republic": ("state", "republic"),
    "Oligarchy": ("state", "oligarchy"),
    "Rebels": ("state", "council"),
}


def normalize_polity_tier(polity_tier: str) -> str:
    normalized = (polity_tier or "tribe").strip().lower()
    if normalized not in POLITY_TIERS:
        raise ValueError(f"Unsupported polity tier: {polity_tier}")
    return normalized


def get_default_government_form(polity_tier: str) -> str:
    normalized_tier = normalize_polity_tier(polity_tier)
    return DEFAULT_GOVERNMENT_FORM_BY_TIER[normalized_tier]


def normalize_government_form(polity_tier: str, government_form: str | None) -> str:
    normalized_tier = normalize_polity_tier(polity_tier)
    normalized_form = (government_form or get_default_government_form(normalized_tier)).strip().lower()
    if normalized_form not in GOVERNMENT_FORMS_BY_TIER[normalized_tier]:
        raise ValueError(
            f"Unsupported government form '{government_form}' for polity tier '{normalized_tier}'."
        )
    return normalized_form


def resolve_government_type(polity_tier: str, government_form: str) -> str:
    normalized_tier = normalize_polity_tier(polity_tier)
    normalized_form = normalize_government_form(normalized_tier, government_form)
    return GOVERNMENT_TYPE_LABELS[(normalized_tier, normalized_form)]


def infer_government_structure(government_type: str | None) -> tuple[str, str] | None:
    if not government_type:
        return None
    return LEGACY_GOVERNMENT_TYPE_TO_STRUCTURE.get(government_type.strip())


@dataclass
class FactionDoctrineState:
    homeland_region: str | None = None
    homeland_terrain_tags: list[str] = field(default_factory=list)
    homeland_climate: str = "temperate"
    terrain_experience: dict[str, float] = field(default_factory=dict)
    climate_experience: dict[str, float] = field(default_factory=dict)
    turns_observed: int = 0
    expansions: int = 0
    attacks: int = 0
    successful_attacks: int = 0
    developments: int = 0
    turns_with_growth: int = 0
    turns_with_conflict: int = 0
    turns_with_development: int = 0
    regions_gained_by_expansion: int = 0
    regions_gained_by_conquest: int = 0
    cumulative_regions_held: int = 0
    peak_regions: int = 0
    starting_regions: int = 0
    last_region_count: int = 0

    @property
    def investments(self) -> int:
        return self.developments

    @investments.setter
    def investments(self, value: int) -> None:
        self.developments = value

    @property
    def turns_with_investment(self) -> int:
        return self.turns_with_development

    @turns_with_investment.setter
    def turns_with_investment(self, value: int) -> None:
        self.turns_with_development = value


@dataclass
class FactionDoctrineProfile:
    homeland_identity: str = "Plains"
    terrain_identity: str = "Plains"
    climate_identity: str = "Temperate"
    preferred_terrains: list[str] = field(default_factory=lambda: ["plains"])
    expansion_posture: float = 0.5
    war_posture: float = 0.5
    development_posture: float = 0.5
    insularity: float = 0.5
    doctrine_label: str = "Adaptive Plains"
    summary: str = ""
    dominant_behavior: str = "adaptive"


@dataclass
class FactionSuccessionState:
    dynasty_name: str = ""
    ruler_name: str = ""
    ruler_age: int = 30
    ruler_reign_turns: int = 0
    heir_name: str = ""
    heir_age: int = 16
    heir_preparedness: float = 0.55
    legitimacy: float = 0.62
    dynasty_prestige: float = 0.45
    regency_turns: int = 0
    succession_crisis_turns: int = 0
    claimant_pressure: float = 0.0
    last_succession_turn: int | None = None
    last_succession_type: str = "founding"


@dataclass
class FactionReligionState:
    official_religion: str = ""
    religious_legitimacy: float = 0.5
    clergy_support: float = 0.5
    religious_tolerance: float = 0.45
    religious_zeal: float = 0.5
    state_cult_strength: float = 0.45
    reform_pressure: float = 0.0
    sacred_sites_controlled: int = 0
    total_sacred_sites: int = 0
    last_reform_turn: int | None = None


@dataclass
class FactionIdeologyState:
    dominant_ideology: str = "customary_pluralism"
    dominant_label: str = "Customary Pluralism"
    currents: dict[str, float] = field(default_factory=dict)
    cohesion: float = 0.5
    radicalism: float = 0.0
    institutionalism: float = 0.0
    reform_pressure: float = 0.0
    legitimacy_model: str = "customary"
    last_shift_turn: int | None = None


@dataclass
class EliteBloc:
    bloc_type: str
    name: str
    influence: float = 0.4
    loyalty: float = 0.5
    wealth: float = 0.3
    militarization: float = 0.0
    reform_pressure: float = 0.0
    base_region: str | None = None
    agenda: str = ""


@dataclass
class LanguageProfile:
    family_name: str = ""
    onsets: list[str] = field(default_factory=list)
    middles: list[str] = field(default_factory=list)
    suffixes: list[str] = field(default_factory=list)
    seed_fragments: list[str] = field(default_factory=list)
    lexical_roots: dict[str, list[str]] = field(default_factory=dict)
    style_notes: list[str] = field(default_factory=list)


@dataclass
class Ethnicity:
    name: str
    language_family: str = ""
    parent_ethnicity: str | None = None
    origin_faction: str | None = None
    language_profile: LanguageProfile = field(default_factory=LanguageProfile)


@dataclass
class Religion:
    name: str
    founding_faction: str | None = None
    parent_religion: str | None = None
    doctrine: str = ""
    sacred_terrain_tags: list[str] = field(default_factory=list)
    sacred_climate: str = "temperate"
    reform_origin_turn: int | None = None


@dataclass
class Region:
    name: str
    neighbors: list[str]
    owner: str | None
    resources: int
    resource_fixed_endowments: dict[str, float] = field(default_factory=dict)
    resource_wild_endowments: dict[str, float] = field(default_factory=dict)
    resource_suitability: dict[str, float] = field(default_factory=dict)
    resource_established: dict[str, float] = field(default_factory=dict)
    resource_output: dict[str, float] = field(default_factory=dict)
    resource_retained_output: dict[str, float] = field(default_factory=dict)
    resource_routed_output: dict[str, float] = field(default_factory=dict)
    resource_effective_output: dict[str, float] = field(default_factory=dict)
    resource_damage: dict[str, float] = field(default_factory=dict)
    resource_monetized_value: float = 0.0
    resource_isolation_factor: float = 0.0
    resource_route_depth: int | None = None
    resource_route_cost: float = 0.0
    resource_route_anchor: str | None = None
    resource_route_bottleneck: float = 1.0
    resource_route_mode: str = "land"
    trade_route_role: str = "local"
    trade_route_parent: str | None = None
    trade_route_children: int = 0
    trade_served_regions: int = 0
    trade_throughput: float = 0.0
    trade_transit_flow: float = 0.0
    trade_import_value: float = 0.0
    trade_transit_value: float = 0.0
    trade_hub_value: float = 0.0
    trade_value_bonus: float = 0.0
    trade_import_reliance: float = 0.0
    trade_disruption_risk: float = 0.0
    trade_warfare_pressure: float = 0.0
    trade_warfare_turns: int = 0
    trade_blockade_strength: float = 0.0
    trade_blockade_turns: int = 0
    trade_value_denied: float = 0.0
    trade_foreign_partner: str | None = None
    trade_foreign_partner_region: str | None = None
    trade_foreign_flow: float = 0.0
    trade_foreign_value: float = 0.0
    trade_gateway_role: str = "none"
    last_resource_project_turn: int | None = None
    infrastructure_level: float = 0.0
    fortification_level: float = 0.0
    garrison_strength: float = 0.0
    logistics_node_level: float = 0.0
    naval_base_level: float = 0.0
    military_damage: float = 0.0
    last_military_project_turn: int | None = None
    granary_level: float = 0.0
    storehouse_level: float = 0.0
    market_level: float = 0.0
    irrigation_level: float = 0.0
    pasture_level: float = 0.0
    logging_camp_level: float = 0.0
    road_level: float = 0.0
    copper_mine_level: float = 0.0
    stone_quarry_level: float = 0.0
    agriculture_level: float = 0.0
    pastoral_level: float = 0.0
    extractive_level: float = 0.0
    food_stored: float = 0.0
    food_storage_capacity: float = 0.0
    food_produced: float = 0.0
    food_consumption: float = 0.0
    food_balance: float = 0.0
    food_deficit: float = 0.0
    food_spoilage: float = 0.0
    food_overflow: float = 0.0
    soil_health: float = 1.0
    ecological_integrity: float = 1.0
    disease_burden: float = 0.0
    climate_anomaly: float = 0.0
    resource_depletion: float = 0.0
    food_stress_turns: int = 0
    trade_stress_turns: int = 0
    active_shock_kinds: list[str] = field(default_factory=list)
    shock_exposure: float = 0.0
    shock_resilience: float = 0.0
    migration_inflow: int = 0
    migration_outflow: int = 0
    refugee_inflow: int = 0
    refugee_outflow: int = 0
    frontier_settler_inflow: int = 0
    migration_pressure: float = 0.0
    migration_attraction: float = 0.0
    administrative_burden: float = 0.0
    administrative_support: float = 0.0
    administrative_distance: float = 0.0
    administrative_autonomy: float = 0.0
    administrative_tax_capture: float = 1.0
    population: int = 0
    ethnic_composition: dict[str, int] = field(default_factory=dict)
    religious_composition: dict[str, int] = field(default_factory=dict)
    sacred_religion: str | None = None
    shrine_level: float = 0.0
    pilgrimage_value: float = 0.0
    religious_unrest: float = 0.0
    technology_presence: dict[str, float] = field(default_factory=dict)
    technology_adoption: dict[str, float] = field(default_factory=dict)
    technology_pressure: dict[str, float] = field(default_factory=dict)
    urban_specialization: str = "none"
    urban_specialization_score: float = 0.0
    urban_network_value: float = 0.0
    display_name: str = ""
    founding_name: str = ""
    original_namer_faction_id: str | None = None
    terrain_tags: list[str] = field(default_factory=list)
    climate: str = "temperate"
    name_metadata: dict[str, Any] = field(default_factory=dict)
    homeland_faction_id: str | None = None
    integrated_owner: str | None = None
    integration_score: float = 0.0
    core_status: str = "frontier"
    settlement_level: str = "wild"
    unrest: float = 0.0
    unrest_event_level: str = "none"
    unrest_event_turns_remaining: int = 0
    unrest_crisis_streak: int = 0
    secession_cooldown_turns: int = 0
    ownership_turns: int = 0
    conquest_count: int = 0

    @property
    def ui_name(self) -> str:
        return self.display_name or self.name

@dataclass
class FactionIdentity:
    internal_id: str
    culture_name: str
    government_type: str = ""
    polity_tier: str = "tribe"
    government_form: str = "council"
    display_name: str = ""
    language_profile: LanguageProfile = field(default_factory=LanguageProfile)
    source_traditions: list[str] = field(default_factory=list)
    generation_method: str = "curated_source_fusion"
    ai_generated: bool = False
    inspirations: list[str] = field(default_factory=list)
    candidate_pool: list[str] = field(default_factory=list)

    def __post_init__(self):
        inferred_structure = infer_government_structure(self.government_type)
        if inferred_structure is not None and (
            self.polity_tier == "tribe"
            and self.government_form == "council"
        ):
            self.polity_tier, self.government_form = inferred_structure

        self.polity_tier = normalize_polity_tier(self.polity_tier)
        self.government_form = normalize_government_form(
            self.polity_tier,
            self.government_form,
        )
        if self.government_type == "State":
            self.government_type = resolve_government_type(
                self.polity_tier,
                self.government_form,
            )
            if self.display_name == f"{self.culture_name} State":
                self.display_name = ""
        if not self.government_type:
            self.government_type = resolve_government_type(
                self.polity_tier,
                self.government_form,
            )
        if not self.display_name:
            self.display_name = self.default_display_name()

    def default_display_name(self) -> str:
        return f"{self.culture_name} {self.get_resolved_government_type()}"

    def get_resolved_government_type(self) -> str:
        return self.government_type or resolve_government_type(
            self.polity_tier,
            self.government_form,
        )

    def set_government_structure(
        self,
        polity_tier: str,
        government_form: str | None = None,
        *,
        government_type: str | None = None,
        update_display_name: bool = False,
    ) -> None:
        self.polity_tier = normalize_polity_tier(polity_tier)
        self.government_form = normalize_government_form(
            self.polity_tier,
            government_form,
        )
        self.government_type = government_type or resolve_government_type(
            self.polity_tier,
            self.government_form,
        )
        if update_display_name:
            self.display_name = self.default_display_name()


@dataclass
class Faction:
    name: str
    treasury: int = 0
    identity: FactionIdentity | None = None
    starting_treasury: int = 0
    doctrine_state: FactionDoctrineState = field(default_factory=FactionDoctrineState)
    doctrine_profile: FactionDoctrineProfile = field(default_factory=FactionDoctrineProfile)
    succession: FactionSuccessionState = field(default_factory=FactionSuccessionState)
    religion: FactionReligionState = field(default_factory=FactionReligionState)
    ideology: FactionIdeologyState = field(default_factory=FactionIdeologyState)
    primary_ethnicity: str | None = None
    is_rebel: bool = False
    origin_faction: str | None = None
    rebel_conflict_type: str = ""
    rebel_age: int = 0
    independence_score: float = 0.0
    proto_state: bool = False
    resource_gross_output: dict[str, float] = field(default_factory=dict)
    resource_effective_access: dict[str, float] = field(default_factory=dict)
    resource_isolated_output: dict[str, float] = field(default_factory=dict)
    resource_access: dict[str, float] = field(default_factory=dict)
    resource_shortages: dict[str, float] = field(default_factory=dict)
    derived_capacity: dict[str, float] = field(default_factory=dict)
    produced_goods: dict[str, float] = field(default_factory=dict)
    production_chain_shortages: dict[str, float] = field(default_factory=dict)
    food_stored: float = 0.0
    food_storage_capacity: float = 0.0
    food_produced: float = 0.0
    food_consumption: float = 0.0
    food_balance: float = 0.0
    food_deficit: float = 0.0
    food_spoilage: float = 0.0
    food_overflow: float = 0.0
    trade_income: float = 0.0
    trade_transit_value: float = 0.0
    trade_import_dependency: float = 0.0
    trade_corridor_exposure: float = 0.0
    trade_foreign_income: float = 0.0
    trade_foreign_imported_flow: float = 0.0
    trade_warfare_damage: float = 0.0
    trade_blockade_losses: float = 0.0
    shock_exposure: float = 0.0
    shock_resilience: float = 0.0
    famine_pressure: float = 0.0
    epidemic_pressure: float = 0.0
    trade_collapse_exposure: float = 0.0
    manpower_pool: float = 0.0
    manpower_capacity: float = 0.0
    standing_forces: float = 0.0
    army_quality: float = 0.0
    military_readiness: float = 0.0
    logistics_capacity: float = 0.0
    naval_power: float = 0.0
    force_projection: float = 0.0
    military_tradition: float = 0.0
    military_reform_pressure: float = 0.0
    military_upkeep: float = 0.0
    last_military_recovery_turn: int | None = None
    tribute_income: float = 0.0
    tribute_paid: float = 0.0
    migration_inflow: int = 0
    migration_outflow: int = 0
    refugee_inflow: int = 0
    refugee_outflow: int = 0
    frontier_settlers: int = 0
    administrative_capacity: float = 0.0
    administrative_load: float = 0.0
    administrative_efficiency: float = 1.0
    administrative_reach: float = 1.0
    administrative_overextension: float = 0.0
    administrative_overextension_penalty: float = 0.0
    capital_region: str | None = None
    urban_network_value: float = 0.0
    urban_specialization_counts: dict[str, int] = field(default_factory=dict)
    elite_blocs: list[EliteBloc] = field(default_factory=list)
    elite_balance: dict[str, float] = field(default_factory=dict)
    elite_unrest_pressure: float = 0.0
    strongest_elite_bloc: str = ""
    alienated_elite_bloc: str = ""
    known_technologies: dict[str, float] = field(default_factory=dict)
    institutional_technologies: dict[str, float] = field(default_factory=dict)
    known_regions: list[str] = field(default_factory=list)
    visible_regions: list[str] = field(default_factory=list)
    known_factions: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.starting_treasury == 0:
            self.starting_treasury = self.treasury

    @property
    def display_name(self):
        return self.identity.display_name if self.identity is not None else self.name

    @property
    def culture_name(self):
        return self.identity.culture_name if self.identity is not None else self.name

    @property
    def government_type(self):
        return (
            self.identity.get_resolved_government_type()
            if self.identity is not None
            else "Tribe"
        )

    @property
    def polity_tier(self):
        return self.identity.polity_tier if self.identity is not None else "tribe"

    @property
    def government_form(self):
        return self.identity.government_form if self.identity is not None else "council"

    @property
    def internal_id(self):
        return self.identity.internal_id if self.identity is not None else self.name

    @property
    def doctrine_label(self):
        return self.doctrine_profile.doctrine_label

    @property
    def doctrine_summary(self):
        return self.doctrine_profile.summary


@dataclass
class Event:
    turn: int
    type: str
    faction: str
    region: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    impact: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    significance: float | None = None

    def _legacy_value(self, key: str):
        for container in (self.details, self.context, self.impact):
            if key in container:
                return container[key]
        raise KeyError(key)

    def __getitem__(self, key):
        if key in self.__dataclass_fields__:
            return getattr(self, key)
        return self._legacy_value(key)

    def get(self, key, default=None):
        try:
            value = self[key]
        except KeyError:
            return default
        return default if value is None else value

    def to_dict(self):
        return asdict(self)

    @property
    def cost(self):
        return self.get("cost")

    @property
    def treasury_after(self):
        return self.get("treasury_after")

    @property
    def resources(self):
        return self.get("resources")

    @property
    def neighbors(self):
        return self.get("neighbors")

    @property
    def unclaimed_neighbors(self):
        return self.get("unclaimed_neighbors")

    @property
    def score(self):
        return self.get("score")

    @property
    def development_amount(self):
        return self.get("development_amount", self.get("invest_amount"))

    @property
    def invest_amount(self):
        return self.development_amount

    @property
    def new_resources(self):
        return self.get("new_resources")


@dataclass
class RelationshipState:
    score: float = 0.0
    status: str = "neutral"
    truce_turns_remaining: int = 0
    years_at_peace: int = 0
    wars_fought: int = 0
    last_conflict_turn: int | None = None
    border_friction: float = 0.0
    trust: float = 0.0
    grievance: float = 0.0
    subordinate_faction: str | None = None
    subordination_type: str = "tributary"
    tribute_share: float = 0.0
    subordination_turns: int = 0


@dataclass
class WarState:
    active: bool = True
    aggressor: str = ""
    defender: str = ""
    objective_type: str = "territorial_conquest"
    objective_label: str = "territorial conquest"
    target_region: str | None = None
    target_faction: str | None = None
    target_ethnicity: str | None = None
    turns_active: int = 0
    last_attack_turn: int | None = None
    total_attacks: int = 0
    successful_attacks: int = 0
    aggressor_attacks: int = 0
    defender_attacks: int = 0
    aggressor_successes: int = 0
    defender_successes: int = 0
    aggressor_score: float = 0.0
    defender_score: float = 0.0
    war_exhaustion: float = 0.0
    last_winner: str | None = None
    last_peace_term: str = ""
    last_settlement_turn: int | None = None


@dataclass
class ShockState:
    id: str
    kind: str
    origin_region: str | None = None
    affected_regions: list[str] = field(default_factory=list)
    faction: str | None = None
    started_turn: int = 0
    duration_turns: int = 1
    intensity: float = 0.0
    phase: str = "onset"
    drivers: dict[str, float] = field(default_factory=dict)
    effects: dict[str, float] = field(default_factory=dict)


@dataclass
class WorldState:
    regions: dict[str, Region]
    factions: dict[str, Faction]
    ethnicities: dict[str, Ethnicity] = field(default_factory=dict)
    religions: dict[str, Religion] = field(default_factory=dict)
    map_name: str = ""
    sea_links: list[tuple[str, str]] = field(default_factory=list)
    river_links: list[tuple[str, str]] = field(default_factory=list)
    turn: int = 0
    events: list[Event] = field(default_factory=list)
    metrics: list = field(default_factory=list)
    region_history: list[dict[str, dict[str, Any]]] = field(default_factory=list)
    relationships: dict[tuple[str, str], RelationshipState] = field(default_factory=dict)
    wars: dict[tuple[str, str], WarState] = field(default_factory=dict)
    active_shocks: list[ShockState] = field(default_factory=list)
    shock_history: list[ShockState] = field(default_factory=list)
