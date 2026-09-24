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


def push_batches(
    summaries: list[dict], sender: BatchSender, batch_size: int = 10, max_retries: int = 3
) -> int:
    """Send ``summaries`` to ``sender`` in batches of ``batch_size``; return how many were sent.

    Currently stops at the first :class:`RateLimited`: that batch and every
    batch after it are lost, and ``max_retries`` is unused. The nightly job
    calls this once per run with the whole night's summaries.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    sent = 0
    for start in range(0, len(summaries), batch_size):
        batch = summaries[start : start + batch_size]
        try:
            sender(batch)
        except RateLimited:
            return sent
        sent += len(batch)
    return sent
