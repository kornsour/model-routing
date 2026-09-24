"""Search, filter, sort, and paginate a list of notes."""

from __future__ import annotations

from notes.models import Note


def filter_text(notes: list[Note], query: str) -> list[Note]:
    q = query.lower()
    return [n for n in notes if q in n.text.lower()]


def filter_done(notes: list[Note], done: bool) -> list[Note]:
    return [n for n in notes if n.done == done]


def filter_due_before(notes: list[Note], cutoff: str) -> list[Note]:
    """Notes due on or before ``cutoff`` (ISO ``YYYY-MM-DD``); undated notes are left out."""
    return [n for n in notes if n.due is not None and n.due <= cutoff]


def sort_by_due(notes: list[Note]) -> list[Note]:
    """Earliest due date first; undated notes last, in their original order."""
    dated = sorted((n for n in notes if n.due is not None), key=lambda n: n.due or "")
    return dated + [n for n in notes if n.due is None]


def paginate(notes: list[Note], page: int, page_size: int) -> list[Note]:
    """Return the notes on ``page`` (1-indexed), ``page_size`` per page.

    Every note must appear on exactly one page across ``page=1..N``.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")
    start = (page - 1) * page_size
    end = start + page_size - 1
    return notes[start:end]
