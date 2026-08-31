from dealfinder.costs import DEFAULT_SCHEDULES, auction_fixed_fees, buyer_premium
from dealfinder.models import CostBreakdown, SourceType
from dealfinder.profit import expected_profit, max_bid, max_buy_price


def test_expected_profit():
    costs = CostBreakdown(purchase_price=27000, repairs=2000)
    assert expected_profit(34000, costs) == 5000.0


def test_max_buy_price_spec_example():
    # Spec example: quick-sale $34,000, required profit $5,000, expenses $2,000
    assert max_buy_price(34000, 5000, 2000) == 27000.0


def test_max_buy_price_floors_at_zero():
    assert max_buy_price(6000, 5000, 2000) == 0.0


def test_max_bid_accounts_for_premium_and_tax():
    schedule = DEFAULT_SCHEDULES[SourceType.COPART]
    bid = max_bid(
        30000, 5000,
        schedule=schedule, tax_rate=0.0725,
        transport_cost=400, repair_estimate=2000,
    )
    assert bid > 0
    # Buying at exactly the max bid must still clear the required profit.
    total = (
        bid
        + buyer_premium(bid, schedule)
        + bid * 0.0725
        + auction_fixed_fees(schedule)
        + 400
        + 2000
    )
    assert 30000 - total >= 5000 - 1.0  # within a dollar of the target
    # And bidding meaningfully higher must not.
    higher = bid * 1.05
    total_higher = (
        higher
        + buyer_premium(higher, schedule)
        + higher * 0.0725
        + auction_fixed_fees(schedule)
        + 400
        + 2000
    )
    assert 30000 - total_higher < 5000


def test_max_bid_zero_when_budget_negative():
    assert max_bid(6000, 5000, transport_cost=2000) == 0.0
