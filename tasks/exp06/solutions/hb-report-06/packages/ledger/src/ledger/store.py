"""Run history: one JSON object per line in ``history.jsonl``.

A record (format version 1)::

    {"version": 1, "run_id": "...", "pipeline": "nightly",
     "started_at": "2026-09-01T02:00:00+00:00", "status": "success",
     "total_usd": 12.5, "jobs": {"load_orders": 4.25, ...}}

``started_at`` is an aware UTC timestamp. Records are appended, never edited.
Months are UTC calendar months unless a query names an IANA time zone, in
which case a run belongs to the month of its start time in that zone.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

FORMAT_VERSION = 1


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    pipeline: str
    started_at: datetime
    status: str
    total_usd: float
    jobs: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": FORMAT_VERSION,
            "run_id": self.run_id,
            "pipeline": self.pipeline,
            "started_at": self.started_at.astimezone(UTC).isoformat(),
            "status": self.status,
            "total_usd": self.total_usd,
            "jobs": dict(self.jobs),
        }

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> RunRecord:
        if doc.get("version") != FORMAT_VERSION:
            raise ValueError(f"unsupported history record version {doc.get('version')!r}")
        return cls(
            run_id=doc["run_id"],
            pipeline=doc["pipeline"],
            started_at=datetime.fromisoformat(doc["started_at"]).astimezone(UTC),
            status=doc["status"],
            total_usd=float(doc["total_usd"]),
            jobs={k: float(v) for k, v in doc["jobs"].items()},
        )

    @property
    def month(self) -> str:
        return self.started_at.strftime("%Y-%m")

    def month_in(self, tz: str) -> str:
        return self.started_at.astimezone(ZoneInfo(tz)).strftime("%Y-%m")


def append(path: str | Path, record: RunRecord) -> None:
    with Path(path).open("a") as f:
        f.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")


def load(path: str | Path) -> list[RunRecord]:
    p = Path(path)
    if not p.exists():
        return []
    return [RunRecord.from_dict(json.loads(line)) for line in p.read_text().splitlines() if line.strip()]


def query(
    records: list[RunRecord],
    *,
    pipeline: str | None = None,
    month: str | None = None,
    tz: str = "UTC",
) -> list[RunRecord]:
    return [
        r
        for r in records
        if (pipeline is None or r.pipeline == pipeline)
        and (month is None or r.month_in(tz) == month)
    ]
