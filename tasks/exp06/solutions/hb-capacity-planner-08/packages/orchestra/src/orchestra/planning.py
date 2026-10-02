"""Capacity planning by simulation.

The scheduler is greedy list scheduling, which has Graham's anomalies: adding
capacity can make a run *slower*. With Graham's classic nine jobs (durations
3, 2, 2, 2, 4, 4, 4, 4, 9; job 9 after job 1, jobs 5-8 after job 4,
priorities in list order) on one warehouse pool, the makespan is 12 with 3
slots, 15 with 4 and 12 with 5. So nothing here assumes monotonicity:
``search`` tries every combination in the bounds, and ``anomalies`` reports
where one more unit of a pool made the run longer.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass

from orchestra.model import JobSpec, RunResult, State
from orchestra.pool import PoolError
from orchestra.scheduler import run


@dataclass(frozen=True)
class Plan:
    capacities: dict[str, int]
    makespan: float
    units: int


def simulate(specs: Iterable[JobSpec], capacities: Mapping[str, int]) -> RunResult | None:
    """Run the scheduler; ``None`` when some job can never fit its pools."""
    specs = list(specs)
    for spec in specs:
        for pool, amount in spec.resources.items():
            if pool not in capacities:
                raise PoolError(f"{spec.name!r} needs unknown resource {pool!r}")
            if amount > capacities[pool]:
                return None
    return run(specs, capacities)


def _ok(result: RunResult | None, sla: float) -> bool:
    return (
        result is not None
        and all(r.state is State.SUCCESS for r in result.runs.values())
        and result.makespan <= sla
    )


def feasible(specs: Iterable[JobSpec], capacities: Mapping[str, int], sla: float) -> bool:
    return _ok(simulate(specs, capacities), sla)


def combinations(bounds: Mapping[str, tuple[int, int]]) -> Iterator[dict[str, int]]:
    """Every capacity assignment within inclusive ``bounds``."""
    pools = sorted(bounds)
    for pool in pools:
        lo, hi = bounds[pool]
        if lo < 1 or hi < lo:
            raise ValueError(f"bounds for {pool!r} must satisfy 1 <= lo <= hi, got {(lo, hi)}")
    ranges = [range(bounds[p][0], bounds[p][1] + 1) for p in pools]
    for values in itertools.product(*ranges):
        yield dict(zip(pools, values, strict=True))


def best(
    specs: Iterable[JobSpec],
    bounds: Mapping[str, tuple[int, int]],
    sla: float,
    key: Callable[[dict[str, int], RunResult], tuple],
) -> tuple[dict[str, int], RunResult] | None:
    """The feasible assignment minimising ``key(capacities, result)``, then
    makespan, then the capacities tuple in sorted pool order."""
    specs = list(specs)
    found = None
    for caps in combinations(bounds):
        result = simulate(specs, caps)
        if not _ok(result, sla):
            continue
        rank = (*key(caps, result), result.makespan, tuple(caps[p] for p in sorted(caps)))
        if found is None or rank < found[0]:
            found = (rank, caps, result)
    return None if found is None else (found[1], found[2])


def search(specs: Iterable[JobSpec], bounds: Mapping[str, tuple[int, int]], sla: float) -> Plan | None:
    hit = best(specs, bounds, sla, lambda caps, _result: (sum(caps.values()),))
    if hit is None:
        return None
    caps, result = hit
    return Plan(capacities=caps, makespan=result.makespan, units=sum(caps.values()))


def anomalies(
    specs: Iterable[JobSpec], pool: str, capacities: Mapping[str, int], lo: int, hi: int
) -> list[int]:
    specs = list(specs)
    spans: dict[int, float | None] = {}
    for c in range(lo, hi + 1):
        result = simulate(specs, {**capacities, pool: c})
        spans[c] = None if result is None else result.makespan
    return [
        c
        for c in range(lo, hi)
        if spans[c] is not None and spans[c + 1] is not None and spans[c + 1] > spans[c]
    ]
