"""Hidden grader: ledger history migrations (exp06 stratum B)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

import ledger
from ledger import cli, store
from ledger.migrations import apply_ops, check, latest_version, load_migrations, upgrade

PKG_MIGRATIONS = Path(ledger.__file__).parent / "migrations"
ORIGINAL_STATUS = {
    "id": "m-c47a", "description": "runner status words and job_costs key",
    "ops": [{"op": "map_values", "field": "status", "mapping": {"ok": "success", "error": "failed"}},
            {"op": "rename_field", "from": "jobs", "to": "job_costs"}],
}


def test_collision_resolved_by_renumbering():
    names = sorted(p.name for p in PKG_MIGRATIONS.glob("*.json"))
    assert names == ["0000_initial.json", "0001_add_currency.json", "0002_add_tags.json", "0003_status_values.json"]
    doc = json.loads((PKG_MIGRATIONS / "0003_status_values.json").read_text())
    assert doc["version"] == 4 and doc["prev_id"] == "m-91d0"
    assert {k: doc[k] for k in ORIGINAL_STATUS} == ORIGINAL_STATUS
    tags = json.loads((PKG_MIGRATIONS / "0002_add_tags.json").read_text())
    assert tags["version"] == 3 and tags["prev_id"] == "m-2b9e"
    migrations = load_migrations()
    assert [m.number for m in migrations] == [0, 1, 2, 3]
    assert check(migrations) == []
    assert latest_version(migrations) == 4


def _chain(tmp_path, docs):
    d = tmp_path / "m"
    d.mkdir(exist_ok=True)
    for name, doc in docs.items():
        (d / name).write_text(json.dumps(doc))
    return load_migrations(d)


BASE = {"id": "a", "prev_id": None, "version": 1, "description": "", "ops": []}
ONE = {"id": "b", "prev_id": "a", "version": 2, "description": "", "ops": [{"op": "drop_field", "field": "x"}]}
TWO = {"id": "c", "prev_id": "b", "version": 3, "description": "", "ops": []}


def test_valid_chain(tmp_path):
    assert check(_chain(tmp_path, {"0000_a.json": BASE, "0001_b.json": ONE, "0002_c.json": TWO})) == []


@pytest.mark.parametrize("docs", [
    {"0000_a.json": BASE, "0002_c.json": dict(TWO, prev_id="a", version=3)},                       # gap
    {"0000_a.json": BASE, "0001_b.json": ONE, "0001_c.json": dict(TWO, version=2)},                  # duplicate number
    {"0000_a.json": dict(BASE, prev_id="z"), "0001_b.json": ONE},                                    # baseline prev_id
    {"0000_a.json": dict(BASE, ops=[{"op": "drop_field", "field": "x"}]), "0001_b.json": ONE},       # baseline ops
    {"0000_a.json": BASE, "0001_b.json": ONE, "0002_c.json": dict(TWO, prev_id="a")},                # wrong prev
    {"0000_a.json": BASE, "0001_b.json": ONE, "0002_c.json": dict(TWO, version=4)},                  # version
    {"0000_a.json": BASE, "0001_b.json": ONE, "0002_c.json": dict(TWO, id="b")},                     # duplicate id
    {"0000_a.json": BASE, "0001_b.json": dict(ONE, ops=[{"op": "explode"}])},                        # unknown op
])
def test_chain_violations_detected(tmp_path, docs):
    assert check(_chain(tmp_path, docs)) != []


def test_apply_ops():
    doc = {"a": 1, "status": "ok", "jobs": {"j": 1.0}}
    ops = [
        {"op": "add_field", "field": "tags", "default": []},
        {"op": "add_field", "field": "a", "default": 99},
        {"op": "map_values", "field": "status", "mapping": {"ok": "success"}},
        {"op": "map_values", "field": "missing", "mapping": {"x": "y"}},
        {"op": "rename_field", "from": "jobs", "to": "job_costs"},
        {"op": "rename_field", "from": "nope", "to": "other"},
        {"op": "drop_field", "field": "a"},
        {"op": "drop_field", "field": "never"},
    ]
    out = apply_ops(doc, ops)
    assert out == {"status": "success", "job_costs": {"j": 1.0}, "tags": []}
    assert doc == {"a": 1, "status": "ok", "jobs": {"j": 1.0}}, "input mutated"
    out["tags"].append("x")
    assert apply_ops({}, ops[:1]) == {"tags": []}, "default shared between records"
    with pytest.raises(ValueError):
        apply_ops({"jobs": 1, "job_costs": 2}, [{"op": "rename_field", "from": "jobs", "to": "job_costs"}])


V1 = {"version": 1, "run_id": "r1", "pipeline": "nightly", "started_at": "2026-09-01T02:00:00+00:00",
      "status": "ok", "total_usd": 1.5, "jobs": {"j": 1.5}}


def test_upgrade_record():
    migrations = load_migrations()
    up = upgrade(V1, migrations)
    assert up == {"version": 4, "run_id": "r1", "pipeline": "nightly", "started_at": "2026-09-01T02:00:00+00:00",
                  "status": "success", "total_usd": 1.5, "job_costs": {"j": 1.5}, "currency": "USD", "tags": []}
    v3 = dict(V1, version=3, currency="EUR", tags=["x"], status="error")
    assert upgrade(v3, migrations)["status"] == "failed" and upgrade(v3, migrations)["currency"] == "EUR"
    assert upgrade(up, migrations) == up
    with pytest.raises(ValueError):
        upgrade(dict(V1, version=5), migrations)


def test_store_reads_mixed_and_writes_latest(tmp_path):
    assert store.FORMAT_VERSION == 4
    path = tmp_path / "h.jsonl"
    v2 = dict(V1, version=2, run_id="r2", currency="EUR", status="error")
    path.write_text(json.dumps(V1) + "\n" + json.dumps(v2) + "\n")
    rec = store.RunRecord("r3", "hourly", datetime(2026, 9, 2, tzinfo=UTC), "success", 2.0, {"j": 2.0}, currency="USD", tags=("adhoc",))
    store.append(path, rec)
    loaded = {r.run_id: r for r in store.load(path)}
    assert loaded["r1"].status == "success" and loaded["r1"].jobs == {"j": 1.5} and loaded["r1"].tags == ()
    assert loaded["r2"].currency == "EUR" and loaded["r2"].status == "failed"
    assert loaded["r3"] == rec
    last = json.loads(path.read_text().splitlines()[-1])
    assert last == {"version": 4, "run_id": "r3", "pipeline": "hourly", "started_at": "2026-09-02T00:00:00+00:00",
                    "status": "success", "total_usd": 2.0, "job_costs": {"j": 2.0}, "currency": "USD", "tags": ["adhoc"]}
    assert path.read_text().splitlines()[0] == json.dumps(V1)
    path.write_text(json.dumps(dict(V1, version=9)) + "\n")
    with pytest.raises(ValueError):
        store.load(path)


def test_cli(tmp_path, capsys):
    assert cli.main(["migrations", "check"]) == 0
    assert capsys.readouterr().out.strip() == "ok (latest version 4)"
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "0000_a.json").write_text(json.dumps(BASE))
    (bad / "0002_c.json").write_text(json.dumps(dict(TWO, prev_id="a")))
    assert cli.main(["migrations", "check", "--dir", str(bad)]) == 1
    assert capsys.readouterr().out.strip()
    history, out = tmp_path / "h.jsonl", tmp_path / "new.jsonl"
    history.write_text(json.dumps(V1) + "\n")
    assert cli.main(["migrate", str(history), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["version"] == 4
    assert history.read_text() == json.dumps(V1) + "\n"
    out.write_text("keep")
    assert cli.main(["migrate", str(history), "--out", str(out)]) == 2
    assert out.read_text() == "keep"
    assert cli.main(["migrate", str(history), "--out", str(history)]) == 2
