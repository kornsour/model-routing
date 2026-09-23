from notes.export import export_csv, import_csv
from notes.models import Note


def test_export_import_roundtrip_with_embedded_comma(tmp_path):
    notes = [Note(id=1, text="Buy milk, eggs, and bread", tags=["errand"], due="2024-03-01")]
    path = tmp_path / "notes.csv"
    export_csv(notes, path)

    imported = import_csv(path)
    assert len(imported) == 1
    assert imported[0].text == "Buy milk, eggs, and bread"
    assert imported[0].tags == ["errand"]


def test_export_import_roundtrip_with_tricky_tag(tmp_path):
    notes = [Note(id=1, text="Plan trip", tags=["errand|urgent", "home"])]
    path = tmp_path / "notes.csv"
    export_csv(notes, path)

    imported = import_csv(path)
    assert imported[0].tags == ["errand|urgent", "home"]
