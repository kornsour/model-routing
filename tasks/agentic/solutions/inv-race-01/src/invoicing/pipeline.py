"""Builds the end-of-run summary report from a :class:`invoicing.storage.Store`."""

from __future__ import annotations

from invoicing.calc import total
from invoicing.storage import Store


def generate_summary(store: Store) -> dict:
    """Count and total every invoice ``store`` currently knows about.

    Uses ``store.all()``, which merges on-disk invoices with anything added
    but not yet flushed, so this is correct regardless of call order.
    """
    invoices = store.all()
    return {
        "count": len(invoices),
        "total": round(sum(total(inv) for inv in invoices), 2),
    }
