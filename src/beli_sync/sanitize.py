"""Strip card / account numbers from any text before it goes further."""
from __future__ import annotations

import re

REDACTED = "[REDACTED]"

# A full card number: 13-19 contiguous digits, or the printed groupings
# 4-4-4-4 (Visa/MC) and 4-6-5 (Amex) separated by spaces/dashes.  Deliberately
# not "any digits with separators", which would eat store numbers + phone numbers.
_PAN = re.compile(
    r"(?<!\d)(?:\d{13,19}"
    r"|\d{4}([ -])\d{4}\1\d{4}\1\d{1,7}"
    r"|\d{4}([ -])\d{6}\2\d{5})(?!\d)"
)
# XXXX1234, ***1234, ••1234, "ending 1234", "acct 12345"
_MASKED = re.compile(
    r"(?i)(?:x{2,}|\*{3,}|•{2,})[\s-]*\d{3,}"
    r"|\b(?:ending|acct|account)(?:\s+(?:in|no|number|#))?[\s:#-]*\d{4,}"
)


def scrub(text: str | None) -> str:
    if not text:
        return ""
    text = _PAN.sub(REDACTED, text)
    return _MASKED.sub(REDACTED, text)
