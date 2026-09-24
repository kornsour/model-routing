"""A buffered JSON-file store for invoices.

New invoices are held in memory (``pending``) until :meth:`Store.flush`
writes them to disk. Buffering lets the CLI batch several ``create`` calls
into one disk write. ``invoicing.pipeline`` reads the store's on-disk file
directly to build its summary report, so callers must flush before anything
downstream depends on freshly-added invoices being visible on disk.

An invoice is identified by ``id``: adding one whose id the store already
holds (on disk or pending) replaces the earlier version in place.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from invoicing.models import Invoice


def _parse_created(text: str) -> date:
    """Parse a "created" timestamp for sort order.

    Accepts the same ISO/US formats as ``invoicing.formatting.parse_invoice_date``.
    Kept separate so storage has no dependency on the formatting module.
    """
    text = text.strip()
    if "-" in text:
        y, m, d = text.split("-")
    elif "/" in text:
        m, d, y = text.split("/")
    else:
        raise ValueError(f"unrecognized date: {text!r}")
    return date(int(y), int(m), int(d))


def _merge(base: list[Invoice], updates: list[Invoice]) -> list[Invoice]:
    """``base`` with every invoice in ``updates`` upserted by id, keeping first-seen order."""
    by_id: dict[str, Invoice] = {}
    for invoice in [*base, *updates]:
        by_id[invoice.id] = invoice
    return list(by_id.values())


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.pending: list[Invoice] = []

    def _load_disk(self) -> list[Invoice]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text() or "[]")
        return [Invoice.from_dict(r) for r in raw]

    def add(self, invoice: Invoice) -> None:
        self.pending.append(invoice)

    def flush(self) -> None:
        """Merge pending invoices into the on-disk file and clear the buffer."""
        merged = _merge(self._load_disk(), self.pending)
        self.path.write_text(json.dumps([inv.to_dict() for inv in merged], indent=2))
        self.pending = []

    def all(self) -> list[Invoice]:
        """All invoices, on disk plus any not yet flushed, each id exactly once."""
        return _merge(self._load_disk(), self.pending)

    def sorted_by_created(self, created: dict[str, str]) -> list[Invoice]:
        """``all()`` sorted by a caller-supplied ``{invoice_id: created_date}`` map."""
        invoices = self.all()
        return sorted(invoices, key=lambda inv: _parse_created(created[inv.id]))
