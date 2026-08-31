"""Import listings from JSON or CSV exports.

For marketplaces whose terms of service prohibit automated scraping (e.g.
Facebook Marketplace, OfferUp), export or copy listings manually and feed
them in here — the rest of the pipeline (valuation, costs, profit, risk,
ranking, alerts) runs the same either way.

JSON: a list of objects matching VehicleListing fields.
CSV: a header row with any subset of those field names.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from ..models import SourceType, TitleStatus, VehicleListing

_INT_FIELDS = {"year", "mileage"}
_FLOAT_FIELDS = {"asking_price"}
_BOOL_FIELDS = {
    "accident_history",
    "flood_history",
    "mileage_inconsistent",
    "warning_lights",
}


def _coerce(row: dict) -> dict:
    out: dict = {}
    for key, value in row.items():
        if value in (None, ""):
            continue
        key = key.strip().lower()
        if key in _INT_FIELDS:
            out[key] = int(float(str(value).replace(",", "")))
        elif key in _FLOAT_FIELDS:
            out[key] = float(str(value).replace(",", "").replace("$", ""))
        elif key in _BOOL_FIELDS:
            out[key] = str(value).strip().lower() in ("1", "true", "yes", "y")
        else:
            out[key] = value
    return out


def load_listings(path: str | Path) -> list[VehicleListing]:
    path = Path(path)
    if path.suffix.lower() == ".json":
        rows = json.loads(path.read_text())
    elif path.suffix.lower() == ".csv":
        with path.open(newline="") as f:
            rows = list(csv.DictReader(f))
    else:
        raise ValueError(f"Unsupported listing file type: {path.suffix}")

    listings = []
    for row in rows:
        data = _coerce(dict(row))
        if "title_status" in data:
            value = str(data["title_status"]).strip().lower().replace(" ", "_")
            data["title_status"] = value if value in TitleStatus._value2member_map_ else "unknown"
        if "source" in data:
            value = str(data["source"]).strip().lower().replace(" ", "_")
            data["source"] = value if value in SourceType._value2member_map_ else "other"
        listings.append(VehicleListing(**data))
    return listings
