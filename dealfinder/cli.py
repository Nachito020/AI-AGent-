"""Command-line interface.

    dealfinder scan [--query "..."] [--config config.yaml]
        Discover listings online (Claude web search), value, and rank them.

    dealfinder analyze LISTINGS.json|csv [--no-research]
        Analyze imported listings (e.g. manual exports from marketplaces).

    dealfinder demo
        Run the full deal math offline on bundled sample data (no API key).

    dealfinder contact LISTINGS.json|csv
        Print seller-question drafts for each listing (never auto-sent).
"""

from __future__ import annotations

import argparse
import sys

from .alerts import format_deal_alert, send_alert
from .config import Settings, load_settings
from .contact import draft_seller_message
from .models import Decision
from .pipeline import analyze_batch, run_scan, strong_deals


def _report(settings: Settings, analyses, html_path: str | None = None) -> None:
    strong = strong_deals(settings, analyses)
    review = [a for a in analyses if a.decision == Decision.MANUAL_REVIEW]

    if html_path:
        from .dashboard import write_dashboard

        print(f"Dashboard written to {write_dashboard(analyses, settings, html_path)}")

    if not analyses:
        print("No candidates cleared the profit floor. (Passing on marginal deals is the job.)")
        return

    for analysis in strong:
        send_alert(analysis)

    if review:
        print(f"\n--- {len(review)} candidate(s) flagged for MANUAL REVIEW ---")
        for analysis in review:
            print("\n" + format_deal_alert(analysis))

    if not strong and not review:
        print("No deals met the $%.0f minimum profit bar." % settings.min_profit)


def cmd_scan(args) -> int:
    settings = load_settings(args.config)
    print(f"Scanning near {settings.location} (min profit ${settings.min_profit:,.0f})...")
    analyses = run_scan(settings, args.query or "")
    _report(settings, analyses, args.html)
    return 0


def cmd_analyze(args) -> int:
    from .sources.manual_import import load_listings

    settings = load_settings(args.config)
    listings = load_listings(args.file)
    print(f"Analyzing {len(listings)} imported listing(s)...")
    analyses = analyze_batch(settings, listings, research=not args.no_research)
    _report(settings, analyses, args.html)
    return 0


def cmd_contact(args) -> int:
    from .sources.manual_import import load_listings

    for listing in load_listings(args.file):
        print(f"\n### Draft for {listing.display_name()} ({listing.url or 'no url'})")
        print(draft_seller_message(listing))
    print("\nDrafts only — review and send manually; never commit to a purchase.")
    return 0


def cmd_demo(args) -> int:
    from pathlib import Path

    from .models import Valuation, ValuationSource
    from .pipeline import analyze_listing, rank_deals
    from .sources.manual_import import load_listings

    settings = load_settings(args.config)
    sample = Path(__file__).parent.parent / "listings" / "sample_listings.json"
    listings = load_listings(sample)

    # Canned valuations so the demo runs offline. Real runs research these.
    demo_values = {
        "2019 Toyota Tacoma": Valuation(
            carvana_offer=27500,
            wholesale_value=27000,
            quick_sale_value=30500,
            retail_value=33500,
            confidence=0.85,
            sources=[
                ValuationSource(source="kbb", value=33500, kind="retail"),
                ValuationSource(source="carvana", value=27500, kind="offer"),
                ValuationSource(source="cargurus_comps", value=30800, kind="quick_sale"),
            ],
        ),
        "2018 Honda CR-V": Valuation(
            wholesale_value=16500,
            quick_sale_value=18500,
            retail_value=20500,
            confidence=0.8,
            sources=[
                ValuationSource(source="edmunds", value=20500, kind="retail"),
                ValuationSource(source="autotrader_comps", value=18600, kind="quick_sale"),
            ],
        ),
        "2015 BMW 328i": Valuation(
            wholesale_value=8000,
            quick_sale_value=9500,
            retail_value=11500,
            confidence=0.5,
            sources=[ValuationSource(source="kbb", value=11500, kind="retail")],
        ),
    }

    analyses = []
    for listing in listings:
        key = f"{listing.year} {listing.make} {listing.model}"
        valuation = demo_values.get(key, Valuation())
        analyses.append(
            analyze_listing(
                settings, listing, valuation,
                why_underpriced="Demo data: priced below comparable listings",
            )
        )
    rank_deals(analyses)  # assigns scores in place on non-PASS deals
    _report(settings, analyses, args.html)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dealfinder", description=__doc__)
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Discover, value, and rank deals online")
    p_scan.add_argument("--query", default="", help="Focus, e.g. 'Toyota trucks under $25k'")
    p_scan.add_argument("--html", default=None, help="Also write an HTML dashboard here")
    p_scan.set_defaults(func=cmd_scan)

    p_an = sub.add_parser("analyze", help="Analyze imported listings (JSON/CSV)")
    p_an.add_argument("file")
    p_an.add_argument("--no-research", action="store_true", help="Skip API valuation")
    p_an.add_argument("--html", default=None, help="Also write an HTML dashboard here")
    p_an.set_defaults(func=cmd_analyze)

    p_ct = sub.add_parser("contact", help="Draft seller questions for listings")
    p_ct.add_argument("file")
    p_ct.set_defaults(func=cmd_contact)

    p_demo = sub.add_parser("demo", help="Offline demo on sample data")
    p_demo.add_argument("--html", default=None, help="Also write an HTML dashboard here")
    p_demo.set_defaults(func=cmd_demo)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
