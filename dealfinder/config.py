"""Runtime configuration loaded from config.yaml (see config.example.yaml)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .profit import MIN_PROFIT, PREFERRED_PROFIT


class CostDefaults(BaseModel):
    tax_rate: float = 0.0725
    registration_fee: float = 350.0
    transport_cost: float = 300.0
    repair_estimate: float = 1000.0
    inspection_detailing: float = 250.0
    other_fees: float = 0.0


class Settings(BaseModel):
    location: str = "United States"
    search_radius_miles: int = 150
    min_profit: float = MIN_PROFIT
    preferred_profit: float = PREFERRED_PROFIT
    vehicle_types: list[str] = Field(
        default_factory=lambda: ["cars", "pickup trucks", "SUVs", "vans"]
    )
    max_candidates_per_scan: int = 10
    # Public sites the discovery agent sweeps, most-reachable first.
    # Craigslist and Cars.com were verified to serve listings to automated
    # requests; Autotrader, GovDeals and GSA Auctions return HTTP 403 to bots,
    # so they are listed last and often need a manual export instead.
    # Login-walled marketplaces are handled via `dealfinder analyze` imports.
    search_sites: list[str] = Field(
        default_factory=lambda: [
            "Craigslist",
            "Cars.com",
            "CarGurus",
            "eBay Motors",
            "TrueCar",
            "Edmunds listings",
            "AutoTempest (aggregator)",
            "Hemmings",
            "franchise and independent dealer websites",
            "Carvana",
            "PublicSurplus",
            "Municibid",
            "AllSurplus",
            "local auction house listings",
            "Autotrader",
            "GovDeals",
            "GSA Auctions (govt fleet, no buyer premium)",
        ]
    )
    # Check that each discovered listing URL actually resolves before it
    # reaches the board. A dead or placeholder link blocks a recommendation.
    verify_listing_urls: bool = True
    costs: CostDefaults = Field(default_factory=CostDefaults)
    model: str = "claude-opus-5"


def load_settings(path: str | Path | None = None) -> Settings:
    candidates = [Path(path)] if path else [Path("config.yaml"), Path("config.example.yaml")]
    for candidate in candidates:
        if candidate.exists():
            data = yaml.safe_load(candidate.read_text()) or {}
            return Settings(**data)
    return Settings()
