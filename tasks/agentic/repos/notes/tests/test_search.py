from notes.models import Note
from notes.search import filter_done, filter_text, paginate


def _notes(n):
    return [Note(id=i, text=f"note {i}") for i in range(n)]


def test_filter_text():
    notes = [Note(id=1, text="Buy milk"), Note(id=2, text="Walk the dog")]
    assert [n.id for n in filter_text(notes, "milk")] == [1]


def test_filter_done():
    notes = [Note(id=1, text="a", done=True), Note(id=2, text="b", done=False)]
    assert [n.id for n in filter_done(notes, True)] == [1]


def test_paginate_single_page():
    notes = _notes(3)
    assert paginate(notes, page=1, page_size=10) == notes
