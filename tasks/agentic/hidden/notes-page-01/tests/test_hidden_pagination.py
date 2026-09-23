from notes.models import Note
from notes.search import paginate


def test_paginate_exact_multiple_covers_every_note():
    notes = [Note(id=i, text=f"note {i}") for i in range(6)]
    page_size = 3
    seen = []
    for page in (1, 2):
        seen.extend(paginate(notes, page=page, page_size=page_size))
    assert seen == notes
