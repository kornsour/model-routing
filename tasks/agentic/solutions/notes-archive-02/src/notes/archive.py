"""Move completed notes out of the main store into an archive store.

The archive is an ordinary :class:`~notes.store.Store` file (``notes
archive`` writes ``<db>.archive.json`` unless ``--to`` says otherwise), so
anything that reads a store - ``list``, ``search``, ``export`` pointed at it
with ``--db`` - works on the archive too, and it must keep a store's
guarantees, ids included. Losing a note is worse than duplicating one.
"""

from __future__ import annotations

from pathlib import Path

from notes.models import Note
from notes.store import Store


def archive_done(store: Store, archive_path: str | Path) -> list[int]:
    """Move every completed note in ``store`` to the store at ``archive_path``.

    Returns the ids (in the main store) of the notes that were moved, empty
    when there was nothing to do. Archived notes get fresh ids from the
    archive store so they can never collide with what it already holds.
    The archive is written before the main store is trimmed: a failure in
    between duplicates notes rather than losing them.
    """
    done = [note for note in store.notes if note.done]
    if not done:
        return []

    archive = Store(archive_path)
    for note in done:
        archive.notes.append(
            Note(
                id=archive.next_id(),
                text=note.text,
                tags=list(note.tags),
                due=note.due,
                done=note.done,
            )
        )
    archive.save()

    store.notes = [note for note in store.notes if not note.done]
    store.save()
    return [note.id for note in done]
