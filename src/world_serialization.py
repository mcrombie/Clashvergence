from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass
from typing import Any, TypeVar

from src.models import (
    EliteBloc,
    Ethnicity,
    Event,
    Faction,
    FactionDoctrineProfile,
    FactionDoctrineState,
    FactionIdentity,
    FactionIdeologyState,
    FactionReligionState,
    FactionSuccessionState,
    LanguageProfile,
    Region,
    RelationshipState,
    Religion,
    ShockState,
    WarState,
    WorldState,
)


WORLD_SAVE_SCHEMA_VERSION = 1

T = TypeVar("T")


def serialize_world(world: WorldState) -> dict[str, Any]:
    """Convert a world into a JSON-safe save payload."""
    return {
        "schema_version": WORLD_SAVE_SCHEMA_VERSION,
        "map_name": world.map_name,
        "random_seed": getattr(world, "random_seed", None),
        "turn": world.turn,
        "regions": {
            name: asdict(region)
            for name, region in world.regions.items()
        },
        "factions": {
            name: asdict(faction)
            for name, faction in world.factions.items()
        },
        "ethnicities": {
            name: asdict(ethnicity)
            for name, ethnicity in world.ethnicities.items()
        },
        "religions": {
            name: asdict(religion)
            for name, religion in world.religions.items()
        },
        "sea_links": [list(link) for link in world.sea_links],
        "river_links": [list(link) for link in world.river_links],
        "events": [event.to_dict() for event in world.events],
        "metrics": list(world.metrics),
        "region_history": list(world.region_history),
        "relationships": [
            {
                "factions": list(pair),
                "state": asdict(state),
            }
            for pair, state in sorted(world.relationships.items())
        ],
        "wars": [
            {
                "factions": list(pair),
                "state": asdict(state),
            }
            for pair, state in sorted(world.wars.items())
        ],
        "active_shocks": [asdict(shock) for shock in world.active_shocks],
        "shock_history": [asdict(shock) for shock in world.shock_history],
    }


def deserialize_world(payload: dict[str, Any]) -> WorldState:
    schema_version = int(payload.get("schema_version", 0))
    if schema_version != WORLD_SAVE_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported world save schema version: {schema_version}"
        )

    world = WorldState(
        regions={
            name: _build_dataclass(Region, region_payload)
            for name, region_payload in payload.get("regions", {}).items()
        },
        factions={
            name: _deserialize_faction(faction_payload)
            for name, faction_payload in payload.get("factions", {}).items()
        },
        ethnicities={
            name: _deserialize_ethnicity(ethnicity_payload)
            for name, ethnicity_payload in payload.get("ethnicities", {}).items()
        },
        religions={
            name: _build_dataclass(Religion, religion_payload)
            for name, religion_payload in payload.get("religions", {}).items()
        },
        map_name=str(payload.get("map_name") or ""),
        sea_links=_deserialize_links(payload.get("sea_links", [])),
        river_links=_deserialize_links(payload.get("river_links", [])),
        turn=int(payload.get("turn", 0) or 0),
        events=[
            _build_dataclass(Event, event_payload)
            for event_payload in payload.get("events", [])
        ],
        metrics=list(payload.get("metrics", [])),
        region_history=list(payload.get("region_history", [])),
        relationships=_deserialize_pair_state_map(
            payload.get("relationships", []),
            RelationshipState,
        ),
        wars=_deserialize_pair_state_map(payload.get("wars", []), WarState),
        active_shocks=[
            _build_dataclass(ShockState, shock_payload)
            for shock_payload in payload.get("active_shocks", [])
        ],
        shock_history=[
            _build_dataclass(ShockState, shock_payload)
            for shock_payload in payload.get("shock_history", [])
        ],
    )
    world.random_seed = payload.get("random_seed")
    return world


def _deserialize_faction(payload: dict[str, Any]) -> Faction:
    data = dict(payload)
    data["identity"] = (
        _deserialize_identity(data["identity"])
        if data.get("identity") is not None
        else None
    )
    data["doctrine_state"] = _build_dataclass(
        FactionDoctrineState,
        data.get("doctrine_state", {}),
    )
    data["doctrine_profile"] = _build_dataclass(
        FactionDoctrineProfile,
        data.get("doctrine_profile", {}),
    )
    data["succession"] = _build_dataclass(
        FactionSuccessionState,
        data.get("succession", {}),
    )
    data["religion"] = _build_dataclass(
        FactionReligionState,
        data.get("religion", {}),
    )
    data["ideology"] = _build_dataclass(
        FactionIdeologyState,
        data.get("ideology", {}),
    )
    data["elite_blocs"] = [
        _build_dataclass(EliteBloc, bloc_payload)
        for bloc_payload in data.get("elite_blocs", [])
    ]
    return _build_dataclass(Faction, data)


def _deserialize_identity(payload: dict[str, Any]) -> FactionIdentity:
    data = dict(payload)
    data["language_profile"] = _build_dataclass(
        LanguageProfile,
        data.get("language_profile", {}),
    )
    return _build_dataclass(FactionIdentity, data)


def _deserialize_ethnicity(payload: dict[str, Any]) -> Ethnicity:
    data = dict(payload)
    data["language_profile"] = _build_dataclass(
        LanguageProfile,
        data.get("language_profile", {}),
    )
    return _build_dataclass(Ethnicity, data)


def _deserialize_links(payload: list[Any]) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for item in payload:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        links.append((str(item[0]), str(item[1])))
    return links


def _deserialize_pair_state_map(
    payload: list[dict[str, Any]],
    state_class: type[T],
) -> dict[tuple[str, str], T]:
    output: dict[tuple[str, str], T] = {}
    for item in payload:
        pair = item.get("factions", [])
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        output[(str(pair[0]), str(pair[1]))] = _build_dataclass(
            state_class,
            item.get("state", {}),
        )
    return output


def _build_dataclass(data_class: type[T], payload: dict[str, Any]) -> T:
    if not is_dataclass(data_class):
        raise TypeError(f"{data_class} is not a dataclass type.")
    allowed_fields = {field.name for field in fields(data_class)}
    data = {
        key: value
        for key, value in dict(payload or {}).items()
        if key in allowed_fields
    }
    return data_class(**data)
