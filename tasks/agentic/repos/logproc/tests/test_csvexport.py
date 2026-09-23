from logproc.csvexport import export_csv, import_csv
from logproc.parser import LogEntry


def test_export_then_import_roundtrip(tmp_path):
    entries = [LogEntry(timestamp="2024-03-01T10:00:00", level="INFO", message="server started")]
    path = tmp_path / "entries.csv"
    export_csv(entries, path)

    imported = import_csv(path)
    assert len(imported) == 1
    assert imported[0].level == "INFO"
    assert imported[0].message == "server started"
