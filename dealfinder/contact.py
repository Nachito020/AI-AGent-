"""Seller contact: question checklist and message drafting.

Guardrails (do not remove):
- Never reveal our resale valuation, expected profit, or maximum buy price.
- Never commit to a purchase; every offer needs the owner's approval.
- Drafts are returned for a human to send where the platform's terms allow.
"""

from __future__ import annotations

from .models import VehicleListing

SELLER_QUESTIONS = [
    "Is it still available?",
    "What is the VIN?",
    "Is the title clean and in your name?",
    "Has it been in any accidents?",
    "Any mechanical problems I should know about?",
    "Are there any warning lights on the dash?",
    "Any recent repairs or maintenance?",
    "What is your lowest price?",
    "Would you be open to a pre-purchase inspection?",
]

# Strings that must never appear in outbound seller messages.
_FORBIDDEN_TOPICS = ("resale", "profit", "margin", "flip", "max buy", "maximum buy", "wholesale")


def draft_seller_message(listing: VehicleListing) -> str:
    """Draft a first-contact message for a private-party listing."""
    name = listing.display_name()
    questions = "\n".join(f"- {q}" for q in SELLER_QUESTIONS)
    draft = (
        f"Hi! I saw your {name} listing and I'm interested. A few quick questions:\n"
        f"{questions}\n"
        "Thanks!"
    )
    assert not any(t in draft.lower() for t in _FORBIDDEN_TOPICS), (
        "Seller message must not reveal valuation or profit information"
    )
    return draft
