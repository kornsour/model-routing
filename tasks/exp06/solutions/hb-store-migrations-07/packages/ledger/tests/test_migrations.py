import json

import pytest

from ledger import store
from ledger.migrations import apply_ops, check, load_migrations, upgrade


def test_package_chain_is_valid():
    assert check(load_migrations()) == []


@pytest.mark.parametrize("op,doc,want", [
    ({"op": "add_field", "field": "t", "default": []}, {}, {"t": []}),
    ({"op": "rename_field", "from": "a", "to": "b"}, {"a": 1}, {"b": 1}),
    ({"op": "map_values", "field": "s", "mapping": {"ok": "success"}}, {"s": "ok"}, {"s": "success"}),
    ({"op": "drop_field", "field": "a"}, {"a": 1}, {}),
])
def test_ops(op, doc, want):
    assert apply_ops(doc, [op]) == want


def test_gap_is_reported(tmp_path):
    (tmp_path / "0000_a.json").write_text(json.dumps({"id": "a", "prev_id": None, "version": 1, "ops": []}))
    (tmp_path / "0002_c.json").write_text(json.dumps({"id": "c", "prev_id": "a", "version": 3, "ops": []}))
    assert check(load_migrations(tmp_path))


def test_mixed_history(tmp_path):
    v1 = {"version": 1, "run_id": "r1", "pipeline": "p", "started_at": "2026-09-01T00:00:00+00:00", "status": "ok", "total_usd": 1.0, "jobs": {}}
    path = tmp_path / "h.jsonl"
    path.write_text(json.dumps(v1) + "\n" + json.dumps(upgrade(dict(v1, run_id="r2"), load_migrations())) + "\n")
    assert [r.status for r in store.load(path)] == ["success", "success"]
