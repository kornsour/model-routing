from datetime import UTC, datetime

from ledger import store
from ledger.export import export


def test_export_writes_manifest(tmp_path):
    history = tmp_path / "h.jsonl"
    store.append(history, store.RunRecord("r1", "p", datetime(2026, 9, 1, tzinfo=UTC), "success", 1.0, {}))
    written = export(tmp_path / "out", history)
    assert "pipelines/p.json" in written and (tmp_path / "out" / ".export-manifest.json").exists()
