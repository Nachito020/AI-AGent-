"""Risk rule engine: decides RECOMMEND / MANUAL_REVIEW / PASS gating."""

from __future__ import annotations

from .models import (
    Decision,
    RiskFlag,
    RiskSeverity,
    TitleStatus,
    Valuation,
    VehicleListing,
)

MIN_VALUATION_SOURCES = 2
MIN_CONFIDENCE = 0.6
SUSPICIOUS_PRICE_RATIO = 0.5  # asking price below 50% of wholesale is suspicious

CONDITION_RED_FLAGS = (
    "blown engine",
    "engine knock",
    "no start",
    "doesn't start",
    "does not start",
    "transmission slip",
    "bad transmission",
    "frame damage",
    "frame rot",
    "rod knock",
    "head gasket",
    "hydrolocked",
)


def assess_risk(listing: VehicleListing, valuation: Valuation) -> list[RiskFlag]:
    flags: list[RiskFlag] = []

    if listing.title_status in (
        TitleStatus.SALVAGE,
        TitleStatus.REBUILT,
        TitleStatus.FLOOD,
        TitleStatus.LEMON,
        TitleStatus.PARTS_ONLY,
    ):
        flags.append(
            RiskFlag(
                code="branded_title",
                severity=RiskSeverity.BLOCKING,
                detail=f"Title status is {listing.title_status.value}",
            )
        )
    elif listing.title_status == TitleStatus.UNKNOWN:
        flags.append(
            RiskFlag(
                code="title_unverified",
                severity=RiskSeverity.WARNING,
                detail="Title status not verified",
            )
        )

    if not listing.vin:
        flags.append(
            RiskFlag(
                code="missing_vin",
                severity=RiskSeverity.WARNING,
                detail="No VIN provided; history cannot be checked",
            )
        )

    if listing.accident_history:
        flags.append(
            RiskFlag(
                code="accident_history",
                severity=RiskSeverity.WARNING,
                detail="Reported accident history",
            )
        )
    if listing.flood_history:
        flags.append(
            RiskFlag(
                code="flood_history",
                severity=RiskSeverity.BLOCKING,
                detail="Reported flood history",
            )
        )
    if listing.mileage_inconsistent:
        flags.append(
            RiskFlag(
                code="mileage_inconsistent",
                severity=RiskSeverity.BLOCKING,
                detail="Mileage inconsistency reported (possible odometer rollback)",
            )
        )
    if listing.warning_lights:
        flags.append(
            RiskFlag(
                code="warning_lights",
                severity=RiskSeverity.WARNING,
                detail="Active warning lights reported",
            )
        )
    if listing.known_mechanical_issues:
        flags.append(
            RiskFlag(
                code="mechanical_issues",
                severity=RiskSeverity.WARNING,
                detail=f"Known mechanical issues: {listing.known_mechanical_issues}",
            )
        )

    notes = (listing.condition_notes or "").lower()
    for phrase in CONDITION_RED_FLAGS:
        if phrase in notes:
            flags.append(
                RiskFlag(
                    code="severe_condition_issue",
                    severity=RiskSeverity.WARNING,
                    detail=f"Condition notes mention: '{phrase}'",
                )
            )
            break

    if (
        listing.asking_price
        and valuation.wholesale_value
        and listing.asking_price < valuation.wholesale_value * SUSPICIOUS_PRICE_RATIO
    ):
        flags.append(
            RiskFlag(
                code="suspiciously_low_price",
                severity=RiskSeverity.WARNING,
                detail=(
                    f"Asking ${listing.asking_price:,.0f} is under "
                    f"{SUSPICIOUS_PRICE_RATIO:.0%} of wholesale "
                    f"(${valuation.wholesale_value:,.0f}) — possible scam or hidden damage"
                ),
            )
        )

    if len(valuation.sources) < MIN_VALUATION_SOURCES:
        flags.append(
            RiskFlag(
                code="thin_valuation",
                severity=RiskSeverity.WARNING,
                detail=(
                    f"Only {len(valuation.sources)} valuation source(s); "
                    f"need at least {MIN_VALUATION_SOURCES}"
                ),
            )
        )
    if valuation.confidence < MIN_CONFIDENCE:
        flags.append(
            RiskFlag(
                code="low_confidence_valuation",
                severity=RiskSeverity.WARNING,
                detail=f"Valuation confidence {valuation.confidence:.2f} < {MIN_CONFIDENCE}",
            )
        )

    return flags


def decide(
    flags: list[RiskFlag],
    expected_profit_value: float | None,
    min_profit: float,
) -> Decision:
    """Gate the deal.

    - Profit below the floor (or unknown) is always a PASS.
    - Any blocking flag, or unverifiable valuation/condition, goes to
      MANUAL_REVIEW instead of a recommendation.
    """
    if expected_profit_value is None or expected_profit_value < min_profit:
        return Decision.PASS
    if any(f.severity == RiskSeverity.BLOCKING for f in flags):
        return Decision.MANUAL_REVIEW
    if any(f.severity == RiskSeverity.WARNING for f in flags):
        return Decision.MANUAL_REVIEW
    return Decision.RECOMMEND
