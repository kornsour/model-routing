"""SQLite index over ``results/``: every run, outcome, and call, queryable.

The JSONL files stay the source of truth; the index is rebuilt idempotently
from them (``index_results``) so it can be deleted at any time.  Standard
library only, like the rest of the harness.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from model_routing.pricing import embedded_list_cost, normalize_recorded_costs

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    experiment TEXT NOT NULL,
    stamp TEXT NOT NULL,
    path TEXT NOT NULL,
    started_at TEXT,
    hypothesis TEXT,
    n_tasks INTEGER,
    trials INTEGER,
    task_order TEXT,
    synthetic INTEGER NOT NULL DEFAULT 0,
    meta_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outcomes (
    run_id TEXT NOT NULL,
    router TEXT NOT NULL,
    task_id TEXT NOT NULL,
    trial INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    difficulty TEXT,
    category TEXT,
    escalations INTEGER,
    final_candidate TEXT,
    cost_usd REAL,
    cost_usd_reported REAL,
    router_cost_usd REAL,
    duration_ms INTEGER,
    input_tokens INTEGER,
    cache_read INTEGER,
    cache_write INTEGER,
    cache_write_1h INTEGER,
    output_tokens INTEGER,
    reasoning INTEGER,
    grade_detail TEXT,
    final_output TEXT,
    PRIMARY KEY (run_id, router, task_id, trial)
);
CREATE TABLE IF NOT EXISTS calls (
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    task_id TEXT NOT NULL,
    candidate TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    resolved_model TEXT,
    effort TEXT,
    role TEXT NOT NULL,
    input_tokens INTEGER,
    cache_read INTEGER,
    cache_write INTEGER,
    cache_write_1h INTEGER,
    output_tokens INTEGER,
    reasoning INTEGER,
    duration_ms INTEGER,
    cost_usd_list REAL,
    cost_usd_reported REAL,
    error TEXT,
    output TEXT,
    PRIMARY KEY (run_id, seq)
);
CREATE TABLE IF NOT EXISTS outcome_calls (
    run_id TEXT NOT NULL, router TEXT NOT NULL, task_id TEXT NOT NULL,
    trial INTEGER NOT NULL, seq INTEGER NOT NULL,
    PRIMARY KEY (run_id, router, task_id, trial, seq)
);
CREATE INDEX IF NOT EXISTS idx_outcomes_router ON outcomes (run_id, router);
CREATE INDEX IF NOT EXISTS idx_calls_task ON calls (run_id, task_id);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def discover_runs(results_dir: str | Path) -> list[Path]:
    """Single-shot run directories: ``results/<experiment>/<stamp>/`` with outcomes.jsonl.

    Dispatch (agentic) runs write ``sessions.jsonl`` instead of ``calls.jsonl``
    and have their own report (``model_routing.dispatch.report``); skip them.
    """
    root = Path(results_dir)
    if not root.exists():
        return []
    return sorted(
        p.parent
        for p in root.glob("*/*/outcomes.jsonl")
        if not (p.parent / "sessions.jsonl").exists()
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open() as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def index_run(conn: sqlite3.Connection, run_dir: Path) -> str:
    """(Re)index one run directory; returns its run_id (``<experiment>/<stamp>``)."""
    meta: dict[str, Any] = {}
    if (run_dir / "meta.json").exists():
        meta = json.loads((run_dir / "meta.json").read_text())
    experiment = meta.get("experiment") or run_dir.parent.name
    stamp = run_dir.name
    run_id = f"{experiment}/{stamp}"
    synthetic = int(stamp.startswith(("fake-", "estimate-")))
    outcomes = normalize_recorded_costs(_read_jsonl(run_dir / "outcomes.jsonl"))
    calls = _read_jsonl(run_dir / "calls.jsonl")
    for call in calls:
        call["cost_usd_list"] = embedded_list_cost(call) or call.get("cost_usd_list", 0.0)
    with conn:
        conn.execute("DELETE FROM outcome_calls WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM outcomes WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM calls WHERE run_id = ?", (run_id,))
        conn.execute(
            "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                experiment,
                stamp,
                str(run_dir),
                meta.get("started_at"),
                meta.get("hypothesis"),
                meta.get("n_tasks"),
                meta.get("trials"),
                meta.get("order"),
                synthetic,
                json.dumps(meta, default=str),
            ),
        )
        conn.executemany(
            "INSERT OR REPLACE INTO outcomes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    run_id,
                    o["router"],
                    o["task_id"],
                    o["trial"],
                    int(o["passed"]),
                    o.get("difficulty"),
                    o.get("category"),
                    o.get("escalations", 0),
                    o.get("final_candidate"),
                    o.get("cost_usd"),
                    o.get("cost_usd_reported"),
                    o.get("router_cost_usd"),
                    o.get("duration_ms"),
                    o["usage"].get("input_tokens", 0),
                    o["usage"].get("cache_read", 0),
                    o["usage"].get("cache_write", 0),
                    o["usage"].get("cache_write_1h", 0),
                    o["usage"].get("output_tokens", 0),
                    o["usage"].get("reasoning", 0),
                    o.get("grade_detail"),
                    o.get("final_output"),
                )
                for o in outcomes
            ],
        )
        conn.executemany(
            "INSERT OR REPLACE INTO calls VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    run_id,
                    c["seq"],
                    c["task_id"],
                    c["candidate"],
                    c["provider"],
                    c["model"],
                    c.get("resolved_model"),
                    c.get("effort"),
                    c["role"],
                    c["usage"].get("input_tokens", 0),
                    c["usage"].get("cache_read", 0),
                    c["usage"].get("cache_write", 0),
                    c["usage"].get("cache_write_1h", 0),
                    c["usage"].get("output_tokens", 0),
                    c["usage"].get("reasoning", 0),
                    c.get("duration_ms"),
                    c.get("cost_usd_list"),
                    c.get("cost_usd_reported"),
                    c.get("error"),
                    c.get("output"),
                )
                for c in calls
            ],
        )
        conn.executemany(
            "INSERT INTO outcome_calls VALUES (?,?,?,?,?)",
            [
                (run_id, o["router"], o["task_id"], o["trial"], c["seq"])
                for o in outcomes
                for c in o.get("calls", [])
            ],
        )
    return run_id


def index_results(results_dir: str | Path, db_path: str | Path) -> list[str]:
    conn = connect(db_path)
    try:
        ids = [index_run(conn, d) for d in discover_runs(results_dir)]
        # Drop runs whose directory disappeared.
        keep = set(ids)
        stale = [
            r["run_id"] for r in conn.execute("SELECT run_id FROM runs") if r["run_id"] not in keep
        ]
        with conn:
            for rid in stale:
                for table in ("outcome_calls", "outcomes", "calls", "runs"):
                    conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (rid,))
        return ids
    finally:
        conn.close()


def list_runs(conn: sqlite3.Connection, include_synthetic: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT * FROM runs" + ("" if include_synthetic else " WHERE synthetic = 0")
    sql += " ORDER BY started_at DESC, stamp DESC"
    return [dict(r) for r in conn.execute(sql)]


def run_outcomes(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    """Outcomes in the same dict shape ``report.aggregate`` consumes, calls attached."""
    calls_by_task: dict[str, list[dict[str, Any]]] = {}
    for c in conn.execute("SELECT * FROM calls WHERE run_id = ? ORDER BY seq", (run_id,)):
        d = dict(c)
        d["usage"] = {
            k: d.pop(k)
            for k in (
                "input_tokens",
                "cache_read",
                "cache_write",
                "cache_write_1h",
                "output_tokens",
                "reasoning",
            )
        }
        calls_by_task.setdefault(d["task_id"], []).append(d)
    outcomes = []
    for row in conn.execute("SELECT * FROM outcomes WHERE run_id = ? ORDER BY rowid", (run_id,)):
        o = dict(row)
        o["passed"] = bool(o["passed"])
        o["usage"] = {
            k: o.pop(k)
            for k in (
                "input_tokens",
                "cache_read",
                "cache_write",
                "cache_write_1h",
                "output_tokens",
                "reasoning",
            )
        }
        # Calls belong to (router, task); calls.jsonl has no router column, so
        # attribute by sequence window: the outcome's calls are the ones for
        # this task not yet claimed by an earlier outcome of the same task.
        o["calls"] = []
        outcomes.append(o)
    links: dict[tuple[str, str, int], list[int]] = {}
    for row in conn.execute("SELECT * FROM outcome_calls WHERE run_id=? ORDER BY seq", (run_id,)):
        links.setdefault((row["router"], row["task_id"], row["trial"]), []).append(row["seq"])
    by_seq = {c["seq"]: c for pool in calls_by_task.values() for c in pool}
    claimed: dict[str, int] = {}
    for o in outcomes:
        key = (o["router"], o["task_id"], o["trial"])
        if key in links:
            o["calls"] = [by_seq[seq] for seq in links[key] if seq in by_seq]
            claimed[o["task_id"]] = claimed.get(o["task_id"], 0) + len(o["calls"])
            continue
        pool = calls_by_task.get(o["task_id"], [])
        start = claimed.get(o["task_id"], 0)
        n = _calls_for_outcome(o, pool[start:])
        o["calls"] = pool[start : start + n]
        claimed[o["task_id"]] = start + n
    return outcomes


def _calls_for_outcome(o: dict[str, Any], pool: list[dict[str, Any]]) -> int:
    """How many of the task's remaining calls belong to this outcome.

    Matches on cumulative list cost, which the outcome stored as ``cost_usd``.
    Falls back to one call when the sum never matches (e.g. a crashed run).
    """
    target = o.get("cost_usd") or 0.0
    total = 0.0
    for i, c in enumerate(pool, start=1):
        total += c.get("cost_usd_list") or 0.0
        if abs(total - target) < 1e-9:
            return i
    return 1 if pool else 0
