import pytest

from beli_sync.sources.csv_inbox import CsvInboxSource, StatementFormatError, parse_statement

APPLE = """Transaction Date,Clearing Date,Description,Merchant,Category,Type,Amount (USD),Purchased By
09/03/2026,09/04/2026,TST* JOES PIZZA NEW YORK NY,Joe's Pizza,Restaurants,Purchase,18.50,Me
09/03/2026,09/04/2026,TST* JOES PIZZA NEW YORK NY,Joe's Pizza,Restaurants,Purchase,18.50,Me
09/05/2026,09/06/2026,ACH DEPOSIT INTERNET TRANSFER,Payment,Payment,Payment,-500.00,Me
"""

AMEX = """Date,Description,Card Member,Account #,Amount,Category,City/State
09/10/2026,LUCALI BROOKLYN,ME,-12345,"1,042.10",Restaurant-Restaurant,BROOKLYN NY
09/11/2026,WHOLEFDS MKT,ME,-12345,64.20,Merchandise & Supplies-Groceries,NEW YORK NY
"""

CHASE = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
09/12/2026,09/13/2026,SQ *CAFE 123,Food & Drink,Sale,-9.75,
"""


def write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_apple(tmp_path):
    txns = parse_statement(write(tmp_path, "apple.csv", APPLE))
    assert [t.amount_cents for t in txns] == [1850, 1850, -50000]
    assert txns[0].merchant == "Joe's Pizza" and txns[0].category == "Restaurants"
    assert txns[0].key != txns[1].key  # identical same-day charges stay distinct


def test_amex_drops_account_number_and_parses_amount(tmp_path):
    txns = parse_statement(write(tmp_path, "amex.csv", AMEX))
    assert txns[0].amount_cents == 104210
    assert txns[0].location_hint == "BROOKLYN NY"
    assert "12345" not in repr(txns)  # Account # column is never read


def test_chase_sign_flipped(tmp_path):
    assert parse_statement(write(tmp_path, "chase.csv", CHASE))[0].amount_cents == 975


def test_keys_stable_across_reads(tmp_path):
    p = write(tmp_path, "apple.csv", APPLE)
    assert [t.key for t in parse_statement(p)] == [t.key for t in parse_statement(p)]


def test_unknown_format_reports_headers_only(tmp_path):
    p = write(tmp_path, "bad.csv", "Foo,Bar\nsecret-value,2\n")
    with pytest.raises(StatementFormatError) as e:
        parse_statement(p)
    assert "Foo" in str(e.value) and "secret-value" not in str(e.value)


def test_inbox_reads_all_csvs(tmp_path):
    write(tmp_path, "a.csv", APPLE)
    write(tmp_path, "b.CSV", AMEX)
    write(tmp_path, "notes.txt", "ignore")
    assert len(list(CsvInboxSource(tmp_path).fetch())) == 5
