from __future__ import annotations

from src.models import Faction
from src.internal_politics import get_faction_elite_effects
from src.ideology import get_faction_ideology_effects


POLITY_TIER_MODIFIERS = {
    "band": {
        "income_factor": 0.75,
        "maintenance_factor": 0.70,
        "integration_factor": 0.65,
        "stability_factor": 0.90,
        "administrative_capacity_factor": 0.78,
        "administrative_reach_factor": 0.84,
        "attack_bias": -1,
        "realm_size_unrest_factor": 1.40,
    },
    "tribe": {
        "income_factor": 0.95,
        "maintenance_factor": 0.90,
        "integration_factor": 1.00,
        "stability_factor": 1.00,
        "administrative_capacity_factor": 0.96,
        "administrative_reach_factor": 0.96,
        "attack_bias": 0,
        "realm_size_unrest_factor": 1.10,
    },
    "chiefdom": {
        "income_factor": 1.05,
        "maintenance_factor": 1.00,
        "integration_factor": 1.05,
        "stability_factor": 1.08,
        "administrative_capacity_factor": 1.1,
        "administrative_reach_factor": 1.04,
        "attack_bias": 1,
        "realm_size_unrest_factor": 0.95,
    },
    "state": {
        "income_factor": 1.15,
        "maintenance_factor": 1.10,
        "integration_factor": 1.15,
        "stability_factor": 1.16,
        "administrative_capacity_factor": 1.26,
        "administrative_reach_factor": 1.12,
        "attack_bias": 1,
        "realm_size_unrest_factor": 0.85,
    },
}

GOVERNMENT_FORM_MODIFIERS = {
    "leader": {
        "income_factor": 0.95,
        "stability_factor": 0.92,
        "attack_bias": 1,
        "integration_factor": 0.95,
        "administrative_capacity_factor": 0.94,
        "administrative_reach_factor": 0.95,
    },
    "council": {
        "income_factor": 1.00,
        "stability_factor": 1.06,
        "attack_bias": 0,
        "integration_factor": 1.00,
        "administrative_capacity_factor": 1.0,
        "administrative_reach_factor": 1.0,
    },
    "assembly": {
        "income_factor": 0.98,
        "stability_factor": 1.10,
        "attack_bias": -1,
        "integration_factor": 1.02,
        "administrative_capacity_factor": 0.98,
        "administrative_reach_factor": 0.97,
    },
    "monarchy": {
        "income_factor": 1.03,
        "stability_factor": 0.98,
        "attack_bias": 1,
        "integration_factor": 1.05,
        "administrative_capacity_factor": 1.05,
        "administrative_reach_factor": 1.03,
    },
    "republic": {
        "income_factor": 1.08,
        "stability_factor": 1.04,
        "attack_bias": 0,
        "integration_factor": 1.08,
        "administrative_capacity_factor": 1.08,
        "administrative_reach_factor": 1.07,
    },
    "oligarchy": {
        "income_factor": 1.10,
        "stability_factor": 0.94,
        "attack_bias": 0,
        "integration_factor": 0.96,
        "administrative_capacity_factor": 1.02,
        "administrative_reach_factor": 1.0,
    },
}

REGIME_AGITATION_GOVERNMENT_FORM_BIAS = {
    "leader": 0.14,
    "council": -0.08,
    "assembly": -0.16,
    "monarchy": 0.16,
    "republic": -0.10,
    "oligarchy": 0.12,
}

REGIME_AGITATION_DIPLOMATIC_FORMS = {"council", "assembly", "republic"}


def get_faction_polity_modifiers(faction: Faction | None) -> dict[str, float]:
    if faction is None:
        return POLITY_TIER_MODIFIERS["tribe"]
    return POLITY_TIER_MODIFIERS.get(
        faction.polity_tier,
        POLITY_TIER_MODIFIERS["tribe"],
    )


def get_faction_government_form_modifiers(faction: Faction | None) -> dict[str, float]:
    if faction is None:
        return GOVERNMENT_FORM_MODIFIERS["council"]
    return GOVERNMENT_FORM_MODIFIERS.get(
        faction.government_form,
        GOVERNMENT_FORM_MODIFIERS["council"],
    )


def get_faction_income_modifier(faction: Faction | None) -> float:
    polity = get_faction_polity_modifiers(faction)
    form = get_faction_government_form_modifiers(faction)
    elite_factor = get_faction_elite_effects(faction).get("trade_income_factor", 0.0) if faction is not None else 0.0
    ideology_factor = get_faction_ideology_effects(faction).get("income_factor", 0.0) if faction is not None else 0.0
    return polity["income_factor"] * form["income_factor"] * (1.0 + elite_factor + ideology_factor)


def get_faction_maintenance_modifier(faction: Faction | None) -> float:
    polity = get_faction_polity_modifiers(faction)
    return polity["maintenance_factor"]


def get_faction_integration_modifier(faction: Faction | None) -> float:
    polity = get_faction_polity_modifiers(faction)
    form = get_faction_government_form_modifiers(faction)
    ideology_factor = get_faction_ideology_effects(faction).get("integration_factor", 0.0) if faction is not None else 0.0
    return polity["integration_factor"] * form["integration_factor"] * (1.0 + ideology_factor)


def get_faction_stability_modifier(faction: Faction | None) -> float:
    polity = get_faction_polity_modifiers(faction)
    form = get_faction_government_form_modifiers(faction)
    ideology_factor = get_faction_ideology_effects(faction).get("stability_factor", 0.0) if faction is not None else 0.0
    return polity["stability_factor"] * form["stability_factor"] * (1.0 + ideology_factor)


def get_faction_administrative_capacity_modifier(faction: Faction | None) -> float:
    polity = get_faction_polity_modifiers(faction)
    form = get_faction_government_form_modifiers(faction)
    ideology_factor = get_faction_ideology_effects(faction).get("administrative_capacity_factor", 0.0) if faction is not None else 0.0
    return polity["administrative_capacity_factor"] * form["administrative_capacity_factor"] * (1.0 + ideology_factor)


def get_faction_administrative_reach_modifier(faction: Faction | None) -> float:
    polity = get_faction_polity_modifiers(faction)
    form = get_faction_government_form_modifiers(faction)
    ideology_factor = get_faction_ideology_effects(faction).get("administrative_reach_factor", 0.0) if faction is not None else 0.0
    return polity["administrative_reach_factor"] * form["administrative_reach_factor"] * (1.0 + ideology_factor)


def get_faction_realm_size_unrest_factor(faction: Faction | None) -> float:
    polity = get_faction_polity_modifiers(faction)
    ideology_factor = get_faction_ideology_effects(faction).get("realm_size_unrest_factor", 1.0) if faction is not None else 1.0
    return polity["realm_size_unrest_factor"] * ideology_factor
