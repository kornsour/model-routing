"""Paired, quality-gated comparisons; descriptive evidence, not significance claims."""

from __future__ import annotations

from typing import Any


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
        keys = base.keys() & group.keys()
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
                status=status,
            )
        )
    return rows
