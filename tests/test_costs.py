from dealfinder.costs import DEFAULT_SCHEDULES, buyer_premium, estimate_costs
from dealfinder.models import SourceType, VehicleListing


def test_buyer_premium_flat_tier():
    schedule = DEFAULT_SCHEDULES[SourceType.COPART]
    assert buyer_premium(400, schedule) == 60.0


def test_buyer_premium_rate_tier_with_minimum():
    schedule = DEFAULT_SCHEDULES[SourceType.COPART]
    # 10% of 4000 = 400, above the $200 minimum
    assert buyer_premium(4000, schedule) == 400.0
    # top tier: 7.5% of 20000 = 1500
    assert buyer_premium(20000, schedule) == 1500.0


def test_buyer_premium_zero_for_non_auction():
    listing = VehicleListing(make="Honda", model="Civic", source=SourceType.CRAIGSLIST)
    costs = estimate_costs(listing, 10000, tax_rate=0.08)
    assert costs.buyer_premium == 0.0
    assert costs.taxes_registration == 800.0


def test_auction_costs_include_premium_and_fixed_fees():
    listing = VehicleListing(make="Ford", model="F-150", source=SourceType.COPART)
    costs = estimate_costs(listing, 10000, transport_cost=400, repair_estimate=1500)
    assert costs.buyer_premium == 750.0  # 7.5% top tier
    assert costs.other_fees == 258.0  # gate/env 139 + internet bid 119
    assert costs.all_in_cost == 10000 + 750 + 400 + 1500 + 258


def test_manheim_flat_tier_fees():
    schedule = DEFAULT_SCHEDULES[SourceType.MANHEIM]
    assert buyer_premium(8000, schedule) == 300.0
    assert buyer_premium(25000, schedule) == 550.0


def test_dealer_auction_listing_is_auction_with_fees():
    listing = VehicleListing(make="Toyota", model="Tacoma", source=SourceType.MANHEIM)
    assert listing.is_auction
    # Dealer resale purchase: no sales tax, small title/doc buffer.
    costs = estimate_costs(listing, 18000, tax_rate=0.0, registration_fee=100)
    assert costs.buyer_premium == 425.0  # $10k-$20k tier
    assert costs.taxes_registration == 100.0
    assert costs.other_fees == 125.0  # online buy fee


def test_all_in_cost_sums_everything():
    listing = VehicleListing(make="Toyota", model="Camry", source=SourceType.CARS_COM)
    costs = estimate_costs(
        listing, 15000,
        tax_rate=0.10, registration_fee=300, transport_cost=200,
        repair_estimate=500, inspection_detailing=150, other_fees=50,
    )
    assert costs.taxes_registration == 1800.0
    assert costs.all_in_cost == 15000 + 1800 + 200 + 500 + 150 + 50
    assert costs.non_purchase_costs == 2700.0
