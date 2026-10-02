"""Monthly budgets.

``budgets.json`` holds a default monthly budget and per-pipeline budgets::

    {"default_monthly_usd": 500, "pipelines": {"nightly": 200}}

A pipeline without its own entry gets the default. ``check`` returns an alert
for every pipeline whose month-to-date spend is over its budget.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ledger.store import RunRecord, query


@dataclass(frozen=True)
class Alert:
    pipeline: str
    spent_usd: float
    budget_usd: float


def load_budgets(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def budget_for(config: dict[str, Any], pipeline: str) -> float:
    return float(config.get("pipelines", {}).get(pipeline, config["default_monthly_usd"]))


def month_to_date(records: list[RunRecord], pipeline: str, month: str) -> float:
    return sum(r.total_usd for r in query(records, pipeline=pipeline, month=month))


def check(records: list[RunRecord], config: dict[str, Any], month: str) -> list[Alert]:
    alerts = []
    for pipeline in sorted({r.pipeline for r in query(records, month=month)}):
        spent = month_to_date(records, pipeline, month)
        limit = budget_for(config, pipeline)
        if spent >= limit:
            alerts.append(Alert(pipeline, spent, limit))
    return alerts
