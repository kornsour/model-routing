import random
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _reference_scheduler import ReferenceScheduler  # noqa: E402

from orchestra import DAG, JobSpec, Scheduler, State, run  # noqa: E402
from orchestra.events import replay  # noqa: E402


def random_specs(rng, n, *, resources=True, fail_rate=0.15, zero_rate=0.1, dup_rate=0.1):
    specs = []
    for i in range(n):
        name = f"j{rng.randrange(10**6):06d}_{i}"
        k = rng.choice([0, 0, 1, 1, 2, 3])
        deps = [specs[rng.randrange(len(specs))].name for _ in range(min(k, len(specs)))]
        if deps and rng.random() < dup_rate:
            deps.append(deps[0])
        res = {}
        if resources and rng.random() < 0.6:
            res[rng.choice(["cpu", "db"])] = rng.choice([1, 1, 2])
            if rng.random() < 0.2:
                res["gpu"] = 1
        outcomes = tuple(rng.choice(["ok", "ok", "ok", "fail"]) for _ in range(rng.randrange(1, 4)))
        if rng.random() > fail_rate:
            outcomes = outcomes[:-1] + ("ok",)
        dur = 0.0 if rng.random() < zero_rate else float(rng.choice([1, 1, 2, 3, 5, 0.5]))
        specs.append(
            JobSpec(
                name,
                deps=tuple(deps),
                priority=rng.choice([0, 0, 1, 5, -2]),
                resources=res,
                duration=dur,
                outcomes=outcomes,
                max_attempts=rng.choice([1, 1, 2, 3]),
                backoff=rng.choice([0.0, 0.5, 1.0, 2.0]),
                max_backoff=rng.choice([float("inf"), 3.0]),
            )
        )
    rng.shuffle(specs)
    return specs


CAPS = {"cpu": 3, "db": 2, "gpu": 1}


@pytest.mark.parametrize("seed", range(40))
def test_matches_reference_exactly(seed):
    rng = random.Random(seed)
    specs = random_specs(rng, rng.randrange(5, 120))
    ref = ReferenceScheduler(DAG(specs), CAPS).run()
    got = Scheduler(DAG(specs), CAPS).run()
    assert got.events == ref.events
    assert got.runs == ref.runs
    assert list(got.runs) == list(ref.runs)
    assert got.makespan == ref.makespan
    assert replay(got.events, got.runs) == got.runs


@pytest.mark.parametrize("seed", range(10))
def test_matches_reference_without_resources(seed):
    rng = random.Random(1000 + seed)
    specs = random_specs(rng, 150, resources=False, fail_rate=0.3, zero_rate=0.3)
    ref = ReferenceScheduler(DAG(specs)).run()
    got = run(specs)
    assert got.events == ref.events and got.runs == ref.runs


def test_matches_reference_on_contention_and_mixed_free_jobs():
    specs = []
    for i in range(60):
        specs.append(JobSpec(f"slot{i:02d}", resources={"cpu": 1}, priority=i % 3, duration=1 + i % 2))
        specs.append(JobSpec(f"free{i:02d}", priority=(i % 5) - 2, duration=0.5 * (i % 3)))
    specs.append(JobSpec("big", resources={"cpu": 3, "db": 2}, priority=10, duration=4))
    ref = ReferenceScheduler(DAG(specs), CAPS).run()
    got = Scheduler(DAG(specs), CAPS).run()
    assert got.events == ref.events and got.runs == ref.runs


def layered(n, width, seed):
    rng = random.Random(seed)
    specs = []
    for i in range(n):
        layer = i // width
        deps = ()
        if layer:
            lo = (layer - 1) * width
            deps = tuple(f"t{rng.randrange(lo, lo + width):05d}" for _ in range(rng.randrange(1, 4)))
        specs.append(JobSpec(f"t{i:05d}", deps=deps, duration=float(rng.randrange(1, 60)), priority=rng.randrange(3)))
    return specs


def test_large_dag_is_fast():
    specs = layered(20000, 100, 7)
    t0 = time.perf_counter()
    res = run(specs)
    elapsed = time.perf_counter() - t0
    assert all(r.state is State.SUCCESS for r in res.runs.values())
    assert len(res.events) == 40000
    assert elapsed < 6.0, f"20k-job run took {elapsed:.1f}s"


def test_contention_is_fast():
    specs = [JobSpec(f"q{i:05d}", resources={"cpu": 1}, priority=i % 4) for i in range(12000)]
    t0 = time.perf_counter()
    res = run(specs, {"cpu": 2})
    elapsed = time.perf_counter() - t0
    assert res.makespan == 6000
    assert elapsed < 6.0, f"12k contended jobs took {elapsed:.1f}s"


def test_failure_cascade_is_fast_and_correct():
    specs = [JobSpec("root", outcomes=("fail",))]
    specs += [JobSpec(f"c{i:05d}", deps=("root" if i == 0 else f"c{i - 1:05d}",)) for i in range(15000)]
    t0 = time.perf_counter()
    res = run(specs)
    elapsed = time.perf_counter() - t0
    assert res.runs["c14999"].state is State.UPSTREAM_FAILED
    assert res.runs["c14999"].reason == "upstream c14998 upstream_failed"
    assert [e.job for e in res.events[2:5]] == ["c00000", "c00001", "c00002"]
    assert elapsed < 6.0
