"""Monthly budgets as a per-pipeline policy.

``budgets.json`` (format version 2)::

    {"version": 2,
     "defaults": {"monthly_usd": 500, "enforce": "alert", "max_run_usd": null},
     "pipelines": {"nightly": {"monthly_usd": 200, "enforce": null, "max_run_usd": 40}}}

Every pipeline field is optional, and a missing key or ``null`` means
*inherit the default*. ``0`` is a real value (a zero budget). ``enforce`` is
``alert`` (warn after the fact), ``block`` (refuse runs that would breach) or
``off`` (never checked). In ``defaults`` only ``monthly_usd`` is required.

A version-1 file (``{"default_monthly_usd": N, "pipelines": {"p": N}}``) is
read as version 2 without being rewritten; only ``save_budgets`` writes.

``resolve`` turns the config into a ``Policy`` for one pipeline and says which
fields were inherited; ``check`` alerts after the fact; ``admit`` is the
scheduler's gate before a run starts.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ledger.store import RunRecord, query

FIELDS = ("monthly_usd", "enforce", "max_run_usd")
ENFORCE = ("alert", "block", "off")


@dataclass(frozen=True)
class Alert:
    pipeline: str
    spent_usd: float
    budget_usd: float
    enforce: str = "alert"


@dataclass(frozen=True)
class Policy:
    monthly_usd: float
    enforce: str
    max_run_usd: float | None
    inherited: frozenset[str]


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reasons: tuple[str, ...] = ()


def _normalise(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("version") == 2:
        cfg = copy.deepcopy(raw)
    elif "version" not in raw:
        cfg = {
            "version": 2,
            "defaults": {"monthly_usd": raw["default_monthly_usd"]},
            "pipelines": {p: {"monthly_usd": v} for p, v in raw.get("pipelines", {}).items()},
        }
    else:
        raise ValueError(f"unsupported budgets version {raw.get('version')!r}")
    defaults = cfg.setdefault("defaults", {})
    if defaults.get("monthly_usd") is None:
        raise ValueError("defaults.monthly_usd is required")
    defaults.setdefault("enforce", "alert")
    defaults.setdefault("max_run_usd", None)
    cfg.setdefault("pipelines", {})
    return cfg


def load_budgets(path: str | Path) -> dict[str, Any]:
    return _normalise(json.loads(Path(path).read_text()))


def save_budgets(path: str | Path, config: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(_normalise(config), indent=2, sort_keys=True))


def resolve(config: dict[str, Any], pipeline: str) -> Policy:
    config = _normalise(config)
    defaults = config["defaults"]
    own = config.get("pipelines", {}).get(pipeline, {})
    values: dict[str, Any] = {}
    inherited = set()
    for field in FIELDS:
        value = own.get(field)
        if value is None:
            value = defaults.get(field)
            inherited.add(field)
        values[field] = value
    if values["enforce"] not in ENFORCE:
        raise ValueError(f"{pipeline}: enforce must be one of {ENFORCE}, got {values['enforce']!r}")
    max_run = values["max_run_usd"]
    return Policy(
        monthly_usd=float(values["monthly_usd"]),
        enforce=values["enforce"],
        max_run_usd=None if max_run is None else float(max_run),
        inherited=frozenset(inherited),
    )


def budget_for(config: dict[str, Any], pipeline: str) -> float:
    return resolve(config, pipeline).monthly_usd


def reset_to_inherit(config: dict[str, Any], pipelines: list[str], field: str) -> int:
    """Clear ``field`` on exactly the listed pipelines. Returns how many changed."""
    if field not in FIELDS:
        raise ValueError(f"unknown policy field {field!r}")
    entries = config.setdefault("pipelines", {})
    missing = [p for p in pipelines if p not in entries]
    if missing:
        raise KeyError(f"unknown pipeline(s): {', '.join(missing)}")
    changed = 0
    for p in pipelines:
        if entries[p].get(field) is not None:
            entries[p][field] = None
            changed += 1
    return changed


def governed_by_default(config: dict[str, Any], pipelines: list[str], field: str = "monthly_usd") -> list[str]:
    return sorted(p for p in set(pipelines) if field in resolve(config, p).inherited)


def month_to_date(records: list[RunRecord], pipeline: str, month: str) -> float:
    return sum(r.total_usd for r in query(records, pipeline=pipeline, month=month))


def check(records: list[RunRecord], config: dict[str, Any], month: str) -> list[Alert]:
    alerts = []
    for pipeline in sorted({r.pipeline for r in query(records, month=month)}):
        policy = resolve(config, pipeline)
        if policy.enforce == "off":
            continue
        spent = month_to_date(records, pipeline, month)
        if spent > policy.monthly_usd:
            alerts.append(Alert(pipeline, spent, policy.monthly_usd, policy.enforce))
    return alerts


def admit(
    records: list[RunRecord], config: dict[str, Any], pipeline: str, month: str, estimate_usd: float
) -> Decision:
    policy = resolve(config, pipeline)
    if policy.enforce == "off":
        return Decision(True)
    reasons = []
    spent = month_to_date(records, pipeline, month)
    if spent + estimate_usd > policy.monthly_usd:
        reasons.append(
            f"month-to-date ${spent:.2f} plus estimate ${estimate_usd:.2f} exceeds the "
            f"monthly budget ${policy.monthly_usd:.2f}"
        )
    if policy.max_run_usd is not None and estimate_usd > policy.max_run_usd:
        reasons.append(f"estimate ${estimate_usd:.2f} exceeds the per-run cap ${policy.max_run_usd:.2f}")
    allowed = policy.enforce == "alert" or not reasons
    return Decision(allowed, tuple(reasons))
