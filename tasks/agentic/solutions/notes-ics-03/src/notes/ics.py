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
_MAX_OCTETS = 75


def _escape(text: str) -> str:
    """Escape a TEXT value (RFC 5545 section 3.3.11)."""
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _split_text_list(value: str) -> list[str]:
    """Split a comma-separated list of TEXT values and unescape each one."""
    items: list[str] = []
    current: list[str] = []
    chars = iter(value)
    for ch in chars:
        if ch == "\\":
            nxt = next(chars, "")
            current.append("\n" if nxt in ("n", "N") else nxt)
        elif ch == ",":
            items.append("".join(current))
            current = []
        else:
            current.append(ch)
    items.append("".join(current))
    return items


def _unescape(value: str) -> str:
    out: list[str] = []
    chars = iter(value)
    for ch in chars:
        if ch == "\\":
            nxt = next(chars, "")
            out.append("\n" if nxt in ("n", "N") else nxt)
        else:
            out.append(ch)
    return "".join(out)


def _fold(line: str) -> list[str]:
    """Fold a content line into physical lines of at most 75 octets (section 3.1)."""
    parts: list[str] = []
    current = ""
    size = 0
    for ch in line:
        width = len(ch.encode("utf-8"))
        if size + width > _MAX_OCTETS:
            parts.append(current)
            current, size = " ", 1
        current += ch
        size += width
    parts.append(current)
    return parts


def export_ics(notes: list[Note], path: str | Path) -> None:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}"]
    for note in notes:
        lines.append("BEGIN:VTODO")
        lines.append(f"UID:note-{note.id}@notes")
        lines.append(f"SUMMARY:{_escape(note.text)}")
        if note.tags:
            lines.append("CATEGORIES:" + ",".join(_escape(t) for t in note.tags))
        if note.due:
            lines.append("DUE;VALUE=DATE:" + note.due.replace("-", ""))
        lines.append("STATUS:" + ("COMPLETED" if note.done else "NEEDS-ACTION"))
        lines.append("END:VTODO")
    lines.append("END:VCALENDAR")
    physical = [part for line in lines for part in _fold(line)]
    Path(path).write_bytes(("\r\n".join(physical) + "\r\n").encode("utf-8"))


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        elif raw:
            lines.append(raw)
    return lines


def _split_content_line(line: str) -> tuple[str, str] | None:
    """Return ``(NAME, value)``; the value starts at the first colon outside quotes."""
    in_quotes = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == ":" and not in_quotes:
            head = line[:i]
            name = head.split(";", 1)[0]
            return name.upper(), line[i + 1 :]
    return None


def import_ics(path: str | Path) -> list[Note]:
    notes: list[Note] = []
    current: dict | None = None
    stack: list[str] = []
    for line in _unfold(Path(path).read_bytes().decode("utf-8")):
        parsed = _split_content_line(line)
        if parsed is None:
            continue
        name, value = parsed
        if name == "BEGIN":
            stack.append(value.upper())
            if stack[-1] == "VTODO":
                current = {"text": "", "tags": [], "due": None, "done": False}
            continue
        if name == "END":
            ended = stack.pop() if stack else ""
            if ended == "VTODO" and current is not None:
                notes.append(Note(id=len(notes) + 1, **current))
                current = None
            continue
        if current is None or not stack or stack[-1] != "VTODO":
            continue
        if name == "SUMMARY":
            current["text"] = _unescape(value)
        elif name == "CATEGORIES":
            current["tags"].extend(t for t in _split_text_list(value) if t)
        elif name == "DUE":
            current["due"] = f"{value[:4]}-{value[4:6]}-{value[6:8]}"
        elif name == "STATUS":
            current["done"] = value.upper() == "COMPLETED"
    return notes
