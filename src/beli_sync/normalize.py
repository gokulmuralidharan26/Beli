"""Turn messy bank merchant strings into something a places search can match."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .sanitize import REDACTED

# (regex, processor-name).  Payment-processor prefixes carry no restaurant info.
_PROCESSORS = [
    (re.compile(r"^TST\s*\*\s*"), "toast"),
    (re.compile(r"^SQ\s*\*\s*"), "square"),
    (re.compile(r"^PY\s*\*\s*"), "paypal"),
    (re.compile(r"^PAYPAL\s*\*\s*"), "paypal"),
]

# Delivery platforms often append the restaurant name: "DD *DOORDASH JOES PIZZA".
_DELIVERY = [
    (re.compile(r"^DD\s*\*\s*DOORDASH\s*\*?\s*"), "doordash"),
    (re.compile(r"^DOORDASH\s*\*?\s*"), "doordash"),
    (re.compile(r"^UBER\s*\*?\s*EATS\s*\*?\s*"), "ubereats"),
    (re.compile(r"^GRUBHUB\s*\*?\s*"), "grubhub"),
    (re.compile(r"^POSTMATES\s*\*?\s*"), "postmates"),
    (re.compile(r"^SEAMLESS\s*\*?\s*"), "seamless"),
    (re.compile(r"^CAVIAR\s*\*?\s*"), "caviar"),
]
# What's left after a delivery prefix when there's no real restaurant name.
_GENERIC_DELIVERY = {"", "dashpass", "eats", "uber", "order", "delivery", "fee", "tip", "help", "pending", "help.uber.com"}

_STATES = set(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND "
    "OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
)

_STORE_NO = re.compile(r"#\s*\d+")
_PHONE = re.compile(r"\b\d{3}[-. ]?\d{3}[-. ]?\d{4}\b")
_URL = re.compile(r"\b(?:HTTPS?://)?(?:WWW\.)?|\.(?:COM|NET|ORG|CO)\b")


@dataclass(frozen=True)
class ParsedMerchant:
    name: str  # cleaned, display-friendly; may be "" for bare delivery charges
    processor: str | None = None  # "toast", "square", ...
    via_delivery: str | None = None  # "doordash", ...


def _display(text: str) -> str:
    out = " ".join(w.capitalize() for w in text.lower().split())
    return out.replace("'S", "'s")


def parse_merchant(text: str) -> ParsedMerchant:
    s = " ".join(text.upper().split()).replace(REDACTED, "")
    processor = delivery = None

    for pattern, name in _DELIVERY:
        if pattern.match(s):
            delivery, s = name, pattern.sub("", s, count=1)
            break
    for pattern, name in _PROCESSORS:  # processor prefix may follow a delivery one
        if pattern.match(s):
            processor, s = name, pattern.sub("", s, count=1)
            break

    s = _URL.sub("", s)
    s = _STORE_NO.sub(" ", s)
    s = _PHONE.sub(" ", s)
    s = re.sub(r"\s+(US|USA)$", "", s)
    tokens = s.split()
    if len(tokens) > 1 and tokens[-1] in _STATES:  # trailing state code
        tokens.pop()
    if len(tokens) > 2 and tokens[-1].isdigit():  # bare store number: "SHAKE SHACK 12"
        tokens.pop()  # (kept when it would leave one word: "CAFE 123")
    s = " ".join(tokens)
    s = s.strip(" -*.,/")

    if delivery and s.lower() in _GENERIC_DELIVERY:
        s = ""
    return ParsedMerchant(name=_display(s), processor=processor, via_delivery=delivery)


def key_for(name: str) -> str:
    """Stable alias key: lowercase alphanumerics only."""
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
