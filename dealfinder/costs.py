"""All-in cost calculation, including auction buyer-premium schedules."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .models import CostBreakdown, SourceType, VehicleListing


class PremiumTier(BaseModel):
    """One tier of a buyer-premium schedule.

    Applies to a hammer price up to ``up_to`` (inclusive; ``None`` = no upper
    bound). Exactly one of ``flat`` or ``rate`` should be set: ``flat`` is a
    fixed dollar amount, ``rate`` a fraction of the full hammer price.
    """

    up_to: float | None = None
    flat: float | None = None
    rate: float | None = None
    minimum: float = 0.0


class FeeSchedule(BaseModel):
    """Fee model for one source (auction house or marketplace)."""

    premium_tiers: list[PremiumTier] = Field(default_factory=list)
    fixed_fees: float = 0.0  # gate fee, environmental fee, doc fee, etc.
    internet_bid_fee: float = 0.0


# Simplified, configurable defaults. Real schedules change; override in config.
DEFAULT_SCHEDULES: dict[SourceType, FeeSchedule] = {
    SourceType.COPART: FeeSchedule(
        premium_tiers=[
            PremiumTier(up_to=100.0, flat=25.0),
            PremiumTier(up_to=500.0, flat=60.0),
            PremiumTier(up_to=1000.0, flat=100.0),
            PremiumTier(up_to=5000.0, rate=0.10, minimum=200.0),
            PremiumTier(up_to=None, rate=0.075, minimum=500.0),
        ],
        fixed_fees=139.0,  # gate + environmental (approx.)
        internet_bid_fee=119.0,
    ),
    SourceType.IAA: FeeSchedule(
        premium_tiers=[
            PremiumTier(up_to=500.0, flat=85.0),
            PremiumTier(up_to=5000.0, rate=0.10, minimum=200.0),
            PremiumTier(up_to=None, rate=0.08, minimum=500.0),
        ],
        fixed_fees=135.0,
        internet_bid_fee=120.0,
    ),
    SourceType.GOVDEALS: FeeSchedule(
        premium_tiers=[PremiumTier(up_to=None, rate=0.125)],
    ),
    SourceType.RITCHIE_BROS: FeeSchedule(
        premium_tiers=[PremiumTier(up_to=None, rate=0.10)],
    ),
    SourceType.IRONPLANET: FeeSchedule(
        premium_tiers=[PremiumTier(up_to=None, rate=0.10)],
    ),
    SourceType.LOCAL_AUCTION: FeeSchedule(
        premium_tiers=[PremiumTier(up_to=None, rate=0.10)],
    ),
}


def buyer_premium(hammer_price: float, schedule: FeeSchedule | None) -> float:
    """Buyer premium for a hammer price under a tiered schedule."""
    if schedule is None or hammer_price <= 0 or not schedule.premium_tiers:
        return 0.0
    for tier in schedule.premium_tiers:
        if tier.up_to is None or hammer_price <= tier.up_to:
            if tier.flat is not None:
                return round(max(tier.flat, tier.minimum), 2)
            if tier.rate is not None:
                return round(max(hammer_price * tier.rate, tier.minimum), 2)
            return 0.0
    return 0.0


def auction_fixed_fees(schedule: FeeSchedule | None) -> float:
    if schedule is None:
        return 0.0
    return schedule.fixed_fees + schedule.internet_bid_fee


def estimate_costs(
    listing: VehicleListing,
    purchase_price: float,
    *,
    tax_rate: float = 0.0,
    registration_fee: float = 0.0,
    transport_cost: float = 0.0,
    repair_estimate: float = 0.0,
    inspection_detailing: float = 0.0,
    other_fees: float = 0.0,
    schedule: FeeSchedule | None = None,
) -> CostBreakdown:
    """Build the full cost breakdown for buying this listing at a given price.

    For auction sources, ``schedule`` (or the built-in default for that
    auction house) adds the buyer premium and fixed auction fees.
    """
    if schedule is None and listing.is_auction:
        schedule = DEFAULT_SCHEDULES.get(listing.source)

    premium = buyer_premium(purchase_price, schedule) if listing.is_auction else 0.0
    fixed = auction_fixed_fees(schedule) if listing.is_auction else 0.0

    return CostBreakdown(
        purchase_price=round(purchase_price, 2),
        buyer_premium=premium,
        taxes_registration=round(purchase_price * tax_rate + registration_fee, 2),
        transportation=round(transport_cost, 2),
        repairs=round(repair_estimate, 2),
        inspection_detailing=round(inspection_detailing, 2),
        other_fees=round(other_fees + fixed, 2),
    )
