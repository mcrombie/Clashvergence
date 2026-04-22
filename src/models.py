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
    ("state", "council"): "State",
    ("state", "assembly"): "State",
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
class LanguageProfile:
    family_name: str = ""
    onsets: list[str] = field(default_factory=list)
    middles: list[str] = field(default_factory=list)
    suffixes: list[str] = field(default_factory=list)
    seed_fragments: list[str] = field(default_factory=list)
    style_notes: list[str] = field(default_factory=list)


@dataclass
class Ethnicity:
    name: str
    language_family: str = ""
    parent_ethnicity: str | None = None
    origin_faction: str | None = None
    language_profile: LanguageProfile = field(default_factory=LanguageProfile)


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
    trade_foreign_partner: str | None = None
    trade_foreign_partner_region: str | None = None
    trade_foreign_flow: float = 0.0
    trade_foreign_value: float = 0.0
    trade_gateway_role: str = "none"
    last_resource_project_turn: int | None = None
    infrastructure_level: float = 0.0
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
    population: int = 0
    ethnic_composition: dict[str, int] = field(default_factory=dict)
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


@dataclass
class WorldState:
    regions: dict[str, Region]
    factions: dict[str, Faction]
    ethnicities: dict[str, Ethnicity] = field(default_factory=dict)
    map_name: str = ""
    sea_links: list[tuple[str, str]] = field(default_factory=list)
    turn: int = 0
    events: list[Event] = field(default_factory=list)
    metrics: list = field(default_factory=list)
    region_history: list[dict[str, dict[str, Any]]] = field(default_factory=list)
    relationships: dict[tuple[str, str], RelationshipState] = field(default_factory=dict)
