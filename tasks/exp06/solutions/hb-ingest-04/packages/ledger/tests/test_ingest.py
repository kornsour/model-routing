import json

from orchestra import JobSpec, run

from ledger import ingest, store


def test_ingest_all_appends_once(tmp_path):
    specs = [JobSpec("a", duration=2, resources={"api": 1})]
    result = run(specs, {"api": 1})
    d = tmp_path / "runs" / "r1"
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"run_id": "r1", "pipeline": "p", "started_at": "2026-09-01T00:00:00+00:00", "specs": [s.to_dict() for s in specs]}))
    (d / "events-1.jsonl").write_text("".join(json.dumps(e.to_dict()) + "\n" for e in result.events))
    history = tmp_path / "h.jsonl"
    assert ingest.ingest_all(tmp_path / "runs", history, {"api": 1.0}) == (["r1"], [])
    assert ingest.ingest_all(tmp_path / "runs", history, {"api": 1.0}) == ([], [])
    assert [r.total_usd for r in store.load(history)] == [2.0]
