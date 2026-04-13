from dataclasses import asdict, dataclass, field
from typing import Any

@dataclass
class Region:
    name: str
    neighbors: list[str]
    owner: str | None
    resources: int

@dataclass
class Faction:
    name: str
    strategy: str
    treasury: int = 0


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
class WorldState:
    regions: dict[str, Region]
    factions: dict[str, Faction]
    turn: int = 0
    events: list[Event] = field(default_factory=list)
    metrics: list = field(default_factory=list)
