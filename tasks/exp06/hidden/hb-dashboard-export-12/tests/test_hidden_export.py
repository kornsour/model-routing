"""Hidden grader: static dashboard export (exp06 stratum B)."""

import json
from datetime import UTC, datetime

import pytest

from orchestra import DAG, JobSpec
from toolbelt.text import unique_slugs

from ledger import cli, inflight, store
from ledger.export import export


def test_unique_slugs():
    assert unique_slugs(["Nightly ETL", "nightly-etl", "nightly etl!", "Hourly", "***"]) == {
        "Hourly": "hourly", "Nightly ETL": "nightly-etl", "nightly etl!": "nightly-etl-2", "nightly-etl": "nightly-etl-3", "***": "item",
    }
    assert unique_slugs(["a b", "a-b", "a-b-2"]) == {"a b": "a-b", "a-b": "a-b-3", "a-b-2": "a-b-2"}


def test_critical_path():
    specs = [JobSpec("a", duration=3), JobSpec("b", duration=5), JobSpec("c", deps=("a", "b"), duration=1),
             JobSpec("d", deps=("a",), duration=3), JobSpec("e", deps=("d",), duration=0)]
    # L: a=3 b=5 c=6 d=6 e=6; the tie for the end goes to the smallest name, "c"; back from c the larger L is b
    assert DAG(specs).critical_path() == (["b", "c"], 6.0)
    tie = [JobSpec("x", duration=2), JobSpec("y", duration=2), JobSpec("z", deps=("y", "x"), duration=1)]
    assert DAG(tie).critical_path() == (["x", "z"], 3.0)
    assert DAG([]).critical_path() == ([], 0.0)


T = lambda d, h=2: datetime(2026, 9, d, h, tzinfo=UTC)  # noqa: E731


def _history(tmp_path):
    path = tmp_path / "history.jsonl"
    rows = [
        ("r1", "Nightly ETL", T(1), "success", 10.004),
        ("r2", "Nightly ETL", T(2), "failed", 5.0),
        ("r3", "nightly-etl", T(2), "success", 1.0),
        ("r4", "hourly", T(3, 1), "success", 0.333),
        ("r5", "hourly", T(3, 1), "success", 0.333),
        ("r0", "hourly", datetime(2026, 8, 31, 23, tzinfo=UTC), "success", 2.0),
    ]
    for run_id, pipeline, when, status, total in rows:
        store.append(path, store.RunRecord(run_id, pipeline, when, status, total, {}))
    return path


def _inflight(tmp_path):
    path = tmp_path / "inflight.json"
    inflight.start(path, "f2", "weekly", T(4, 3))
    inflight.start(path, "f1", "hourly", T(4, 3))
    inflight.start(path, "f0", "done", T(4, 1))
    inflight.finish(path, "f0")
    return path


def _specs(tmp_path):
    d = tmp_path / "specs"
    d.mkdir()
    specs = [JobSpec("extract", duration=30), JobSpec("load", deps=("extract",), duration=60), JobSpec("audit", duration=10)]
    (d / "nightly-etl.json").write_text(json.dumps([s.to_dict() for s in specs]))
    return d


def load(out, rel):
    text = (out / rel).read_text()
    assert text.endswith("\n") and text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
    return json.loads(text)


