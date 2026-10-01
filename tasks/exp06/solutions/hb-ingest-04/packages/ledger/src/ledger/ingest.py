"""Ingesting real runs from the runner's event logs.

A run directory holds ``meta.json`` (``run_id``, ``pipeline``, ``started_at``,
``specs``) and event-log segments ``events-N.jsonl`` (see
``orchestra.events``). ``ingest_run`` rebuilds and prices the run, billing
attempts still open at the end of the log up to the last event ("billed so
far"). ``ingest_all`` appends each *complete* run to the history exactly once;
incomplete runs are reported and picked up by a later ingest.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from orchestra.events import read_log, result_from_log
from orchestra.model import JobSpec, State

from ledger import pricing, store


@dataclass(frozen=True)
class Ingested:
    record: store.RunRecord
    complete: bool
    finished: int
    total: int


def ingest_run(run_dir: str | Path, rates: Mapping[str, float]) -> Ingested:
    d = Path(run_dir)
    meta = json.loads((d / "meta.json").read_text())
    specs = [JobSpec.from_dict(s) for s in meta["specs"]]
    events = read_log(d.glob("events-*.jsonl"))
    result = result_from_log(events, specs)
    open_until = events[-1].time if events else 0.0
    cost = pricing.price_run(result, {s.name: s for s in specs}, rates, open_until=open_until)
    finished = sum(1 for r in result.runs.values() if r.state.terminal)
    total = len(result.runs)
    complete = finished == total
    if not complete:
        status = "incomplete"
    elif all(r.state is State.SUCCESS for r in result.runs.values()):
        status = "success"
    else:
        status = "failed"
    record = store.RunRecord(
        run_id=meta["run_id"],
        pipeline=meta["pipeline"],
        started_at=datetime.fromisoformat(meta["started_at"]).astimezone(UTC),
        status=status,
        total_usd=cost.total,
        jobs=cost.by_job,
    )
    return Ingested(record, complete, finished, total)


def ingest_all(
    runs_root: str | Path, history_path: str | Path, rates: Mapping[str, float]
) -> tuple[list[str], list[str]]:
    """Append every complete, not-yet-recorded run; report incomplete ones."""
    known = {r.run_id for r in store.load(history_path)}
    appended: list[str] = []
    incomplete: list[str] = []
    for d in sorted(p for p in Path(runs_root).iterdir() if (p / "meta.json").exists()):
        run_id = json.loads((d / "meta.json").read_text())["run_id"]
        if run_id in known:
            continue
        ingested = ingest_run(d, rates)
        if ingested.complete:
            store.append(history_path, ingested.record)
            known.add(run_id)
            appended.append(run_id)
        else:
            incomplete.append(run_id)
    return sorted(appended), sorted(incomplete)
