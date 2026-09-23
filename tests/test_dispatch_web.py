import http.client
import json
import socket
import threading
import time
from pathlib import Path

import pytest

from model_routing.dispatch import api as dispatch_api
from model_routing.dispatch.runner import DispatchConfig
from model_routing.dispatch.types import Progress
from model_routing.dispatch.web import DispatchLab
from model_routing.server import serve
from model_routing.types import Candidate

ROOT = Path(__file__).resolve().parents[1]
CONFIG_REL = "experiments/agentic/exp05_dispatch.toml"
TOKEN = "test-token"


def fake_config(tasks_path: Path) -> DispatchConfig:
    return DispatchConfig(
        name="exp05_dispatch",
        tasks=tasks_path,
        candidates={
            "haiku": Candidate("haiku", "claude_cli", "haiku"),
            "sonnet": Candidate("sonnet", "claude_cli", "sonnet"),
        },
        policies=[
            {"name": "B", "kind": "spawn_static", "candidate": "sonnet"},
            {"name": "C1", "kind": "spawn_parent_pick"},
        ],
        parent="opus",
        menu=["haiku", "sonnet"],
        trials=1,
        primary={"treatment": "C1", "control": "B"},
        margin_pp=5.0,
        source=ROOT / CONFIG_REL,
    )


def fake_auth_status(ready: bool = True) -> dict:
    return {
        "claude": {
            "installed": True,
            "logged_in": ready,
            "detail": "ok" if ready else "run: claude login",
        },
        "codex": {"installed": False, "logged_in": None, "detail": "codex CLI not found"},
    }


def fake_estimate(cfg, *, sample=None, trials=None, policies=None) -> dict:
    n = sample or 2
    return {
        "cells": n,
        "sessions": n * 2,
        "usd_low": 0.10 * n,
        "usd_mid": 0.20 * n,
        "usd_high": 0.40 * n,
        "by_policy": {"B": 0.1, "C1": 0.1},
        "assumptions": ["fake estimate for tests"],
    }


def _build_summary(cfg, out_dir, fake, total, trials, spent) -> dict:
    return {
        "experiment": cfg.name,
        "run_dir": str(out_dir),
        "fake": fake,
        "spent_usd": spent,
        "n_tasks": total,
        "trials": trials or cfg.trials,
        "policies": [
            {
                "name": "B",
                "n": total,
                "pass_rate": 0.8,
                "pass_ci": [0.5, 1.0],
                "cost_per_task": 0.1,
                "cost_per_pass": 0.125,
                "cost_per_pass_ci": [0.1, 0.2],
                "router_share": 0.0,
                "escalation_rate": 0.0,
                "mean_turns": 3.0,
                "setup_cost_usd": 0.0,
                "by_difficulty": {},
                "model_mix": {"sonnet": 1.0},
            },
            {
                "name": "C1",
                "n": total,
                "pass_rate": 0.9,
                "pass_ci": [0.6, 1.0],
                "cost_per_task": 0.08,
                "cost_per_pass": 0.09,
                "cost_per_pass_ci": [0.07, 0.11],
                "router_share": 0.1,
                "escalation_rate": 0.0,
                "mean_turns": 2.5,
                "setup_cost_usd": 0.0,
                "by_difficulty": {},
                "model_mix": {"haiku": 0.5, "sonnet": 0.5},
            },
        ],
        "oracle": None,
        "comparisons": [
            {
                "id": "H-D1",
                "treatment": "C1",
                "control": "B",
                "delta_pass_pp": 10.0,
                "delta_pass_ci": [-2.0, 20.0],
                "saving_pct": 0.28,
                "saving_ci": [0.1, 0.4],
                "verdict": "supported",
                "sentence": "C1 costs less with no meaningful quality loss.",
            }
        ],
        "headline": "C1 saves money over B with non-inferior quality.",
    }


