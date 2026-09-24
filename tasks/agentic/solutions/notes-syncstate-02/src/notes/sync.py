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
import time
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


def _fingerprint(note: Note) -> str:
    """What the remote last saw of a note: any field change changes this."""
    return json.dumps(note.to_dict(), sort_keys=True)


def _push_with_retries(note: Note, pusher: Pusher, max_retries: int) -> bool:
    """Push one note, honouring ``retry_after``; ``False`` if still rate-limited."""
    for attempt in range(1, max_retries + 1):
        try:
            pusher(note)
        except RateLimited as exc:
            if attempt == max_retries:
                return False
            time.sleep(exc.retry_after)
        else:
            return True
    return False


def sync_changed(
    notes: list[Note], pusher: Pusher, state_path: str | Path, max_retries: int = 3
) -> list[int]:
    """Push the notes the remote has not seen yet; return the ids pushed this run.

    A note counts as seen when its current content matches what the state
    file recorded at its last successful push. ``max_retries`` is how many
    attempts a rate-limited note gets before it is skipped for this run (it
    is picked up again next time); the remote's ``retry_after`` says how
    long to wait between attempts. The state file is updated after every
    successful push, so a failure later in the batch never forgets progress.
    """
    state = load_state(state_path)
    seen: dict[str, str] = dict(state.get("pushed", {}))
    pushed: list[int] = []
    try:
        for note in notes:
            fingerprint = _fingerprint(note)
            if seen.get(str(note.id)) == fingerprint:
                continue
            if _push_with_retries(note, pusher, max_retries):
                seen[str(note.id)] = fingerprint
                pushed.append(note.id)
    finally:
        state["pushed"] = seen
        save_state(state_path, state)
    return pushed
