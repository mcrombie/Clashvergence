"""Population, settlement, and surplus system boundary.

This module currently preserves the established heartland implementations while
giving callers a stable domain-specific import path.
"""

from src.heartland import (
    apply_region_population_loss,
    change_region_population,
    estimate_region_population,
    estimate_region_population_from_resource_profile,
    get_faction_settlement_profile,
    get_next_polity_tier,
    get_region_population_pressure,
    get_region_productive_capacity,
    get_region_settlement_level,
    get_region_surplus,
    get_region_surplus_label,
    transfer_region_population,
    update_faction_polity_tiers,
    update_region_populations,
    update_region_settlement_levels,
)

