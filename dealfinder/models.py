"""Core data models for the vehicle deal finder."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TitleStatus(str, Enum):
    CLEAN = "clean"
    SALVAGE = "salvage"
    REBUILT = "rebuilt"
    FLOOD = "flood"
    LEMON = "lemon"
    PARTS_ONLY = "parts_only"
    UNKNOWN = "unknown"


class SourceType(str, Enum):
    FACEBOOK_MARKETPLACE = "facebook_marketplace"
    CRAIGSLIST = "craigslist"
    OFFERUP = "offerup"
    AUTOTRADER = "autotrader"
    CARS_COM = "cars_com"
    CARGURUS = "cargurus"
    EBAY_MOTORS = "ebay_motors"
    CARVANA = "carvana"
    CARMAX = "carmax"
    TRUECAR = "truecar"
    HEMMINGS = "hemmings"
    DEALER = "dealer"
    COPART = "copart"
    IAA = "iaa"
    MANHEIM = "manheim"  # dealer-only
    ADESA = "adesa"  # dealer-only
    GOVDEALS = "govdeals"
    GSA_AUCTIONS = "gsa_auctions"
    PUBLICSURPLUS = "publicsurplus"
    MUNICIBID = "municibid"
    ALLSURPLUS = "allsurplus"
    RITCHIE_BROS = "ritchie_bros"
    IRONPLANET = "ironplanet"
    LOCAL_AUCTION = "local_auction"
    OTHER = "other"


AUCTION_SOURCES = {
    SourceType.COPART,
    SourceType.IAA,
    SourceType.MANHEIM,
    SourceType.ADESA,
    SourceType.GOVDEALS,
    SourceType.GSA_AUCTIONS,
    SourceType.PUBLICSURPLUS,
    SourceType.MUNICIBID,
    SourceType.ALLSURPLUS,
    SourceType.RITCHIE_BROS,
    SourceType.IRONPLANET,
    SourceType.LOCAL_AUCTION,
}


class VehicleListing(BaseModel):
    """A single vehicle listing, normalized across sources."""

    year: Optional[int] = None
    make: str = ""
    model: str = ""
    trim: Optional[str] = None
    mileage: Optional[int] = None
    vin: Optional[str] = None
    asking_price: Optional[float] = None  # asking price or current bid
    location: Optional[str] = None
    title_status: TitleStatus = TitleStatus.UNKNOWN
    condition_notes: Optional[str] = None
    seller: Optional[str] = None
    source: SourceType = SourceType.OTHER
    source_detail: Optional[str] = None  # site name when source is OTHER
    url: Optional[str] = None

    # Optional risk-relevant facts, when known
    accident_history: Optional[bool] = None
    flood_history: Optional[bool] = None
    mileage_inconsistent: Optional[bool] = None
    warning_lights: Optional[bool] = None
    known_mechanical_issues: Optional[str] = None

    @property
    def is_auction(self) -> bool:
        return self.source in AUCTION_SOURCES

    def source_label(self) -> str:
        if self.source == SourceType.OTHER and self.source_detail:
            return self.source_detail
        return self.source.value

    def display_name(self) -> str:
        parts = [str(self.year) if self.year else "?", self.make or "?", self.model or "?"]
        if self.trim:
            parts.append(self.trim)
        return " ".join(parts)


class ValuationSource(BaseModel):
    """One market-value data point from one pricing source."""

    source: str  # e.g. "kbb", "carvana", "edmunds", "comparable_listing"
    value: float
    kind: str = "retail"  # "offer" | "wholesale" | "quick_sale" | "retail"
    url: Optional[str] = None
    note: Optional[str] = None


class Valuation(BaseModel):
    """Aggregated market valuation for a vehicle."""

    carvana_offer: Optional[float] = None
    wholesale_value: Optional[float] = None
    quick_sale_value: Optional[float] = None
    retail_value: Optional[float] = None
    sources: list[ValuationSource] = Field(default_factory=list)
    confidence: float = 0.0  # 0..1
    notes: Optional[str] = None

    @property
    def conservative_resale_value(self) -> Optional[float]:
        """The most conservative realistic resale figure we can defend.

        The quick-sale estimate is the base case (falling back to wholesale).
        A Carvana purchase offer is a firm, guaranteed exit, so it acts as a
        floor: if it exceeds the estimate we can defend the higher number.
        """
        estimate = self.quick_sale_value or self.wholesale_value
        firm_floor = self.carvana_offer
        candidates = [v for v in (estimate, firm_floor) if v is not None and v > 0]
        if not candidates:
            return None
        return max(candidates) if firm_floor else candidates[0]


class CostBreakdown(BaseModel):
    """All-in acquisition cost for one purchase scenario."""

    purchase_price: float
    buyer_premium: float = 0.0
    taxes_registration: float = 0.0
    transportation: float = 0.0
    repairs: float = 0.0
    inspection_detailing: float = 0.0
    other_fees: float = 0.0

    @property
    def all_in_cost(self) -> float:
        return round(
            self.purchase_price
            + self.buyer_premium
            + self.taxes_registration
            + self.transportation
            + self.repairs
            + self.inspection_detailing
            + self.other_fees,
            2,
        )

    @property
    def non_purchase_costs(self) -> float:
        return round(self.all_in_cost - self.purchase_price, 2)


class RiskSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"  # pushes toward manual review
    BLOCKING = "blocking"  # never auto-recommend


class RiskFlag(BaseModel):
    code: str
    severity: RiskSeverity
    detail: str


class Decision(str, Enum):
    RECOMMEND = "RECOMMEND"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    PASS = "PASS"


class DealAnalysis(BaseModel):
    """Full analysis of one listing."""

    listing: VehicleListing
    valuation: Valuation
    costs: CostBreakdown
    expected_profit: Optional[float] = None
    max_buy_price: Optional[float] = None
    max_bid: Optional[float] = None  # auctions only: max hammer-price bid
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    decision: Decision = Decision.PASS
    score: float = 0.0
    why_underpriced: Optional[str] = None
