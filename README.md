# AI Vehicle Deal Finder Agent

An autonomous agent that hunts for underpriced cars, pickup trucks, SUVs, and
vans that can realistically generate **at least $5,000 profit** after all
costs — and ignores everything else.

The core rule: the goal is not lots of listings; it's a small number of
vehicles with a clear, defensible pricing mismatch.

## How it works

```
discover -> dedupe -> value -> cost -> profit -> risk -> rank -> alert
```

1. **Discover** — Claude (with server-side web search) sweeps public listing
   sites (Craigslist, Autotrader, Cars.com, CarGurus, dealer sites, public
   auction pages) for candidates. Listings from login-walled marketplaces
   (Facebook Marketplace, OfferUp) and auction accounts (Copart, IAA,
   GovDeals, Ritchie Bros., IronPlanet) are fed in via `dealfinder analyze`
   from JSON/CSV exports — see *A note on logins* below.
2. **Dedupe** — duplicates removed by VIN, or fuzzy year/make/model/mileage/price.
3. **Value** — Claude researches each candidate against multiple pricing
   sources (KBB, Edmunds, Carvana, CarGurus, Autotrader, comps, auction
   results) and reports Carvana offer, wholesale, quick-sale, and retail
   values with a confidence score. A low asking price alone is never treated
   as evidence of a deal.
4. **Cost** — all-in cost = purchase + buyer premium (tiered auction
   schedules built in for Copart/IAA/etc.) + taxes/registration + transport +
   repairs + inspection/detailing + other fees.
5. **Profit** — expected profit = conservative resale value − all-in cost.
   The conservative resale value is the quick-sale estimate, with a firm
   Carvana offer acting as a guaranteed floor.
6. **Max buy price** — worked backward from resale value; for auctions, the
   max *bid* is solved so that bid + premium(bid) + tax(bid) + fees still
   clears the profit floor.
7. **Risk** — branded titles, flood/accident history, mileage
   inconsistencies, missing VINs, suspiciously low prices, thin or
   low-confidence valuations. Anything unverifiable goes to **MANUAL REVIEW**
   instead of being recommended. Branded titles and flood history are never
   auto-recommended.
8. **Rank & alert** — deals scored on profit, valuation confidence, discount
   to market, and liquidity; only deals clearing **$5,000 expected profit**
   surface, with $7,500+ preferred. Alerts use the standard `DEAL ALERT`
   template.

## Install

```bash
pip install -e ".[dev]"
cp config.example.yaml config.yaml   # then edit location, tax rate, etc.
cp .env.example .env                 # add ANTHROPIC_API_KEY
```

## Usage

```bash
# Offline demo of the full deal math on sample data (no API key needed)
dealfinder demo

# Live scan: discover candidates online, research values, rank deals
dealfinder scan --query "Toyota/Honda trucks and SUVs under $25k"

# Analyze listings you exported yourself (JSON or CSV)
dealfinder analyze listings/my_export.json
dealfinder analyze listings/my_export.csv --no-research   # skip API valuation

# Draft seller questions (drafts only — you send them)
dealfinder contact listings/my_export.json
```

`listings/sample_listings.json` shows the JSON shape; CSV files use the same
field names as a header row.

## Guardrails (by design)

- **PASS** on anything under $5,000 expected profit — marginal deals are noise.
- Unverifiable valuation or condition ⇒ **MANUAL REVIEW**, never a recommendation.
- Seller messages ask the availability/VIN/title/accidents/mechanical/
  warning-lights/repairs/lowest-price/inspection questions and **never**
  reveal resale value, expected profit, or the max buy price (enforced in
  `dealfinder/contact.py`).
- The agent never commits to a purchase — it drafts, calculates, and alerts;
  buying decisions are yours.
- Never pay above the calculated max buy price / max bid.

## A note on logins and scraping

Some sources (Facebook Marketplace, OfferUp, and auction accounts) sit behind
logins, and automated scraping of several of them violates their Terms of
Service. This project therefore does **not** ship credentialed scrapers for
those sites. Instead:

- Public sites are searched via Claude's web search.
- For login-walled sources, export/copy listings and run
  `dealfinder analyze` — the whole valuation/cost/profit/risk pipeline is
  identical from there.
- `.env.example` reserves credential slots so an official API or an
  export-based integration (e.g. Copart's data services) can be wired into
  `dealfinder/sources/` later.

## Configuration

See `config.example.yaml`: location and radius, profit gates, per-scan
candidate cap, default cost assumptions (tax rate, registration, transport,
repair buffer, inspection), and the Claude model (default `claude-opus-5`).
Auction fee schedules live in `dealfinder/costs.py` and are simplified
defaults — verify against the auction house's current fee table before
bidding.

**Licensed dealers:** buying for resale inventory usually means no sales tax
at purchase (resale exemption) and no registration in your name — set
`tax_rate: 0` and a small `registration_fee` buffer per the dealer block in
`config.example.yaml`. That lowers all-in cost and raises the max buy price
the agent will approve. Dealer-only auction sources (`manheim`, `adesa`) are
supported with tiered buy-fee schedules. State rules vary; verify the
exemption with your DMV/state tax authority.

## Tests

```bash
pytest
```

Covers the buyer-premium tiers, the spec's max-buy-price example
($34,000 quick-sale − $5,000 profit − $2,000 expenses = $27,000 max), the
max-bid solver (bidding at the cap clears the profit floor; 5% over does
not), risk gating, dedupe, ranking, alert formatting, and the
no-leaks-to-sellers rule.

## Disclaimer

Valuations and fee schedules are estimates. Always verify title, history
(VIN check), condition, and current auction fees before making an offer or
bid. Alerts are decision support, not purchase commitments.
