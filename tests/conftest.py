import pytest

from beli_sync.db import Database
from beli_sync.filtering import FilterConfig
from beli_sync.places import Place

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cfg():
    return FilterConfig.load(ROOT / "config" / "filters.yaml")


@pytest.fixture
def db():
    d = Database(":memory:")
    yield d
    d.close()


class FakePlaces:
    """Deterministic stand-in for Google Places."""

    def __init__(self, catalog):
        self.catalog = catalog  # {substring: [Place, ...]}
        self.calls = []

    def search(self, query):
        self.calls.append(query)
        q = query.lower().replace("'", "")
        for needle, places in self.catalog.items():
            if needle in q:
                return places
        return []


JOES = Place("pid_joes", "Joe's Pizza", "7 Carmine St, New York, NY 10014, USA", ("pizza_restaurant", "restaurant", "food"))
SALON = Place("pid_salon", "Cafe 123 Hair Salon", "1 Main St, Austin, TX", ("hair_care",))