def make_fake_run_dispatch(gate: threading.Event | None = None):
    def fake_run_dispatch(
        cfg,
        *,
        out_dir,
        budget_usd,
        sample=None,
        trials=None,
        policies=None,
        fake=False,
        progress=None,
        cancel=None,
    ):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        total = sample or 2
        done = 0
        state = "done"
        for i in range(total):
            if gate is not None:
                gate.wait(timeout=5)
            if cancel is not None and cancel.is_set():
                state = "cancelled"
                break
            done = i + 1
            if progress:
                progress(
                    Progress(
                        run_dir=str(out_dir),
                        state="running",
                        total=total,
                        done=done,
                        spent_usd=0.05 * done,
                        budget_usd=budget_usd,
                        current=f"task{i}",
                    )
                )
        spent = 0.05 * done
        summary = _build_summary(cfg, out_dir, fake, total, trials, spent)
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
        (out_dir / "summary.md").write_text("# summary\n")
        if progress:
            progress(
                Progress(
                    run_dir=str(out_dir),
                    state=state,
                    total=total,
                    done=done,
                    spent_usd=spent,
                    budget_usd=budget_usd,
                    message="finished",
                )
            )
        return out_dir

    return fake_run_dispatch


def fake_summarize(run_dir) -> dict:
    return json.loads((Path(run_dir) / "summary.json").read_text())


def patch_api(monkeypatch, tasks_path: Path, run_dispatch=None, auth_ready: bool = True) -> None:
    monkeypatch.setattr(dispatch_api, "load_dispatch_config", lambda path: fake_config(tasks_path))
    monkeypatch.setattr(dispatch_api, "auth_status", lambda: fake_auth_status(auth_ready))
    monkeypatch.setattr(dispatch_api, "estimate_dispatch", fake_estimate)
    monkeypatch.setattr(dispatch_api, "run_dispatch", run_dispatch or make_fake_run_dispatch())
    monkeypatch.setattr(dispatch_api, "summarize", fake_summarize)


def _tasks_file(tmp_path: Path, n: int = 4) -> Path:
    path = tmp_path / "tasks.jsonl"
    path.write_text("\n".join(json.dumps({"id": str(i)}) for i in range(n)) + "\n")
    return path


