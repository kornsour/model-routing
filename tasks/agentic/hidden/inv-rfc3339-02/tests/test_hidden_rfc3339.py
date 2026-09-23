from datetime import date

import pytest
from invoicing.formatting import parse_invoice_date
from invoicing.models import Customer, Invoice
from invoicing.storage import Store

CUSTOMER = Customer(id="c1", name="Acme")


# brief: "parse_invoice_date must accept RFC 3339 timestamps ... and return the UTC calendar day"
def test_rfc3339_utc_timestamp_gives_that_day():
    assert parse_invoice_date("2024-03-01T10:00:00Z") == date(2024, 3, 1)


# brief: "2024-03-01T23:30:00-05:00 is 2024-03-02" (the UTC calendar day, not the local one)
def test_rfc3339_negative_offset_rolls_forward_to_next_utc_day():
    assert parse_invoice_date("2024-03-01T23:30:00-05:00") == date(2024, 3, 2)


# brief: "return the UTC calendar day" - a positive offset can roll the day backwards too
def test_rfc3339_positive_offset_rolls_back_to_previous_utc_day():
    assert parse_invoice_date("2024-03-02T01:00:00+02:00") == date(2024, 3, 1)


# brief: "fractional seconds (2024-03-01T10:00:00.250+00:00)"
def test_rfc3339_fractional_seconds():
    assert parse_invoice_date("2024-03-01T10:00:00.250+00:00") == date(2024, 3, 1)


# brief: "while still accepting the existing plain ISO and US forms unchanged"
def test_legacy_forms_still_parse():
    assert parse_invoice_date("2024-03-01") == date(2024, 3, 1)
    assert parse_invoice_date("03/01/2024") == date(2024, 3, 1)
    assert parse_invoice_date("  2024-03-01  ") == date(2024, 3, 1)


# brief: "unrecognized text must still raise ValueError"
def test_unrecognized_text_raises():
    with pytest.raises(ValueError):
        parse_invoice_date("March 1st, 2024")
    with pytest.raises(ValueError):
        parse_invoice_date("2024-03-01T25:00:00Z")


# brief: "sorting stored invoices by created date must order by instant ... a date-only value
# sorts as midnight UTC of that day; a mix of forms in one store must sort correctly"
def test_sorted_by_created_orders_by_instant_across_forms(tmp_path):
    store = Store(tmp_path / "invoices.json")
    for invoice_id in ("i1", "i2", "i3", "i4"):
        store.add(Invoice(id=invoice_id, customer=CUSTOMER))
    store.flush()
    created = {
        "i1": "2024-03-02T01:00:00Z",  # 2024-03-02 01:00 UTC
        "i2": "2024-03-01T23:00:00-05:00",  # 2024-03-02 04:00 UTC
        "i3": "2024-03-02",  # 2024-03-02 00:00 UTC
        "i4": "03/01/2024",  # 2024-03-01 00:00 UTC
    }
    ordered = [inv.id for inv in store.sorted_by_created(created)]
    assert ordered == ["i4", "i3", "i1", "i2"]


# brief: "sorting ... must order by instant": two timestamps on the same UTC day but at
# different times must not be treated as equal
def test_sorted_by_created_distinguishes_times_within_a_day(tmp_path):
    store = Store(tmp_path / "invoices.json")
    store.add(Invoice(id="late", customer=CUSTOMER))
    store.add(Invoice(id="early", customer=CUSTOMER))
    created = {"late": "2024-03-01T18:00:00Z", "early": "2024-03-01T06:00:00Z"}
    ordered = [inv.id for inv in store.sorted_by_created(created)]
    assert ordered == ["early", "late"]
