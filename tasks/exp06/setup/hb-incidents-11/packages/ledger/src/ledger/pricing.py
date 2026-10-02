"""Pricing a finished orchestra run.

Every attempt of a job is billed from its ``start`` event to the event that
ends it (``success``, ``retry`` or ``fail``), for the resources the job's spec
holds: ``seconds * sum(units * rate)``. Retries are billed like any other
attempt. Jobs that never started cost nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from orchestra.model import JobSpec, RunResult

from ledger.rates import rate_for

_ENDS = ("success", "fail")


@dataclass(frozen=True)
class AttemptCost:
    job: str
    attempt: int
    start: float
    end: float
    cost: float

    @property
    def seconds(self) -> float:
        return self.end - self.start


@dataclass
class RunCost:
    attempts: list[AttemptCost] = field(default_factory=list)

    @property
    def by_job(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for a in self.attempts:
            out[a.job] = out.get(a.job, 0.0) + a.cost
        return out

    @property
    def total(self) -> float:
        return sum(a.cost for a in self.attempts)


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
    result: RunResult, specs: Mapping[str, JobSpec], rates: Mapping[str, float]
) -> RunCost:
    cost = RunCost()
    for job, attempt, start, end in attempt_windows(result):
        per_second = sum(units * rate_for(rates, pool) for pool, units in specs[job].resources.items())
        cost.attempts.append(AttemptCost(job, attempt, start, end, (end - start) * per_second))
    return cost
