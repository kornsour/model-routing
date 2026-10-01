import copy
import hashlib
import json

import pytest

from orchestra import JobSpec, State, run
from orchestra.model import Event
from orchestra.store import dumps, load, loads, migrate, save

V1 = {
    "version": 1,
    "total_time": 6.0,
    "jobs": {
        "load": {"status": "FAILED", "tries": 2, "start": 1.0, "end": 4.0},
        "extract": {"status": "SUCCEEDED", "tries": 1, "start": 0.0, "end": 1.0},
        "report": {"status": "UPSTREAM_FAILED", "tries": 0, "start": None, "end": 4.0},
        "side": {"status": "WAITING", "tries": 1, "start": 0.0, "end": None},
    },
    "log": [
        [0.0, "extract", "started", 1],
        [0.0, "side", "started", 1],
        [1.0, "extract", "succeeded", 1],
        [1.0, "load", "started", 1],
        [1.0, "side", "retrying", 1, 2.5],
        [2.0, "load", "retrying", 1, 3.0],
        [3.0, "load", "started", 2],
        [3.0, "side", "retrying", 1, 9.0],
        [4.0, "load", "failed", 2],
        [4.0, "report", "skipped_upstream", 0],
    ],
}


def checksum(doc):
    body = {k: v for k, v in doc.items() if k != "checksum"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sample():
    return run([
        JobSpec("a", outcomes=("fail", "ok"), max_attempts=2, backoff=1.5),
        JobSpec("b", deps=("a",)),
        JobSpec("c", outcomes=("fail",)),
        JobSpec("d", deps=("c",)),
    ])


def test_v1_is_migrated():
    before = copy.deepcopy(V1)
    res = loads(json.dumps(V1))
    assert V1 == before
    assert list(res.runs) == ["extract", "load", "report", "side"]
    assert res.makespan == 6.0
    load_ = res.runs["load"]
    assert (load_.state, load_.attempts, load_.started_at, load_.finished_at) == (State.FAILED, 2, 1.0, 4.0)
    assert load_.reason == "attempt 2 failed" and load_.retry_at is None
    assert res.runs["report"].state is State.UPSTREAM_FAILED and res.runs["report"].reason == ""
    side = res.runs["side"]
    assert side.state is State.RETRY_WAIT and side.retry_at == 9.0
    assert res.events[0] == Event(0.0, "extract", "start", 1, "")
    kinds = [e.kind for e in res.events]
    assert kinds == ["start", "start", "success", "start", "retry", "retry", "start", "retry", "fail", "upstream_failed"]
    retry = res.events[4]
    assert retry.detail == repr(2.5) and retry.job == "side"
    assert res.events[8].detail == "attempt 2 failed"
    assert res.events[9] == Event(4.0, "report", "upstream_failed", 0, "")


def test_migrate_steps_and_does_not_mutate():
    before = copy.deepcopy(V1)
    doc = migrate(V1)
    assert V1 == before
    assert doc["version"] == 3
    assert doc["job_order"] == ["extract", "load", "report", "side"]
    assert doc["checksum"] == checksum(doc)
    assert set(doc["events"]) == {"time", "job", "kind", "attempt", "detail"}
    assert doc["events"]["job"][:3] == [0, 3, 0]
    assert "name" not in doc["runs"]["load"]
    assert migrate(doc) == doc


def test_v2_documents_load():
    res = sample()
    v2 = {
        "version": 2,
        "makespan": res.makespan,
        "runs": [r.to_dict() for r in res.runs.values()],
        "events": [e.to_dict() for e in res.events],
    }
    got = loads(json.dumps(v2))
    assert got.runs == res.runs and got.events == res.events and got.makespan == res.makespan
    assert list(got.runs) == list(res.runs)


def test_dumps_writes_v3():
    res = sample()
    text = dumps(res)
    doc = json.loads(text)
    assert doc["version"] == 3
    assert doc["job_order"] == list(res.runs)
    assert doc["checksum"] == checksum(doc)
    assert len(doc["events"]["time"]) == len(res.events)
    assert all(isinstance(j, int) for j in doc["events"]["job"])
    assert text == json.dumps(doc, indent=2, sort_keys=True)
    again = loads(text)
    assert again.runs == res.runs and again.events == res.events and again.makespan == res.makespan
    assert list(again.runs) == list(res.runs)


def test_save_load(tmp_path):
    res = sample()
    p = tmp_path / "run.json"
    save(res, p)
    assert load(p).runs == res.runs


def _v3():
    return json.loads(dumps(sample()))


def _resign(doc):
    doc["checksum"] = checksum(doc)
    return doc


def test_checksum_mismatch():
    doc = _v3()
    doc["makespan"] = 999
    with pytest.raises(ValueError, match="checksum"):
        loads(json.dumps(doc))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["events"]["kind"].pop(),
        lambda d: d["events"]["job"].__setitem__(0, 99),
        lambda d: d["events"]["job"].__setitem__(0, -1),
        lambda d: d["job_order"].pop(),
        lambda d: d["job_order"].append("ghost"),
    ],
)
def test_structural_errors(mutate):
    doc = _v3()
    mutate(doc)
    _resign(doc)
    with pytest.raises(ValueError):
        loads(json.dumps(doc))


@pytest.mark.parametrize(
    "doc",
    [
        {"version": 4},
        {"makespan": 1},
        {"version": "2"},
        {"version": True},
        {**V1, "jobs": {**V1["jobs"], "x": {"status": "EXPLODED", "tries": 0, "start": None, "end": None}}},
        {**V1, "log": V1["log"] + [[5.0, "extract", "teleported", 1]]},
    ],
)
def test_bad_documents(doc):
    with pytest.raises(ValueError):
        loads(json.dumps(doc))


def test_not_json():
    with pytest.raises(ValueError):
        loads("{nope")
