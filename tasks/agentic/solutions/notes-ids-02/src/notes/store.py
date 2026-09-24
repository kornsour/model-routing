"""JSON-file backed store for notes, including id assignment.

Note ids must be unique and stable. The store is the only thing that should
mint new ids (:meth:`Store.add`); anything that constructs a ``Note`` with an
id of its own - such as a bulk importer - must ask the store for the next id
rather than guessing, or it can collide with ids the store already handed
out.

An id, once handed out for a file, is never handed out again for that file,
even after the note is deleted: things that remember an id (a ``#12``
reference in another note's text, the sync state) must keep pointing at the
same note, or at nothing, never at a different note.

On disk the file is ``{"next_id": N, "notes": [...]}``; ``next_id`` is the
high-water mark that makes the no-reuse promise survive deletes and
restarts. Files written by earlier versions are a bare list of notes and
load the same way, numbering on from their highest id.
"""

from __future__ import annotations

import json
from pathlib import Path

from notes.models import Note


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._next_id = 1
        self.notes: list[Note] = self._load()

    def _load(self) -> list[Note]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text() or "[]")
        if isinstance(raw, dict):
            rows = raw.get("notes", [])
            self._next_id = int(raw.get("next_id", 1))
        else:
            rows = raw
        notes = [Note.from_dict(r) for r in rows]
        self._next_id = max(self._next_id, max((n.id for n in notes), default=0) + 1)
        return notes

    def save(self) -> None:
        # Anything appended directly (e.g. a bulk import) bumps the mark too.
        self._next_id = max(self._next_id, max((n.id for n in self.notes), default=0) + 1)
        payload = {"next_id": self._next_id, "notes": [n.to_dict() for n in self.notes]}
        self.path.write_text(json.dumps(payload, indent=2))

    def next_id(self) -> int:
        return max(self._next_id, max((n.id for n in self.notes), default=0) + 1)

    def add(self, text: str, tags: list[str] | None = None, due: str | None = None) -> Note:
        note = Note(id=self.next_id(), text=text, tags=list(tags or []), due=due)
        self.notes.append(note)
        self.save()
        return note

    def get(self, note_id: int) -> Note | None:
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

    def remove(self, note_id: int) -> bool:
        """Delete the note with ``note_id``; ``False`` if there is no such note."""
        note = self.get(note_id)
        if note is None:
            return False
        self.notes.remove(note)
        self.save()
        return True
