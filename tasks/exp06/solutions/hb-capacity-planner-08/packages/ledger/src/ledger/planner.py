"""Cost-optimal capacity plans.

Capacity is reserved for the whole run, so a plan costs
``sum(capacity * rate) * makespan``. The cheapest plan is often not the one
with the fewest units: a bigger pool that finishes sooner can cost less. The
search is ``orchestra.planning``'s exhaustive search with cost as the first
key (then makespan, then the capacities tuple in sorted pool order).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from orchestra.model import JobSpec
from orchestra.planning import best

from ledger.rates import rate_for


@dataclass(frozen=True)
class PricedPlan:
    capacities: dict[str, int]
    makespan: float
    cost: float


def plan_cost(capacities: Mapping[str, int], makespan: float, rates: Mapping[str, float]) -> float:
    return sum(c * float(rate_for(rates, pool)) for pool, c in capacities.items()) * makespan


def cheapest(
    specs: Iterable[JobSpec],
    bounds: Mapping[str, tuple[int, int]],
    sla: float,
    rates: Mapping[str, float],
) -> PricedPlan | None:
    hit = best(specs, bounds, sla, lambda caps, result: (plan_cost(caps, result.makespan, rates),))
    if hit is None:
        return None
    caps, result = hit
    return PricedPlan(caps, result.makespan, plan_cost(caps, result.makespan, rates))
