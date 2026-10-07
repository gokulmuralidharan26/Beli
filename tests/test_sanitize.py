from beli_sync.sanitize import REDACTED, scrub


def test_redacts_full_card_numbers():
    assert "4111" not in scrub("PAYMENT 4111 1111 1111 1111 THANKS")
    assert "5500" not in scrub("5500-0000-0000-0004")
    assert "371449635398431" not in scrub("AMEX 371449635398431")


def test_redacts_masked_account_refs():
    for s in ("XXXX1234", "xxxx-1234", "***1234", "ending in 1234", "Acct 98765"):
        assert "1234" not in scrub(s) and "98765" not in scrub(s), s


def test_keeps_store_numbers_and_phones():
    assert scrub("TST* JOES PIZZA #1234 212-555-0100") == "TST* JOES PIZZA #1234 212-555-0100"


def test_empty():
    assert scrub(None) == "" and scrub("") == ""
    assert REDACTED in scrub("1234567890123456")
