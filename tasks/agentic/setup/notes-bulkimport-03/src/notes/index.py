"""Word index for ``notes search``, kept on disk next to the store.

For a store at ``notes.json`` the index lives in ``notes.json.idx.json`` and
maps each lowercased word to the ids of the notes whose text contains it, so
``search`` can answer from the index instead of scanning every note. The
store keeps the index up to date as notes are added; a store file with no
index yet gets one built on first open.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from notes.models import Note

_WORD = re.compile(r"\w+")


def words(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text)}


class WordIndex:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def _load(self) -> dict[str, list[int]]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text() or "{}")

    def _save(self, data: dict[str, list[int]]) -> None:
        self.path.write_text(json.dumps(data, indent=1, sort_keys=True))

    def add(self, note: Note) -> None:
        """Index one note's text."""
        data = self._load()
        for word in words(note.text):
            ids = data.setdefault(word, [])
            if note.id not in ids:
                ids.append(note.id)
        self._save(data)

    def rebuild(self, notes: list[Note]) -> None:
        """Throw the index away and index ``notes`` from scratch."""
        data: dict[str, list[int]] = {}
        for note in notes:
            for word in words(note.text):
                data.setdefault(word, []).append(note.id)
        self._save(data)

    def lookup(self, query: str) -> set[int]:
        """Ids of the notes whose text contains every word of ``query``."""
        wanted = words(query)
        if not wanted:
            return set()
        data = self._load()
        found = [set(data.get(word, [])) for word in wanted]
        return set.intersection(*found)
