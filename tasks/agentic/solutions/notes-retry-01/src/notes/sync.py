"""Push notes to a (simulated) remote notebook service.

There is no real network call: ``push`` stands in for an HTTP client that
occasionally rate-limits the caller. Tests inject a fake ``pusher`` with the
same signature.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from notes.models import Note


class RateLimited(Exception):
    """Raised by a pusher when the remote asks the caller to slow down."""

    def __init__(self, retry_after: float):
        super().__init__(f"rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


Pusher = Callable[[Note], None]


def push_all(notes: list[Note], pusher: Pusher, max_retries: int = 3) -> list[int]:
    """Push every note with ``pusher``; return the ids that were pushed.

    Retries a rate-limited note by sleeping for the exact ``retry_after`` the
    remote reported, up to ``max_retries`` attempts. A note still rate-
    limited after that many attempts is skipped (not included in the
    returned ids) rather than aborting the rest of the batch.
    """
    pushed: list[int] = []
    for note in notes:
        attempts = 0
        while True:
            try:
                pusher(note)
            except RateLimited as exc:
                attempts += 1
                if attempts > max_retries:
                    break
                time.sleep(exc.retry_after)
                continue
            else:
                pushed.append(note.id)
                break
    return pushed
