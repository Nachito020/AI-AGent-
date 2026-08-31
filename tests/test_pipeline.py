from dealfinder.alerts import format_deal_alert
from dealfinder.config import Settings
from dealfinder.contact import draft_seller_message
from dealfinder.models import (
    Decision,
    SourceType,
    TitleStatus,
    Valuation,
    ValuationSource,
    VehicleListing,
)
from dealfinder.pipeline import analyze_listing, rank_deals, strong_deals


def _settings() -> Settings:
    return Settings()


def _tacoma() -> VehicleListing:
    return VehicleListing(
        year=2019, make="Toyota", model="Tacoma", trim="TRD Off-Road",
        mileage=62000, vin="3TMCZ5AN0KM123456", asking_price=21500,
        location="Sacramento, CA", title_status=TitleStatus.CLEAN,
        source=SourceType.CRAIGSLIST, url="https://example.org/tacoma",
    )


def _tacoma_valuation() -> Valuation:
    return Valuation(
        carvana_offer=27500, wholesale_value=27000,
        quick_sale_value=30500, retail_value=33500, confidence=0.85,
        sources=[
            ValuationSource(source="kbb", value=33500),
            ValuationSource(source="carvana", value=27500, kind="offer"),
            ValuationSource(source="cargurus_comps", value=30800, kind="quick_sale"),
        ],
    )


def test_good_deal_recommended_with_profit_and_max_price():
    analysis = analyze_listing(_settings(), _tacoma(), _tacoma_valuation())
    assert analysis.decision == Decision.RECOMMEND
    assert analysis.expected_profit is not None and analysis.expected_profit >= 5000
    assert analysis.max_buy_price is not None
    # Max buy price must be consistent: paying it leaves exactly min profit.
    resale = analysis.valuation.conservative_resale_value
    assert (
        abs(resale - (analysis.max_buy_price + analysis.costs.non_purchase_costs) - 5000)
        < 1.0
    )


def test_auction_listing_gets_max_bid_below_max_buy_price():
    listing = _tacoma().model_copy(update={"source": SourceType.COPART, "asking_price": 18000})
    analysis = analyze_listing(_settings(), listing, _tacoma_valuation())
    assert analysis.max_bid is not None
    assert analysis.max_bid < analysis.max_buy_price


def test_no_valuation_means_pass():
    analysis = analyze_listing(_settings(), _tacoma(), Valuation())
    assert analysis.decision == Decision.PASS
    assert analysis.expected_profit is None


def test_marginal_profit_passes():
    valuation = _tacoma_valuation().model_copy(update={
        "carvana_offer": None, "quick_sale_value": 25000, "wholesale_value": 23000,
    })
    analysis = analyze_listing(_settings(), _tacoma(), valuation)
    assert analysis.expected_profit < 5000
    assert analysis.decision == Decision.PASS


def test_rank_and_strong_deals_filter():
    settings = _settings()
    good = analyze_listing(settings, _tacoma(), _tacoma_valuation())
    salvage = analyze_listing(
        settings,
        _tacoma().model_copy(update={"title_status": TitleStatus.SALVAGE, "asking_price": 15000}),
        _tacoma_valuation(),
    )
    ranked = rank_deals([good, salvage])
    assert ranked and ranked[0].score >= ranked[-1].score
    strong = strong_deals(settings, ranked)
    assert good in strong
    assert salvage not in strong  # branded title -> manual review, never auto-recommend


def test_alert_contains_required_fields():
    analysis = analyze_listing(_settings(), _tacoma(), _tacoma_valuation())
    alert = format_deal_alert(analysis)
    for field in (
        "DEAL ALERT", "Vehicle:", "Year / Make / Model / Trim:", "Mileage:",
        "Source:", "Location:", "Seller Asking:", "Possible Purchase Price:",
        "Carvana Offer:", "Estimated Wholesale Value:", "Estimated Quick-Sale Value:",
        "Estimated Retail Value:", "Estimated All-In Cost:", "Expected Profit:",
        "Maximum Buy Price:", "Main Risks:", "Why It Looks Underpriced:",
        "Recommendation:",
    ):
        assert field in alert


def test_seller_message_never_leaks_numbers():
    message = draft_seller_message(_tacoma())
    for forbidden in ("profit", "resale", "wholesale", "maximum buy"):
        assert forbidden not in message.lower()
    assert "VIN" in message
    assert "lowest price" in message
