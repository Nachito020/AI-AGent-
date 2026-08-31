"""Listing URL verification.

A recommendation is only actionable if you can actually open the listing.
This checks that a discovered URL resolves before it reaches the board, so
dead, expired, or invented links surface as a risk flag instead of a
click that goes nowhere.

Uses only the standard library — no new dependency, and no page parsing.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from .models import RiskFlag, RiskSeverity, VehicleListing

_UA = "Mozilla/5.0 (compatible; dealfinder/0.1; +listing link check)"
_TIMEOUT = 10

# Hosts reserved by RFC 2606/6761 — can never be a real listing.
_RESERVED_SUFFIXES = (".invalid", ".example", ".test", ".localhost")
_RESERVED_HOSTS = ("example.com", "example.org", "example.net")

# Sites that answer automated requests with 403 even for live listings.
# A block is not evidence the listing is dead, so we report it separately.
BOT_BLOCKED_HOSTS = (
    "autotrader.com",
    "govdeals.com",
    "gsaauctions.gov",
    "copart.com",
    "iaai.com",
    "facebook.com",
    "offerup.com",
    "carmax.com",
)


class UrlStatus:
    """Outcome of checking one listing URL."""

    OK = "ok"  # resolved
    DEAD = "dead"  # 404/410/DNS failure — listing is gone or never existed
    PLACEHOLDER = "placeholder"  # reserved domain, cannot be real
    BLOCKED = "blocked"  # site refuses bots; unknown, needs a human click
    MISSING = "missing"  # no URL at all
    ERROR = "error"  # transient network problem


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def check_url(url: str | None) -> tuple[str, str]:
    """Return ``(status, detail)`` for one URL. Never raises."""
    if not url:
        return UrlStatus.MISSING, "No listing URL provided"

    host = _host(url)
    if not host:
        return UrlStatus.PLACEHOLDER, f"Malformed listing URL: {url}"
    if host.endswith(_RESERVED_SUFFIXES) or host in _RESERVED_HOSTS:
        return UrlStatus.PLACEHOLDER, f"Listing URL is a placeholder domain ({host})"

    request = urllib.request.Request(url, method="GET", headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            code = response.status
        if code < 400:
            return UrlStatus.OK, f"Listing URL resolved (HTTP {code})"
        return UrlStatus.DEAD, f"Listing URL returned HTTP {code}"
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 429):
            if any(host.endswith(h) for h in BOT_BLOCKED_HOSTS):
                return (
                    UrlStatus.BLOCKED,
                    f"{host} blocks automated checks (HTTP {exc.code}) — open it yourself",
                )
            return UrlStatus.BLOCKED, f"Listing URL refused automated check (HTTP {exc.code})"
        if exc.code in (404, 410):
            return UrlStatus.DEAD, f"Listing is gone (HTTP {exc.code})"
        return UrlStatus.DEAD, f"Listing URL returned HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return UrlStatus.DEAD, f"Listing URL unreachable ({exc.reason})"
    except Exception as exc:  # timeouts, malformed redirects, TLS problems
        return UrlStatus.ERROR, f"Could not check listing URL ({type(exc).__name__})"


def url_risk_flag(status: str, detail: str) -> RiskFlag | None:
    """Map a URL status to a risk flag, or None when nothing is wrong."""
    if status == UrlStatus.OK:
        return None
    severity = {
        UrlStatus.PLACEHOLDER: RiskSeverity.BLOCKING,
        UrlStatus.DEAD: RiskSeverity.BLOCKING,
        UrlStatus.MISSING: RiskSeverity.WARNING,
        UrlStatus.BLOCKED: RiskSeverity.INFO,
        UrlStatus.ERROR: RiskSeverity.WARNING,
    }[status]
    return RiskFlag(code=f"listing_url_{status}", severity=severity, detail=detail)


def verify_listings(listings: list[VehicleListing]) -> dict[int, tuple[str, str]]:
    """Check every listing's URL concurrently, keyed by ``id(listing)``."""
    if not listings:
        return {}
    with ThreadPoolExecutor(max_workers=min(8, len(listings))) as pool:
        results = list(pool.map(lambda l: check_url(l.url), listings))
    return {id(l): r for l, r in zip(listings, results)}
