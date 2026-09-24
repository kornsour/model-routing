"""``notes agenda``: open to-dos coming up over the next few days, by day.

The agenda covers ``days`` calendar days starting with today, so ``days=1``
is today alone and the default ``days=7`` is today plus the following six
days. Completed notes and notes without a due date are left out, and so are
overdue ones (``list --overdue`` shows those).
"""

from __future__ import annotations

from datetime import date, timedelta

from notes import clock
from notes.dates import parse_due
from notes.models import Note


def agenda(notes: list[Note], days: int = 7) -> list[tuple[date, list[Note]]]:
    """Return ``(day, notes due that day)`` pairs in date order, skipping empty days."""
    if days < 1:
        raise ValueError("days must be >= 1")
    start = clock.today()
    end = start + timedelta(days=days - 1)
    by_day: dict[date, list[Note]] = {}
    for note in notes:
        if note.done or not note.due:
            continue
        due = parse_due(note.due)
        if start <= due <= end:
            by_day.setdefault(due, []).append(note)
    return sorted(by_day.items())
