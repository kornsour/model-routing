"""Runs that are still in flight.

The real runner registers a run when it starts and finishes it when it ends;
``inflight.json`` maps run id to ``{"pipeline", "started_at", "status"}``.
A runner that dies leaves its run ``running`` forever, so ``reap_stale``
marks a run ``abandoned`` once it has been running longer than
``STALE_AFTER``. Real nightly runs have taken up to 4.5 hours, which is why
the threshold is that generous.

``already_running`` is the guard the scheduler uses so two runs of the same
pipeline never overlap.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from toolbelt.durations import _td

STALE_AFTER = _td(Decimal(6 * 3600))


def _load(path: Path) -> dict[str, dict[str, Any]]:
    return json.loads(path.read_text()) if path.exists() else {}


def _save(path: Path, data: dict[str, dict[str, Any]]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def start(path: str | Path, run_id: str, pipeline: str, now: datetime) -> None:
    p = Path(path)
    data = _load(p)
    data[run_id] = {"pipeline": pipeline, "started_at": now.astimezone(UTC).isoformat(), "status": "running"}
    _save(p, data)


def finish(path: str | Path, run_id: str, status: str = "success") -> None:
    p = Path(path)
    data = _load(p)
    data[run_id]["status"] = status
    _save(p, data)


def _started(entry: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(entry["started_at"])


def reap_stale(path: str | Path, now: datetime) -> list[str]:
    """Mark runs ``running`` for longer than ``STALE_AFTER`` as ``abandoned``."""
    p = Path(path)
    data = _load(p)
    reaped = []
    for run_id, entry in sorted(data.items()):
        if entry["status"] == "running" and now - _started(entry) > STALE_AFTER:
            entry["status"] = "abandoned"
            entry["reason"] = "Runner stopped reporting. Nothing it finished was lost."
            reaped.append(run_id)
    _save(p, data)
    return reaped


def already_running(path: str | Path, pipeline: str) -> bool:
    return any(
        e["pipeline"] == pipeline and e["status"] == "running" for e in _load(Path(path)).values()
    )
