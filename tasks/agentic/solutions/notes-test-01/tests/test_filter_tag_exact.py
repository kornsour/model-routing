from notes.models import Note
from notes.tags import filter_tag


def test_filter_tag_is_exact_not_substring():
    notes = [
        Note(id=1, text="Buy groceries", tags=["errand"]),
        Note(id=2, text="Plan the trip", tags=["errands-weekend"]),
    ]
    matched = filter_tag(notes, "errand")
    assert [n.id for n in matched] == [1]
