from logproc.csvexport import export_csv, import_csv
from logproc.parser import LogEntry


def test_export_import_roundtrip_with_embedded_comma(tmp_path):
    entries = [
        LogEntry(
            timestamp="2024-03-01T10:00:00",
            level="ERROR",
            message="failed to connect, retrying",
        )
    ]
    path = tmp_path / "entries.csv"
    export_csv(entries, path)

    imported = import_csv(path)
    assert len(imported) == 1
    assert imported[0].message == "failed to connect, retrying"
