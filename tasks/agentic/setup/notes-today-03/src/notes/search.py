"""Search, filter, and paginate a list of notes."""

from __future__ import annotations

from datetime import date

from notes.dates import parse_due
from notes.models import Note


def filter_text(notes: list[Note], query: str) -> list[Note]:
    q = query.lower()
    return [n for n in notes if q in n.text.lower()]


def filter_done(notes: list[Note], done: bool) -> list[Note]:
    return [n for n in notes if n.done == done]


def paginate(notes: list[Note], page: int, page_size: int) -> list[Note]:
    """Return the notes on ``page`` (1-indexed), ``page_size`` per page.

    Every note must appear on exactly one page across ``page=1..N``.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")
    start = (page - 1) * page_size
    end = start + page_size
    return notes[start:end]


def filter_overdue(notes: list[Note], today: date) -> list[Note]:
    """Open notes that are past due on ``today`` - due strictly before it."""
    return [n for n in notes if not n.done and n.due and parse_due(n.due) <= today]
