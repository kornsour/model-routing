from datetime import date

from invoicing.dateutil import parse_date
from invoicing.formatting import parse_invoice_date
from invoicing.storage import _parse_created


def test_shared_helper_used_by_both_call_sites():
    assert parse_date("2024-03-01") == date(2024, 3, 1)
    assert parse_invoice_date("2024-03-01") == date(2024, 3, 1)
    assert _parse_created("03/01/2024") == date(2024, 3, 1)
