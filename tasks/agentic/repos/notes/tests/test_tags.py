from notes.models import Note
from notes.tags import filter_tag, parse_tags


def test_parse_tags():
    assert parse_tags("errand, home ,  ") == ["errand", "home"]


def test_filter_tag():
    notes = [Note(id=1, text="a", tags=["errand"]), Note(id=2, text="b", tags=["home"])]
    assert [n.id for n in filter_tag(notes, "errand")] == [1]
