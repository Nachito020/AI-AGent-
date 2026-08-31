from dealfinder.config import Settings
from dealfinder.models import Decision, RiskSeverity, TitleStatus, Valuation, ValuationSource, VehicleListing
from dealfinder.pipeline import analyze_listing
from dealfinder.verify import UrlStatus, check_url, url_risk_flag


def test_placeholder_domains_rejected_without_network():
    for url in (
        "https://example.invalid/SAMPLE-DATA/2019-toyota-tacoma",
        "https://example.com/listing",
        "http://foo.test/listing",
    ):
        status, detail = check_url(url)
        assert status == UrlStatus.PLACEHOLDER, url
        assert detail


def test_missing_url():
    assert check_url(None)[0] == UrlStatus.MISSING
    assert check_url("")[0] == UrlStatus.MISSING


def test_risk_flag_severities():
    assert url_risk_flag(UrlStatus.OK, "fine") is None
    assert url_risk_flag(UrlStatus.DEAD, "gone").severity == RiskSeverity.BLOCKING
    assert url_risk_flag(UrlStatus.PLACEHOLDER, "fake").severity == RiskSeverity.BLOCKING
    assert url_risk_flag(UrlStatus.MISSING, "none").severity == RiskSeverity.WARNING
    # A site that blocks bots is informational only — it must not gate a deal.
    assert url_risk_flag(UrlStatus.BLOCKED, "403").severity == RiskSeverity.INFO


def _good_deal(url_status):
    listing = VehicleListing(
        year=2019, make="Toyota", model="Tacoma", vin="3TMCZ5AN0KM123456",
        asking_price=21500, title_status=TitleStatus.CLEAN, source="craigslist",
        url="https://example.org/tacoma",
    )
    valuation = Valuation(
        carvana_offer=27500, wholesale_value=27000, quick_sale_value=30500,
        retail_value=33500, confidence=0.85,
        sources=[
            ValuationSource(source="kbb", value=33500),
            ValuationSource(source="carvana", value=27500, kind="offer"),
        ],
    )
    return analyze_listing(Settings(), listing, valuation, url_status=url_status)


def test_dead_link_blocks_recommendation():
    analysis = _good_deal((UrlStatus.DEAD, "Listing is gone (HTTP 404)"))
    assert analysis.expected_profit >= 5000  # the math still says it's profitable
    assert analysis.decision == Decision.MANUAL_REVIEW  # but you can't open it


def test_bot_blocked_link_still_recommendable():
    analysis = _good_deal((UrlStatus.BLOCKED, "site blocks automated checks"))
    assert analysis.decision == Decision.RECOMMEND
    assert any(f.code == "listing_url_blocked" for f in analysis.risk_flags)


def test_ok_link_adds_no_flag():
    analysis = _good_deal((UrlStatus.OK, "resolved"))
    assert analysis.decision == Decision.RECOMMEND
    assert not any(f.code.startswith("listing_url") for f in analysis.risk_flags)
