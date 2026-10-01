from toolbelt.runlog import humanize


def test_matches_legacy_samples():
    assert [humanize(s) for s in (7384, 45, 60, 0, 86400)] == ["2h 3m", "45s", "1m 0s", "0s", "1d 0h"]
