"""Monthly budgets.

``budgets.json`` holds a default monthly budget and per-pipeline budgets in
USD, as JSON numbers or strings, read exactly::

    {"default_monthly_usd": 500, "pipelines": {"nightly": "200.50"}}

A pipeline without its own entry gets the default. Amounts are compared in
integer minor units (cents); a budget finer than a cent is an error. ``check``
returns an alert for every pipeline whose month-to-date spend is strictly over
its budget.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from toolbelt.money import to_minor

from ledger.store import RunRecord, query


@dataclass(frozen=True)
class Alert:
    pipeline: str
    spent_minor: int
    budget_minor: int


def load_budgets(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(), parse_float=Decimal)


def _minor(amount: object) -> int:
    exact = Decimal(str(amount)) * 100
    if exact != exact.to_integral_value():
        raise ValueError(f"budget {amount} is finer than a cent")
    return to_minor(Decimal(str(amount)), "USD")


def budget_for(config: dict[str, Any], pipeline: str) -> int:
    return _minor(config.get("pipelines", {}).get(pipeline, config["default_monthly_usd"]))


def month_to_date(records: list[RunRecord], pipeline: str, month: str) -> int:
    return sum(r.total_minor for r in query(records, pipeline=pipeline, month=month))


def check(records: list[RunRecord], config: dict[str, Any], month: str) -> list[Alert]:
    alerts = []
    for pipeline in sorted({r.pipeline for r in query(records, month=month)}):
        spent = month_to_date(records, pipeline, month)
        limit = budget_for(config, pipeline)
        if spent > limit:
            alerts.append(Alert(pipeline, spent, limit))
    return alerts
