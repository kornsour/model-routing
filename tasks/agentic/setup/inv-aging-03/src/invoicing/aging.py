"""Accounts-receivable aging: how overdue the money customers still owe is.

Rules (these are what accounts receivable use when they check the report by
hand at month-end close):

- An invoice's issue date is its ``issued_on`` field, written in any of the
  forms the "issued on" field accepts elsewhere in the tool.
- It falls due ``terms_days`` calendar days after it was issued ("Net 30"
  means 30 days after the issue date, "Net 45" 45 days).
- Days overdue, as of a given day, is the number of days from the due date to
  that day. An invoice is ``current`` up to and including its due date.
- Overdue invoices are bucketed by days overdue: ``1-30``, ``31-60``,
  ``61-90`` and ``90+``. Both ends of each range are inclusive.
- The amount aged is what the customer still owes on the invoice as billed
  (the invoice total, after discount and tax, minus ``amount_paid``).
  Invoices with nothing left to pay do not appear in the report at all.
"""

from __future__ import annotations

from datetime import date, timedelta

from invoicing.models import Invoice

BUCKETS = ["current", "1-30", "31-60", "61-90", "90+"]


def due_date(invoice: Invoice) -> date:
    issued = date.fromisoformat(invoice.issued_on)
    months, days = divmod(invoice.terms_days, 30)
    year, month = divmod(issued.month - 1 + months, 12)
    return issued.replace(year=issued.year + year, month=month + 1) + timedelta(days=days)


def bucket_for(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "current"
    if days_overdue < 30:
        return "1-30"
    if days_overdue < 60:
        return "31-60"
    if days_overdue < 90:
        return "61-90"
    return "90+"


def outstanding(invoice: Invoice) -> float:
    return round(invoice.subtotal - invoice.amount_paid, 2)


def aging(invoices: list[Invoice], as_of: date) -> dict[str, dict]:
    """``{bucket: {"count": n, "amount": owed}}`` for every bucket, in ``BUCKETS`` order."""
    report: dict[str, dict] = {name: {"count": 0, "amount": 0.0} for name in BUCKETS}
    for invoice in invoices:
        if invoice.status == "paid":
            continue
        days_overdue = (as_of - due_date(invoice)).days
        row = report[bucket_for(days_overdue)]
        row["count"] += 1
        row["amount"] = round(row["amount"] + outstanding(invoice), 2)
    return report


def grand_total(report: dict[str, dict]) -> float:
    return round(sum(row["amount"] for row in report.values()), 2)
