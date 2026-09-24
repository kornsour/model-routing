"""Repeating to-dos: work out and create the next occurrence on completion.

See the ``repeat`` field on :class:`notes.models.Note` for the rules.
"""

from __future__ import annotations

import calendar
from dataclasses import replace
from datetime import date, timedelta

from notes.dates import parse_due
from notes.models import REPEATS, Note
from notes.store import Store


def next_due(due: date, repeat: str) -> date:
    """Return the due date of the occurrence after one due on ``due``."""
    if repeat not in REPEATS:
        raise ValueError(f"unknown repeat: {repeat!r}")
    if repeat == "daily":
        return due + timedelta(days=1)
    if repeat == "weekly":
        return due + timedelta(weeks=1)
    if repeat == "monthly":
        days_in_month = calendar.monthrange(due.year, due.month)[1]
        return due + timedelta(days=days_in_month)
    return due.replace(year=due.year + 1)


def complete(store: Store, note_id: int) -> Note | None:
    """Mark ``note_id`` done and save; return the next occurrence if one was added.

    Raises ``KeyError`` when there is no such note.
    """
    note = store.get(note_id)
    if note is None:
        raise KeyError(note_id)
    note.done = True
    following = None
    if note.repeat and note.due:
        due = next_due(parse_due(note.due), note.repeat)
        following = replace(note, id=store.next_id(), due=due.isoformat())
        store.notes.append(following)
    store.save()
    return following
