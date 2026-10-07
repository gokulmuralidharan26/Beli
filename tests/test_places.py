from beli_sync.places import DELIVERY_CAP, HIGH, MEDIUM, Place, level, name_similarity, rank, score

from conftest import JOES, SALON


def test_exact_food_match_is_high():
    assert score("Joes Pizza", None, JOES) >= HIGH


def test_city_in_query_still_matches():
    assert name_similarity("Joes Pizza New York", "Joe's Pizza") >= 0.9


def test_truncated_bank_name():
    assert name_similarity("Joes Pizz", "Joe's Pizza") >= 0.85


def test_non_food_place_is_low():
    assert level(score("Cafe 123", None, SALON)) == "low"


def test_location_mismatch_lowers_score():
    good = score("Joes Pizza", "NEW YORK NY", JOES)
    bad = score("Joes Pizza", "AUSTIN TX", JOES)
    assert good > bad


def test_unrelated_name_is_low():
    other = Place("x", "Totally Different Bistro", "NY", ("restaurant",))
    assert score("Joes Pizza", "NY", other) < MEDIUM


def test_delivery_is_capped():
    assert score("Joes Pizza", None, JOES, via_delivery=True) <= DELIVERY_CAP


def test_rank_orders_best_first():
    other = Place("x", "Totally Different Bistro", "NY", ("restaurant",))
    assert rank("Joes Pizza", None, [other, JOES])[0].place is JOES
