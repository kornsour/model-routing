"""Runs that are still in flight.

The real runner registers a run when it starts and finishes it when it ends;
``inflight.json`` maps run id to ``{"pipeline", "started_at", "heartbeat_at",
"status", ...}``.

Liveness is measured, not guessed. The runner refreshes ``heartbeat_at`` with
``heartbeat`` and with every ``report_progress`` call, so a run is live while
its heartbeat is younger than ``HEARTBEAT_STALE``. That threshold must stay
above ``ATTEMPT_TIMEOUT``: a single job attempt can be silent that long.
Rows written before heartbeats existed have no ``heartbeat_at``; they fall
back to the old age rule (live while younger than ``STALE_AFTER``). Real
nightly runs take up to 4.5 hours, which is why that fallback is generous.

``is_live`` is the one definition of "live": ``reap_stale`` marks every
running row that is not live as ``abandoned`` (recording ``reaped_by``), and
``already_running`` - the scheduler's overlap guard - only counts live rows.

On SIGTERM or SIGINT, ``install_shutdown_handlers`` pauses every run this
process is tracking (``track``/``untrack``). ``paused`` means "coming back to
this": it is never live and never reaped, and ``resume`` puts it back to
``running`` with a fresh heartbeat.
"""

from __future__ import annotations

import json
import os
import signal
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

STALE_AFTER = timedelta(hours=6)
HEARTBEAT_STALE = timedelta(minutes=15)
ATTEMPT_TIMEOUT = timedelta(minutes=10)

ACTIVE: set[str] = set()
SHUTDOWN_INSTALLED = False
_shutdown: dict[str, Any] = {"path": None, "clock": None}


def _load(path: Path) -> dict[str, dict[str, Any]]:
    return json.loads(path.read_text()) if path.exists() else {}


def _save(path: Path, data: dict[str, dict[str, Any]]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat()


def start(path: str | Path, run_id: str, pipeline: str, now: datetime) -> None:
    p = Path(path)
    data = _load(p)
    data[run_id] = {
        "pipeline": pipeline,
        "started_at": _iso(now),
        "heartbeat_at": _iso(now),
        "status": "running",
    }
    _save(p, data)


def finish(path: str | Path, run_id: str, status: str = "success") -> None:
    p = Path(path)
    data = _load(p)
    data[run_id]["status"] = status
    _save(p, data)


def heartbeat(path: str | Path, run_id: str, now: datetime) -> None:
    p = Path(path)
    data = _load(p)
    entry = data[run_id]
    if entry["status"] == "running":
        entry["heartbeat_at"] = _iso(now)
        _save(p, data)


def report_progress(path: str | Path, run_id: str, done: int, total: int, now: datetime) -> None:
    """Record progress; the same write refreshes the heartbeat."""
    p = Path(path)
    data = _load(p)
    entry = data[run_id]
    entry["progress"] = {"done": done, "total": total}
    if entry["status"] == "running":
        entry["heartbeat_at"] = _iso(now)
    _save(p, data)


def is_live(entry: dict[str, Any], now: datetime) -> bool:
    if entry.get("status") != "running":
        return False
    beat = entry.get("heartbeat_at")
    if beat:
        return now - datetime.fromisoformat(beat) <= HEARTBEAT_STALE
    return now - datetime.fromisoformat(entry["started_at"]) <= STALE_AFTER


def reap_stale(path: str | Path, now: datetime) -> list[str]:
    """Mark running rows that are not live as ``abandoned``."""
    p = Path(path)
    data = _load(p)
    reaped = []
    for run_id, entry in sorted(data.items()):
        if entry["status"] != "running" or is_live(entry, now):
            continue
        entry["status"] = "abandoned"
        if entry.get("heartbeat_at"):
            entry["reaped_by"] = "heartbeat"
            entry["reason"] = (
                f"No heartbeat for more than {int(HEARTBEAT_STALE.total_seconds() // 60)} minutes; "
                "the runner is presumed dead. Nothing it finished was lost."
            )
        else:
            entry["reaped_by"] = "age"
            entry["reason"] = (
                f"Running for more than {int(STALE_AFTER.total_seconds() // 3600)} hours with no "
                "heartbeat recorded. Nothing it finished was lost."
            )
        reaped.append(run_id)
    _save(p, data)
    return reaped


def already_running(path: str | Path, pipeline: str, now: datetime) -> bool:
    return any(e["pipeline"] == pipeline and is_live(e, now) for e in _load(Path(path)).values())


def track(run_id: str) -> None:
    ACTIVE.add(run_id)


def untrack(run_id: str) -> None:
    ACTIVE.discard(run_id)


def handle_shutdown(signum: int) -> list[str]:
    """Pause every tracked run that is still running; returns the paused ids."""
    path = _shutdown["path"]
    if path is None:
        return []
    clock: Callable[[], datetime] = _shutdown["clock"] or (lambda: datetime.now(UTC))
    p = Path(path)
    data = _load(p)
    name = signal.Signals(signum).name
    paused = []
    for run_id in sorted(ACTIVE):
        entry = data.get(run_id)
        if entry is None or entry["status"] != "running":
            continue
        entry["status"] = "paused"
        entry["paused_at"] = _iso(clock())
        entry["reason"] = (
            f"Paused: the process running this exited ({name}). "
            "Everything it finished is saved; resume it to carry on."
        )
        paused.append(run_id)
    if paused:
        _save(p, data)
    return paused


def _on_signal(signum: int, frame: object) -> None:
    try:
        handle_shutdown(signum)
    finally:
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)


def install_shutdown_handlers(
    path: str | Path, clock: Callable[[], datetime] | None = None
) -> None:
    """Pause tracked runs on SIGTERM/SIGINT. Safe to call more than once."""
    global SHUTDOWN_INSTALLED
    _shutdown["path"] = path
    _shutdown["clock"] = clock
    if SHUTDOWN_INSTALLED:
        return
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _on_signal)
    SHUTDOWN_INSTALLED = True


def resume(path: str | Path, run_id: str, now: datetime) -> None:
    p = Path(path)
    data = _load(p)
    entry = data[run_id]
    if entry["status"] != "paused":
        raise ValueError(f"{run_id} is {entry['status']}, not paused")
    entry["status"] = "running"
    entry["heartbeat_at"] = _iso(now)
    entry.pop("paused_at", None)
    entry.pop("reason", None)
    _save(p, data)
