from datetime import date, timedelta

import pytest
from invoicing.aging import aging, grand_total
from invoicing.cli import main
from invoicing.models import Customer, Invoice, LineItem

ACME = Customer(id="c1", name="Acme")


def _inv(inv_id, issued_on, price=100.0, terms=30, **kw):
    return Invoice(
        id=inv_id,
        customer=ACME,
        items=[LineItem("W", 1, price)],
        issued_on=issued_on,
        terms_days=terms,
        **kw,
    )


def _bucket_of(invoice, as_of):
    report = aging([invoice], as_of)
    hits = [name for name, row in report.items() if row["count"]]
    assert len(hits) == 1, report
    return hits[0]


# brief: "an invoice issued 2024-01-31 on Net 30 terms makes `aging --as-of 2024-03-15` crash";
# rule: due = issue date + terms in calendar days (2024-03-01), so it is 14 days overdue
def test_month_end_issue_date_does_not_crash(tmp_path, capsys):
    assert _bucket_of(_inv("i1", "2024-01-31"), date(2024, 3, 1)) == "current"
    assert _bucket_of(_inv("i1", "2024-01-31"), date(2024, 3, 2)) == "1-30"
    db = str(tmp_path / "invoices.json")
    args = ["--db", db, "create", "--customer", "Acme", "--amount", "100"]
    assert main([*args, "--issued-on", "2024-01-31"]) == 0
    capsys.readouterr()
    assert main(["--db", db, "aging", "--as-of", "2024-03-15"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[1] == "1-30: 1 invoices, 100.00"


# rule: "due date is the issue date plus the invoice's terms in calendar days" - for any terms
# and any month length, not only Net 30 in a 30-day month
@pytest.mark.parametrize(
    ("issued", "terms", "due"),
    [
        ("2024-03-01", 45, date(2024, 4, 15)),
        ("2024-01-01", 30, date(2024, 1, 31)),
        ("2024-12-15", 60, date(2025, 2, 13)),
        ("2024-05-31", 10, date(2024, 6, 10)),
    ],
)
def test_due_date_is_issue_plus_terms_days(issued, terms, due):
    invoice = _inv("i1", issued, terms=terms)
    assert _bucket_of(invoice, due) == "current"
    assert _bucket_of(invoice, due + timedelta(days=1)) == "1-30"


# brief: "an invoice exactly 30 days overdue is shown under 31-60"; rule: both ends of every
# range are inclusive, so every boundary (30/31, 60/61, 90/91) must land correctly
@pytest.mark.parametrize(
    ("days", "bucket"),
    [
        (1, "1-30"),
        (30, "1-30"),
        (31, "31-60"),
        (60, "31-60"),
        (61, "61-90"),
        (90, "61-90"),
        (91, "90+"),
    ],
)
def test_bucket_boundaries_inclusive(days, bucket):
    invoice = _inv("i1", "2024-04-01")  # Net 30 -> due 2024-05-01
    assert _bucket_of(invoice, date(2024, 5, 1) + timedelta(days=days)) == bucket


# rule: "the amount is what the customer still owes on the invoice as billed" (after discount
# and tax, minus what has been paid)
def test_amount_is_total_as_billed_minus_paid():
    invoice = _inv("i1", "2024-04-01", tax_rate=0.08, discount_pct=10, amount_paid=20.0)
    report = aging([invoice], date(2024, 5, 20))
    assert report["1-30"] == {"count": 1, "amount": 77.2}
    assert grand_total(report) == 77.2


# rule: "invoices owing nothing are left out" - whether marked paid or paid off in full
def test_invoices_owing_nothing_are_left_out():
    paid_off = _inv("i1", "2024-04-01", tax_rate=0.1, amount_paid=110.0, status="sent")
    marked = _inv("i2", "2024-04-01", status="paid")
    owing = _inv("i3", "2024-04-01", price=40.0)
    report = aging([paid_off, marked, owing], date(2024, 5, 20))
    assert sum(row["count"] for row in report.values()) == 1
    assert report["1-30"] == {"count": 1, "amount": 40.0}


# rule: issue dates "in any of the forms the 'issued on' field accepts elsewhere" (ISO or US)
def test_us_format_issue_date():
    iso = aging([_inv("i1", "2024-01-31")], date(2024, 4, 15))
    us = aging([_inv("i1", "01/31/2024")], date(2024, 4, 15))
    assert us == iso
    assert us["31-60"]["count"] == 1
