"""Local SQLite store: restaurants seen, visits, remembered decisions, lookup cache."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS restaurants (
    place_id    TEXT PRIMARY KEY,           -- Google place id, or 'manual:<slug>'
    name        TEXT NOT NULL,
    address     TEXT,
    status      TEXT NOT NULL CHECK (status IN ('approved', 'added')),
    first_seen  TEXT NOT NULL,
    approved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS visits (
    txn_key      TEXT PRIMARY KEY,          -- hash; makes re-importing a CSV a no-op
    place_id     TEXT NOT NULL REFERENCES restaurants(place_id),
    visit_date   TEXT NOT NULL,
    amount_cents INTEGER NOT NULL
);
-- Remembers how a bank string was resolved so you're never asked twice.
CREATE TABLE IF NOT EXISTS aliases (
    query_key TEXT PRIMARY KEY,
    place_id  TEXT,
    decision  TEXT NOT NULL CHECK (decision IN ('match', 'skip'))
);
CREATE TABLE IF NOT EXISTS place_cache (
    query     TEXT PRIMARY KEY,
    payload   TEXT NOT NULL,
    cached_at TEXT NOT NULL
);
"""

CACHE_DAYS = 30  # Google's terms limit how long Places results may be cached


class Database:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # visits
    def has_visit(self, txn_key: str) -> bool:
        return self.conn.execute("SELECT 1 FROM visits WHERE txn_key=?", (txn_key,)).fetchone() is not None

    def add_visit(self, txn_key: str, place_id: str, visit_date: date, amount_cents: int) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO visits VALUES (?,?,?,?)", (txn_key, place_id, visit_date.isoformat(), amount_cents)
        )
        self.conn.commit()

    # restaurants
    def get_restaurant(self, place_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM restaurants WHERE place_id=?", (place_id,)).fetchone()

    def add_restaurant(self, place_id: str, name: str, address: str, first_seen: date) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO restaurants VALUES (?,?,?,?,?,?)",
            (place_id, name, address, "approved", first_seen.isoformat(), datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()

    def mark_added(self, place_id: str) -> None:
        self.conn.execute("UPDATE restaurants SET status='added' WHERE place_id=?", (place_id,))
        self.conn.commit()

    def list_restaurants(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT r.*, COUNT(v.txn_key) AS visit_count, MIN(v.visit_date) AS first_visit, MAX(v.visit_date) AS last_visit
               FROM restaurants r LEFT JOIN visits v USING (place_id)
               GROUP BY r.place_id ORDER BY r.name"""
        ).fetchall()

    def visit_dates(self, place_id: str) -> list[str]:
        rows = self.conn.execute("SELECT visit_date FROM visits WHERE place_id=? ORDER BY visit_date", (place_id,))
        return [r[0] for r in rows]

    # aliases
    def get_alias(self, query_key: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM aliases WHERE query_key=?", (query_key,)).fetchone()

    def set_alias(self, query_key: str, decision: str, place_id: str | None = None) -> None:
        self.conn.execute("INSERT OR REPLACE INTO aliases VALUES (?,?,?)", (query_key, place_id, decision))
        self.conn.commit()

    # places lookup cache (satisfies places.GooglePlacesClient's cache interface)
    def cache_get(self, query: str) -> str | None:
        row = self.conn.execute("SELECT payload, cached_at FROM place_cache WHERE query=?", (query,)).fetchone()
        if row and datetime.fromisoformat(row["cached_at"]) > datetime.now() - timedelta(days=CACHE_DAYS):
            return row["payload"]
        return None

    def cache_put(self, query: str, payload: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO place_cache VALUES (?,?,?)", (query, payload, datetime.now().isoformat(timespec="seconds"))
        )
        self.conn.commit()
