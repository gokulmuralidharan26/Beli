from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Transaction:
    """A card transaction reduced to the few fields we allow into the system.

    Nothing here can hold a card or account number: the input layer only copies
    allowlisted columns and every text field is run through sanitize.scrub().
    """

    key: str  # stable id, used to avoid counting a visit twice
    date: date
    description: str
    amount_cents: int  # charges are positive, credits/payments negative
    source: str  # e.g. "apple_card", "amex"
    merchant: str | None = None  # bank's cleaned merchant name, when provided
    category: str | None = None
    location_hint: str | None = None  # "NEW YORK NY" when the bank gives one

    @property
    def lookup_text(self) -> str:
        return self.merchant or self.description
