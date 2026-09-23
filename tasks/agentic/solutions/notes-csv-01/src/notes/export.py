"""Export notes to a flat CSV: id,text,tags,due,done.

Tags are stored as a JSON-encoded list in the ``tags`` column, so a tag can
safely contain any character (including ``|`` or a comma) without colliding
with the encoding itself; the ``csv`` module handles quoting/escaping the
column values (including note text) at the row level.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from notes.models import Note

HEADER = ["id", "text", "tags", "due", "done"]


def export_csv(notes: list[Note], path: str | Path) -> None:
    with Path(path).open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for note in notes:
            writer.writerow(
                [
                    note.id,
                    note.text,
                    json.dumps(note.tags),
                    note.due or "",
                    note.done,
                ]
            )


def import_csv(path: str | Path) -> list[Note]:
    with Path(path).open(newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            header = []
        if header != HEADER:
            raise ValueError("missing or unexpected CSV header")

        notes = []
        for row in reader:
            if not row:
                continue
            note_id, text_field, tags, due, done = row
            notes.append(
                Note(
                    id=int(note_id),
                    text=text_field,
                    tags=json.loads(tags) if tags else [],
                    due=due or None,
                    done=done == "True",
                )
            )
    return notes
