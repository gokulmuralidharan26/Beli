import pytest

from beli_sync.normalize import key_for, parse_merchant


@pytest.mark.parametrize("raw,name,processor,delivery", [
    ("TST* JOES PIZZA", "Joes Pizza", "toast", None),
    ("SQ *CAFE 123", "Cafe", "square", None),
    ("TST* JOES PIZZA #4412 NEW YORK NY", "Joes Pizza New York", "toast", None),
    ("DD *DOORDASH SWEETGREEN", "Sweetgreen", None, "doordash"),
    ("DD *DOORDASH", "", None, "doordash"),
    ("DOORDASH*DASHPASS", "", None, "doordash"),
    ("UBER *EATS", "", None, "ubereats"),
    ("LUCALI 718-555-0199 BROOKLYN NY", "Lucali Brooklyn", None, None),
    ("SHAKE SHACK 12", "Shake Shack", None, None),
    ("WWW.SWEETGREEN.COM", "Sweetgreen", None, None),
    ("AplPay TST* LOS TACO", "Los Taco", "toast", None),
    ("AplPay CHIPOTLE 2644", "Chipotle", None, None),
    ("Sumup *vintage Mood B", "Vintage Mood B", "sumup", None),
    ("Zettle_*oslo Badstufor", "Oslo Badstufor", "zettle", None),
    ("Wolt", "", None, "wolt"),
])
def test_parse(raw, name, processor, delivery):
    p = parse_merchant(raw)
    assert (p.name, p.processor, p.via_delivery) == (name, processor, delivery)


def test_key_for():
    assert key_for("Joe's  Pizza!") == "joe s pizza"
