"""Hidden grader: shared backoff policy (exp06 stratum B)."""

import math
import warnings

import pytest

from orchestra import JobSpec, run
from toolbelt.backoff import Backoff

from ledger import cli
from ledger.estimate import estimate


# ------------------------------------------------------------------ toolbelt
def test_plain_delays_and_cap():
    b = Backoff(1.5)
    assert [b.delay(n) for n in (1, 2, 3, 4)] == [1.5, 3.0, 6.0, 12.0]
    assert Backoff(2, factor=3, cap=50).schedule(5) == [2, 6, 18, 50, 50]
    assert Backoff(2, factor=3, cap=50).total(3) == 26
    assert Backoff(0).schedule(3) == [0, 0, 0]
    assert Backoff(1, cap=math.inf).delay(30) == 2 ** 29


@pytest.mark.parametrize("kwargs", [dict(base=-1), dict(base=1, factor=0.5), dict(base=1, cap=-1),
                                    dict(base=1, jitter="wild", seed=1), dict(base=1, jitter="full")])
def test_validation(kwargs):
    with pytest.raises(ValueError):
        Backoff(**kwargs)


def test_attempt_validation():
    b = Backoff(1)
    with pytest.raises(ValueError):
        b.delay(0)
    with pytest.raises(TypeError):
        b.delay(True)
    with pytest.raises(TypeError):
        b.delay(1.0)


def test_full_jitter_is_seeded_per_attempt():
    b = Backoff(10, jitter="full", seed=7)
    first = [b.delay(n) for n in (1, 2, 3, 4)]
    again = [b.delay(n) for n in (4, 3, 2, 1)][::-1]
    assert first == again
    import random

    assert b.delay(3) == random.Random("7:3").uniform(0, 40)
    assert all(0 <= d <= 10 * 2 ** (n - 1) for n, d in zip((1, 2, 3, 4), first))
    assert Backoff(10, jitter="full", seed=8).delay(4) != first[3]


def test_equal_jitter_bounds():
    b = Backoff(8, jitter="equal", seed=1)
    for n in range(1, 6):
        d = min(8 * 2 ** (n - 1), math.inf)
        assert d / 2 <= b.delay(n) <= d


# ------------------------------------------------------------------ orchestra
def test_jobspec_backoff_factor_round_trip():
    spec = JobSpec("a", backoff=1, backoff_factor=3)
    assert spec.to_dict()["backoff_factor"] == 3
    legacy = spec.to_dict()
    del legacy["backoff_factor"]
    assert JobSpec.from_dict(legacy).backoff_factor == 2.0
    with pytest.raises(ValueError):
        JobSpec("a", backoff_factor=0.9)


def test_scheduler_uses_factor_without_warnings():
    spec = JobSpec("a", duration=1, outcomes=("fail", "fail", "ok"), max_attempts=3, backoff=2, backoff_factor=3)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        result = run([spec])
    starts = [e.time for e in result.events if e.kind == "start"]
    assert starts == [0, 1 + 2, 1 + 2 + 1 + 6]


def test_shim_warns_and_matches():
    from orchestra.retry import backoff_delay, should_retry

    spec = JobSpec("a", backoff=1.5, max_backoff=5)
    with pytest.warns(DeprecationWarning, match="toolbelt.backoff"):
        assert backoff_delay(spec, 3) == 5
    with pytest.warns(DeprecationWarning):
        assert backoff_delay(spec, 1) == 1.5
    assert should_retry(JobSpec("b", max_attempts=2), 1)


# ------------------------------------------------------------------ ledger
RATES = {"warehouse": 0.5}


def test_estimate_closed_form():
    spec = JobSpec("a", duration=10, max_attempts=3, backoff=4, resources={"warehouse": 2})
    e = estimate(spec, RATES, 0.5)
    assert e.cost == pytest.approx((1 + 0.5 + 0.25) * 10 * 1.0)
    assert e.seconds == pytest.approx((1 + 0.5 + 0.25) * 10 + 0.5 * 4 + 0.25 * 8)
    once = estimate(spec, RATES, 0)
    assert (once.cost, once.seconds) == (pytest.approx(10.0), pytest.approx(10.0))
    always = estimate(spec, RATES, 1)
    assert always.cost == pytest.approx(30.0) and always.seconds == pytest.approx(30 + 4 + 8)
    with pytest.raises(ValueError):
        estimate(spec, RATES, 1.5)


def test_cli_estimate(tmp_path, capsys):
    import json

    specs = [JobSpec("load", duration=10, max_attempts=2, backoff=5, resources={"warehouse": 1}), JobSpec("free", duration=3)]
    path = tmp_path / "specs.json"
    path.write_text(json.dumps([s.to_dict() for s in specs]))
    rates = tmp_path / "rates.json"
    rates.write_text('{"warehouse": "0.5"}')
    assert cli.main(["estimate", str(path), "--p-fail", "0.2", "--rates", str(rates)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        f"{'load':<24} $6.0000 13.0s",
        f"{'free':<24} $0.0000 3.0s",
        f"{'total':<24} $6.0000 16.0s",
    ]
