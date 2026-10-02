from datetime import UTC, datetime, timedelta

from ledger import inflight

T0 = datetime(2026, 9, 1, 2, tzinfo=UTC)


def test_reap_after_heartbeat_goes_silent(tmp_path):
    path = tmp_path / "inflight.json"
    inflight.start(path, "r1", "nightly", T0)
    inflight.heartbeat(path, "r1", T0 + timedelta(hours=5))
    assert inflight.reap_stale(path, T0 + timedelta(hours=5, minutes=10)) == []
    assert inflight.reap_stale(path, T0 + timedelta(hours=5, minutes=16)) == ["r1"]
    assert not inflight.already_running(path, "nightly", T0 + inflight.STALE_AFTER + timedelta(seconds=1))


def test_finished_runs_are_never_reaped(tmp_path):
    path = tmp_path / "inflight.json"
    inflight.start(path, "r1", "nightly", T0)
    inflight.finish(path, "r1")
    assert inflight.reap_stale(path, T0 + timedelta(days=2)) == []


def test_fresh_heartbeat_outlives_stale_after(tmp_path):
    path = tmp_path / "inflight.json"
    inflight.start(path, "r1", "nightly", T0)
    now = T0 + inflight.STALE_AFTER + timedelta(hours=1)
    inflight.report_progress(path, "r1", 8, 9, now - timedelta(minutes=1))
    assert inflight.reap_stale(path, now) == []


def test_legacy_rows_use_age(tmp_path):
    import json

    path = tmp_path / "inflight.json"
    path.write_text(json.dumps({"r1": {"pipeline": "p", "status": "running", "started_at": T0.isoformat()}}))
    assert inflight.reap_stale(path, T0 + timedelta(hours=5)) == []
    assert inflight.reap_stale(path, T0 + timedelta(hours=7)) == ["r1"]


def test_heartbeat_threshold_exceeds_attempt_timeout():
    assert inflight.HEARTBEAT_STALE > inflight.ATTEMPT_TIMEOUT
