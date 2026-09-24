"""Builds the end-of-run summary report from a :class:`invoicing.storage.Store`."""

from __future__ import annotations

import json

from invoicing.calc import total
from invoicing.fx import RateProvider, to_usd
from invoicing.models import Invoice
from invoicing.storage import Store


def _invoices_on_disk(store: Store) -> list[Invoice]:
    if not store.path.exists():
        return []
    raw = json.loads(store.path.read_text() or "[]")
    return [Invoice.from_dict(r) for r in raw]


def generate_summary(store: Store, rates: RateProvider | None = None) -> dict:
    """Count and total the invoices in ``store``.

    Reads the store's on-disk file, since that is what a second process (or a
    later run of this CLI) would see. Callers in the same process must
    ``store.flush()`` before calling this if they just added invoices.

    ``total`` adds up invoice totals in their own currencies. When ``rates``
    is given, ``total_usd`` is the same total with each invoice converted to
    US dollars.
    """
    invoices = _invoices_on_disk(store)
    summary: dict = {
        "count": len(invoices),
        "total": round(sum(total(inv) for inv in invoices), 2),
    }
    if rates is not None:
        summary["total_usd"] = round(
            sum(to_usd(total(inv), inv.currency, rates) for inv in invoices), 2
        )
    return summary
