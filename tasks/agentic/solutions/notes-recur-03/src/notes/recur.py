"""Repeating to-dos: work out and create the next occurrence on completion.

See the ``repeat`` field on :class:`notes.models.Note` for the rules.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from notes.dates import parse_due
from notes.models import REPEATS, Note
from notes.store import Store


def _on_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def next_due(due: date, repeat: str, day: int | None = None) -> date:
    """Return the due date of the occurrence after one due on ``due``.

    ``day`` is the day of the month a monthly/yearly to-do was first due
    (defaults to ``due.day``).
    """
    if repeat not in REPEATS:
        raise ValueError(f"unknown repeat: {repeat!r}")
    if repeat == "daily":
        return due + timedelta(days=1)
    if repeat == "weekly":
        return due + timedelta(weeks=1)
    day = day or due.day
    if repeat == "monthly":
        year, month = (due.year + 1, 1) if due.month == 12 else (due.year, due.month + 1)
        return _on_day(year, month, day)
    return _on_day(due.year + 1, due.month, day)


def complete(store: Store, note_id: int) -> Note | None:
    """Mark ``note_id`` done and save; return the next occurrence if one was added.

    Raises ``KeyError`` when there is no such note.
    """
    note = store.get(note_id)
    if note is None:
        raise KeyError(note_id)
    if note.done:
        return None
    note.done = True
    following = None
    if note.repeat and note.due:
        current = parse_due(note.due)
        day = None
        if note.repeat in ("monthly", "yearly"):
            day = note.repeat_day or current.day
        following = Note(
            id=store.next_id(),
            text=note.text,
            tags=list(note.tags),
            due=next_due(current, note.repeat, day).isoformat(),
            repeat=note.repeat,
            repeat_day=day,
        )
        store.notes.append(following)
    store.save()
    return following
