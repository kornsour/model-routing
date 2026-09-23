"""Customer identity and per-customer roll-ups for the ``report --by-customer`` view.

A customer is identified by name, compared case-insensitively and ignoring
surrounding whitespace: ``customer_id`` is the stable id every entry point
(``create``, ``import-csv``) must use, and ``customer_totals`` groups by the
same key so invoices created before ids were stable still roll up correctly.
Each row is one customer: ``{"id", "name", "count", "total"}``.
"""

from __future__ import annotations

from invoicing.calc import total
from invoicing.models import Invoice


def customer_id(name: str) -> str:
    """The deterministic customer id for ``name`` (case- and whitespace-insensitive)."""
    return name.strip().casefold()


def customer_totals(invoices: list[Invoice]) -> list[dict]:
    """One row per customer, in order of first appearance in ``invoices``.

    The display name is the name on the customer's first invoice.
    """
    rows: dict[str, dict] = {}
    for invoice in invoices:
        key = customer_id(invoice.customer.name)
        row = rows.setdefault(
            key, {"id": key, "name": invoice.customer.name, "count": 0, "total": 0.0}
        )
        row["count"] += 1
        row["total"] = round(row["total"] + total(invoice), 2)
    return list(rows.values())
