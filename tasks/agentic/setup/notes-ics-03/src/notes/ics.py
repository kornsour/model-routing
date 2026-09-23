"""iCalendar export/import: notes as RFC 5545 ``VTODO`` components.

``export_ics`` writes one ``VCALENDAR`` holding a ``VTODO`` per note, and
``import_ics`` reads such a file back - including files written by other
calendar apps, so the reader must accept anything RFC 5545 allows for the
properties it understands. Mapping, per note:

- ``UID`` - ``note-<id>@notes`` (ignored on import; the store assigns ids)
- ``SUMMARY`` - the note text
- ``CATEGORIES`` - the tags, one list value per tag (omitted when untagged)
- ``DUE;VALUE=DATE:YYYYMMDD`` - the due date (omitted when there is none)
- ``STATUS`` - ``COMPLETED`` when done, otherwise ``NEEDS-ACTION``

Any other property, and any component other than ``VTODO``, is ignored on
import.
"""

from __future__ import annotations

from pathlib import Path

from notes.models import Note

PRODID = "-//notes//notes 0.1//EN"


def export_ics(notes: list[Note], path: str | Path) -> None:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}"]
    for note in notes:
        lines.append("BEGIN:VTODO")
        lines.append(f"UID:note-{note.id}@notes")
        lines.append(f"SUMMARY:{note.text}")
        if note.tags:
            lines.append("CATEGORIES:" + ",".join(note.tags))
        if note.due:
            lines.append("DUE;VALUE=DATE:" + note.due.replace("-", ""))
        lines.append("STATUS:" + ("COMPLETED" if note.done else "NEEDS-ACTION"))
        lines.append("END:VTODO")
    lines.append("END:VCALENDAR")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def import_ics(path: str | Path) -> list[Note]:
    notes: list[Note] = []
    current: dict | None = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line == "BEGIN:VTODO":
            current = {"text": "", "tags": [], "due": None, "done": False}
        elif line == "END:VTODO" and current is not None:
            notes.append(Note(id=len(notes) + 1, **current))
            current = None
        elif current is not None and ":" in line:
            name, value = line.split(":", 1)
            name = name.split(";")[0]
            if name == "SUMMARY":
                current["text"] = value
            elif name == "CATEGORIES":
                current["tags"] = value.split(",")
            elif name == "DUE":
                current["due"] = f"{value[:4]}-{value[4:6]}-{value[6:8]}"
            elif name == "STATUS":
                current["done"] = value == "COMPLETED"
    return notes
