"""Push a batch summary to a (simulated) remote metrics endpoint.

There is no real network call: ``push_summary`` stands in for an HTTP client
that occasionally rate-limits the caller. Tests inject a fake ``sender`` with
the same signature.
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


def push_summary(summary: dict, sender: Sender, max_retries: int = 3) -> bool:
    """Send ``summary`` with ``sender``; return whether it was sent.

    Retries a rate-limited push by sleeping for the exact ``retry_after`` the
    remote reported, up to ``max_retries`` attempts. Returns ``False``
    (rather than raising) if still rate-limited after that many attempts, so
    an unattended caller can log-and-continue.
    """
    attempts = 0
    while True:
        try:
            sender(summary)
        except RateLimited as exc:
            attempts += 1
            if attempts > max_retries:
                return False
            time.sleep(exc.retry_after)
            continue
        else:
            return True
