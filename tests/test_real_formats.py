"""Layouts taken from real exports (fake rows, real column names)."""
from datetime import date

from beli_sync.pipeline import build_candidates
from beli_sync.places import Place
from beli_sync.sources.csv_inbox import CsvInboxSource, parse_statement

from conftest import FakePlaces
from test_sources import write

APPLE_V2 = """Transaction Date,Merchant,Location / Method,Amount (USD),Daily Cash %
05/31/2026,Jabeque Soul,"Ibiza, Balearic Isles",108.20,2%
05/30/2026,Ndk 3,"Sant Antoni de Portmany, Bal...",16.25,2%
05/28/2026,Topstep,Card Number Used,49.00,1%
05/27/2026,Airbnb,Apple Pay,1847.44,2%
05/23/2026,Headout,book.seine-river-cruises.com,19.77,2%
05/06/2026,Wawa,"Gainesville, FL",6.00,2%
"""

AMEX_REAL = """Date,Description,Card Member,Account #,Amount,Extended Details,Appears On Your Statement As,Address,City/State,Zip Code,Country,Reference,Category
09/10/2026,AplPay CHIPOTLE 2644JACKSONVILLE        FL,ME,-12345,12.50,x,x,x,"JACKSONVILLE
FL",32256,UNITED STATES,'320,Restaurant-Restaurant
09/11/2026,AplPay TST* LOS TACONEW YORK            NY,ME,-12345,30.00,x,x,x,"NEW YORK
NY",10001,UNITED STATES,'321,Restaurant-Restaurant
09/12/2026,AUTOPAY PAYMENT - THANK YOU,ME,-12345,-500.00,x,x,x,,,,'322,
"""


def test_apple_v2_columns_and_locations(tmp_path):
    txns = parse_statement(write(tmp_path, "apple.csv", APPLE_V2))
    by = {t.description: t for t in txns}
    assert by["Jabeque Soul"].location_hint == "Ibiza, Balearic Isles"
    assert by["Ndk 3"].location_hint == "Sant Antoni de Portmany"  # truncated tail dropped
    for name in ("Topstep", "Airbnb", "Headout"):
        assert by[name].location_hint is None  # Card Number Used / Apple Pay / web domain
    assert by["Wawa"].location_hint == "Gainesville, FL"
    assert all(t.category is None for t in txns)


def test_amex_city_stripped_from_name(tmp_path):
    txns = parse_statement(write(tmp_path, "amex.csv", AMEX_REAL))
    assert [t.description for t in txns] == ["AplPay CHIPOTLE 2644", "AplPay TST* LOS TACO", "AUTOPAY PAYMENT - THANK YOU"]
    assert txns[0].category == "Restaurant-Restaurant" and txns[0].location_hint == "JACKSONVILLE FL"
    assert "12345" not in repr(txns)


def test_uncategorised_charges_are_decided_by_place_lookup(tmp_path, db, cfg):
    write(tmp_path, "apple.csv", APPLE_V2)
    soul = Place("p_soul", "Jabeque Soul", "Ibiza, Spain", ("restaurant", "food"))
    wawa = Place("p_wawa", "Wawa", "Gainesville, FL, USA", ("convenience_store", "gas_station", "food"))
    places = FakePlaces({"jabeque soul": [soul], "wawa": [wawa]})
    result = build_candidates(CsvInboxSource(tmp_path), db, places, cfg, since=date(2026, 5, 1), until=date(2026, 5, 31))

    assert [c.match.place.name for c in result.candidates] == ["Jabeque Soul"]  # Wawa is "food" but not a restaurant
    assert result.stats["not dining (place lookup)"] >= 1  # Wawa, Ndk 3 (no match), Topstep, Headout...
    assert "airbnb" in {n.lower() for n, _ in result.excluded}  # excluded by name, no Google call
    assert not any("airbnb" in q.lower() for q in places.calls)


def test_date_range(tmp_path, db, cfg):
    write(tmp_path, "apple.csv", APPLE_V2)
    result = build_candidates(CsvInboxSource(tmp_path), db, FakePlaces({}), cfg, since=date(2026, 6, 1))
    assert result.stats["outside date range"] == 6 and result.candidates == []


AMEX_TRUNCATED = """Date,Description,Card Member,Account #,Amount,Extended Details,Appears On Your Statement As,Address,City/State,Zip Code,Country,Reference,Category
09/10/2026,AplPay TST* 7TH STRENEW YORK            NY,ME,-12345,18.00,99999996273 6462246919 AplPay TST* 7TH STREET BURGER - 000074221 NEW YORK NY Description : FAST FOOD REST.,x,x,"NEW YORK
NY",10001,UNITED STATES,'1,Restaurant-Restaurant
09/11/2026,TST* AMPERSAND BAR &NEW YORK            NY,ME,-12345,40.00,21105176209 RESTAURANT TST* AMPERSAND BAR & GRIL 00266925 NEW YORK NY RESTAURANT,x,x,"NEW YORK
NY",10001,UNITED STATES,'2,Restaurant-Restaurant
09/12/2026,AplPay TST* BURGERHENEW YORK            NY,ME,-12345,22.00,21105176270 RESTAURANT AplPay TST* BURGERHEAD - 2ND AVE 00180341 NEW YORK NY RESTAURANT,x,x,"BEDFORD
NY",10001,UNITED STATES,'3,Restaurant-Restaurant
09/13/2026,TST* 55 STONE STREETMANHATTAN            NY,ME,-12345,50.00,21105176219 RESTAURANT TST* 55 STONE STREET 00181430 MANHATTAN NY RESTAURANT,x,x,"NEW YORK
NY",10001,UNITED STATES,'4,Restaurant-Restaurant
09/14/2026,AplPay CHICK-FIL-A #JACKSONVILLE        FL,ME,-12345,9.00,,x,x,"JACKSONVILLE
FL",32256,UNITED STATES,'5,Restaurant-Bar & Café
09/15/2026,TST* 230 FIFTH 00006NEW YORK            NY,ME,-12345,60.00,21105176 TST* 230 FIFTH 000067461 NEW YORK NY Description : Bars Price : 0.48 - 12.00,x,x,"NEW YORK
NY",10001,UNITED STATES,'6,Restaurant-Restaurant
09/16/2026,AplPay BD PIZZA     New York            NY,ME,-12345,15.00,2110 AplPay BD PIZZA New York NY RESTAURANT,x,x,"NEW YORK
NY",10001,UNITED STATES,'7,Restaurant-Restaurant
09/17/2026,AplPay GRUBHUB*GRACEDELINEW YORK            NY,ME,-12345,25.00,,x,x,"NEW YORK
NY",10001,UNITED STATES,'8,Restaurant-Restaurant
09/18/2026,AplPay UBER EATS SAN FRANCISCO        CA,ME,-12345,30.00,,x,x,"SAN FRANCISCO
CA",94103,UNITED STATES,'9,Restaurant-Restaurant
"""


def test_amex_truncated_names_completed_from_extended_details(tmp_path):
    from beli_sync.normalize import parse_merchant

    txns = parse_statement(write(tmp_path, "amex.csv", AMEX_TRUNCATED))
    names = [parse_merchant(t.description).name for t in txns]
    assert names == ["7th Street Burger", "Ampersand Bar & Gril", "Burgerhead", "55 Stone Street", "Chick-fil-a",
                     "230 Fifth", "Bd Pizza", "Gracedeli", ""]  # last: bare Uber Eats, no restaurant named
    assert "12345" not in repr(txns) and "99999996273" not in repr(txns)  # details text never kept
