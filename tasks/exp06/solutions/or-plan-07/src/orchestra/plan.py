"""Critical-path planning: when would each job run with unlimited resources?"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from orchestra.dag import DAG
from orchestra.model import JobSpec
from orchestra.retry import backoff_delay, should_retry


@dataclass(frozen=True)
class JobPlan:
    name: str
    reachable: bool
    succeeds: bool
    duration: float  # time from first start to terminal state (0 if unreachable)
    earliest_start: float | None
    earliest_finish: float | None
    latest_start: float | None
    latest_finish: float | None

    @property
    def slack(self) -> float | None:
        if self.earliest_start is None or self.latest_start is None:
            return None
        return self.latest_start - self.earliest_start

    @property
    def critical(self) -> bool:
        return self.slack == 0


@dataclass(frozen=True)
class Plan:
    jobs: dict[str, JobPlan]
    makespan: float
    critical_path: list[str]


def planned_duration(spec: JobSpec) -> tuple[float, bool]:
    """Elapsed time from first start to terminal state, and whether it succeeds,
    following the scheduler's retry rules with no resource contention."""
    elapsed = 0.0
    attempt = 1
    while True:
        elapsed += spec.duration
        if spec.outcome(attempt) == "ok":
            return elapsed, True
        if not should_retry(spec, attempt):
            return elapsed, False
        elapsed += backoff_delay(spec, attempt)
        attempt += 1


def critical_path(specs: Iterable[JobSpec]) -> Plan:
    dag = DAG(specs)
    order = dag.topo_order()
    dur: dict[str, float] = {}
    ok: dict[str, bool] = {}
    reach: dict[str, bool] = {}
    es: dict[str, float] = {}
    ef: dict[str, float] = {}
    for n in order:
        deps = dag.deps(n)
        reach[n] = all(reach[d] and ok[d] for d in deps)
        dur[n], ok[n] = planned_duration(dag.spec(n))
        if reach[n]:
            es[n] = max((ef[d] for d in deps), default=0.0)
            ef[n] = es[n] + dur[n]
    makespan = max(ef.values(), default=0.0)
    ls: dict[str, float] = {}
    lf: dict[str, float] = {}
    for n in reversed(order):
        if not reach[n]:
            continue
        succ = [m for m in dag.dependents(n) if reach[m]]
        lf[n] = min((ls[m] for m in succ), default=makespan)
        ls[n] = lf[n] - dur[n]
    jobs = {
        n: JobPlan(
            name=n,
            reachable=reach[n],
            succeeds=ok[n] and reach[n],
            duration=dur[n] if reach[n] else 0.0,
            earliest_start=es.get(n),
            earliest_finish=ef.get(n),
            latest_start=ls.get(n),
            latest_finish=lf.get(n),
        )
        for n in order
    }
    path: list[str] = []
    crit = [n for n in order if jobs[n].critical]
    if crit:
        roots = sorted(n for n in crit if es[n] == 0 and not any(d in crit for d in dag.deps(n)))
        cur = roots[0]
        path.append(cur)
        while True:
            nxt = sorted(m for m in dag.dependents(cur) if m in crit and es[m] == ef[cur])
            if not nxt:
                break
            cur = nxt[0]
            path.append(cur)
    return Plan(jobs=jobs, makespan=makespan, critical_path=path)


def _num(x: float | None) -> str:
    return "-" if x is None else f"{x:g}"


def render(plan: Plan) -> str:
    names = list(plan.jobs)
    width = max([len("job")] + [len(n) for n in names])
    lines = [f"{'job':<{width}}  {'start':>6}  {'finish':>6}  {'slack':>6}  note"]
    for n in names:
        j = plan.jobs[n]
        if not j.reachable:
            note = "unreachable"
        elif not j.succeeds:
            note = "fails"
        elif j.critical:
            note = "critical"
        else:
            note = ""
        lines.append(
            f"{n:<{width}}  {_num(j.earliest_start):>6}  {_num(j.earliest_finish):>6}  "
            f"{_num(j.slack):>6}  {note}".rstrip()
        )
    path = " -> ".join(plan.critical_path) if plan.critical_path else "(none)"
    lines.append(f"critical path: {path} ({_num(plan.makespan)})")
    return "\n".join(lines)
