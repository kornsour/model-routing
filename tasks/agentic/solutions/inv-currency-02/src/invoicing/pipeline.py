"""Builds the end-of-run summary report from a :class:`invoicing.storage.Store`."""

from __future__ import annotations

import json

from invoicing.calc import total
from invoicing.models import Invoice
from invoicing.storage import Store


def _invoices_on_disk(store: Store) -> list[Invoice]:
    if not store.path.exists():
        return []
    raw = json.loads(store.path.read_text() or "[]")
    return [Invoice.from_dict(r) for r in raw]


def generate_summary(store: Store) -> dict:
    """Count and total the invoices in ``store``, overall and per currency.

    Reads the store's on-disk file, since that is what a second process (or a
    later run of this CLI) would see. Callers in the same process must
    ``store.flush()`` before calling this if they just added invoices.
    """
    invoices = _invoices_on_disk(store)
    by_currency: dict[str, dict] = {}
    for inv in invoices:
        bucket = by_currency.setdefault(inv.currency, {"count": 0, "total": 0.0})
        bucket["count"] += 1
        bucket["total"] = round(bucket["total"] + total(inv), 2)
    return {
        "count": len(invoices),
        "total": round(sum(total(inv) for inv in invoices), 2),
        "by_currency": dict(sorted(by_currency.items())),
    }
