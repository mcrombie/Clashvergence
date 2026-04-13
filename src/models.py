from dataclasses import dataclass, field

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
class WorldState:
    regions: dict[str, Region]
    factions: dict[str, Faction]
    turn: int = 0
    events: list = field(default_factory=list)
    metrics: list = field(default_factory=list)
