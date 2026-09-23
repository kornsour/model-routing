"""Push invoices to a (simulated) remote billing API.

There is no real network call here: ``send_one`` is a stand-in for an HTTP
client that occasionally rate-limits the caller. Tests inject a fake
``sender`` with the same signature.
"""

from __future__ import annotations

from collections.abc import Callable

from invoicing.models import Invoice


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
