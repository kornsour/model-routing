"""Tests for ``model_routing.backup``: durable off-repo backups + export/restore.

Every test runs with HOME pointed at a temp directory (autouse fixture) so
nothing here ever touches the real ``~/.config/model-routing`` or a real
Google Drive folder, per the project's rule that spend and local data are
real and must not be risked by tests.
"""

from __future__ import annotations

import http.client
import json
import re
import socket
import sqlite3
import threading
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from model_routing import backup as backup_mod
from model_routing.backup import (
    Settings,
    auto_backup,
    backup_all,
    backup_run,
    backup_status,
    detect_drive_backup_dir,
    export_run,
    render_report_html,
    restore,
    set_auto_backup,
    set_backup_dir,
)
from model_routing.cli import main
from model_routing.server import serve
from model_routing.store import index_results

ROOT = Path(__file__).resolve().parents[1]
DISPATCH_CFG = ROOT / "experiments" / "agentic" / "exp05_pilot.toml"
LLM_CFG = ROOT / "experiments" / "llm" / "exp02_routing.toml"


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    """Never let a test touch the real ~/.config or scan the real Google Drive."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("MODEL_ROUTING_BACKUP_DIR", raising=False)
    monkeypatch.delenv("MODEL_ROUTING_CONFIG_HOME", raising=False)
    yield


# ---------------------------------------------------------------------------
# Synthetic run directories
# ---------------------------------------------------------------------------


def _dispatch_fake_run(tmp_path: Path, sample: int = 2) -> Path:
    results = tmp_path / "results"
    rc = main(
        [
            "dispatch-run",
            str(DISPATCH_CFG),
            "--fake",
            "--sample",
            str(sample),
            "--budget-usd",
            "1",
            "--out",
            str(results),
        ]
    )
    assert rc == 0
    (run_dir,) = results.glob("exp05_pilot/fake-*")
    return run_dir


def _single_shot_fake_run(tmp_path: Path, sample: int = 4) -> Path:
    results = tmp_path / "results"
    rc = main(["run", str(LLM_CFG), "--fake", "--sample", str(sample), "--out", str(results)])
    assert rc == 0
    (run_dir,) = results.glob("*/fake-*")
    return run_dir


def _real_looking_run(tmp_path: Path, name: str = "widget") -> Path:
    """A minimal run dir that ``is_fake_run`` reports as real (no fake-/estimate- prefix)."""
    run_dir = tmp_path / "results" / "exp_x" / f"20260101-000000-{name}"
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(
        json.dumps({"experiment": "exp_x", "fake": False, "started_at": "2026-01-01T00:00:00Z"})
    )
    (run_dir / "outcomes.jsonl").write_text("")
    (run_dir / "calls.jsonl").write_text("")
    (run_dir / "sandboxes").mkdir()
    (run_dir / "sandboxes" / "throwaway.txt").write_text("do not back this up")
    return run_dir


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def test_settings_persist_under_temp_home(tmp_path):
    backup_dir = tmp_path / "my-backups"
    settings = set_backup_dir(backup_dir)
    assert settings.backup_dir == backup_dir
    path = backup_mod.settings_path()
    assert str(Path.home()) in str(path)
    assert path.is_file()
    data = json.loads(path.read_text())
    assert data["backup_dir"] == str(backup_dir)
    assert data["auto_backup"] is True

    reloaded = Settings.load()
    assert reloaded.backup_dir == backup_dir
    assert reloaded.auto_backup is True

    set_auto_backup(False)
    assert Settings.load().auto_backup is False


def test_env_var_overrides_backup_dir(tmp_path, monkeypatch):
    set_backup_dir(tmp_path / "configured")
    override = tmp_path / "override"
    monkeypatch.setenv("MODEL_ROUTING_BACKUP_DIR", str(override))
    settings = Settings.load()
    assert settings.backup_dir == override
    assert settings.auto_backup is True


def test_drive_detection_requires_exactly_one_candidate(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert detect_drive_backup_dir() is None
    cloud = tmp_path / "Library" / "CloudStorage"
    (cloud / "GoogleDrive-a@example.com" / "My Drive").mkdir(parents=True)
    assert detect_drive_backup_dir() is not None
    (cloud / "GoogleDrive-b@example.com" / "My Drive").mkdir(parents=True)
    assert detect_drive_backup_dir() is None  # ambiguous -> require explicit setting


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def test_render_report_html_dispatch_run(tmp_path):
    run_dir = _dispatch_fake_run(tmp_path)
    html = render_report_html(run_dir)
    assert "<html" in html and "</html>" in html
    assert "SIMULATED" in html
    assert "exp05_pilot" in html
    assert "Comparisons" in html


def test_render_report_html_single_shot_run(tmp_path):
    run_dir = _single_shot_fake_run(tmp_path)
    html = render_report_html(run_dir)
    assert "<html" in html and "</html>" in html
    assert "SIMULATED" in html
    assert "Routers" in html


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def test_export_zip_contents_skip_sandboxes(tmp_path):
    run_dir = _real_looking_run(tmp_path)
    out_dir = tmp_path / "exported"
    zip_path = export_run(run_dir, out_dir)
    # Named by when the run started, in local time, so exports sort and are unique.
    when = datetime(2026, 1, 1, tzinfo=UTC).astimezone().strftime("%Y-%m-%d_%H-%M-%S")
    assert zip_path == out_dir / f"{when}_exp_x.zip"
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    prefix = "exp_x/20260101-000000-widget/"
    assert prefix + "meta.json" in names
    assert prefix + "outcomes.jsonl" in names
    assert prefix + "report.html" in names
    assert prefix + "README.txt" in names
    assert not any("sandboxes" in n for n in names)


def test_export_deterministic_name_for_dispatch_run(tmp_path):
    run_dir = _dispatch_fake_run(tmp_path)
    zip_path = export_run(run_dir)
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_exp05_pilot_simulated\.zip", zip_path.name
    )
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert any(n.endswith("sessions.jsonl") for n in names)
    assert not any("/sandboxes/" in n for n in names)


# ---------------------------------------------------------------------------
# Backup: idempotency, manifest, never-delete
# ---------------------------------------------------------------------------


def test_backup_run_idempotent_with_verified_manifest(tmp_path):
    run_dir = _real_looking_run(tmp_path)
    settings = Settings(backup_dir=tmp_path / "backups", auto_backup=True)

    first = backup_run(run_dir, settings)
    assert first["status"] == "backed-up"
    assert first["copied"]

    dest = Path(first["dest"])
    manifest = json.loads((dest / "manifest.json").read_text())
    for rel, expected_hash in manifest["files"].items():
        assert backup_mod._sha256(dest / rel) == expected_hash

    second = backup_run(run_dir, settings)
    assert second["status"] == "up-to-date"
    assert second["copied"] == []
    assert set(second["skipped"]) >= {"meta.json", "outcomes.jsonl", "calls.jsonl"}


def test_backup_run_never_deletes_existing_files(tmp_path):
    run_dir = _real_looking_run(tmp_path)
    settings = Settings(backup_dir=tmp_path / "backups", auto_backup=True)
    first = backup_run(run_dir, settings)
    dest = Path(first["dest"])
    stray = dest / "operator_added_this.txt"
    stray.write_text("keep me")

    backup_run(run_dir, settings)
    assert stray.is_file()
    assert stray.read_text() == "keep me"


def test_backup_status_reports_freshness(tmp_path):
    run_dir = _real_looking_run(tmp_path)
    results = run_dir.parent.parent
    settings = Settings(backup_dir=tmp_path / "backups", auto_backup=True)

    (status_before,) = backup_status(results, settings)
    assert status_before["backed_up"] is False
    assert status_before["up_to_date"] is False

    backup_run(run_dir, settings)
    (status_after,) = backup_status(results, settings)
    assert status_after["backed_up"] is True
    assert status_after["up_to_date"] is True
    assert status_after["backed_up_at"]

    # Change a local file after backup: now stale, not up to date.
    (run_dir / "meta.json").write_text(
        json.dumps({"experiment": "exp_x", "fake": False, "extra": "changed"})
    )
    (status_stale,) = backup_status(results, settings)
    assert status_stale["backed_up"] is True
    assert status_stale["up_to_date"] is False


# ---------------------------------------------------------------------------
# backup_all: index snapshot + dispatch_jobs
# ---------------------------------------------------------------------------


def test_backup_all_snapshots_index_and_keeps_last_ten(tmp_path):
    run_dir = _real_looking_run(tmp_path)
    results = run_dir.parent.parent
    index_results(results, results / "index.sqlite")
    backup_dir = tmp_path / "backups"
    settings = Settings(backup_dir=backup_dir, auto_backup=True)

    result = backup_all(results, settings)
    assert result["index_snapshot"] is not None
    snap = Path(result["index_snapshot"])
    assert snap.is_file()
    conn = sqlite3.connect(snap)
    conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    conn.close()

    index_dir = backup_dir / "_index"
    for i in range(15):
        (index_dir / f"index-fake{i:02d}.sqlite").write_text("")
    from model_routing.backup import _snapshot_index

    _snapshot_index(results, settings)
    assert len(list(index_dir.glob("index-*.sqlite"))) <= backup_mod.KEEP_INDEX_SNAPSHOTS


def test_backup_all_copies_dispatch_jobs(tmp_path):
    run_dir = _real_looking_run(tmp_path)
    results = run_dir.parent.parent
    jobs_dir = results / "dispatch_jobs"
    jobs_dir.mkdir()
    (jobs_dir / "job1.json").write_text(json.dumps({"id": "job1", "state": "done"}))
    backup_dir = tmp_path / "backups"
    settings = Settings(backup_dir=backup_dir, auto_backup=True)

    result = backup_all(results, settings)
    assert result["dispatch_jobs_copied"] == 1
    assert (backup_dir / "_dispatch_jobs" / "job1.json").is_file()


def test_backup_all_never_loses_a_run_on_one_failure(tmp_path, monkeypatch):
    good = _real_looking_run(tmp_path, "good")
    bad = _real_looking_run(tmp_path, "bad")
    results = good.parent.parent
    settings = Settings(backup_dir=tmp_path / "backups", auto_backup=True)

    real_backup_run = backup_mod.backup_run

    def flaky(run_dir, s=None):
        if run_dir == bad:
            raise OSError("simulated failure")
        return real_backup_run(run_dir, s)

    monkeypatch.setattr(backup_mod, "backup_run", flaky)
    result = backup_all(results, settings)
    assert any(r.get("status") == "failed" for r in result["runs"])
    assert any(r.get("status") in ("backed-up", "up-to-date") for r in result["runs"])
    assert good.is_dir() and (good / "meta.json").is_file()  # local data untouched


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


def test_restore_into_empty_results_and_reindex(tmp_path):
    run_dir = _real_looking_run(tmp_path)
    backup_dir = tmp_path / "backups"
    settings = Settings(backup_dir=backup_dir, auto_backup=True)
    backup_run(run_dir, settings)

    fresh_results = tmp_path / "fresh_results"
    fresh_results.mkdir()
    result = restore(backup_dir, fresh_results)
    assert "exp_x/20260101-000000-widget" in result["restored"]
    assert (fresh_results / "exp_x" / "20260101-000000-widget" / "meta.json").is_file()
    assert not (fresh_results / "exp_x" / "20260101-000000-widget" / "manifest.json").exists()
    assert result["conflicts"] == []
    assert (fresh_results / "index.sqlite").is_file()
    assert any(rid == "exp_x/20260101-000000-widget" for rid in result["indexed"])


def test_restore_reports_conflicts_and_never_overwrites_local(tmp_path):
    run_dir = _real_looking_run(tmp_path)
    backup_dir = tmp_path / "backups"
    settings = Settings(backup_dir=backup_dir, auto_backup=True)
    backup_run(run_dir, settings)

    fresh_results = tmp_path / "fresh_results"
    fresh_results.mkdir()
    restore(backup_dir, fresh_results)

    local_meta = fresh_results / "exp_x" / "20260101-000000-widget" / "meta.json"
    local_meta.write_text(json.dumps({"experiment": "exp_x", "fake": False, "local": "edit"}))

    result = restore(backup_dir, fresh_results)
    assert len(result["conflicts"]) == 1
    conflict = result["conflicts"][0]
    assert conflict["run_id"] == "exp_x/20260101-000000-widget"
    assert "meta.json" in conflict["files"]
    # The local edit was never overwritten.
    assert json.loads(local_meta.read_text())["local"] == "edit"


def test_restore_skips_runs_already_present_without_conflicts(tmp_path):
    run_dir = _real_looking_run(tmp_path)
    results = run_dir.parent.parent
    backup_dir = tmp_path / "backups"
    settings = Settings(backup_dir=backup_dir, auto_backup=True)
    backup_run(run_dir, settings)

    result = restore(backup_dir, results)
    assert result["restored"] == []  # already there, nothing to restore
    assert result["conflicts"] == []  # and files match, so no conflicts either


# ---------------------------------------------------------------------------
# Automatic backup hook
# ---------------------------------------------------------------------------


def test_auto_backup_skips_fake_runs(tmp_path, monkeypatch):
    run_dir = _dispatch_fake_run(tmp_path)
    monkeypatch.setenv("MODEL_ROUTING_BACKUP_DIR", str(tmp_path / "backups"))
    logs: list[str] = []
    result = auto_backup(run_dir, log=logs.append)
    assert result is None
    assert not (tmp_path / "backups").exists()


def test_auto_backup_runs_for_real_runs_when_enabled(tmp_path, monkeypatch):
    run_dir = _real_looking_run(tmp_path)
    monkeypatch.setenv("MODEL_ROUTING_BACKUP_DIR", str(tmp_path / "backups"))
    logs: list[str] = []
    result = auto_backup(run_dir, log=logs.append)
    assert result is not None
    assert result["status"] == "backed-up"
    assert any("backup:" in line for line in logs)


def test_auto_backup_noop_when_disabled(tmp_path):
    run_dir = _real_looking_run(tmp_path)
    set_backup_dir(tmp_path / "backups", auto_backup=False)
    result = auto_backup(run_dir)
    assert result is None
    assert not (tmp_path / "backups").exists()


def test_auto_backup_never_raises_on_failure(tmp_path, monkeypatch):
    run_dir = _real_looking_run(tmp_path)
    monkeypatch.setenv("MODEL_ROUTING_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(
        backup_mod,
        "backup_run",
        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
    )
    logs: list[str] = []
    result = auto_backup(run_dir, log=logs.append)
    assert result is None
    assert any("FAILED" in line for line in logs)
    assert run_dir.is_dir()  # local data untouched


def test_cli_run_fake_triggers_no_backup(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_ROUTING_BACKUP_DIR", str(tmp_path / "backups"))
    run_dir = _single_shot_fake_run(tmp_path)
    assert run_dir.is_dir()
    assert not (tmp_path / "backups").exists()


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

TOKEN = "test-token"


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_for(predicate, timeout=5.0, interval=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


@pytest.fixture
def running_server(tmp_path, monkeypatch):
    # Backups must land under the (isolated) home directory: the settings and
    # restore endpoints both refuse a directory outside it.
    monkeypatch.setenv("MODEL_ROUTING_BACKUP_DIR", str(Path.home() / "backups"))
    results = tmp_path / "results"
    results.mkdir()
    port = _free_port()
    thread = threading.Thread(
        target=serve,
        args=(ROOT, results),
        kwargs={"port": port, "token": TOKEN},
        daemon=True,
    )
    thread.start()

    def _ready() -> bool:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=0.3)
            conn.request("GET", "/", headers={"Host": f"127.0.0.1:{port}"})
            conn.getresponse()
            conn.close()
            return True
        except OSError:
            return False

    assert _wait_for(_ready, timeout=5.0)
    yield port, results


def _request(port, method, path, *, headers=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    hdrs = {"Host": f"127.0.0.1:{port}"}
    hdrs.update(headers or {})
    data = json.dumps(body).encode() if body is not None else None
    conn.request(method, path, body=data, headers=hdrs)
    resp = conn.getresponse()
    payload = resp.read()
    conn.close()
    return resp.status, payload


def _post_headers(port):
    return {
        "Origin": f"http://127.0.0.1:{port}",
        "Content-Type": "application/json",
        "X-Lab-Token": TOKEN,
    }


def test_export_and_report_endpoints_refuse_path_traversal(running_server):
    port, _results = running_server
    status, body = _request(port, "GET", "/api/runs/export?dir=../../etc")
    assert status == 400
    assert "error" in json.loads(body)
    status, body = _request(port, "GET", "/api/runs/report?dir=../../etc")
    assert status == 400


def test_export_and_report_endpoints_serve_a_real_run(running_server):
    port, results = running_server
    run_dir = results / "exp_x" / "20260101-000000-widget"
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(json.dumps({"experiment": "exp_x", "fake": False}))
    (run_dir / "outcomes.jsonl").write_text("")

    status, body = _request(port, "GET", "/api/runs/report?dir=" + "exp_x/20260101-000000-widget")
    assert status == 200
    assert b"<html" in body

    status, body = _request(port, "GET", "/api/runs/export?dir=" + "exp_x/20260101-000000-widget")
    assert status == 200
    assert body[:2] == b"PK"  # zip magic


def test_backup_run_endpoint_refuses_path_traversal(running_server):
    port, _results = running_server
    status, body = _request(
        port,
        "POST",
        "/api/backup/run",
        headers=_post_headers(port),
        body={"dir": "../../etc"},
    )
    assert status == 400
    assert "error" in json.loads(body)


def test_backup_settings_endpoint_validates_path(running_server, monkeypatch):
    port, _results = running_server
    # The fixture sets MODEL_ROUTING_BACKUP_DIR, which would otherwise always
    # win over whatever this test asks the settings endpoint to persist.
    monkeypatch.delenv("MODEL_ROUTING_BACKUP_DIR", raising=False)
    # Relative path refused.
    status, body = _request(
        port,
        "POST",
        "/api/backup/settings",
        headers=_post_headers(port),
        body={"dir": "relative/path"},
    )
    assert status == 400

    # Path outside the home directory refused.
    status, body = _request(
        port,
        "POST",
        "/api/backup/settings",
        headers=_post_headers(port),
        body={"dir": "/etc/model-routing-backups"},
    )
    assert status == 400

    # A path under home is accepted and created.
    target = str(Path.home() / "mr-backups-test")
    status, body = _request(
        port,
        "POST",
        "/api/backup/settings",
        headers=_post_headers(port),
        body={"dir": target, "auto": True},
    )
    assert status == 200
    result = json.loads(body)
    assert result["backup_dir"] == target
    assert Path(target).is_dir()


def test_backup_status_endpoint(running_server):
    port, results = running_server
    run_dir = results / "exp_x" / "20260101-000000-widget"
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(json.dumps({"experiment": "exp_x", "fake": False}))
    (run_dir / "outcomes.jsonl").write_text("")

    status, body = _request(port, "GET", "/api/backup/status")
    assert status == 200
    payload = json.loads(body)
    assert payload["auto_backup"] is True
    assert any(r["run_id"] == "exp_x/20260101-000000-widget" for r in payload["runs"])


def test_backup_run_and_restore_endpoints_over_http(running_server):
    port, results = running_server
    run_dir = results / "exp_x" / "20260101-000000-widget"
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(json.dumps({"experiment": "exp_x", "fake": False}))
    (run_dir / "outcomes.jsonl").write_text("")

    status, body = _request(
        port,
        "POST",
        "/api/backup/run",
        headers=_post_headers(port),
        body={"dir": "exp_x/20260101-000000-widget"},
    )
    assert status == 200
    result = json.loads(body)
    assert result["status"] == "backed-up"

    status, body = _request(port, "POST", "/api/backup/all", headers=_post_headers(port), body={})
    assert status == 200

    backup_dir = json.loads(_request(port, "GET", "/api/backup/status")[1])["backup_dir"]
    status, body = _request(
        port,
        "POST",
        "/api/backup/restore",
        headers=_post_headers(port),
        body={"dir": backup_dir},
    )
    assert status == 200
    restored = json.loads(body)
    assert "restored" in restored and "conflicts" in restored


def test_restore_endpoint_refuses_nonexistent_dir(running_server):
    port, _results = running_server
    missing = str(Path.home() / "does-not-exist")
    status, body = _request(
        port,
        "POST",
        "/api/backup/restore",
        headers=_post_headers(port),
        body={"dir": missing},
    )
    assert status == 400


def test_post_backup_endpoints_require_token(running_server):
    port, _results = running_server
    status, _ = _request(
        port,
        "POST",
        "/api/backup/all",
        headers={"Origin": f"http://127.0.0.1:{port}", "Content-Type": "application/json"},
        body={},
    )
    assert status == 403


def test_backup_writes_timestamped_exports_to_reports_folder(tmp_path):
    from model_routing.backup import REPORTS_DIRNAME, Settings, backup_run

    run_dir = _real_looking_run(tmp_path)
    backup_dir = tmp_path / "drive"
    result = backup_run(run_dir, Settings(backup_dir=backup_dir, auto_backup=True))
    when = datetime(2026, 1, 1, tzinfo=UTC).astimezone().strftime("%Y-%m-%d_%H-%M-%S")
    reports = backup_dir / REPORTS_DIRNAME
    assert (reports / f"{when}_exp_x.zip").is_file()
    assert (reports / f"{when}_exp_x_report.html").is_file()
    assert result["report"].endswith(f"{when}_exp_x_report.html")
    # The restorable per-run mirror is unchanged: raw files + report + manifest.
    run_backup = backup_dir / "exp_x" / run_dir.name
    assert (run_backup / "manifest.json").is_file()
    assert (run_backup / "report.html").is_file()
