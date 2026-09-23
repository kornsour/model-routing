"""JSON-file backed store for notes, including id assignment.

Note ids must be unique and stable. The store is the only thing that should
mint new ids (:meth:`Store.add`); anything that constructs a ``Note`` with an
id of its own - such as a bulk importer - must ask the store for the next id
rather than guessing, or it can collide with ids the store already handed
out.

Several ``notes`` processes may share one file - people keep a second
terminal open. A :class:`Store` that is already open therefore promises that
:meth:`Store.get` reflects anything another ``Store`` has saved to the same
file since it was opened: a lookup never answers from stale data.
"""

from __future__ import annotations

import json
from pathlib import Path

from notes.models import Note


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._signature = self._stat()
        self.notes: list[Note] = self._load()

    def _stat(self) -> tuple[int, int] | None:
        """A cheap fingerprint of the file on disk (mtime, size), or ``None`` if absent."""
        try:
            st = self.path.stat()
        except FileNotFoundError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def _load(self) -> list[Note]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text() or "[]")
        return [Note.from_dict(r) for r in raw]

    def reload(self) -> None:
        """Re-read the file so lookups see what other processes have saved."""
        self._signature = self._stat()
        self.notes = self._load()

    def refresh(self) -> None:
        """Re-read the file only if it changed on disk since we last read or wrote it."""
        if self._stat() != self._signature:
            self.reload()

    def save(self) -> None:
        self.path.write_text(json.dumps([n.to_dict() for n in self.notes], indent=2))
        self._signature = self._stat()

    def next_id(self) -> int:
        return max((n.id for n in self.notes), default=0) + 1

    def add(self, text: str, tags: list[str] | None = None, due: str | None = None) -> Note:
        note = Note(id=self.next_id(), text=text, tags=list(tags or []), due=due)
        self.notes.append(note)
        self.save()
        return note

    def get(self, note_id: int) -> Note | None:
        self.refresh()
        for note in self.notes:
            if note.id == note_id:
                return note
        return None

    def mark_done(self, note_id: int) -> bool:
        note = self.get(note_id)
        if note is None:
            return False
        note.done = True
        self.save()
        return True
