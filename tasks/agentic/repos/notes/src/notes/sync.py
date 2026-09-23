"""Push notes to a (simulated) remote notebook service.

There is no real network call: ``push`` stands in for an HTTP client that
occasionally rate-limits the caller. Tests inject a fake ``pusher`` with the
same signature.
"""

from __future__ import annotations

from collections.abc import Callable

from notes.models import Note


class RateLimited(Exception):
    """Raised by a pusher when the remote asks the caller to slow down."""

    def __init__(self, retry_after: float):
        super().__init__(f"rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


Pusher = Callable[[Note], None]


def push_all(notes: list[Note], pusher: Pusher) -> list[int]:
    """Push every note with ``pusher``; return the ids that were pushed.

    Does not retry: a single :class:`RateLimited` aborts the whole batch,
    leaving later notes unsent even though the remote only asked for a pause.
    """
    pushed: list[int] = []
    for note in notes:
        pusher(note)
        pushed.append(note.id)
    return pushed
