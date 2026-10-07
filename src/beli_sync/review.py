"""Interactive terminal review: approve, fix or skip each new restaurant."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from .models import Transaction
from .places import Match, Place, PlacesClient, level, rank


@dataclass
class Candidate:
    name: str  # cleaned bank name
    keys: set[str]  # alias keys that resolved here
    match: Match | None
    hint: str | None = None
    via_delivery: bool = False
    bank_strings: list[str] = field(default_factory=list)
    visits: list[Transaction] = field(default_factory=list)


@dataclass
class Decision:
    candidate: Candidate
    place: Place | None  # None means skip


class Reviewer:
    def __init__(self, places: PlacesClient, input_fn: Callable[[str], str] = input, print_fn: Callable[..., None] = print):
        self.places, self.ask, self.out = places, input_fn, print_fn

    def review(self, c: Candidate, index: int, total: int) -> Decision | None:
        """Returns a Decision, or None if the user quit."""
        self._show(c, index, total)
        place = c.match.place if c.match else None
        flagged = c.match is None or c.match.level == "low"
        while True:
            actions = "[f]ix  [s]kip  [q]uit" if place is None else "[a]pprove  [f]ix  [s]kip  [q]uit"
            default = "s" if flagged else "a"
            choice = (self.ask(f"  {actions}  (Enter = {'skip' if default == 's' else 'approve'}) > ").strip().lower() or default)
            if choice == "q":
                return None
            if choice == "s":
                return Decision(c, None)
            if choice == "a" and place is not None:
                return Decision(c, place)
            if choice == "f":
                fixed = self._fix(c)
                if fixed is not None:
                    return Decision(c, fixed)
                self._show(c, index, total)
                continue
            self.out("  ?")

    def _show(self, c: Candidate, index: int, total: int) -> None:
        o = self.out
        o("")
        if c.match:
            tag = f"{c.match.confidence:.2f} {c.match.level.upper()}"
            o(f"[{index}/{total}] {c.match.place.name}")
            o(f"        {c.match.place.address}")
            if c.match.level == "low":
                o(f"        ⚠  LOW CONFIDENCE ({tag}): check this one carefully")
            else:
                o(f"        confidence {tag}")
        else:
            o(f"[{index}/{total}] {c.name}")
            o("        ⚠  NO MATCH FOUND: fix the name or skip")
        if c.via_delivery:
            o("        ⚠  delivery order: you may not have visited in person")
        o(f"        bank: {'; '.join(f'“{s}”' for s in c.bank_strings[:3])}")
        dates = ", ".join(t.date.isoformat() for t in sorted(c.visits, key=lambda t: t.date))
        o(f"        {len(c.visits)} visit{'s' if len(c.visits) != 1 else ''}: {dates}")

    def _fix(self, c: Candidate) -> Place | None:
        query = self.ask("  Correct name (add city if needed), Enter to cancel > ").strip()
        if not query:
            return None
        matches = rank(query, c.hint, self.places.search(query))[:3]
        for i, m in enumerate(matches, 1):
            self.out(f"   {i}. {m.place.name}, {m.place.address}  ({m.confidence:.2f})")
        self.out("   m. use the name exactly as typed (no map link)")
        pick = self.ask("  Pick > ").strip().lower()
        if pick == "m":
            slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
            return Place(f"manual:{slug}", query, "")
        if pick.isdigit() and 1 <= int(pick) <= len(matches):
            return matches[int(pick) - 1].place
        return None
