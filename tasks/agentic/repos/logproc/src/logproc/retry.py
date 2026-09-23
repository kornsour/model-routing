"""Push a batch summary to a (simulated) remote metrics endpoint.

There is no real network call: ``push_summary`` stands in for an HTTP client
that occasionally rate-limits the caller. Tests inject a fake ``sender`` with
the same signature.
"""

from __future__ import annotations

from collections.abc import Callable


class RateLimited(Exception):
    """Raised by a sender when the remote asks the caller to slow down."""

    def __init__(self, retry_after: float):
        super().__init__(f"rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


Sender = Callable[[dict], None]


def push_summary(summary: dict, sender: Sender) -> bool:
    """Send ``summary`` with ``sender``; return whether it was sent.

    Does not retry: a single :class:`RateLimited` from ``sender`` means the
    summary for this batch is simply lost, even though the remote only asked
    for a pause.
    """
    sender(summary)
    return True
