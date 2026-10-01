import json
from datetime import UTC, datetime

from ledger import audit, store


def _rec(i, month):
    return store.RunRecord(f"r{i}", "p", datetime(2026, month, 1, tzinfo=UTC), "success", float(i), {})


def test_chain_verifies_and_detects_edit(tmp_path):
    path = tmp_path / "h.jsonl"
    for i in range(3):
        store.append(path, _rec(i, 7))
    assert audit.verify(path).ok
    lines = path.read_text().splitlines()
    doc = json.loads(lines[1])
    doc["status"] = "failed"
    lines[1] = json.dumps(doc)
    path.write_text("\n".join(lines) + "\n")
    assert audit.verify(path).bad_line == 2


def test_compaction_keeps_chain(tmp_path):
    path, out = tmp_path / "h.jsonl", tmp_path / "c.jsonl"
    for i, month in enumerate((6, 6, 7)):
        store.append(path, _rec(i, month))
    assert audit.compact(path, out, "2026-07")
    assert audit.verify(out).ok and [r.run_id for r in store.load(out)] == ["r2"]
