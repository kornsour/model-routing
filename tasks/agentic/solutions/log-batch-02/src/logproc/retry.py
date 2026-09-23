"""Push batch summaries to a (simulated) remote metrics endpoint.

There is no real network call: ``push_summary`` and ``push_batches`` stand
in for an HTTP client that occasionally rate-limits the caller. Tests inject
a fake ``sender`` with the same signature.

The remote's contract: a call that returns normally was accepted and is
recorded on the remote side - sending the same payload again records it
twice. A call that raises :class:`RateLimited` recorded nothing and asks the
caller to wait ``retry_after`` seconds before trying again.
"""

from __future__ import annotations

import time
from collections.abc import Callable


class RateLimited(Exception):
    """Raised by a sender when the remote asks the caller to slow down."""

    def __init__(self, retry_after: float):
        super().__init__(f"rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


Sender = Callable[[dict], None]
BatchSender = Callable[[list[dict]], None]


def push_summary(summary: dict, sender: Sender) -> bool:
    """Send ``summary`` with ``sender``; return whether it was sent.

    Does not retry: a single :class:`RateLimited` from ``sender`` means the
    summary for this batch is simply lost, even though the remote only asked
    for a pause.
    """
    sender(summary)
    return True


def _send_with_retries(batch: list[dict], sender: BatchSender, max_retries: int) -> bool:
    """Send one batch, retrying up to ``max_retries`` times on :class:`RateLimited`."""
    for attempt in range(max_retries + 1):
        try:
            sender(batch)
        except RateLimited as exc:
            if attempt == max_retries:
                return False
            time.sleep(exc.retry_after)
        else:
            return True
    return False


def push_batches(
    summaries: list[dict], sender: BatchSender, batch_size: int = 10, max_retries: int = 3
) -> int:
    """Send ``summaries`` to ``sender`` in batches of ``batch_size``; return how many were sent.

    Each batch is delivered exactly once: a batch the remote accepted is never
    sent again, and a rate-limited batch is retried (after the ``retry_after``
    the remote asked for) up to ``max_retries`` times. If a batch is still
    rate-limited after that, the run stops there and the count of summaries
    delivered so far is returned; nothing is raised.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    sent = 0
    for start in range(0, len(summaries), batch_size):
        batch = summaries[start : start + batch_size]
        if not _send_with_retries(batch, sender, max_retries):
            return sent
        sent += len(batch)
    return sent
