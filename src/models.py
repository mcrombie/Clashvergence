from dataclasses import asdict, dataclass, field
from typing import Any


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
    investments: int = 0
    turns_with_growth: int = 0
    turns_with_conflict: int = 0
    turns_with_investment: int = 0
    regions_gained_by_expansion: int = 0
    regions_gained_by_conquest: int = 0
    cumulative_regions_held: int = 0
    peak_regions: int = 0
    starting_regions: int = 0
    last_region_count: int = 0


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
class Region:
    name: str
    neighbors: list[str]
    owner: str | None
    resources: int
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
    government_type: str = "Tribe"
    display_name: str = ""
    source_traditions: list[str] = field(default_factory=list)
    generation_method: str = "curated_source_fusion"
    ai_generated: bool = False
    inspirations: list[str] = field(default_factory=list)
    candidate_pool: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.display_name:
            self.display_name = f"{self.culture_name} {self.government_type}"


@dataclass
class Faction:
    name: str
    treasury: int = 0
    identity: FactionIdentity | None = None
    starting_treasury: int = 0
    doctrine_state: FactionDoctrineState = field(default_factory=FactionDoctrineState)
    doctrine_profile: FactionDoctrineProfile = field(default_factory=FactionDoctrineProfile)
    is_rebel: bool = False
    origin_faction: str | None = None
    rebel_age: int = 0
    independence_score: float = 0.0
    proto_state: bool = False

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
        return self.identity.government_type if self.identity is not None else "Tribe"

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
    def invest_amount(self):
        return self.get("invest_amount")

    @property
    def new_resources(self):
        return self.get("new_resources")


@dataclass
class RelationshipState:
    score: float = 0.0
    status: str = "neutral"
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
    map_name: str = ""
    turn: int = 0
    events: list[Event] = field(default_factory=list)
    metrics: list = field(default_factory=list)
    region_history: list[dict[str, dict[str, Any]]] = field(default_factory=list)
    relationships: dict[tuple[str, str], RelationshipState] = field(default_factory=dict)
