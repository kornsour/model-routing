"""Saving and loading run results as JSON (format version 2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orchestra.model import Event, JobRun, RunResult, State

FORMAT_VERSION = 2


def dumps(result: RunResult) -> str:
    doc: dict[str, Any] = {
        "version": FORMAT_VERSION,
        "makespan": result.makespan,
        "runs": [r.to_dict() for r in result.runs.values()],
        "events": [e.to_dict() for e in result.events],
    }
    return json.dumps(doc, indent=2, sort_keys=True)


def loads(text: str) -> RunResult:
    doc = json.loads(text)
    if doc.get("version") != FORMAT_VERSION:
        raise ValueError(f"unsupported run format version {doc.get('version')!r}")
    runs = {
        r["name"]: JobRun(
            name=r["name"],
            state=State(r["state"]),
            attempts=r["attempts"],
            started_at=r["started_at"],
            finished_at=r["finished_at"],
            retry_at=r["retry_at"],
            reason=r["reason"],
        )
        for r in doc["runs"]
    }
    events = [Event(**e) for e in doc["events"]]
    return RunResult(runs=runs, events=events, makespan=doc["makespan"])


def save(result: RunResult, path: str | Path) -> None:
    Path(path).write_text(dumps(result))


def load(path: str | Path) -> RunResult:
    return loads(Path(path).read_text())
