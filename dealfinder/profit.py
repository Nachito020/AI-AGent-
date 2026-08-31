"""Profit math: expected profit, maximum buy price, and maximum auction bid."""

from __future__ import annotations

from .costs import FeeSchedule, auction_fixed_fees, buyer_premium
from .models import CostBreakdown

MIN_PROFIT = 5000.0
PREFERRED_PROFIT = 7500.0


def expected_profit(conservative_resale_value: float, costs: CostBreakdown) -> float:
    return round(conservative_resale_value - costs.all_in_cost, 2)


def max_buy_price(
    conservative_resale_value: float,
    required_profit: float,
    non_purchase_costs: float,
) -> float:
    """Work backward from resale value to the most we can pay for the vehicle.

    ``non_purchase_costs`` is everything that is not the purchase price itself
    (premium, taxes, transport, repairs, fees).
    """
    return round(max(conservative_resale_value - required_profit - non_purchase_costs, 0.0), 2)


def max_bid(
    conservative_resale_value: float,
    required_profit: float,
    *,
    schedule: FeeSchedule | None = None,
    tax_rate: float = 0.0,
    registration_fee: float = 0.0,
    transport_cost: float = 0.0,
    repair_estimate: float = 0.0,
    inspection_detailing: float = 0.0,
    other_fees: float = 0.0,
) -> float:
    """Highest hammer-price bid that still clears the required profit.

    Buyer premium and sales tax both scale with the bid, so this solves
    ``bid + premium(bid) + tax(bid) + fixed_costs <= budget`` by binary
    search over the bid.
    """
    budget = (
        conservative_resale_value
        - required_profit
        - transport_cost
        - repair_estimate
        - inspection_detailing
        - other_fees
        - registration_fee
        - auction_fixed_fees(schedule)
    )
    if budget <= 0:
        return 0.0

    def total_cost(bid: float) -> float:
        return bid + buyer_premium(bid, schedule) + bid * tax_rate

    lo, hi = 0.0, budget  # total_cost(bid) >= bid, so the answer is <= budget
    for _ in range(60):
        mid = (lo + hi) / 2
        if total_cost(mid) <= budget:
            lo = mid
        else:
            hi = mid
    return round(lo, 2)
