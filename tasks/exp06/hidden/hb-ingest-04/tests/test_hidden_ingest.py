"""Hidden grader: event-log reading in orchestra and ingestion in ledger (exp06 stratum B)."""

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from orchestra import JobSpec, State, run
from orchestra.events import read_log, result_from_log

from ledger import cli, ingest, pricing, store

RATES = {"warehouse": 0.5, "api": 0.25}


def _specs():
    return [
        JobSpec("extract", duration=3, resources={"api": 2}),
        JobSpec("load", deps=("extract",), duration=5, outcomes=("fail", "ok"), max_attempts=2, backoff=1, resources={"warehouse": 1}),
        JobSpec("report", deps=("load",), duration=2, resources={"warehouse": 1}),
        JobSpec("side", duration=4),
    ]


def _write_run(root, run_id, events, specs=None, per_segment=2, truncate_tail=None):
    d = root / run_id
    d.mkdir(parents=True)
    specs = specs or _specs()
    (d / "meta.json").write_text(json.dumps({
        "run_id": run_id, "pipeline": "nightly", "started_at": "2026-09-05T02:00:00+00:00",
        "specs": [s.to_dict() for s in specs],
    }))
    lines = [json.dumps(e.to_dict()) for e in events]
    chunks = [lines[i:i + per_segment] for i in range(0, len(lines), per_segment)] or [[]]
    for n, chunk in enumerate(chunks, start=1):
        text = "".join(line + "\n" for line in chunk)
        if truncate_tail and n == len(chunks):
            text += truncate_tail
        (d / f"events-{n}.jsonl").write_text(text)
    return d


def test_segments_sorted_numerically(tmp_path):
    result = run(_specs(), {"api": 2, "warehouse": 1})
    d = _write_run(tmp_path, "r1", result.events, per_segment=1)
    paths = sorted(d.glob("events-*.jsonl"))  # lexical: events-1, events-10, events-11, events-2, ...
    assert len(paths) >= 10
    assert read_log(paths) == result.events


def test_truncated_tail_ignored_and_middle_errors(tmp_path):
    result = run(_specs(), {"api": 2, "warehouse": 1})
    d = _write_run(tmp_path, "r1", result.events, per_segment=3, truncate_tail='{"time": 9.0, "job": "rep')
    assert read_log(list(d.glob("events-*.jsonl"))) == result.events
    bad = d / "events-1.jsonl"
    lines = bad.read_text().splitlines()
    lines[1] = "{not json"
    bad.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match=r"events-1\.jsonl.*\b2\b"):
        read_log(list(d.glob("events-*.jsonl")))


def test_unknown_kind_and_time_regression(tmp_path):
    p = tmp_path / "events-1.jsonl"
    p.write_text(json.dumps({"time": 0, "job": "a", "kind": "explode", "attempt": 1, "detail": ""}) + "\n")
    with pytest.raises(ValueError):
        read_log([p])
    p.write_text(
        json.dumps({"time": 2, "job": "a", "kind": "start", "attempt": 1, "detail": ""}) + "\n"
        + json.dumps({"time": 1, "job": "a", "kind": "success", "attempt": 1, "detail": ""}) + "\n"
    )
    with pytest.raises(ValueError):
        read_log([p])


def test_result_from_log_matches_simulator():
    specs = _specs()
    result = run(specs, {"api": 2, "warehouse": 1})
    rebuilt = result_from_log(result.events, specs)
    assert rebuilt.runs == result.runs
    assert rebuilt.makespan == result.makespan
    partial = result_from_log(result.events[:2], specs)
    assert partial.runs["report"].state is State.PENDING
    assert partial.makespan == 0


def test_open_attempts_billed_so_far():
    specs = {s.name: s for s in _specs()}
    result = run(specs.values(), {"api": 2, "warehouse": 1})
    cut = [e for e in result.events if e.time <= 4]
    partial = result_from_log(cut, list(specs.values()))
    assert pricing.price_run(partial, specs, RATES).by_job.get("load", 0) == 0
    billed = pricing.price_run(partial, specs, RATES, open_until=cut[-1].time)
    assert float(billed.by_job["load"]) == pytest.approx((cut[-1].time - 3) * 0.5)
    assert float(billed.by_job["extract"]) == pytest.approx(3 * 2 * 0.25)


def test_ingest_run_complete_and_incomplete(tmp_path):
    result = run(_specs(), {"api": 2, "warehouse": 1})
    done = ingest.ingest_run(_write_run(tmp_path, "done", result.events), RATES)
    assert done.complete and (done.finished, done.total) == (4, 4)
    assert done.record.status == "success" and done.record.run_id == "done" and done.record.pipeline == "nightly"
    assert done.record.started_at == datetime(2026, 9, 5, 2, tzinfo=UTC)
    assert done.record.total_usd == pytest.approx(3 * 2 * 0.25 + 10 * 0.5 + 2 * 0.5)
    part = ingest.ingest_run(_write_run(tmp_path, "part", result.events[:4]), RATES)
    assert not part.complete and part.record.status == "incomplete"
    assert part.total == 4 and part.finished < 4
    empty = ingest.ingest_run(_write_run(tmp_path, "empty", []), RATES)
    assert not empty.complete and empty.record.total_usd == 0 and empty.finished == 0


def test_failed_run_status(tmp_path):
    specs = [JobSpec("a", duration=1, outcomes=("fail",)), JobSpec("b", deps=("a",), duration=1)]
    result = run(specs)
    ing = ingest.ingest_run(_write_run(tmp_path, "f", result.events, specs=specs), RATES)
    assert ing.complete and ing.record.status == "failed"


def test_ingest_all_is_idempotent(tmp_path):
    root, history = tmp_path / "runs", tmp_path / "h.jsonl"
    result = run(_specs(), {"api": 2, "warehouse": 1})
    _write_run(root, "b-done", result.events)
    d = _write_run(root, "a-growing", result.events[:3], per_segment=10)
    assert ingest.ingest_all(root, history, RATES) == (["b-done"], ["a-growing"])
    assert ingest.ingest_all(root, history, RATES) == ([], ["a-growing"])
    (d / "events-2.jsonl").write_text("".join(json.dumps(e.to_dict()) + "\n" for e in result.events[3:]))
    assert ingest.ingest_all(root, history, RATES) == (["a-growing"], [])
    assert ingest.ingest_all(root, history, RATES) == ([], [])
    ids = [r.run_id for r in store.load(history)]
    assert sorted(ids) == ["a-growing", "b-done"] and len(ids) == 2
    assert all(r.status != "incomplete" for r in store.load(history))


def test_cli_ingest(tmp_path, capsys):
    root, history = tmp_path / "runs", tmp_path / "h.jsonl"
    result = run(_specs(), {"api": 2, "warehouse": 1})
    _write_run(root, "r2", result.events)
    _write_run(root, "r1", result.events[:3])
    assert cli.main(["ingest", str(root), "--history", str(history)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "ingested r2"
    assert out[1].startswith("incomplete r1 (") and out[1].endswith(" of 4 jobs finished)")
