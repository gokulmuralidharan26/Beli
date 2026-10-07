"""Column layouts for each supported statement format.

Only the columns named here are ever read, so anything else in the file
(Account #, Card Member, addresses...) never enters the program.

Headers below are matched case-insensitively.  If a bank changes its export, an
unrecognised file fails loudly with its header row (never any data rows) so the
layout can be added here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BankFormat:
    name: str
    required: frozenset[str]  # all must be present to match
    forbidden: frozenset[str]  # none may be present
    date: str
    description: str
    amount: str
    merchant: str | None = None
    category: str | None = None
    location: str | None = None
    charge_sign: int = 1  # +1 if charges are positive in this export, -1 if negative


APPLE_CARD = BankFormat(
    name="apple_card",
    required=frozenset({"transaction date", "clearing date", "description", "merchant", "category", "amount (usd)"}),
    forbidden=frozenset(),
    date="transaction date",
    description="description",
    merchant="merchant",
    category="category",
    amount="amount (usd)",
)

CHASE = BankFormat(
    name="chase",
    required=frozenset({"transaction date", "post date", "description", "category", "amount"}),
    forbidden=frozenset(),
    date="transaction date",
    description="description",
    category="category",
    amount="amount",
    charge_sign=-1,
)

# Amex "Date, Description, Amount" plus (in the detailed export) Category and City/State.
AMEX = BankFormat(
    name="amex",
    required=frozenset({"date", "description", "amount"}),
    forbidden=frozenset({"post date", "clearing date"}),
    date="date",
    description="description",
    category="category",
    location="city/state",
    amount="amount",
)

FORMATS = [APPLE_CARD, CHASE, AMEX]  # most specific first


def detect(headers: list[str]) -> BankFormat | None:
    present = {h.strip().lower() for h in headers}
    for fmt in FORMATS:
        if fmt.required <= present and not (fmt.forbidden & present):
            return fmt
    return None
