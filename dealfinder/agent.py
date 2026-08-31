"""Claude-powered research: listing discovery and market valuation.

Both entry points run a web-search research loop on the Claude API and then
extract a structured result. Requires ANTHROPIC_API_KEY (or an `ant auth
login` profile) in the environment.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .config import Settings
from .models import SourceType, TitleStatus, Valuation, ValuationSource, VehicleListing

_MAX_RESEARCH_TURNS = 8


def _web_search_tool(max_uses: int) -> dict:
    return {"type": "web_search_20260209", "name": "web_search", "max_uses": max_uses}


class DiscoveredListing(BaseModel):
    year: Optional[int] = None
    make: str = ""
    model: str = ""
    trim: Optional[str] = None
    mileage: Optional[int] = None
    vin: Optional[str] = None
    asking_price: Optional[float] = None
    location: Optional[str] = None
    title_status: str = "unknown"
    condition_notes: Optional[str] = None
    seller: Optional[str] = None
    source: str = "other"
    source_detail: Optional[str] = None  # site name if not a known source type
    url: Optional[str] = None


class DiscoveryReport(BaseModel):
    listings: list[DiscoveredListing] = Field(default_factory=list)


class ValuationReport(BaseModel):
    carvana_offer: Optional[float] = None
    wholesale_value: Optional[float] = None
    quick_sale_value: Optional[float] = None
    retail_value: Optional[float] = None
    sources: list[ValuationSource] = Field(default_factory=list)
    confidence: float = 0.0
    repair_estimate: Optional[float] = None
    why_underpriced: Optional[str] = None
    notes: Optional[str] = None


def _client():
    import anthropic

    return anthropic.Anthropic()


def _research(client, model: str, system: str, prompt: str, *, max_searches: int = 12) -> str:
    """Run a web-search research loop and return the model's final text."""
    user_turn = {"role": "user", "content": prompt}
    messages = [user_turn]
    response = None
    for _ in range(_MAX_RESEARCH_TURNS):
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=system,
            tools=[_web_search_tool(max_searches)],
            messages=messages,
        )
        if response.stop_reason == "pause_turn":
            messages = [user_turn, {"role": "assistant", "content": response.content}]
            continue
        break

    if response is None or response.stop_reason == "refusal":
        raise RuntimeError("Research request was refused or produced no result")
    return "\n".join(b.text for b in response.content if b.type == "text")


def _extract(client, model: str, text: str, schema: type[BaseModel]) -> BaseModel:
    response = client.messages.parse(
        model=model,
        max_tokens=16000,
        messages=[
            {
                "role": "user",
                "content": (
                    "Extract the structured data from this vehicle research report. "
                    "Use null for anything the report does not state — never invent "
                    f"numbers.\n\n{text}"
                ),
            }
        ],
        output_format=schema,
    )
    return response.parsed_output


DISCOVERY_SYSTEM = """You are a vehicle sourcing researcher for a licensed reseller.
Search public vehicle listing sites for currently-listed vehicles matching the
request, sweeping as many of the requested sites as the search budget allows —
do not stop after the first site that returns results. For each candidate,
capture: year, make, model, trim, mileage, VIN if shown, asking price, location,
title status, condition notes, seller type, source site name, and the listing URL.

Rules:
- Only report listings you actually found, with their real URLs copied exactly
  from the search results. Never invent listings, prices, VINs, or URLs.
- Prefer listings that look priced below typical comparable listings.
- Skip obvious scams (prices far below market with no explanation, stock photos,
  shipping-only sellers)."""


VALUATION_SYSTEM = """You are a used-vehicle pricing analyst. Research the current
market value of the specific vehicle described, using multiple independent
sources: Kelley Blue Book, Edmunds, Carvana, CarGurus, Autotrader, Cars.com,
dealer listings, and recent auction results where available.

Produce, in USD:
- Carvana purchase offer (only if you can find a real figure for this spec)
- Estimated wholesale value
- Estimated quick-sale value (sells within ~2 weeks to a private buyer or dealer)
- Estimated retail value
- A list of the individual data points you found (source, value, kind, URL)
- A confidence score 0-1 based on how many independent sources agree
- An estimated repair cost if the condition notes imply needed repairs
- One or two sentences on whether/why the asking price is below market

Be conservative. If sources disagree widely, say so and lower confidence.
Never invent a source or a number."""


def discover_listings(settings: Settings, query: str) -> list[VehicleListing]:
    """Search the web for candidate listings matching a query."""
    client = _client()
    sites = "\n".join(f"- {s}" for s in settings.search_sites)
    prompt = (
        f"Find up to {settings.max_candidates_per_scan} used-vehicle listings "
        f"({', '.join(settings.vehicle_types)}) near {settings.location} "
        f"(within ~{settings.search_radius_miles} miles) that appear underpriced "
        f"relative to comparable listings. Focus: {query or 'any strong candidates'}. "
        f"Search across these sites:\n{sites}\n"
        "Report each listing with all details you can find, including which "
        "site it came from and its exact URL."
    )
    text = _research(client, settings.model, DISCOVERY_SYSTEM, prompt, max_searches=25)
    report: DiscoveryReport = _extract(client, settings.model, text, DiscoveryReport)

    listings = []
    for item in report.listings:
        data = item.model_dump()
        title = str(data.get("title_status") or "unknown").strip().lower().replace(" ", "_")
        source = str(data.get("source") or "other").strip().lower().replace(" ", "_")
        data["title_status"] = title if title in TitleStatus._value2member_map_ else "unknown"
        data["source"] = source if source in SourceType._value2member_map_ else "other"
        listings.append(VehicleListing(**data))
    return listings


def research_valuation(
    settings: Settings, listing: VehicleListing
) -> tuple[Valuation, Optional[float], Optional[str]]:
    """Research market value for one listing.

    Returns (valuation, repair_estimate_or_None, why_underpriced_or_None).
    """
    client = _client()
    details = listing.model_dump_json(indent=2)
    prompt = (
        "Research the market value of this specific vehicle and report your "
        f"findings:\n{details}"
    )
    text = _research(client, settings.model, VALUATION_SYSTEM, prompt)
    report: ValuationReport = _extract(client, settings.model, text, ValuationReport)

    valuation = Valuation(
        carvana_offer=report.carvana_offer,
        wholesale_value=report.wholesale_value,
        quick_sale_value=report.quick_sale_value,
        retail_value=report.retail_value,
        sources=report.sources,
        confidence=report.confidence,
        notes=report.notes,
    )
    return valuation, report.repair_estimate, report.why_underpriced
