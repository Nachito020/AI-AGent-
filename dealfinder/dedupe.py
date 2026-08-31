"""Duplicate-listing removal across sources."""

from __future__ import annotations

from .models import VehicleListing


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _fuzzy_key(listing: VehicleListing) -> tuple:
    """Loose identity for listings without a VIN.

    Two listings are considered the same vehicle when year/make/model match
    and mileage and price land in the same coarse buckets.
    """
    mileage_bucket = (listing.mileage // 1000) if listing.mileage else None
    price_bucket = round(listing.asking_price / 500) if listing.asking_price else None
    return (
        listing.year,
        _norm(listing.make),
        _norm(listing.model),
        mileage_bucket,
        price_bucket,
    )


def dedupe_listings(listings: list[VehicleListing]) -> list[VehicleListing]:
    """Remove duplicates, preferring the listing with the most information.

    VIN is the strong key; listings without a VIN fall back to a fuzzy
    year/make/model/mileage/price key.
    """
    def richness(l: VehicleListing) -> int:
        return sum(
            1
            for v in (
                l.vin, l.trim, l.mileage, l.asking_price, l.location,
                l.condition_notes, l.seller, l.url,
            )
            if v
        )

    by_key: dict[tuple, VehicleListing] = {}
    for listing in listings:
        key = ("vin", listing.vin.strip().upper()) if listing.vin else _fuzzy_key(listing)
        existing = by_key.get(key)
        if existing is None or richness(listing) > richness(existing):
            by_key[key] = listing
    return list(by_key.values())
