from orchestra import JobSpec, run
from orchestra.events import replay


def test_replay_ignores_resent_events():
    res = run([JobSpec("a", duration=1)])
    assert replay(res.events + res.events, res.runs) == res.runs
