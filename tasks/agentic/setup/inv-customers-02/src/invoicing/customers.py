"""Per-customer roll-ups for the ``report --by-customer`` view.

Each row is one customer: ``{"id", "name", "count", "total"}`` - the
customer's id, a display name, how many invoices they have and the sum of
those invoices' totals.
"""

from __future__ import annotations

from invoicing.calc import total
from invoicing.models import Invoice


def customer_totals(invoices: list[Invoice]) -> list[dict]:
    """One row per customer, in order of first appearance in ``invoices``."""
    rows: dict[str, dict] = {}
    for invoice in invoices:
        row = rows.setdefault(
            invoice.customer.id,
            {"id": invoice.customer.id, "name": invoice.customer.name, "count": 0, "total": 0.0},
        )
        row["count"] += 1
        row["total"] = round(row["total"] + total(invoice), 2)
    return list(rows.values())
