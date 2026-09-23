from datetime import date

from invoicing.formatting import format_money, parse_invoice_date


def test_format_money():
    assert format_money(1234.5) == "$1,234.50"


def test_parse_invoice_date_iso():
    assert parse_invoice_date("2024-03-01") == date(2024, 3, 1)


def test_parse_invoice_date_us():
    assert parse_invoice_date("03/01/2024") == date(2024, 3, 1)
