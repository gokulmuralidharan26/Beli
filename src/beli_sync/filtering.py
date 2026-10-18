"""Decide whether a transaction is a restaurant visit."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .models import Transaction
from .normalize import ParsedMerchant, parse_merchant


@dataclass
class FilterConfig:
    dining_categories: list[str] = field(default_factory=list)
    dining_keywords: list[str] = field(default_factory=list)
    exclude_merchants: list[str] = field(default_factory=list)
    include_overrides: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "FilterConfig":
        data = yaml.safe_load(path.read_text()) or {}
        return cls(**{k: [str(x).lower() for x in data.get(k) or []] for k in cls.__dataclass_fields__})


@dataclass(frozen=True)
class Decision:
    include: bool
    reason: str  # why it was included/excluded, shown by --show-excluded
    parsed: ParsedMerchant
    # No bank category and no name clue: only a restaurant if the places lookup says so.
    needs_place_check: bool = False


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(n in text for n in needles)


def classify(txn: Transaction, cfg: FilterConfig) -> Decision:
    parsed = parse_merchant(txn.lookup_text)
    text = txn.lookup_text.lower()

    def no(reason: str) -> Decision:
        return Decision(False, reason, parsed)

    if txn.amount_cents <= 0:
        return no("payment or refund")

    overridden = _contains_any(text, cfg.include_overrides)
    if not overridden and _contains_any(text, cfg.exclude_merchants):
        return no("excluded merchant")

    # Bank category wins when present; names are only the fallback.
    needs_check = False
    if txn.category:
        if not _contains_any(txn.category.lower(), cfg.dining_categories):
            return no(f"category: {txn.category}")
        dining_reason = "bank category"
    elif parsed.processor == "toast":
        dining_reason = "Toast (TST*) merchant"
    elif _contains_any(text, cfg.dining_keywords):
        dining_reason = "name keyword"
    else:
        needs_check, dining_reason = True, "no category: decided by place lookup"

    if parsed.via_delivery and not parsed.name:
        return no("delivery platform, restaurant unknown")
    if not parsed.name:
        return no("empty merchant name")
    return Decision(True, dining_reason, parsed, needs_place_check=needs_check)
