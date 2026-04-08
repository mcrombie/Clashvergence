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
    regions: dict[str, Region] = field(default_factory=dict)
    factions: dict[str, Faction] = field(default_factory=dict)
    turn: int = 0