def test_export_layout_and_content(tmp_path):
    out = tmp_path / "site"
    written = export(out, _history(tmp_path), _inflight(tmp_path), _specs(tmp_path), page_size=4)
    assert written == sorted([
        "index.json", "inflight.json", "pipelines/hourly.json", "pipelines/nightly-etl.json",
        "pipelines/nightly-etl-2.json", "pipelines/weekly.json", "runs/page-1.json", "runs/page-2.json",
    ])
    index = load(out, "index.json")
    assert index == {
        "schema_version": 1,
        "generated_from": {"history_records": 6, "inflight_running": 2},
        "pipelines": {"Nightly ETL": "nightly-etl", "hourly": "hourly", "nightly-etl": "nightly-etl-2", "weekly": "weekly"},
        "months": ["2026-09", "2026-08"],
        "run_pages": 2,
    }
    etl = load(out, "pipelines/nightly-etl.json")
    assert etl == {
        "pipeline": "Nightly ETL", "slug": "nightly-etl", "runs": 2, "total_usd": 15.0,
        "months": {"2026-09": {"runs": 2, "total_usd": 15.0}},
        "last_run": {"run_id": "r2", "pipeline": "Nightly ETL", "slug": "nightly-etl", "started_at": "2026-09-02T02:00:00+00:00", "status": "failed", "total_usd": 5.0},
        "jobs": 3, "critical_path": ["extract", "load"], "critical_path_seconds": 90.0,
    }
    hourly = load(out, "pipelines/hourly.json")
    assert hourly["last_run"]["run_id"] == "r5" and hourly["total_usd"] == 2.67
    assert hourly["months"] == {"2026-08": {"runs": 1, "total_usd": 2.0}, "2026-09": {"runs": 2, "total_usd": 0.67}}
    assert hourly["jobs"] is None and hourly["critical_path"] is None and hourly["critical_path_seconds"] is None
    weekly = load(out, "pipelines/weekly.json")
    assert weekly["runs"] == 0 and weekly["last_run"] is None and weekly["months"] == {} and weekly["total_usd"] == 0
    p1, p2 = load(out, "runs/page-1.json"), load(out, "runs/page-2.json")
    assert (p1["page"], p1["pages"], p1["page_size"], p2["page"]) == (1, 2, 4, 2)
    assert [r["run_id"] for r in p1["runs"]] == ["r4", "r5", "r2", "r3"]
    assert [r["run_id"] for r in p2["runs"]] == ["r1", "r0"]
    assert p1["runs"][3] == {"run_id": "r3", "pipeline": "nightly-etl", "slug": "nightly-etl-2", "started_at": "2026-09-02T02:00:00+00:00", "status": "success", "total_usd": 1.0}
    assert load(out, "inflight.json") == {"count": 2, "running": [
        {"run_id": "f1", "pipeline": "hourly", "slug": "hourly", "started_at": "2026-09-04T03:00:00+00:00"},
        {"run_id": "f2", "pipeline": "weekly", "slug": "weekly", "started_at": "2026-09-04T03:00:00+00:00"},
    ]}
    assert json.loads((out / ".export-manifest.json").read_text()) == written


def test_empty_history(tmp_path):
    out = tmp_path / "site"
    written = export(out, tmp_path / "none.jsonl")
    assert written == ["index.json", "inflight.json", "runs/page-1.json"]
    assert load(out, "runs/page-1.json") == {"page": 1, "pages": 1, "page_size": 50, "runs": []}
    assert load(out, "inflight.json") == {"count": 0, "running": []}
    assert load(out, "index.json")["months"] == []


def test_reexport_cleans_only_its_own_files(tmp_path):
    out = tmp_path / "site"
    history = _history(tmp_path)
    export(out, history, page_size=2)
    assert (out / "runs/page-3.json").exists() and (out / "pipelines/nightly-etl-2.json").exists()
    (out / "README.md").write_text("keep me")
    (out / "pipelines/notes.txt").write_text("keep me too")
    smaller = tmp_path / "small.jsonl"
    store.append(smaller, store.RunRecord("only", "hourly", T(5), "success", 1.0, {}))
    written = export(out, smaller, page_size=2)
    assert written == ["index.json", "inflight.json", "pipelines/hourly.json", "runs/page-1.json"]
    assert not (out / "runs/page-3.json").exists() and not (out / "pipelines/nightly-etl.json").exists()
    assert (out / "README.md").read_text() == "keep me" and (out / "pipelines/notes.txt").exists()
    export(out, tmp_path / "none.jsonl")
    assert not (out / "pipelines/hourly.json").exists()
    assert (out / "pipelines").is_dir()  # still holds notes.txt
    export(out, tmp_path / "none.jsonl")


def test_failure_leaves_output_untouched(tmp_path):
    out = tmp_path / "site"
    export(out, _history(tmp_path))
    before = {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    bad = tmp_path / "bad.jsonl"
    bad.write_text((tmp_path / "history.jsonl").read_text() + "{not json\n")
    with pytest.raises(Exception):
        export(out, bad)
    after = {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    assert after == before


def test_cli(tmp_path, capsys):
    out = tmp_path / "site"
    history = _history(tmp_path)
    assert cli.main(["export", str(out), "--history", str(history), "--page-size", "10"]) == 0
    assert capsys.readouterr().out.strip() == f"wrote 6 files to {out}"
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not json\n")
    assert cli.main(["export", str(out), "--history", str(bad)]) == 1
    assert capsys.readouterr().err.startswith("export failed: ")
