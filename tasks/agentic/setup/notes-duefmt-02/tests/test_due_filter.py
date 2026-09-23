from notes.models import Note
from notes.search import filter_due_before, sort_by_due


def test_filter_due_before_iso():
    notes = [
        Note(id=1, text="a", due="2024-03-01"),
        Note(id=2, text="b", due="2024-02-01"),
        Note(id=3, text="c"),
    ]
    assert [n.id for n in filter_due_before(notes, "2024-02-15")] == [2]


def test_sort_by_due_iso_dated_first():
    notes = [
        Note(id=1, text="a", due="2024-03-01"),
        Note(id=2, text="b"),
        Note(id=3, text="c", due="2024-02-01"),
    ]
    assert [n.id for n in sort_by_due(notes)] == [3, 1, 2]
