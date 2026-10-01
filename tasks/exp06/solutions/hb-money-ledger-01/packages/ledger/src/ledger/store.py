"""Run history: one JSON object per line in ``history.jsonl``.

A record (format version 2)::

    {"version": 2, "run_id": "...", "pipeline": "nightly",
     "started_at": "2026-09-01T02:00:00+00:00", "status": "success",
     "currency": "USD", "total_minor": 1250, "jobs_minor": {"load_orders": 425, ...}}

Amounts are integer minor units; ``jobs_minor`` always sums to
``total_minor``. ``started_at`` is an aware UTC timestamp. Records are
appended, never edited, and ``load`` also reads version-1 lines (float
``total_usd`` / ``jobs``): the total is rounded half-even to cents and
re-allocated over the jobs in sorted name order.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from toolbelt.money import from_minor, to_minor

from ledger.pricing import split_minor

FORMAT_VERSION = 2


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    pipeline: str
    started_at: datetime
    status: str
    total_minor: int
    jobs_minor: dict[str, int] = field(default_factory=dict)
    currency: str = "USD"

    def __post_init__(self) -> None:
        if self.jobs_minor and sum(self.jobs_minor.values()) != self.total_minor:
            raise ValueError(
                f"{self.run_id}: job amounts sum to {sum(self.jobs_minor.values())}, "
                f"not the total {self.total_minor}"
            )

    @property
    def total_usd(self) -> Decimal:
        return from_minor(self.total_minor, self.currency)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": FORMAT_VERSION,
            "run_id": self.run_id,
            "pipeline": self.pipeline,
            "started_at": self.started_at.astimezone(UTC).isoformat(),
            "status": self.status,
            "currency": self.currency,
            "total_minor": self.total_minor,
            "jobs_minor": dict(self.jobs_minor),
        }

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> RunRecord:
        version = doc.get("version")
        if version == 1:
            total_minor = to_minor(Decimal(str(doc["total_usd"])), "USD")
            jobs = {k: Decimal(str(v)) for k, v in doc["jobs"].items()}
            return cls(
                run_id=doc["run_id"],
                pipeline=doc["pipeline"],
                started_at=datetime.fromisoformat(doc["started_at"]).astimezone(UTC),
                status=doc["status"],
                total_minor=total_minor,
                jobs_minor=split_minor(total_minor, jobs),
            )
        if version != FORMAT_VERSION:
            raise ValueError(f"unsupported history record version {version!r}")
        return cls(
            run_id=doc["run_id"],
            pipeline=doc["pipeline"],
            started_at=datetime.fromisoformat(doc["started_at"]).astimezone(UTC),
            status=doc["status"],
            total_minor=int(doc["total_minor"]),
            jobs_minor={k: int(v) for k, v in doc["jobs_minor"].items()},
            currency=doc["currency"],
        )

    @property
    def month(self) -> str:
        return self.started_at.strftime("%Y-%m")


def append(path: str | Path, record: RunRecord) -> None:
    with Path(path).open("a") as f:
        f.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")


def load(path: str | Path) -> list[RunRecord]:
    p = Path(path)
    if not p.exists():
        return []
    return [RunRecord.from_dict(json.loads(line)) for line in p.read_text().splitlines() if line.strip()]


def query(
    records: list[RunRecord], *, pipeline: str | None = None, month: str | None = None
) -> list[RunRecord]:
    return [
        r
        for r in records
        if (pipeline is None or r.pipeline == pipeline) and (month is None or r.month == month)
    ]
