"""Push notes to a (simulated) remote notebook service.

There is no real network call: ``push`` stands in for an HTTP client that
occasionally rate-limits the caller. Tests inject a fake ``pusher`` with the
same signature.

Incremental sync: :func:`sync_changed` pushes only what the remote has not
seen yet and records what it pushed in a small JSON state file kept next to
the store (``notes sync`` uses ``<db>.sync.json``), so the next run starts
where this one left off instead of re-sending the whole notebook.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

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


def load_state(path: str | Path) -> dict:
    """The sync state at ``path`` (``{}`` if there is none yet)."""
    state_path = Path(path)
    if not state_path.exists():
        return {}
    return json.loads(state_path.read_text() or "{}")


def save_state(path: str | Path, state: dict) -> None:
    Path(path).write_text(json.dumps(state, indent=2))


def sync_changed(
    notes: list[Note], pusher: Pusher, state_path: str | Path, max_retries: int = 3
) -> list[int]:
    """Push the notes the remote has not seen yet; return the ids pushed this run.

    ``max_retries`` is how many attempts a note that the remote rate-limits
    gets before it is skipped for this run; the remote's ``retry_after`` says
    how long to wait between attempts.
    """
    state = load_state(state_path)
    last_id = int(state.get("last_id", 0))
    pushed: list[int] = []
    for note in notes:
        if note.id <= last_id:
            continue
        pusher(note)
        pushed.append(note.id)
    if pushed:
        state["last_id"] = max(pushed)
    save_state(state_path, state)
    return pushed
