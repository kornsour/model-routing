"""Hidden grader: heartbeat liveness and shutdown pause in ledger.inflight (exp06 stratum B)."""

import json
import signal
from datetime import UTC, datetime, timedelta

import pytest

from ledger import cli, inflight

T0 = datetime(2026, 9, 1, 2, tzinfo=UTC)


@pytest.fixture
def path(tmp_path):
    return tmp_path / "inflight.json"


def _data(path):
    return json.loads(path.read_text())


def test_constants():
    assert inflight.HEARTBEAT_STALE == timedelta(minutes=15)
    assert inflight.ATTEMPT_TIMEOUT == timedelta(minutes=10)
    assert inflight.STALE_AFTER == timedelta(hours=6)
    assert inflight.HEARTBEAT_STALE > inflight.ATTEMPT_TIMEOUT


def test_start_sets_heartbeat(path):
    inflight.start(path, "r1", "nightly", T0)
    entry = _data(path)["r1"]
    assert datetime.fromisoformat(entry["heartbeat_at"]) == T0


def test_heartbeat_and_progress(path):
    inflight.start(path, "r1", "nightly", T0)
    inflight.heartbeat(path, "r1", T0 + timedelta(minutes=3))
    assert datetime.fromisoformat(_data(path)["r1"]["heartbeat_at"]) == T0 + timedelta(minutes=3)
    inflight.report_progress(path, "r1", 4, 9, T0 + timedelta(minutes=7))
    entry = _data(path)["r1"]
    assert entry["progress"] == {"done": 4, "total": 9}
    assert datetime.fromisoformat(entry["heartbeat_at"]) == T0 + timedelta(minutes=7)
    with pytest.raises(KeyError):
        inflight.heartbeat(path, "nope", T0)
    inflight.finish(path, "r1")
    inflight.heartbeat(path, "r1", T0 + timedelta(hours=1))
    assert datetime.fromisoformat(_data(path)["r1"]["heartbeat_at"]) == T0 + timedelta(minutes=7)


def test_is_live_rules():
    hb = {"pipeline": "p", "status": "running", "started_at": T0.isoformat(), "heartbeat_at": T0.isoformat()}
    assert inflight.is_live(hb, T0 + timedelta(minutes=15))
    assert not inflight.is_live(hb, T0 + timedelta(minutes=15, seconds=1))
    legacy = {"pipeline": "p", "status": "running", "started_at": T0.isoformat()}
    assert inflight.is_live(legacy, T0 + timedelta(hours=6))
    assert not inflight.is_live(legacy, T0 + timedelta(hours=6, seconds=1))
    assert inflight.is_live(dict(legacy, heartbeat_at=None), T0 + timedelta(hours=5))
    assert not inflight.is_live(dict(hb, status="paused"), T0)
    assert not inflight.is_live(dict(hb, status="success"), T0)


def test_long_run_with_fresh_heartbeat_is_not_reaped(path):
    inflight.start(path, "nightly-1", "nightly", T0)
    now = T0 + timedelta(hours=7)
    inflight.heartbeat(path, "nightly-1", now - timedelta(minutes=2))
    assert inflight.reap_stale(path, now) == []
    assert inflight.already_running(path, "nightly", now)


def test_silent_run_is_reaped_by_heartbeat(path):
    inflight.start(path, "h1", "hourly", T0)
    now = T0 + timedelta(minutes=16)
    assert not inflight.already_running(path, "hourly", now), "a dead row must not block the pipeline"
    assert inflight.reap_stale(path, now) == ["h1"]
    entry = _data(path)["h1"]
    assert entry["status"] == "abandoned" and entry["reaped_by"] == "heartbeat"
    assert "Nothing it finished was lost." in entry["reason"]


