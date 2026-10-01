import warnings

from orchestra import JobSpec, run


def test_factor_three_without_deprecation_warnings():
    spec = JobSpec("a", duration=1, outcomes=("fail", "ok"), max_attempts=2, backoff=1, backoff_factor=3)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        assert [e.time for e in run([spec]).events if e.kind == "start"] == [0, 2]
