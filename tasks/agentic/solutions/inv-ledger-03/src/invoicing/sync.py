"""Push invoices to a (simulated) remote billing API.

There is no real network call here: ``send_one`` is a stand-in for an HTTP
client that occasionally rate-limits the caller. Tests inject a fake
``sender`` with the same signature.

:func:`sync_store` is what the nightly job runs. It keeps a small JSON
*ledger* file next to the store recording what the remote has already
accepted, so that a nightly run only pushes what the remote does not have
yet. The remote bills (and audits) every call it receives, so pushing an
invoice it already holds is not free.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

from invoicing.models import Invoice
from invoicing.storage import Store


class RateLimited(Exception):
    """Raised by a sender when the remote asks the caller to slow down."""

    def __init__(self, retry_after: float):
        super().__init__(f"rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


Sender = Callable[[Invoice], None]


def send_all(invoices: list[Invoice], sender: Sender) -> list[str]:
    """Send every invoice with ``sender``; return the ids that were sent.

    Does not retry: a single :class:`RateLimited` from ``sender`` aborts the
    whole batch, leaving later invoices unsent even though the remote only
    asked for a pause.
    """
    sent: list[str] = []
    for invoice in invoices:
        sender(invoice)
        sent.append(invoice.id)
    return sent


def _fingerprint(invoice: Invoice) -> str:
    """A digest of everything the remote stores about ``invoice``."""
    payload = json.dumps(invoice.to_dict(), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _read_ledger(path: Path) -> dict[str, str | None]:
    """``{invoice_id: fingerprint}`` of what the remote has accepted.

    Ledgers written before fingerprints existed are a plain JSON list of ids;
    those entries map to ``None`` ("accepted, version not recorded") and are
    treated as up to date.
    """
    if not path.exists():
        return {}
    raw = json.loads(path.read_text() or "{}")
    if isinstance(raw, list):
        return dict.fromkeys(raw)
    return dict(raw)


def _write_ledger(path: Path, synced: dict[str, str | None]) -> None:
    path.write_text(json.dumps(synced, indent=2, sort_keys=True))


def sync_store(store: Store, sender: Sender, ledger_path: str | Path) -> list[str]:
    """Push every invoice in ``store`` that the remote does not have yet.

    Returns the ids sent during this run, in store order. ``ledger_path`` is
    the JSON ledger of what the remote has accepted across earlier runs.
    """
    ledger_path = Path(ledger_path)
    synced = _read_ledger(ledger_path)
    sent: list[str] = []
    for invoice in store.all():
        digest = _fingerprint(invoice)
        if invoice.id in synced and synced[invoice.id] in (None, digest):
            continue
        try:
            sender(invoice)
        except RateLimited:
            break
        synced[invoice.id] = digest
        _write_ledger(ledger_path, synced)
        sent.append(invoice.id)
    return sent
