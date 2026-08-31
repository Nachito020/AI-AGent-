"""Deal scoring and ranking."""

from __future__ import annotations

from .models import DealAnalysis, Decision, RiskSeverity

# High-liquidity vehicles resell faster; makes ranked roughly by demand.
LIQUIDITY_BY_MAKE = {
    "toyota": 1.0, "honda": 1.0, "ford": 0.9, "chevrolet": 0.9, "gmc": 0.9,
    "ram": 0.85, "subaru": 0.85, "lexus": 0.85, "nissan": 0.8, "jeep": 0.8,
    "hyundai": 0.75, "kia": 0.75, "mazda": 0.75, "dodge": 0.7, "bmw": 0.6,
    "mercedes-benz": 0.6, "audi": 0.55, "volkswagen": 0.6,
}
DEFAULT_LIQUIDITY = 0.6

HIGH_DEMAND_MODELS = (
    "tacoma", "tundra", "4runner", "f-150", "f150", "f-250", "f250", "silverado",
    "sierra", "civic", "accord", "camry", "corolla", "cr-v", "crv", "rav4",
    "wrangler", "highlander", "odyssey", "sienna",
)


def score_deal(analysis: DealAnalysis) -> float:
    """0-100 composite score: profit, valuation confidence, discount, liquidity, risk."""
    profit = analysis.expected_profit or 0.0
    if profit <= 0:
        return 0.0

    # Profit: $5k -> ~50, $10k -> ~75, capped at 100
    profit_score = min(profit / 100.0 * 0.5 + 25.0, 100.0)

    confidence_score = analysis.valuation.confidence * 100.0

    resale = analysis.valuation.conservative_resale_value or 0.0
    asking = analysis.listing.asking_price or 0.0
    discount_score = min(max((resale - asking) / resale, 0.0) * 250.0, 100.0) if resale and asking else 0.0

    make = (analysis.listing.make or "").strip().lower()
    model = (analysis.listing.model or "").strip().lower()
    liquidity = LIQUIDITY_BY_MAKE.get(make, DEFAULT_LIQUIDITY)
    if any(m in model for m in HIGH_DEMAND_MODELS):
        liquidity = min(liquidity + 0.15, 1.0)
    liquidity_score = liquidity * 100.0

    risk_penalty = sum(
        15.0 if f.severity == RiskSeverity.BLOCKING else 5.0
        for f in analysis.risk_flags
        if f.severity != RiskSeverity.INFO
    )

    score = (
        0.35 * profit_score
        + 0.25 * confidence_score
        + 0.20 * discount_score
        + 0.20 * liquidity_score
        - risk_penalty
    )
    return round(max(min(score, 100.0), 0.0), 1)


def rank_deals(analyses: list[DealAnalysis]) -> list[DealAnalysis]:
    """Score and sort deals, dropping marginal/PASS opportunities."""
    kept = [a for a in analyses if a.decision != Decision.PASS]
    for a in kept:
        a.score = score_deal(a)
    return sorted(kept, key=lambda a: a.score, reverse=True)
