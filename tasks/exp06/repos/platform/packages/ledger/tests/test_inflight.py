from datetime import UTC, datetime, timedelta

from ledger import inflight

T0 = datetime(2026, 9, 1, 2, tzinfo=UTC)


def test_reap_after_stale_window(tmp_path):
    path = tmp_path / "inflight.json"
    inflight.start(path, "r1", "nightly", T0)
    assert inflight.reap_stale(path, T0 + timedelta(hours=5)) == []
    assert inflight.reap_stale(path, T0 + inflight.STALE_AFTER + timedelta(seconds=1)) == ["r1"]
    assert not inflight.already_running(path, "nightly")


def test_finished_runs_are_never_reaped(tmp_path):
    path = tmp_path / "inflight.json"
    inflight.start(path, "r1", "nightly", T0)
    inflight.finish(path, "r1")
    assert inflight.reap_stale(path, T0 + timedelta(days=2)) == []
