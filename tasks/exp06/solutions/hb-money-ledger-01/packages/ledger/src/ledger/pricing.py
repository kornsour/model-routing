"""Pricing a finished orchestra run.

Every attempt of a job is billed from its ``start`` event to the event that
ends it (``success``, ``retry`` or ``fail``), for the resources the job's spec
holds: ``seconds * sum(units * rate)``. Retries are billed like any other
attempt. Jobs that never started cost nothing.

Costs are exact, unrounded ``Decimal``s: simulator times are converted with
``Decimal(repr(t))`` before subtracting. ``RunCost.minor`` rounds the total
once (half-even) and splits it over jobs with ``toolbelt.money.allocate``, so
the parts always add up to the total.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from orchestra.model import JobSpec, RunResult
from toolbelt.money import allocate, to_minor

from ledger.rates import rate_for

_ENDS = ("success", "retry", "fail")


@dataclass(frozen=True)
class AttemptCost:
    job: str
    attempt: int
    start: float
    end: float
    cost: Decimal

    @property
    def seconds(self) -> Decimal:
        return Decimal(repr(self.end)) - Decimal(repr(self.start))


def split_minor(total_minor: int, parts: Mapping[str, Decimal]) -> dict[str, int]:
    """Allocate ``total_minor`` over ``parts`` (sorted by key) so the result sums
    to it exactly. All-zero parts get zero each."""
    names = sorted(parts)
    if not names:
        return {}
    if all(parts[n] == 0 for n in names):
        return {n: 0 for n in names}
    return dict(zip(names, allocate(total_minor, [parts[n] for n in names]), strict=True))


@dataclass
class RunCost:
    attempts: list[AttemptCost] = field(default_factory=list)

    @property
    def by_job(self) -> dict[str, Decimal]:
        out: dict[str, Decimal] = {}
        for a in self.attempts:
            out[a.job] = out.get(a.job, Decimal(0)) + a.cost
        return out

    @property
    def total(self) -> Decimal:
        return sum((a.cost for a in self.attempts), Decimal(0))

    def minor(self, currency: str = "USD") -> tuple[int, dict[str, int]]:
        total_minor = to_minor(self.total, currency)
        return total_minor, split_minor(total_minor, self.by_job)


def attempt_windows(result: RunResult) -> list[tuple[str, int, float, float]]:
    """``(job, attempt, start, end)`` for every attempt that finished."""
    open_: dict[str, tuple[int, float]] = {}
    out: list[tuple[str, int, float, float]] = []
    for ev in result.events:
        if ev.kind == "start":
            open_[ev.job] = (ev.attempt, ev.time)
        elif ev.kind in _ENDS and ev.job in open_:
            attempt, start = open_.pop(ev.job)
            out.append((ev.job, attempt, start, ev.time))
    return out


def price_run(
    result: RunResult, specs: Mapping[str, JobSpec], rates: Mapping[str, Decimal]
) -> RunCost:
    cost = RunCost()
    for job, attempt, start, end in attempt_windows(result):
        per_second = sum(
            (units * rate_for(rates, pool) for pool, units in specs[job].resources.items()),
            Decimal(0),
        )
        seconds = Decimal(repr(end)) - Decimal(repr(start))
        cost.attempts.append(AttemptCost(job, attempt, start, end, seconds * per_second))
    return cost
