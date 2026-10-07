from __future__ import annotations

import csv
import hashlib
from collections import Counter
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

from ..models import Transaction
from ..sanitize import scrub
from .banks import BankFormat, detect

_DATE_FORMATS = ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d")


class StatementFormatError(Exception):
    pass


def _parse_date(text: str) -> date | None:
    text = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_cents(text: str) -> int | None:
    text = text.strip().replace("$", "").replace(",", "")
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    cents = int((value * 100).to_integral_value(ROUND_HALF_UP))
    return -cents if negative else cents


def _clean(value: str | None) -> str | None:
    value = scrub(" ".join((value or "").split()))
    return value or None


def parse_statement(path: Path) -> list[Transaction]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        fmt = detect(headers)
        if fmt is None:
            # Header names only; never echo data rows.
            raise StatementFormatError(
                f"{path.name}: unrecognised statement format. Headers: {headers}. "
                "Add the layout to src/beli_sync/sources/banks.py."
            )
        return _rows_to_transactions(fmt, reader)


def _rows_to_transactions(fmt: BankFormat, reader: csv.DictReader) -> list[Transaction]:
    out: list[Transaction] = []
    seen: Counter[str] = Counter()
    for raw in reader:
        row = {(k or "").strip().lower(): v for k, v in raw.items()}
        when = _parse_date(row.get(fmt.date) or "")
        cents = _parse_cents(row.get(fmt.amount) or "")
        description = _clean(row.get(fmt.description))
        if when is None or cents is None or not description:
            continue  # blank/summary rows
        cents *= fmt.charge_sign
        base = f"{fmt.name}|{when.isoformat()}|{cents}|{description}"
        seen[base] += 1  # two identical same-day charges stay distinct
        key = hashlib.sha256(f"{base}|{seen[base]}".encode()).hexdigest()[:20]
        out.append(
            Transaction(
                key=key,
                date=when,
                description=description,
                amount_cents=cents,
                source=fmt.name,
                merchant=_clean(row.get(fmt.merchant)) if fmt.merchant else None,
                category=_clean(row.get(fmt.category)) if fmt.category else None,
                location_hint=_clean(row.get(fmt.location)) if fmt.location else None,
            )
        )
    return out


class CsvInboxSource:
    """Reads every *.csv in the inbox folder."""

    def __init__(self, inbox: Path):
        self.inbox = inbox

    def files(self) -> list[Path]:
        return sorted(p for p in self.inbox.glob("*") if p.suffix.lower() == ".csv")

    def fetch(self) -> Iterable[Transaction]:
        for path in self.files():
            yield from parse_statement(path)
