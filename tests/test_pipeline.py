from datetime import date

from beli_sync.pipeline import build_candidates, run_review
from beli_sync.review import Reviewer
from beli_sync.sinks.checklist import write_checklist
from beli_sync.sources.csv_inbox import CsvInboxSource

from conftest import JOES, SALON, FakePlaces
from test_sources import AMEX, APPLE, write

TODAY = date(2026, 10, 1)


def reviewer(places, answers):
    it = iter(answers)
    return Reviewer(places, input_fn=lambda _: next(it), print_fn=lambda *a: None)


def setup(tmp_path):
    write(tmp_path, "apple.csv", APPLE)
    return CsvInboxSource(tmp_path), FakePlaces({"joes pizza": [JOES]})


def test_full_run_then_rerun_is_idempotent(tmp_path, db, cfg):
    source, places = setup(tmp_path)

    result = build_candidates(source, db, places, cfg)
    assert len(result.candidates) == 1  # payment excluded, two Joe's charges merged
    assert len(result.candidates[0].visits) == 2

    run_review(db, reviewer(places, [""]), result, TODAY)  # Enter = approve
    assert result.stats["approved"] == 1
    row = db.list_restaurants()[0]
    assert (row["name"], row["visit_count"]) == ("Joe's Pizza", 2)

    again = build_candidates(source, db, places, cfg)  # same CSV next month
    assert again.candidates == [] and again.stats["already processed"] == 2 and again.stats["not dining"] == 1


def test_known_restaurant_new_visit_counts_without_review(tmp_path, db, cfg):
    source, places = setup(tmp_path)
    run_review(db, reviewer(places, [""]), build_candidates(source, db, places, cfg), TODAY)

    write(tmp_path, "apple.csv", APPLE + "10/02/2026,10/03/2026,TST* JOES PIZZA NEW YORK NY,Joe's Pizza,Restaurants,Purchase,20.00,Me\n")
    result = build_candidates(source, db, places, cfg)
    assert result.candidates == [] and result.stats["visits at known restaurants"] == 1
    assert db.list_restaurants()[0]["visit_count"] == 3


def test_skip_is_remembered(tmp_path, db, cfg):
    source, places = setup(tmp_path)
    run_review(db, reviewer(places, ["s"]), build_candidates(source, db, places, cfg), TODAY)
    assert db.list_restaurants() == []
    again = build_candidates(source, db, places, cfg)
    assert again.candidates == [] and again.stats["skipped before"] == 2


def test_quit_keeps_progress_and_reports_remainder(tmp_path, db, cfg):
    write(tmp_path, "apple.csv", APPLE)
    write(tmp_path, "amex.csv", AMEX)
    places = FakePlaces({"joes pizza": [JOES], "lucali": []})
    result = build_candidates(CsvInboxSource(tmp_path), db, places, cfg)
    assert len(result.candidates) == 2
    run_review(db, reviewer(places, ["q"]), result, TODAY)
    assert result.unreviewed == 2 and db.list_restaurants() == []


def test_low_confidence_defaults_to_skip(tmp_path, db, cfg):
    write(tmp_path, "apple.csv", APPLE.replace("Joe's Pizza", "Cafe 123"))
    places = FakePlaces({"cafe": [SALON]})
    result = build_candidates(CsvInboxSource(tmp_path), db, places, cfg)
    assert result.candidates[0].match.level == "low"
    run_review(db, reviewer(places, [""]), result, TODAY)  # Enter on a flagged item = skip
    assert db.list_restaurants() == []


def test_fix_flow_and_checklist(tmp_path, db, cfg):
    write(tmp_path, "amex.csv", AMEX)
    lucali = type(JOES)("pid_lucali", "Lucali", "575 Henry St, Brooklyn, NY", ("pizza_restaurant", "restaurant"))
    places = FakePlaces({"lucali pizza": [lucali]})
    result = build_candidates(CsvInboxSource(tmp_path), db, places, cfg)
    assert result.candidates[0].match is None  # nothing found for the raw string

    run_review(db, reviewer(places, ["f", "Lucali Pizza Brooklyn", "1"]), result, TODAY)
    assert db.list_restaurants()[0]["name"] == "Lucali"

    path = write_checklist(result.approved, tmp_path / "out", TODAY)
    text = path.read_text()
    assert "- [ ] **Lucali**" in text and "query_place_id=pid_lucali" in text
