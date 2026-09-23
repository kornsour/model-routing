"""Export notes to a flat CSV: id,text,tags,due,done."""

from __future__ import annotations

from pathlib import Path

from notes.models import Note

HEADER = "id,text,tags,due,done"


def export_csv(notes: list[Note], path: str | Path) -> None:
    lines = [HEADER]
    for note in notes:
        fields = [
            str(note.id),
            note.text,
            "|".join(note.tags),
            note.due or "",
            str(note.done),
        ]
        lines.append(",".join(fields))
    Path(path).write_text("\n".join(lines) + "\n")


def import_csv(path: str | Path) -> list[Note]:
    text = Path(path).read_text()
    rows = [line for line in text.splitlines() if line.strip()]
    if not rows or rows[0] != HEADER:
        raise ValueError("missing or unexpected CSV header")

    notes = []
    for row in rows[1:]:
        note_id, text_field, tags, due, done = row.split(",")
        notes.append(
            Note(
                id=int(note_id),
                text=text_field,
                tags=[t for t in tags.split("|") if t],
                due=due or None,
                done=done == "True",
            )
        )
    return notes
