from notes.ics import export_ics, import_ics
from notes.models import Note


def test_ics_roundtrip_simple(tmp_path):
    notes = [
        Note(id=1, text="Buy milk", tags=["errand"], due="2024-03-01"),
        Note(id=2, text="Walk the dog", done=True),
    ]
    path = tmp_path / "notes.ics"
    export_ics(notes, path)

    back = import_ics(path)
    assert [(n.text, n.tags, n.due, n.done) for n in back] == [
        ("Buy milk", ["errand"], "2024-03-01", False),
        ("Walk the dog", [], None, True),
    ]


def test_ics_has_calendar_envelope(tmp_path):
    path = tmp_path / "notes.ics"
    export_ics([Note(id=1, text="Buy milk")], path)
    text = path.read_text()
    assert text.startswith("BEGIN:VCALENDAR")
    assert "BEGIN:VTODO" in text
    assert "UID:note-1@notes" in text
