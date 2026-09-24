"""Move completed notes out of the main store into an archive store.

The archive is an ordinary :class:`~notes.store.Store` file (``notes
archive`` writes ``<db>.archive.json`` unless ``--to`` says otherwise), so
anything that reads a store - ``list``, ``search``, ``export`` pointed at it
with ``--db`` - works on the archive too, and it must keep a store's
guarantees, ids included. Losing a note is worse than duplicating one.
"""

from __future__ import annotations

from pathlib import Path

from notes.store import Store


def archive_done(store: Store, archive_path: str | Path) -> list[int]:
    """Move every completed note in ``store`` to the store at ``archive_path``.

    Returns the ids of the notes that were moved (empty when there was
    nothing to do).
    """
    archive = Store(archive_path)
    moved: list[int] = []
    for note in store.notes:
        if note.done:
            archive.notes.append(note)
            store.notes.remove(note)
            moved.append(note.id)
    store.save()
    archive.save()
    return moved
