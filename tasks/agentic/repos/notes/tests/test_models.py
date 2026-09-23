from notes.models import Note


def test_note_roundtrip_dict():
    note = Note(id=1, text="Buy milk", tags=["errand"], due="2024-03-01")
    restored = Note.from_dict(note.to_dict())
    assert restored == note
