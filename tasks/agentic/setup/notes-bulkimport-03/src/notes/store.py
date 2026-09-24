"""JSON-file backed store for notes, including id assignment.

Note ids must be unique and stable. The store is the only thing that should
mint new ids (:meth:`Store.add`); anything that constructs a ``Note`` with an
id of its own - such as a bulk importer - must ask the store for the next id
rather than guessing, or it can collide with ids the store already handed
out.

The store also owns the search index (:mod:`notes.index`) that lives next to
its file: every note the store adds is indexed as it is added.
"""

from __future__ import annotations

import json
from pathlib import Path

from notes.index import WordIndex
from notes.models import Note


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.index = WordIndex(self.path.with_name(self.path.name + ".idx.json"))
        self.notes: list[Note] = self._load()
        if self.notes and not self.index.exists():
            self.index.rebuild(self.notes)

    def _load(self) -> list[Note]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text() or "[]")
        return [Note.from_dict(r) for r in raw]

    def save(self) -> None:
        self.path.write_text(json.dumps([n.to_dict() for n in self.notes], indent=2))

    def next_id(self) -> int:
        return max((n.id for n in self.notes), default=0) + 1

    def add(self, text: str, tags: list[str] | None = None, due: str | None = None) -> Note:
        note = Note(id=self.next_id(), text=text, tags=list(tags or []), due=due)
        self.notes.append(note)
        self.save()
        self.index.add(note)
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
