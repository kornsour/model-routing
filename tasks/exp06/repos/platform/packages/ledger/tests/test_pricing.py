import pytest

from orchestra import JobSpec, run

from ledger.pricing import attempt_windows, price_run

RATES = {"warehouse": 0.5, "api": 0.25}


def test_single_attempt_is_billed_for_its_duration():
    specs = {"a": JobSpec("a", duration=10, resources={"warehouse": 2})}
    cost = price_run(run(specs.values(), {"warehouse": 2}), specs, RATES)
    assert cost.total == pytest.approx(10 * 2 * 0.5)


def test_retries_are_billed():
    specs = {"a": JobSpec("a", duration=4, outcomes=("fail", "ok"), max_attempts=2, backoff=1, resources={"api": 1})}
    result = run(specs.values(), {"api": 1})
    assert [w[:2] for w in attempt_windows(result)] == [("a", 1), ("a", 2)]
    assert price_run(result, specs, RATES).by_job == {"a": pytest.approx(8 * 0.25)}


def test_jobs_without_resources_are_free():
    specs = {"a": JobSpec("a", duration=3)}
    assert price_run(run(specs.values()), specs, RATES).total == 0
