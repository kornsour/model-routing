"""Push invoices to a (simulated) remote billing API.

There is no real network call here: ``send_one`` is a stand-in for an HTTP
client that occasionally rate-limits the caller. Tests inject a fake
``sender`` with the same signature.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from invoicing.models import Invoice


class RateLimited(Exception):
    """Raised by a sender when the remote asks the caller to slow down."""

    def __init__(self, retry_after: float):
        super().__init__(f"rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


Sender = Callable[[Invoice], None]


def send_all(invoices: list[Invoice], sender: Sender, max_retries: int = 3) -> list[str]:
    """Send every invoice with ``sender``; return the ids that were sent.

    Retries a rate-limited invoice by sleeping for the exact ``retry_after``
    the remote reported, up to ``max_retries`` attempts. An invoice still
    rate-limited after that many attempts is skipped (not included in the
    returned ids) rather than aborting the rest of the batch.
    """
    sent: list[str] = []
    for invoice in invoices:
        attempts = 0
        while True:
            try:
                sender(invoice)
            except RateLimited as exc:
                attempts += 1
                if attempts > max_retries:
                    break
                time.sleep(exc.retry_after)
                continue
            else:
                sent.append(invoice.id)
                break
    return sent