def test_legacy_rows_fall_back_to_age(path):
    path.write_text(json.dumps({
        "old": {"pipeline": "nightly", "status": "running", "started_at": T0.isoformat()},
        "young": {"pipeline": "weekly", "status": "running", "started_at": (T0 + timedelta(hours=2)).isoformat()},
    }))
    now = T0 + timedelta(hours=6, seconds=1)
    assert inflight.reap_stale(path, now) == ["old"]
    data = _data(path)
    assert data["old"]["reaped_by"] == "age" and "Nothing it finished was lost." in data["old"]["reason"]
    assert data["old"]["reason"] != _reason_by_heartbeat()
    assert data["young"]["status"] == "running"


def _reason_by_heartbeat():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "i.json"
        inflight.start(p, "x", "p", T0)
        inflight.reap_stale(p, T0 + timedelta(hours=1))
        return json.loads(p.read_text())["x"]["reason"]


def test_paused_and_terminal_rows_untouched(path):
    for rid in ("p1", "s1", "f1"):
        inflight.start(path, rid, "nightly", T0)
    inflight.finish(path, "s1", "success")
    inflight.finish(path, "f1", "failed")
    data = _data(path)
    data["p1"]["status"] = "paused"
    path.write_text(json.dumps(data))
    before = _data(path)
    assert inflight.reap_stale(path, T0 + timedelta(days=3)) == []
    assert _data(path) == before
    assert not inflight.already_running(path, "nightly", T0)


@pytest.fixture
def restore_signals():
    saved = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
    yield
    for s, h in saved.items():
        signal.signal(s, h)
    inflight.ACTIVE.clear()


def test_shutdown_pauses_tracked_running_rows(path, restore_signals):
    for rid in ("a", "b", "c"):
        inflight.start(path, rid, "nightly", T0)
    inflight.finish(path, "b", "success")
    for rid in ("a", "b"):
        inflight.track(rid)
    inflight.install_shutdown_handlers(path, clock=lambda: T0 + timedelta(minutes=30))
    handler = signal.getsignal(signal.SIGTERM)
    inflight.install_shutdown_handlers(path, clock=lambda: T0 + timedelta(minutes=30))
    assert inflight.SHUTDOWN_INSTALLED is True
    assert signal.getsignal(signal.SIGTERM) is handler, "handlers registered twice"
    assert callable(handler) and handler not in (signal.SIG_DFL, signal.SIG_IGN)
    assert inflight.handle_shutdown(signal.SIGTERM) == ["a"]
    data = _data(path)
    assert data["a"]["status"] == "paused" and "SIGTERM" in data["a"]["reason"]
    assert datetime.fromisoformat(data["a"]["paused_at"]) == T0 + timedelta(minutes=30)
    assert data["b"]["status"] == "success" and data["c"]["status"] == "running"
    assert inflight.reap_stale(path, T0 + timedelta(days=2)) == ["c"]
    assert _data(path)["a"]["status"] == "paused"


def test_resume(path):
    inflight.start(path, "a", "nightly", T0)
    with pytest.raises(ValueError):
        inflight.resume(path, "a", T0)
    data = _data(path)
    data["a"]["status"] = "paused"
    path.write_text(json.dumps(data))
    later = T0 + timedelta(hours=9)
    inflight.resume(path, "a", later)
    entry = _data(path)["a"]
    assert entry["status"] == "running" and datetime.fromisoformat(entry["heartbeat_at"]) == later
    assert inflight.already_running(path, "nightly", later + timedelta(minutes=5))


def test_track_untrack():
    inflight.track("z")
    assert "z" in inflight.ACTIVE
    inflight.untrack("z")
    assert "z" not in inflight.ACTIVE


def test_cli_reap(path, capsys):
    inflight.start(path, "h1", "hourly", T0)
    path.write_text(json.dumps(dict(_data(path), legacy={"pipeline": "x", "status": "running", "started_at": T0.isoformat()})))
    now = (T0 + timedelta(hours=7)).isoformat()
    assert cli.main(["reap", "--inflight", str(path), "--now", now]) == 0
    assert capsys.readouterr().out.splitlines() == ["reaped h1 (heartbeat)", "reaped legacy (age)"]
