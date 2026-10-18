from datetime import date

from beli_sync.filtering import classify
from beli_sync.models import Transaction


def txn(desc, category=None, cents=2500, merchant=None):
    return Transaction("k", date(2026, 9, 1), desc, cents, "test", merchant=merchant, category=category)


def test_category_decides_when_present(cfg):
    assert classify(txn("JOES", "Restaurants"), cfg).include
    assert classify(txn("Restaurant Depot", "Grocery"), cfg).include is False  # category wins over name
    assert classify(txn("X", "Restaurant-Bar & Café"), cfg).include
    assert classify(txn("X", "Merchandise & Supplies-Groceries"), cfg).include is False


def test_fallback_to_name_without_category(cfg):
    assert classify(txn("TST* JOES"), cfg).include  # Toast
    assert classify(txn("BLUE DOOR CAFE"), cfg).include  # keyword
    d = classify(txn("ACME HARDWARE"), cfg)  # no clue either way: Google decides
    assert d.include and d.needs_place_check
    assert classify(txn("BLUE DOOR CAFE"), cfg).needs_place_check is False


def test_exclusions(cfg):
    assert classify(txn("WHOLE FOODS #123", "Restaurants"), cfg).include is False
    assert classify(txn("DD *DOORDASH", "Restaurants"), cfg).include is False
    assert classify(txn("DD *DOORDASH SWEETGREEN", "Restaurants"), cfg).include is True
    assert classify(txn("JOES", "Restaurants", cents=-2500), cfg).include is False  # refund


def test_include_override(cfg):
    cfg.include_overrides = ["whole foods"]
    assert classify(txn("WHOLE FOODS BAR", "Restaurants"), cfg).include
