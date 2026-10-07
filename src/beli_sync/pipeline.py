"""The monthly run: import -> filter -> resolve -> dedupe -> review -> record."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date

from .db import Database
from .filtering import FilterConfig, classify
from .normalize import key_for
from .places import PlacesClient, Place, rank
from .review import Candidate, Decision, Reviewer
from .sources.base import TransactionSource


@dataclass
class RunResult:
    stats: Counter = field(default_factory=Counter)
    excluded: list[tuple[str, str]] = field(default_factory=list)  # (description, reason)
    candidates: list[Candidate] = field(default_factory=list)
    approved: list[dict] = field(default_factory=list)  # entries for the checklist
    unreviewed: int = 0


def build_candidates(source: TransactionSource, db: Database, places: PlacesClient, cfg: FilterConfig,
                     home_location: str = "", result: RunResult | None = None, record_known: bool = True) -> RunResult:
    result = result or RunResult()
    stats = result.stats

    groups: dict[str, list] = defaultdict(list)  # alias key -> [(txn, decision)]
    for txn in source.fetch():
        stats["transactions"] += 1
        if db.has_visit(txn.key):
            stats["already processed"] += 1
            continue
        d = classify(txn, cfg)
        if not d.include:
            stats["not dining"] += 1
            result.excluded.append((txn.lookup_text, d.reason))
            continue
        groups[key_for(d.parsed.name)].append((txn, d))

    by_place: dict[str, Candidate] = {}
    unmatched: list[Candidate] = []
    for key, items in groups.items():
        alias = db.get_alias(key)
        if alias and alias["decision"] == "skip":
            stats["skipped before"] += len(items)
            continue

        txn0, d0 = items[0]
        hint = txn0.location_hint
        via_delivery = bool(d0.parsed.via_delivery)
        if alias:  # previously resolved to a place you already approved
            known = db.get_restaurant(alias["place_id"])
            match_place = Place(known["place_id"], known["name"], known["address"] or "")
            matches = rank(d0.parsed.name, hint, [match_place], via_delivery)
        else:
            query = f"{d0.parsed.name} {hint or home_location}".strip()
            matches = rank(d0.parsed.name, hint, places.search(query), via_delivery)
        best = matches[0] if matches else None

        cand = Candidate(
            name=d0.parsed.name, keys={key}, match=best, hint=hint, via_delivery=via_delivery,
            bank_strings=sorted({t.lookup_text for t, _ in items}), visits=[t for t, _ in items],
        )
        if best is None:
            unmatched.append(cand)
        elif best.place.place_id in by_place:  # two bank spellings, one restaurant
            merged = by_place[best.place.place_id]
            merged.keys |= cand.keys
            merged.bank_strings = sorted(set(merged.bank_strings) | set(cand.bank_strings))
            merged.visits += cand.visits
        else:
            by_place[best.place.place_id] = cand

    for place_id, cand in list(by_place.items()):
        if db.get_restaurant(place_id):  # already in Beli/approved: just count the visits
            stats["visits at known restaurants"] += len(cand.visits)
            if record_known:
                for t in cand.visits:
                    db.add_visit(t.key, place_id, t.date, t.amount_cents)
                for k in cand.keys:
                    db.set_alias(k, "match", place_id)
            del by_place[place_id]

    result.candidates = sorted(list(by_place.values()) + unmatched, key=lambda c: (c.match.confidence if c.match else -1))
    stats["new restaurants"] = len(result.candidates)
    return result


def record(db: Database, decision: Decision, today: date) -> dict | None:
    c = decision.candidate
    if decision.place is None:
        for k in c.keys:
            db.set_alias(k, "skip")
        return None
    p = decision.place
    db.add_restaurant(p.place_id, p.name, p.address, today)
    for t in c.visits:
        db.add_visit(t.key, p.place_id, t.date, t.amount_cents)
    for k in c.keys:
        db.set_alias(k, "match", p.place_id)
    return {"place_id": p.place_id, "name": p.name, "address": p.address,
            "visits": sorted(t.date.isoformat() for t in c.visits)}


def run_review(db: Database, reviewer: Reviewer, result: RunResult, today: date) -> RunResult:
    """Walks the candidates, saving each decision immediately so quitting loses nothing."""
    total = len(result.candidates)
    for i, cand in enumerate(result.candidates, 1):
        decision = reviewer.review(cand, i, total)
        if decision is None:
            result.unreviewed = total - i + 1
            break
        entry = record(db, decision, today)
        if entry:
            result.approved.append(entry)
            result.stats["approved"] += 1
        else:
            result.stats["skipped"] += 1
    return result
