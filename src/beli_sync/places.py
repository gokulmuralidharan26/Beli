"""Resolve a cleaned merchant name to a real place, with a confidence score."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Protocol

import requests

HIGH = 0.85  # >= HIGH: confident
MEDIUM = 0.65  # >= MEDIUM: plausible; below this is flagged LOW
DELIVERY_CAP = 0.70  # a delivery charge is not proof you were there

_FOOD_TYPES = {
    "restaurant", "food", "cafe", "bar", "bakery", "meal_takeaway", "meal_delivery",
    "coffee_shop", "ice_cream_shop", "night_club", "brunch_restaurant", "breakfast_restaurant",
}


@dataclass(frozen=True)
class Place:
    place_id: str
    name: str
    address: str
    types: tuple[str, ...] = ()


@dataclass(frozen=True)
class Match:
    place: Place
    confidence: float

    @property
    def level(self) -> str:
        return level(self.confidence)


def level(confidence: float) -> str:
    return "high" if confidence >= HIGH else "medium" if confidence >= MEDIUM else "low"


class PlacesClient(Protocol):
    def search(self, query: str) -> list[Place]: ...


# --- scoring (pure, no network) ----------------------------------------------

def _tokens(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]+", "", text.lower().replace("&", " and ")).split()


def name_similarity(query: str, candidate: str) -> float:
    qt, ct = _tokens(query), _tokens(candidate)
    qj, cj = "".join(qt), "".join(ct)
    if not qj or not cj:
        return 0.0
    best = SequenceMatcher(None, qj, cj).ratio()
    if set(ct) <= set(qt) and len(cj) >= 6:  # query carries extra words (a city)
        best = max(best, 0.90)
    if set(qt) <= set(ct) and len(qj) >= 6:  # candidate is a longer official name
        best = max(best, 0.85)
    if cj.startswith(qj) and len(qj) >= 5:  # bank truncated the name
        best = max(best, 0.85)
    return best


def _is_food(place: Place) -> bool:
    return any(t in _FOOD_TYPES or t.endswith("_restaurant") for t in place.types)


def _location_score(hint: str | None, address: str) -> float:
    if not hint:
        return 0.5  # no information either way
    words = [w for w in _tokens(hint) if len(w) >= 3 or w.upper() in {"NY", "LA", "SF", "DC"}]
    addr = address.lower()
    return 1.0 if any(w in addr for w in words) else 0.0


def score(query: str, hint: str | None, place: Place, via_delivery: bool = False) -> float:
    conf = (
        0.60 * name_similarity(query, place.name)
        + 0.25 * (1.0 if _is_food(place) else 0.0)
        + 0.15 * _location_score(hint, place.address)
    )
    return round(min(conf, DELIVERY_CAP) if via_delivery else conf, 3)


def rank(query: str, hint: str | None, places: list[Place], via_delivery: bool = False) -> list[Match]:
    matches = [Match(p, score(query, hint, p, via_delivery)) for p in places]
    return sorted(matches, key=lambda m: m.confidence, reverse=True)


# --- Google Places (New) ------------------------------------------------------

class GooglePlacesError(Exception):
    pass


class GooglePlacesClient:
    URL = "https://places.googleapis.com/v1/places:searchText"
    FIELDS = "places.id,places.displayName,places.formattedAddress,places.types"

    def __init__(self, api_key: str, cache=None, session: requests.Session | None = None):
        if not api_key:
            raise GooglePlacesError("GOOGLE_PLACES_API_KEY is not set (see .env.example)")
        self._key = api_key
        self._cache = cache  # needs cache_get(query) / cache_put(query, payload)
        self._http = session or requests.Session()

    def search(self, query: str) -> list[Place]:
        if self._cache and (hit := self._cache.cache_get(query)) is not None:
            return [Place(p["id"], p["name"], p["address"], tuple(p["types"])) for p in json.loads(hit)]
        resp = self._http.post(
            self.URL,
            headers={"X-Goog-Api-Key": self._key, "X-Goog-FieldMask": self.FIELDS},
            json={"textQuery": query, "pageSize": 5},
            timeout=15,
        )
        if resp.status_code != 200:
            # Don't include request details: the key is in the headers.
            raise GooglePlacesError(f"Places API returned HTTP {resp.status_code}: {resp.text[:200]}")
        places = [
            Place(p["id"], p.get("displayName", {}).get("text", ""), p.get("formattedAddress", ""), tuple(p.get("types", [])))
            for p in resp.json().get("places", [])
        ]
        if self._cache:
            payload = [{"id": p.place_id, "name": p.name, "address": p.address, "types": list(p.types)} for p in places]
            self._cache.cache_put(query, json.dumps(payload))
        return places
