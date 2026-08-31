"""Deal alert formatting and delivery."""

from __future__ import annotations

from .models import DealAnalysis, Decision


def _money(value: float | None) -> str:
    return f"${value:,.0f}" if value is not None else "N/A"


def format_deal_alert(analysis: DealAnalysis) -> str:
    """Render the DEAL ALERT block in the agreed template."""
    listing = analysis.listing
    valuation = analysis.valuation
    ymmt = " / ".join(
        str(p)
        for p in (listing.year, listing.make, listing.model, listing.trim)
        if p
    )
    possible_price = analysis.max_bid if listing.is_auction else analysis.max_buy_price
    risks = "; ".join(f.detail for f in analysis.risk_flags) or "None identified"

    if analysis.decision == Decision.RECOMMEND:
        recommendation = (
            f"Pursue. Do not pay more than {_money(analysis.max_buy_price)} for the "
            f"vehicle" + (f" (max bid {_money(analysis.max_bid)})." if listing.is_auction else ".")
        )
    else:
        recommendation = "Manual review required before any offer — verify the flagged items first."

    lines = [
        "DEAL ALERT",
        f"Vehicle: {listing.display_name()}",
        f"Year / Make / Model / Trim: {ymmt or 'N/A'}",
        f"Mileage: {listing.mileage:,}" if listing.mileage else "Mileage: N/A",
        f"Source: {listing.source_label()}" + (f" ({listing.url})" if listing.url else ""),
        f"Location: {listing.location or 'N/A'}",
        f"Seller Asking: {_money(listing.asking_price)}",
        f"Possible Purchase Price: {_money(possible_price)}",
        f"Carvana Offer: {_money(valuation.carvana_offer)}",
        f"Estimated Wholesale Value: {_money(valuation.wholesale_value)}",
        f"Estimated Quick-Sale Value: {_money(valuation.quick_sale_value)}",
        f"Estimated Retail Value: {_money(valuation.retail_value)}",
        f"Estimated All-In Cost: {_money(analysis.costs.all_in_cost)}",
        f"Expected Profit: {_money(analysis.expected_profit)}",
        f"Maximum Buy Price: {_money(analysis.max_buy_price)}",
        f"Main Risks: {risks}",
        f"Why It Looks Underpriced: {analysis.why_underpriced or 'See valuation sources'}",
        f"Recommendation: {recommendation}",
    ]
    return "\n".join(lines)


def send_alert(analysis: DealAnalysis, *, channel: str = "console") -> None:
    """Deliver an alert. Console is built in; wire email/SMS here as needed."""
    text = format_deal_alert(analysis)
    if channel == "console":
        print("\n" + "=" * 60)
        print(text)
        print("=" * 60)
    else:
        raise NotImplementedError(f"Alert channel not configured: {channel}")
