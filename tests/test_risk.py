from dealfinder.models import (
    Decision,
    RiskSeverity,
    TitleStatus,
    Valuation,
    ValuationSource,
    VehicleListing,
)
from dealfinder.risk import assess_risk, decide


def _clean_listing(**overrides) -> VehicleListing:
    data = dict(
        year=2019, make="Toyota", model="Tacoma", vin="3TMCZ5AN0KM123456",
        asking_price=21500, title_status=TitleStatus.CLEAN,
        source="craigslist",
    )
    data.update(overrides)
    return VehicleListing(**data)


def _solid_valuation() -> Valuation:
    return Valuation(
        wholesale_value=27000, quick_sale_value=30500, retail_value=33500,
        confidence=0.85,
        sources=[
            ValuationSource(source="kbb", value=33500),
            ValuationSource(source="carvana", value=27500, kind="offer"),
        ],
    )


def test_clean_deal_recommended():
    flags = assess_risk(_clean_listing(), _solid_valuation())
    assert flags == []
    assert decide(flags, 6000, 5000) == Decision.RECOMMEND


def test_salvage_title_blocks_recommendation():
    flags = assess_risk(
        _clean_listing(title_status=TitleStatus.SALVAGE), _solid_valuation()
    )
    assert any(f.code == "branded_title" and f.severity == RiskSeverity.BLOCKING for f in flags)
    assert decide(flags, 8000, 5000) == Decision.MANUAL_REVIEW


def test_missing_vin_forces_manual_review():
    flags = assess_risk(_clean_listing(vin=None), _solid_valuation())
    assert any(f.code == "missing_vin" for f in flags)
    assert decide(flags, 8000, 5000) == Decision.MANUAL_REVIEW


def test_suspiciously_low_price_flagged():
    flags = assess_risk(_clean_listing(asking_price=9000), _solid_valuation())
    assert any(f.code == "suspiciously_low_price" for f in flags)


def test_thin_valuation_flagged():
    valuation = Valuation(
        quick_sale_value=30000, confidence=0.9,
        sources=[ValuationSource(source="kbb", value=30000)],
    )
    flags = assess_risk(_clean_listing(), valuation)
    assert any(f.code == "thin_valuation" for f in flags)


def test_profit_below_floor_is_pass_even_when_clean():
    assert decide([], 4999, 5000) == Decision.PASS
    assert decide([], None, 5000) == Decision.PASS


def test_condition_red_flag_from_notes():
    flags = assess_risk(
        _clean_listing(condition_notes="Great truck but has a rod knock"),
        _solid_valuation(),
    )
    assert any(f.code == "severe_condition_issue" for f in flags)
