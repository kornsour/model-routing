import json
from pathlib import Path

from model_routing.cli import main
from model_routing.dashboard import build_payload, render_html
from model_routing.findings import compute_findings
from model_routing.store import connect, index_results, list_runs, run_outcomes

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "experiments" / "llm" / "exp02_routing.toml"


def _fake_run(tmp_path: Path) -> Path:
    results = tmp_path / "results"
    assert main(["run", str(CFG), "--fake", "--sample", "4", "--out", str(results)]) == 0
    runs = list(results.glob("exp02_routing/fake-*"))
    assert len(runs) == 1
    return results


def test_index_roundtrip_matches_jsonl(tmp_path: Path):
    results = _fake_run(tmp_path)
    db = results / "index.sqlite"
    ids = index_results(results, db)
    assert len(ids) == 1 and ids[0].startswith("exp02_routing/fake-")
    conn = connect(db)
    runs = list_runs(conn, include_synthetic=True)
    assert runs[0]["synthetic"] == 1 and list_runs(conn) == []
    outcomes = run_outcomes(conn, ids[0])
    raw = [
        json.loads(line)
        for line in (Path(runs[0]["path"]) / "outcomes.jsonl").read_text().splitlines()
    ]
    assert len(outcomes) == len(raw)
    # Calls are re-attached to the right outcome: their cost sums to the outcome cost.
    for o in outcomes:
        assert abs(sum(c["cost_usd_list"] for c in o["calls"]) - o["cost_usd"]) < 1e-9
    assert sum(len(o["calls"]) for o in outcomes) == sum(len(r["calls"]) for r in raw)
    # Re-indexing is idempotent.
    index_results(results, db)
    assert len(run_outcomes(connect(db), ids[0])) == len(raw)
    conn.close()


def test_findings_cover_every_hypothesis(tmp_path: Path):
    results = _fake_run(tmp_path)
    db = results / "index.sqlite"
    (rid,) = index_results(results, db)
    conn = connect(db)
    meta = json.loads(list_runs(conn, include_synthetic=True)[0]["meta_json"])
    findings = compute_findings(meta, run_outcomes(conn, rid))
    ids = [f.id for f in findings]
    assert ids[:7] == ["F1", "F2", "F3", "F4", "F5", "F6", "F7"]
    assert all(
        f.verdict in ("supported", "contradicted", "mixed", "insufficient") for f in findings
    )
    assert all(f.evidence for f in findings)
    # F7 needs two providers; the fake run has one.
    assert next(f for f in findings if f.id == "F7").verdict == "insufficient"


def test_dashboard_html_is_self_contained(tmp_path: Path):
    results = _fake_run(tmp_path)
    db = results / "index.sqlite"
    index_results(results, db)
    payload = build_payload(db, include_synthetic=True)
    assert payload["runs"] and payload["runs"][0]["stats"]
    page = render_html(payload)
    assert "<script src" not in page and "https://" not in page.split("<script>")[0]
    assert payload["runs"][0]["run_id"] in page
    out = tmp_path / "dash.html"
    assert (
        main(
            [
                "dashboard",
                "--results",
                str(results),
                "--db",
                str(db),
                "--out",
                str(out),
                "--include-synthetic",
            ]
        )
        == 0
    )
    assert out.exists() and "Model routing runs" in out.read_text()
