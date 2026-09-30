"""Saving and loading run results as JSON.  See ``docs/run-format.md``."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from orchestra.model import Event, JobRun, RunResult, State

FORMAT_VERSION = 3

_V1_STATUS = {
    "PENDING": "pending",
    "RUNNING": "running",
    "WAITING": "retry_wait",
    "SUCCEEDED": "success",
    "FAILED": "failed",
    "UPSTREAM_FAILED": "upstream_failed",
}
_V1_KIND = {
    "started": "start",
    "succeeded": "success",
    "failed": "fail",
    "retrying": "retry",
    "skipped_upstream": "upstream_failed",
}
_EVENT_COLS = ("time", "job", "kind", "attempt", "detail")


def _checksum(doc: dict[str, Any]) -> str:
    body = {k: v for k, v in doc.items() if k != "checksum"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _v1_to_v2(doc: dict[str, Any]) -> dict[str, Any]:
    jobs = doc["jobs"]
    last_retry: dict[str, float] = {}
    events: list[dict[str, Any]] = []
    names = sorted(jobs)
    for entry in doc["log"]:
        time, job, kind = entry[0], entry[1], entry[2]
        attempt = entry[3] if len(entry) > 3 else 0
        if kind not in _V1_KIND:
            raise ValueError(f"unknown v1 event kind {kind!r}")
        if job not in jobs:
            raise ValueError(f"v1 event for unknown job {job!r}")
        new_kind = _V1_KIND[kind]
        detail = ""
        if new_kind == "retry":
            if len(entry) < 5:
                raise ValueError("v1 retrying entry without a retry time")
            retry_at = float(entry[4])
            last_retry[job] = retry_at
            detail = repr(retry_at)
        elif new_kind == "fail":
            detail = f"attempt {attempt} failed"
        events.append(
            {"time": time, "job": job, "kind": new_kind, "attempt": attempt, "detail": detail}
        )
    runs = []
    for name in names:
        j = jobs[name]
        status = j["status"]
        if status not in _V1_STATUS:
            raise ValueError(f"unknown v1 status {status!r}")
        state = _V1_STATUS[status]
        runs.append(
            {
                "name": name,
                "state": state,
                "attempts": j["tries"],
                "started_at": j["start"],
                "finished_at": j["end"],
                "retry_at": last_retry.get(name) if state == "retry_wait" else None,
                "reason": f"attempt {j['tries']} failed" if state == "failed" else "",
            }
        )
    return {"version": 2, "makespan": doc["total_time"], "runs": runs, "events": events}


def _v2_to_v3(doc: dict[str, Any]) -> dict[str, Any]:
    order = [r["name"] for r in doc["runs"]]
    index = {n: i for i, n in enumerate(order)}
    runs = {r["name"]: {k: v for k, v in r.items() if k != "name"} for r in doc["runs"]}
    cols: dict[str, list[Any]] = {c: [] for c in _EVENT_COLS}
    for e in doc["events"]:
        if e["job"] not in index:
            raise ValueError(f"event for unknown job {e['job']!r}")
        cols["time"].append(e["time"])
        cols["job"].append(index[e["job"]])
        cols["kind"].append(e["kind"])
        cols["attempt"].append(e["attempt"])
        cols["detail"].append(e["detail"])
    out: dict[str, Any] = {
        "version": 3,
        "makespan": doc["makespan"],
        "job_order": order,
        "runs": runs,
        "events": cols,
    }
    out["checksum"] = _checksum(out)
    return out


def migrate(doc: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(doc, dict):
        raise ValueError("run document must be an object")
    doc = copy.deepcopy(doc)
    version = doc.get("version")
    if version not in (1, 2, 3) or isinstance(version, bool):
        raise ValueError(f"unsupported run format version {version!r}")
    if version == 1:
        doc = _v1_to_v2(doc)
        version = 2
    if version == 2:
        doc = _v2_to_v3(doc)
    return doc


def _from_v3(doc: dict[str, Any]) -> RunResult:
    if doc.get("checksum") != _checksum(doc):
        raise ValueError("checksum mismatch")
    order = doc["job_order"]
    if len(set(order)) != len(order) or set(order) != set(doc["runs"]):
        raise ValueError("job_order and runs disagree")
    runs = {}
    for name in order:
        r = doc["runs"][name]
        runs[name] = JobRun(
            name=name,
            state=State(r["state"]),
            attempts=r["attempts"],
            started_at=r["started_at"],
            finished_at=r["finished_at"],
            retry_at=r["retry_at"],
            reason=r["reason"],
        )
    cols = doc["events"]
    lengths = {len(cols[c]) for c in _EVENT_COLS}
    if len(lengths) != 1:
        raise ValueError("event columns have different lengths")
    events = []
    for i in range(lengths.pop()):
        j = cols["job"][i]
        if not isinstance(j, int) or isinstance(j, bool) or not 0 <= j < len(order):
            raise ValueError(f"event job index out of range: {j!r}")
        events.append(
            Event(
                time=cols["time"][i],
                job=order[j],
                kind=cols["kind"][i],
                attempt=cols["attempt"][i],
                detail=cols["detail"][i],
            )
        )
    return RunResult(runs=runs, events=events, makespan=doc["makespan"])


def dumps(result: RunResult) -> str:
    v2 = {
        "version": 2,
        "makespan": result.makespan,
        "runs": [r.to_dict() for r in result.runs.values()],
        "events": [e.to_dict() for e in result.events],
    }
    return json.dumps(_v2_to_v3(v2), indent=2, sort_keys=True)


def loads(text: str) -> RunResult:
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"not JSON: {exc}") from exc
    return _from_v3(migrate(doc))


def save(result: RunResult, path: str | Path) -> None:
    Path(path).write_text(dumps(result))


def load(path: str | Path) -> RunResult:
    return loads(Path(path).read_text())
