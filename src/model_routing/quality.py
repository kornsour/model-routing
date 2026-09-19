"""Paired, quality-gated comparisons with task-clustered uncertainty.

Trials repeat the same task, so they are not independent observations. The
bootstrap resamples task IDs and keeps every trial for a selected task
together. These are descriptive intervals for this benchmark, not claims that
the bundled convenience task set represents a wider population.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any


def _percentile(values: list[float], q: float) -> float:
    values = sorted(values)
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    frac = pos - lo
    return values[lo] * (1 - frac) + values[hi] * frac


def _clustered_intervals(
    router: str,
    rows: dict[tuple[str, int], dict[str, Any]],
    base: dict[tuple[str, int], dict[str, Any]],
    keys: list[tuple[str, int]],
    draws: int = 2000,
) -> tuple[list[float] | None, list[float] | None, int]:
    """Return 95% bootstrap intervals for quality delta and cost saving."""
    tasks = sorted({task_id for task_id, _ in keys})
    if len(tasks) < 2:
        return None, None, len(tasks)
    by_task = {task: [key for key in keys if key[0] == task] for task in tasks}
    seed = int.from_bytes(hashlib.sha256(router.encode()).digest()[:8])
    rng = random.Random(seed)
    quality_deltas: list[float] = []
    savings: list[float] = []
    for _ in range(draws):
        selected = [key for _task in tasks for key in by_task[rng.choice(tasks)]]
        n = len(selected)
        quality = sum(bool(rows[k]["passed"]) for k in selected) / n
        base_quality = sum(bool(base[k]["passed"]) for k in selected) / n
        cost = sum(float(rows[k]["cost_usd"] or 0) for k in selected)
        base_cost = sum(float(base[k]["cost_usd"] or 0) for k in selected)
        quality_deltas.append(quality - base_quality)
        savings.append(1 - cost / base_cost if base_cost else 0.0)
    return (
        [_percentile(quality_deltas, 0.025), _percentile(quality_deltas, 0.975)],
        [_percentile(savings, 0.025), _percentile(savings, 0.975)],
        len(tasks),
    )


def compare(
    outcomes: list[dict[str, Any]],
    baseline: str,
    expected: int,
    min_quality: float = 0.95,
    max_drop: float = 0.02,
    min_saving: float = 0.10,
    run_complete: bool = True,
) -> list[dict[str, Any]]:
    groups: dict[str, dict[tuple[str, int], dict[str, Any]]] = {}
    for o in outcomes:
        groups.setdefault(o["router"], {})[(o["task_id"], o["trial"])] = o
    base = groups.get(baseline, {})
    rows = []
    for name, group in groups.items():
        keys = sorted(base.keys() & group.keys())
        n = len(keys)
        complete = (
            run_complete
            and expected > 0
            and n == expected
            and len(base) == expected
            and len(group) == expected
        )
        quality = sum(bool(group[k]["passed"]) for k in keys) / n if n else 0
        base_quality = sum(bool(base[k]["passed"]) for k in keys) / n if n else 0
        cost = sum(group[k]["cost_usd"] or 0 for k in keys)
        base_cost = sum(base[k]["cost_usd"] or 0 for k in keys)
        saving = 1 - cost / base_cost if base_cost else None
        regressions = sum(bool(base[k]["passed"]) and not group[k]["passed"] for k in keys)
        quality_ci, saving_ci, clusters = _clustered_intervals(name, group, base, keys)
        status = "incomplete"
        if complete:
            status = (
                "quality failed"
                if quality < min_quality or base_quality - quality > max_drop
                else (
                    "promising; validate on holdout"
                    if saving is not None and saving >= min_saving
                    else "no meaningful saving"
                )
            )
        rows.append(
            dict(
                router=name,
                paired=n,
                quality=quality,
                quality_delta=quality - base_quality,
                saving=saving,
                regressions=regressions,
                quality_delta_ci=quality_ci,
                saving_ci=saving_ci,
                task_clusters=clusters,
                status=status,
            )
        )
    return rows
