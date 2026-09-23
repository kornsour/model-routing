"""``notes remind``: a short digest of what needs attention today.

The digest lists open to-dos in three groups, each note at most once:
``overdue`` (due before today), ``today`` (due today) and ``tomorrow``
(due tomorrow). Anything due later, completed, or without a due date is left
out. Each line reads ``<group>: #<id> <text>``, overdue first, then today,
then tomorrow, in store order within a group.
"""

from __future__ import annotations

from datetime import date, timedelta

from notes import clock
from notes.dates import parse_due
from notes.models import Note


def _is_overdue(note: Note, today: date) -> bool:
    return not note.done and note.due is not None and parse_due(note.due) < today


def digest(notes: list[Note], today: date | None = None) -> list[str]:
    today = today or clock.today()
    groups: dict[str, list[Note]] = {"overdue": [], "today": [], "tomorrow": []}
    for note in notes:
        if note.done or not note.due:
            continue
        due = parse_due(note.due)
        if _is_overdue(note, today):
            groups["overdue"].append(note)
        elif due == today:
            groups["today"].append(note)
        elif due == today + timedelta(days=1):
            groups["tomorrow"].append(note)
    return [f"{group}: #{n.id} {n.text}" for group, items in groups.items() for n in items]
