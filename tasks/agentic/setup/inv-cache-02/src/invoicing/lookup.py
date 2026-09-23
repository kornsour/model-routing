"""Look up stored invoices by id.

Thin helpers over :class:`invoicing.storage.Store`, used by the ``show``
command and by batch scripts that resolve many ids at once (a status check
after an import, a reconciliation run against the remote billing service).
"""

from __future__ import annotations

from invoicing.models import Invoice
from invoicing.storage import Store


def find(store: Store, invoice_id: str) -> Invoice | None:
    """The invoice with ``invoice_id`` (on disk or not yet flushed), or ``None``."""
    for invoice in store.all():
        if invoice.id == invoice_id:
            return invoice
    return None


def find_many(store: Store, invoice_ids: list[str]) -> dict[str, Invoice | None]:
    """Resolve every id in ``invoice_ids``; ids the store does not hold map to ``None``."""
    return {invoice_id: find(store, invoice_id) for invoice_id in invoice_ids}