def wait_for(predicate, timeout=5.0, interval=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def load_job(lab: DispatchLab, job_id: str) -> dict:
    job = lab._load_job(job_id)
    assert job is not None
    return job


# --------------------------------------------------------------------------
# DispatchLab unit tests (no HTTP)
# --------------------------------------------------------------------------


def test_configs_report_track_and_task_count(tmp_path, monkeypatch):
    tasks = _tasks_file(tmp_path, n=5)
    patch_api(monkeypatch, tasks)
    lab = DispatchLab(ROOT, tmp_path)
    configs = lab.configs()
    entry = next(c for c in configs if c["path"] == CONFIG_REL)
    assert entry["track"] == "claude"
    assert entry["n_tasks"] == 5
    assert entry["policies"] == ["B", "C1"]
    assert entry["primary"] == {"treatment": "C1", "control": "B"}


def test_fake_run_end_to_end_progress_and_summary(tmp_path, monkeypatch):
    tasks = _tasks_file(tmp_path)
    patch_api(monkeypatch, tasks)
    lab = DispatchLab(ROOT, tmp_path)
    result = lab.start(
        {
            "config": CONFIG_REL,
            "sample": 2,
            "trials": 1,
            "policies": ["B", "C1"],
            "fake": True,
            "budget": 1,
        }
    )
    assert wait_for(lambda: load_job(lab, result["id"])["state"] != "running")
    job = load_job(lab, result["id"])
    assert job["state"] == "done"
    assert job["progress"]["done"] == job["progress"]["total"] == 2
    summary = lab.get_run(Path(job["run_dir"]).relative_to(tmp_path).as_posix())
    assert summary["headline"]
    assert summary["comparisons"][0]["id"] == "H-D1"


def test_start_refuses_real_run_without_confirmed_estimate(tmp_path, monkeypatch):
    tasks = _tasks_file(tmp_path)
    patch_api(monkeypatch, tasks)
    lab = DispatchLab(ROOT, tmp_path)
    with pytest.raises(ValueError):
        lab.start({"config": CONFIG_REL, "sample": 1, "fake": False, "budget": 1})
    with pytest.raises(ValueError):
        lab.start({"config": CONFIG_REL, "sample": 1, "fake": False, "budget": 0})


def test_start_refuses_when_a_job_is_running(tmp_path, monkeypatch):
    tasks = _tasks_file(tmp_path)
    gate = threading.Event()
    patch_api(monkeypatch, tasks, run_dispatch=make_fake_run_dispatch(gate))
    lab = DispatchLab(ROOT, tmp_path)
    lab.start({"config": CONFIG_REL, "sample": 2, "fake": True, "budget": 1})
    try:
        with pytest.raises(ValueError):
            lab.start({"config": CONFIG_REL, "sample": 2, "fake": True, "budget": 1})
    finally:
        gate.set()
    assert wait_for(lambda: not lab.lock.locked() if hasattr(lab.lock, "locked") else True)


def test_job_history_persists_across_restart(tmp_path, monkeypatch):
    tasks = _tasks_file(tmp_path)
    patch_api(monkeypatch, tasks)
    lab = DispatchLab(ROOT, tmp_path)
    result = lab.start({"config": CONFIG_REL, "sample": 1, "fake": True, "budget": 1})
    assert wait_for(lambda: load_job(lab, result["id"])["state"] != "running")

    restarted = DispatchLab(ROOT, tmp_path)
    job = load_job(restarted, result["id"])
    assert job["state"] == "done"


def test_running_job_marked_interrupted_on_restart(tmp_path, monkeypatch):
    tasks = _tasks_file(tmp_path)
    patch_api(monkeypatch, tasks)
    jobs_dir = tmp_path / "dispatch_jobs"
    jobs_dir.mkdir(parents=True)
    (jobs_dir / "abc.json").write_text(
        json.dumps({"id": "abc", "created": "2026-01-01T00:00:00+00:00", "state": "running"})
    )
    lab = DispatchLab(ROOT, tmp_path)
    job = load_job(lab, "abc")
    assert job["state"] == "interrupted"


def test_get_run_refuses_path_traversal(tmp_path, monkeypatch):
    tasks = _tasks_file(tmp_path)
    patch_api(monkeypatch, tasks)
    lab = DispatchLab(ROOT, tmp_path)
    with pytest.raises(ValueError):
        lab.get_run("../../etc/passwd")
    with pytest.raises(ValueError):
        lab.get_run("")


# --------------------------------------------------------------------------
# HTTP endpoint security
# --------------------------------------------------------------------------


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def running_server(tmp_path, monkeypatch):
    tasks = _tasks_file(tmp_path)
    patch_api(monkeypatch, tasks)
    port = _free_port()
    thread = threading.Thread(
        target=serve,
        args=(ROOT, tmp_path),
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

    assert wait_for(_ready, timeout=5.0)
    yield port


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


def test_post_without_token_is_refused(running_server):
    port = running_server
    status, _ = _request(
        port,
        "POST",
        "/api/dispatch/start",
        headers={"Origin": f"http://127.0.0.1:{port}", "Content-Type": "application/json"},
        body={"config": CONFIG_REL, "fake": True, "budget": 1},
    )
    assert status == 403


def test_post_with_wrong_origin_is_refused(running_server):
    port = running_server
    status, _ = _request(
        port,
        "POST",
        "/api/dispatch/estimate",
        headers={
            "Origin": "http://evil.example",
            "Content-Type": "application/json",
            "X-Lab-Token": TOKEN,
        },
        body={"config": CONFIG_REL, "sample": 1},
    )
    assert status == 403


def test_run_path_traversal_refused_over_http(running_server):
    port = running_server
    status, body = _request(port, "GET", "/api/dispatch/run?dir=../../etc")
    assert status == 400
    assert "error" in json.loads(body)


def test_dispatch_page_and_status_serve_over_http(running_server):
    port = running_server
    status, body = _request(port, "GET", "/dispatch")
    assert status == 200
    assert TOKEN.encode() in body

    status, body = _request(port, "GET", "/api/dispatch/status")
    assert status == 200
    payload = json.loads(body)
    assert payload["auth"]["claude"]["installed"] is True
    assert any(c["path"] == CONFIG_REL for c in payload["configs"])


def test_fake_run_flow_over_http(running_server):
    port = running_server
    headers = {
        "Origin": f"http://127.0.0.1:{port}",
        "Content-Type": "application/json",
        "X-Lab-Token": TOKEN,
    }
    status, body = _request(
        port,
        "POST",
        "/api/dispatch/start",
        headers=headers,
        body={"config": CONFIG_REL, "sample": 2, "fake": True, "budget": 1},
    )
    assert status == 200
    run_dir = json.loads(body)["run_dir"]

    def done() -> bool:
        _, b = _request(port, "GET", "/api/dispatch/status")
        job = json.loads(b)["job"]
        return job is not None and job["state"] != "running"

    assert wait_for(done, timeout=5.0)

    dir_param = "/".join(Path(run_dir).parts[-2:])
    status, body = _request(port, "GET", f"/api/dispatch/run?dir={dir_param}")
    assert status == 200
    summary = json.loads(body)
    assert summary["comparisons"][0]["id"] == "H-D1"
