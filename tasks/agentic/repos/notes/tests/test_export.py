from notes.export import export_csv, import_csv
from notes.models import Note


def test_export_then_import_roundtrip(tmp_path):
    notes = [Note(id=1, text="Buy milk", tags=["errand"], due="2024-03-01")]
    path = tmp_path / "notes.csv"
    export_csv(notes, path)

    imported = import_csv(path)
    assert len(imported) == 1
    assert imported[0].text == "Buy milk"
    assert imported[0].tags == ["errand"]
