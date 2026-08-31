"""HTML dashboard generator.

Renders a set of deal analyses into a single self-contained HTML file:
per-vehicle cards with VIN, listing link, Carvana cash offer, the full
itemized extra-cost breakdown, a value-vs-cost bar, and risk flags.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

from .config import Settings
from .models import DealAnalysis, Decision

_FONTS = (
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2'
    "?family=Barlow+Semi+Condensed:wght@600;700"
    "&family=Source+Sans+3:ital,wght@0,400;0,600;1,400"
    '&family=IBM+Plex+Mono:wght@400;600&display=swap">'
)

_CSS = """
:root {
  color-scheme: light;
  --bg: #f3f4f6;
  --surface: #ffffff;
  --surface-2: #e9ecef;
  --ink: #171d24;
  --muted: #5a6572;
  --line: #d4d9df;
  --accent: #1c5cab;
  --good-bg: #d8efe3; --good-ink: #0c5c38;
  --warn-bg: #f7e8c8; --warn-ink: #7a5200;
  --pass-bg: #e5e7ea; --pass-ink: #4a545f;
  --bar-purchase: #2a78d6;
  --bar-extras: #eb6834;
  --bar-profit: #1baf7a;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #14181d;
    --surface: #1c2229;
    --surface-2: #242c35;
    --ink: #e8ebee;
    --muted: #98a3ae;
    --line: #333d48;
    --accent: #5598e7;
    --good-bg: #17402e; --good-ink: #7ed8ac;
    --warn-bg: #453410; --warn-ink: #e5b95e;
    --pass-bg: #2a323b; --pass-ink: #a3adb8;
    --bar-purchase: #3987e5;
    --bar-extras: #d95926;
    --bar-profit: #199e70;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #14181d;
  --surface: #1c2229;
  --surface-2: #242c35;
  --ink: #e8ebee;
  --muted: #98a3ae;
  --line: #333d48;
  --accent: #5598e7;
  --good-bg: #17402e; --good-ink: #7ed8ac;
  --warn-bg: #453410; --warn-ink: #e5b95e;
  --pass-bg: #2a323b; --pass-ink: #a3adb8;
  --bar-purchase: #3987e5;
  --bar-extras: #d95926;
  --bar-profit: #199e70;
}
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 16px/1.5 "Source Sans 3", "Segoe UI", system-ui, sans-serif;
}
.wrap { max-width: 960px; margin: 0 auto; padding: 32px 20px 64px; }
h1, h2, .deal-title {
  font-family: "Barlow Semi Condensed", "Arial Narrow", sans-serif;
  text-wrap: balance;
  margin: 0;
}
h1 { font-size: 2rem; font-weight: 700; }
.sub { color: var(--muted); margin: 4px 0 0; }
.kpis {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px; margin: 24px 0 32px;
}
.kpi {
  background: var(--surface); border: 1px solid var(--line);
  border-radius: 6px; padding: 12px 16px;
}
.kpi .label {
  font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--muted);
}
.kpi .value {
  font-family: "IBM Plex Mono", monospace; font-size: 1.5rem; font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.section-h {
  font-size: 1.15rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--muted); margin: 32px 0 12px;
}
.card {
  background: var(--surface); border: 1px solid var(--line);
  border-radius: 8px; padding: 20px; margin-bottom: 20px;
}
.deal-head {
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 10px 14px;
  margin-bottom: 4px;
}
.deal-title { font-size: 1.45rem; font-weight: 700; }
.pill {
  font-size: 0.72rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.05em; padding: 3px 10px; border-radius: 999px;
}
.pill.recommend { background: var(--good-bg); color: var(--good-ink); }
.pill.review { background: var(--warn-bg); color: var(--warn-ink); }
.pill.pass { background: var(--pass-bg); color: var(--pass-ink); }
.facts {
  display: flex; flex-wrap: wrap; gap: 6px 24px;
  color: var(--muted); font-size: 0.92rem; margin-bottom: 16px;
}
.vin { font-family: "IBM Plex Mono", monospace; font-size: 0.88rem; }
a.listing {
  color: var(--accent); font-weight: 600; text-decoration: none;
}
a.listing:hover, a.listing:focus-visible { text-decoration: underline; }
a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
@media (max-width: 700px) { .grid2 { grid-template-columns: 1fr; } }
.money-table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
.money-table caption {
  text-align: left; font-size: 0.72rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted);
  padding-bottom: 6px;
}
.money-table td { padding: 3px 0; }
.money-table td.num {
  text-align: right; font-family: "IBM Plex Mono", monospace;
  font-variant-numeric: tabular-nums;
}
.money-table tr.total td {
  border-top: 1px solid var(--line); font-weight: 600; padding-top: 6px;
}
.money-table tr.profit td { color: var(--good-ink); font-weight: 600; }
.money-table tr.loss td { color: var(--warn-ink); font-weight: 600; }
.bar-wrap { margin: 18px 0 6px; }
.bar {
  display: flex; gap: 2px; height: 22px; border-radius: 4px; overflow: hidden;
  background: var(--surface-2);
}
.bar .seg-purchase { background: var(--bar-purchase); }
.bar .seg-extras { background: var(--bar-extras); }
.bar .seg-profit { background: var(--bar-profit); }
.bar-legend {
  display: flex; flex-wrap: wrap; gap: 4px 18px; font-size: 0.85rem;
  color: var(--muted); margin-top: 6px;
}
.bar-legend .swatch {
  display: inline-block; width: 10px; height: 10px; border-radius: 2px;
  margin-right: 6px;
}
.bar-legend .num {
  font-family: "IBM Plex Mono", monospace; font-variant-numeric: tabular-nums;
  color: var(--ink);
}
.callouts { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
.callout {
  border: 1px solid var(--line); border-radius: 6px; padding: 8px 14px;
  background: var(--surface-2);
}
.callout .label {
  font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--muted);
}
.callout .value {
  font-family: "IBM Plex Mono", monospace; font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.risks { margin: 14px 0 0; padding-left: 20px; font-size: 0.92rem; }
.risks li { margin: 2px 0; }
.why { margin-top: 12px; font-size: 0.95rem; font-style: italic; color: var(--muted); }
.empty {
  background: var(--surface); border: 1px dashed var(--line); border-radius: 8px;
  padding: 24px; color: var(--muted);
}
.foot { margin-top: 40px; font-size: 0.85rem; color: var(--muted); }
"""


def _money(v: float | None) -> str:
    return f"${v:,.0f}" if v is not None else "—"


def _esc(v) -> str:
    return html.escape(str(v)) if v not in (None, "") else "—"


def _pill(decision: Decision) -> str:
    cls, label = {
        Decision.RECOMMEND: ("recommend", "Recommended"),
        Decision.MANUAL_REVIEW: ("review", "Manual review"),
        Decision.PASS: ("pass", "Pass"),
    }[decision]
    return f'<span class="pill {cls}">{label}</span>'


def _cost_rows(a: DealAnalysis) -> str:
    c = a.costs
    items = [
        ("Purchase price", c.purchase_price),
        ("Buyer premium", c.buyer_premium),
        ("Taxes / registration", c.taxes_registration),
        ("Transportation", c.transportation),
        ("Repairs", c.repairs),
        ("Inspection / detailing", c.inspection_detailing),
        ("Other fees", c.other_fees),
    ]
    rows = "".join(
        f"<tr><td>{label}</td><td class='num'>{_money(v)}</td></tr>"
        for label, v in items
        if v or label == "Purchase price"
    )
    rows += (
        f"<tr class='total'><td>All-in cost</td>"
        f"<td class='num'>{_money(c.all_in_cost)}</td></tr>"
    )
    profit = a.expected_profit
    if profit is not None:
        cls = "profit" if profit >= 0 else "loss"
        rows += (
            f"<tr class='{cls}'><td>Expected profit</td>"
            f"<td class='num'>{_money(profit)}</td></tr>"
        )
    return rows


def _value_rows(a: DealAnalysis) -> str:
    v = a.valuation
    items = [
        ("Carvana cash offer", v.carvana_offer),
        ("Wholesale value", v.wholesale_value),
        ("Quick-sale value", v.quick_sale_value),
        ("Retail value", v.retail_value),
    ]
    rows = "".join(
        f"<tr><td>{label}</td><td class='num'>{_money(val)}</td></tr>"
        for label, val in items
    )
    resale = v.conservative_resale_value
    rows += (
        f"<tr class='total'><td>Conservative resale</td>"
        f"<td class='num'>{_money(resale)}</td></tr>"
    )
    return rows


def _cost_bar(a: DealAnalysis) -> str:
    resale = a.valuation.conservative_resale_value
    if not resale or resale <= 0:
        return ""
    purchase = a.costs.purchase_price
    extras = a.costs.non_purchase_costs
    profit = max(resale - purchase - extras, 0.0)
    total = max(resale, purchase + extras)

    def seg(cls: str, label: str, value: float) -> str:
        if value <= 0:
            return ""
        width = value / total * 100
        return (
            f'<div class="seg-{cls}" style="width:{width:.1f}%" '
            f'title="{label}: {_money(value)}"></div>'
        )

    def legend(cls: str, label: str, value: float) -> str:
        var = {"purchase": "--bar-purchase", "extras": "--bar-extras", "profit": "--bar-profit"}[cls]
        return (
            f'<span><span class="swatch" style="background:var({var})"></span>'
            f'{label} <span class="num">{_money(value)}</span></span>'
        )

    over = purchase + extras - resale
    over_note = (
        f'<div class="bar-legend">Costs exceed conservative resale by '
        f'<span class="num">{_money(over)}</span></div>'
        if over > 0
        else ""
    )
    return (
        '<div class="bar-wrap">'
        f'<div class="bar" role="img" aria-label="Cost vs value: purchase {_money(purchase)}, '
        f'extra costs {_money(extras)}, profit {_money(profit)} '
        f'against conservative resale {_money(resale)}">'
        + seg("purchase", "Purchase", purchase)
        + seg("extras", "Extra costs", extras)
        + seg("profit", "Profit headroom", profit)
        + "</div>"
        + '<div class="bar-legend">'
        + legend("purchase", "Purchase", purchase)
        + legend("extras", "Extra costs", extras)
        + legend("profit", "Profit", profit)
        + "</div>"
        + over_note
        + "</div>"
    )


def _card(a: DealAnalysis) -> str:
    l = a.listing
    link = (
        f'<a class="listing" href="{html.escape(l.url, quote=True)}" '
        f'target="_blank" rel="noopener">View listing on {_esc(l.source.value)} ↗</a>'
        if l.url
        else f"Source: {_esc(l.source.value)}"
    )
    facts = [
        f'<span class="vin">VIN {_esc(l.vin)}</span>',
        f"{l.mileage:,} mi" if l.mileage else "Mileage —",
        _esc(l.location),
        f"Title: {_esc(l.title_status.value)}",
        link,
    ]
    callouts = [
        ("Seller asking", l.asking_price),
        ("Max buy price", a.max_buy_price),
    ]
    if a.max_bid is not None:
        callouts.append(("Max auction bid", a.max_bid))
    callouts_html = "".join(
        f'<div class="callout"><div class="label">{label}</div>'
        f'<div class="value">{_money(v)}</div></div>'
        for label, v in callouts
    )
    risks = "".join(f"<li>{_esc(f.detail)}</li>" for f in a.risk_flags)
    risks_html = f'<ul class="risks">{risks}</ul>' if risks else ""
    why = f'<p class="why">{_esc(a.why_underpriced)}</p>' if a.why_underpriced else ""
    score = f'<span class="sub">score {a.score:.0f}</span>' if a.score else ""

    return f"""<article class="card">
  <div class="deal-head">
    <span class="deal-title">{_esc(l.display_name())}</span>
    {_pill(a.decision)} {score}
  </div>
  <div class="facts">{''.join(f'<span>{f}</span>' for f in facts)}</div>
  <div class="grid2">
    <table class="money-table"><caption>Market value</caption>{_value_rows(a)}</table>
    <table class="money-table"><caption>Costs to think about</caption>{_cost_rows(a)}</table>
  </div>
  {_cost_bar(a)}
  <div class="callouts">{callouts_html}</div>
  {risks_html}
  {why}
</article>"""


def render_dashboard(
    analyses: list[DealAnalysis],
    settings: Settings,
    *,
    generated_at: datetime | None = None,
    full_page: bool = True,
) -> str:
    """Render analyses to HTML. ``full_page=False`` omits the document shell."""
    generated_at = generated_at or datetime.now(timezone.utc)
    ordered = sorted(analyses, key=lambda a: (a.expected_profit or 0), reverse=True)
    recommended = [a for a in ordered if a.decision == Decision.RECOMMEND]
    review = [a for a in ordered if a.decision == Decision.MANUAL_REVIEW]
    passed = [a for a in ordered if a.decision == Decision.PASS]
    total_profit = sum(a.expected_profit or 0 for a in recommended)

    kpis = [
        ("Recommended deals", str(len(recommended))),
        ("Manual review", str(len(review))),
        ("Passed (marginal)", str(len(passed))),
        ("Expected profit (recommended)", _money(total_profit)),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="label">{label}</div>'
        f'<div class="value">{value}</div></div>'
        for label, value in kpis
    )

    def section(title: str, deals: list[DealAnalysis]) -> str:
        if not deals:
            return ""
        cards = "".join(_card(a) for a in deals)
        return f'<h2 class="section-h">{title}</h2>{cards}'

    body = section("Deals worth pursuing", recommended) + section(
        "Needs manual review", review
    ) + section("Passed — under the profit floor", passed)
    if not body:
        body = (
            '<div class="empty">No candidates analyzed yet. Run '
            "<code>dealfinder scan</code> or <code>dealfinder analyze</code>.</div>"
        )

    content = f"""<title>Deal Finder Lot Board</title>
{_FONTS}
<style>{_CSS}</style>
<div class="wrap">
  <header>
    <h1>Deal Finder Lot Board</h1>
    <p class="sub">{html.escape(settings.location)} · profit floor {_money(settings.min_profit)}
    · generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')}</p>
  </header>
  <div class="kpis">{kpi_html}</div>
  {body}
  <p class="foot">Valuations and fee schedules are estimates — verify title, VIN history,
  and current auction fees before any offer. Max buy price / max bid are ceilings, not targets.
  Nothing here is a purchase commitment.</p>
</div>"""

    if not full_page:
        return content
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "</head>\n<body>\n" + content + "\n</body>\n</html>\n"
    )


def write_dashboard(
    analyses: list[DealAnalysis], settings: Settings, path: str
) -> str:
    from pathlib import Path

    out = Path(path)
    out.write_text(render_dashboard(analyses, settings))
    return str(out)
