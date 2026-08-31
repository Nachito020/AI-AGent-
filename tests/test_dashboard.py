from dealfinder.config import Settings
from dealfinder.dashboard import render_dashboard
from dealfinder.models import (
    SourceType,
    TitleStatus,
    Valuation,
    ValuationSource,
    VehicleListing,
)
from dealfinder.pipeline import analyze_listing


def _analysis():
    listing = VehicleListing(
        year=2019, make="Toyota", model="Tacoma", trim="TRD Off-Road",
        mileage=62000, vin="3TMCZ5AN0KM123456", asking_price=21500,
        location="Sacramento, CA", title_status=TitleStatus.CLEAN,
        source=SourceType.CRAIGSLIST, url="https://example.org/tacoma?a=1&b=2",
    )
    valuation = Valuation(
        carvana_offer=27500, wholesale_value=27000,
        quick_sale_value=30500, retail_value=33500, confidence=0.85,
        sources=[
            ValuationSource(source="kbb", value=33500),
            ValuationSource(source="carvana", value=27500, kind="offer"),
        ],
    )
    return analyze_listing(Settings(), listing, valuation)


def test_dashboard_contains_vin_link_carvana_and_costs():
    html = render_dashboard([_analysis()], Settings())
    assert "3TMCZ5AN0KM123456" in html
    assert 'href="https://example.org/tacoma?a=1&amp;b=2"' in html
    assert "Carvana cash offer" in html
    for label in (
        "Purchase price", "Taxes / registration", "Transportation",
        "Repairs", "Inspection / detailing", "All-in cost",
        "Expected profit", "Max buy price", "Seller asking",
    ):
        assert label in html


def test_dashboard_escapes_listing_text():
    analysis = _analysis()
    analysis.listing.location = "<script>alert(1)</script>"
    html = render_dashboard([analysis], Settings())
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_dashboard_fragment_has_no_document_shell():
    fragment = render_dashboard([_analysis()], Settings(), full_page=False)
    assert "<!doctype" not in fragment.lower()
    assert "<title>" in fragment
    full = render_dashboard([_analysis()], Settings(), full_page=True)
    assert full.lower().startswith("<!doctype html>")


def test_dashboard_empty_state():
    html = render_dashboard([], Settings())
    assert "No candidates analyzed yet" in html
