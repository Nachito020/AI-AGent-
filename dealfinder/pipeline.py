"""Orchestration: listings -> dedupe -> valuation -> costs -> profit -> risk -> rank."""

from __future__ import annotations

from typing import Optional

from .config import Settings
from .costs import DEFAULT_SCHEDULES, estimate_costs
from .dedupe import dedupe_listings
from .models import DealAnalysis, Decision, Valuation, VehicleListing
from .profit import expected_profit, max_bid, max_buy_price
from .ranking import rank_deals
from .risk import assess_risk, decide


def analyze_listing(
    settings: Settings,
    listing: VehicleListing,
    valuation: Valuation,
    *,
    repair_estimate: Optional[float] = None,
    why_underpriced: Optional[str] = None,
    url_status: Optional[tuple[str, str]] = None,
) -> DealAnalysis:
    """Run the deterministic deal math for one listing with a known valuation."""
    c = settings.costs
    repairs = repair_estimate if repair_estimate is not None else c.repair_estimate
    purchase = listing.asking_price or 0.0

    costs = estimate_costs(
        listing,
        purchase,
        tax_rate=c.tax_rate,
        registration_fee=c.registration_fee,
        transport_cost=c.transport_cost,
        repair_estimate=repairs,
        inspection_detailing=c.inspection_detailing,
        other_fees=c.other_fees,
    )

    resale = valuation.conservative_resale_value
    profit = expected_profit(resale, costs) if resale else None

    max_price = None
    bid_cap = None
    if resale:
        max_price = max_buy_price(resale, settings.min_profit, costs.non_purchase_costs)
        if listing.is_auction:
            bid_cap = max_bid(
                resale,
                settings.min_profit,
                schedule=DEFAULT_SCHEDULES.get(listing.source),
                tax_rate=c.tax_rate,
                registration_fee=c.registration_fee,
                transport_cost=c.transport_cost,
                repair_estimate=repairs,
                inspection_detailing=c.inspection_detailing,
                other_fees=c.other_fees,
            )

    flags = assess_risk(listing, valuation)
    if url_status is not None:
        from .verify import url_risk_flag

        flag = url_risk_flag(*url_status)
        if flag is not None:
            flags.append(flag)
    decision = decide(flags, profit, settings.min_profit)

    return DealAnalysis(
        listing=listing,
        valuation=valuation,
        costs=costs,
        expected_profit=profit,
        max_buy_price=max_price,
        max_bid=bid_cap,
        risk_flags=flags,
        decision=decision,
        why_underpriced=why_underpriced,
    )


def run_scan(settings: Settings, query: str = "") -> list[DealAnalysis]:
    """Full pipeline: discover listings online, research values, rank deals."""
    from .agent import discover_listings, research_valuation  # requires API key
    from .verify import verify_listings

    listings = dedupe_listings(discover_listings(settings, query))
    listings = listings[: settings.max_candidates_per_scan]
    statuses = verify_listings(listings) if settings.verify_listing_urls else {}

    analyses = []
    for listing in listings:
        try:
            valuation, repairs, why = research_valuation(settings, listing)
        except Exception as exc:  # keep scanning if one valuation fails
            print(f"  ! valuation failed for {listing.display_name()}: {exc}")
            continue
        analyses.append(
            analyze_listing(
                settings, listing, valuation,
                repair_estimate=repairs, why_underpriced=why,
                url_status=statuses.get(id(listing)),
            )
        )
    return rank_deals(analyses)


def analyze_batch(
    settings: Settings,
    listings: list[VehicleListing],
    *,
    research: bool = True,
) -> list[DealAnalysis]:
    """Analyze imported listings; with research=True, value each via the API."""
    from .verify import verify_listings

    listings = dedupe_listings(listings)
    statuses = verify_listings(listings) if settings.verify_listing_urls else {}

    analyses = []
    for listing in listings:
        if research:
            from .agent import research_valuation

            valuation, repairs, why = research_valuation(settings, listing)
        else:
            valuation, repairs, why = Valuation(), None, None
        analyses.append(
            analyze_listing(
                settings, listing, valuation,
                repair_estimate=repairs, why_underpriced=why,
                url_status=statuses.get(id(listing)),
            )
        )
    return rank_deals(analyses)


def strong_deals(settings: Settings, analyses: list[DealAnalysis]) -> list[DealAnalysis]:
    """Only deals that clear the profit floor and are safe to recommend."""
    return [
        a
        for a in analyses
        if a.decision == Decision.RECOMMEND
        and a.expected_profit is not None
        and a.expected_profit >= settings.min_profit
    ]
