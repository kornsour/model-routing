"""Per-customer statements: the lines and balance one customer sees.

A statement lists every line item on every invoice for a customer and the
balance across those invoices. It is what the ``statement`` command prints
and what gets pasted into a customer email, so every figure on it must be
a figure the customer could reproduce from the unit prices shown.
"""

from __future__ import annotations

from invoicing.calc import round_currency, total
from invoicing.models import Invoice


def line_totals(invoice: Invoice) -> list[tuple[str, float]]:
    """``(description, amount)`` for each line, amount in whole cents."""
    return [(item.description, item.amount) for item in invoice.items]


def statement_for(invoices: list[Invoice], customer_name: str) -> dict:
    """Lines and balance for every invoice whose customer is ``customer_name``."""
    mine = [inv for inv in invoices if inv.customer.name == customer_name]
    lines = [(inv.id, desc, amount) for inv in mine for desc, amount in line_totals(inv)]
    balance = round_currency(sum(total(inv) for inv in mine))
    return {"customer": customer_name, "lines": lines, "balance": balance}
