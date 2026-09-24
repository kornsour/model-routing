"""Job manager and request handlers for the dispatch routing lab (``/dispatch``).

``DispatchLab`` runs at most one dispatch experiment at a time, in a
background thread, and persists job state as JSON under
``results/dispatch_jobs/<id>.json`` so a restarted server still shows job
history (``results/index.sqlite`` is untouched by this module). All spend
still goes through ``model_routing.dispatch.api`` -- this module never talks
to a provider directly.

``server.py`` delegates every ``/api/dispatch/*`` route to a method here; see
that module for the token/Origin/Content-Type checks every write endpoint
gets.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from model_routing.dispatch import api
from model_routing.dispatch.types import Progress

AUTH_CACHE_SECONDS = 60.0


def _opt_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Expected an integer") from exc


def _opt_policy_list(value: Any) -> list[str] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError("policies must be a list of strings")
    return list(value) or None


def _track_for(cfg: Any) -> str:
    providers = {c.provider for c in cfg.candidates.values()}
    if providers <= {"claude_cli"}:
        return "claude"
    if providers <= {"codex_cli"}:
        return "codex"
    return "mixed"


class DispatchLab:
    """Owns dispatch job state: at most one run in flight, JSON on disk."""

    def __init__(self, root: Path, results: Path) -> None:
        self.root = root
        self.results = results
        self.jobs_dir = results / "dispatch_jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self._cancel: threading.Event | None = None
        self._current_id: str | None = None
        self._auth_cache: dict[str, Any] | None = None
        self._auth_cache_at: float = 0.0
        self._mark_interrupted_jobs()

    # -- startup -----------------------------------------------------

    def _mark_interrupted_jobs(self) -> None:
        for path in self.jobs_dir.glob("*.json"):
            try:
                record = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if record.get("state") == "running":
                record["state"] = "interrupted"
                record["error"] = "Server restarted; run is partial"
                record["finished_at"] = datetime.now(UTC).isoformat()
                path.write_text(json.dumps(record, indent=2))

    # -- job persistence ----------------------------------------------

    def _job_path(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.json"

    def _save_job(self, record: dict[str, Any]) -> None:
        self._job_path(record["id"]).write_text(json.dumps(record, indent=2))

    def _load_job(self, job_id: str) -> dict[str, Any] | None:
        path = self._job_path(job_id)
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    def _all_jobs(self) -> list[dict[str, Any]]:
        jobs = []
        for path in self.jobs_dir.glob("*.json"):
            try:
                jobs.append(json.loads(path.read_text()))
            except (OSError, json.JSONDecodeError):
                continue
        jobs.sort(key=lambda j: j.get("created", ""), reverse=True)
        return jobs

    # -- read-only status ----------------------------------------------

    def auth_status(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._auth_cache is None or now - self._auth_cache_at > AUTH_CACHE_SECONDS:
            self._auth_cache = api.auth_status()
            self._auth_cache_at = now
        return self._auth_cache

    def _count_tasks(self, cfg: Any) -> int:
        path = cfg.tasks if Path(cfg.tasks).is_absolute() else self.root / cfg.tasks
        try:
            lines = Path(path).read_text().splitlines()
        except OSError:
            return 0
        return sum(1 for line in lines if line.strip())

    def configs(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        config_dir = self.root / "experiments" / "agentic"
        if not config_dir.is_dir():
            return out
        for path in sorted(config_dir.glob("*.toml")):
            entry: dict[str, Any] = {"path": str(path.relative_to(self.root)), "name": path.stem}
            try:
                cfg = api.load_dispatch_config(path)
            except Exception as exc:  # runner workstream may not be ready yet
                entry["error"] = str(exc)
                out.append(entry)
                continue
            entry.update(
                name=cfg.name,
                track=_track_for(cfg),
                policies=[p.get("name", "") for p in cfg.policies],
                n_tasks=self._count_tasks(cfg),
                trials=cfg.trials,
                primary=cfg.primary,
                margin_pp=cfg.margin_pp,
            )
            out.append(entry)
        return out

    def _current_job_snapshot(self) -> dict[str, Any] | None:
        if self._current_id is not None:
            return self._load_job(self._current_id)
        jobs = self._all_jobs()
        return jobs[0] if jobs else None

    def history(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for summary_path in sorted(self.results.glob("exp05*/*/summary.json"), reverse=True):
            try:
                summary = json.loads(summary_path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            out.append(
                {
                    "run_dir": str(summary_path.parent.relative_to(self.results)),
                    "experiment": summary.get("experiment"),
                    "fake": summary.get("fake"),
                    "spent_usd": summary.get("spent_usd"),
                    "n_tasks": summary.get("n_tasks"),
                    "trials": summary.get("trials"),
                    "headline": summary.get("headline"),
                    # Additive: None for summaries written before the
                    # pre-registration check existed.
                    "confirmatory": summary.get("confirmatory"),
                }
            )
        return out

    def status(self) -> dict[str, Any]:
        return {
            "auth": self.auth_status(),
            "configs": self.configs(),
            "job": self._current_job_snapshot(),
            "history": self.history(),
        }

    def get_run(self, dir_param: str) -> dict[str, Any]:
        run_dir = self._safe_run_dir(dir_param)
        summary_path = run_dir / "summary.json"
        if not summary_path.is_file():
            raise ValueError("No summary.json for that run")
        return json.loads(summary_path.read_text())

    def _safe_run_dir(self, dir_param: str) -> Path:
        if not dir_param:
            raise ValueError("Missing dir")
        base = self.results.resolve()
        candidate = (self.results / dir_param).resolve()
        if candidate != base and base not in candidate.parents:
            raise ValueError("Path must stay under results/")
        return candidate

    # -- config resolution ----------------------------------------------

    def _resolve_config(self, config: str) -> Path:
        if not config:
            raise ValueError("Missing config")
        base = (self.root / "experiments" / "agentic").resolve()
        candidate = (self.root / config).resolve()
        if base not in candidate.parents:
            raise ValueError("Config path must be under experiments/agentic")
        if candidate.suffix != ".toml" or not candidate.is_file():
            raise ValueError("Unknown config")
        return candidate

    # -- estimate / start / cancel ----------------------------------------------

    def estimate(self, payload: dict[str, Any]) -> dict[str, Any]:
        cfg_path = self._resolve_config(str(payload.get("config", "")))
        cfg = api.load_dispatch_config(cfg_path)
        sample = _opt_int(payload.get("sample"))
        trials = _opt_int(payload.get("trials"))
        policies = _opt_policy_list(payload.get("policies"))
        return api.estimate_dispatch(cfg, sample=sample, trials=trials, policies=policies)

    def start(self, payload: dict[str, Any]) -> dict[str, Any]:
        cfg_path = self._resolve_config(str(payload.get("config", "")))
        cfg = api.load_dispatch_config(cfg_path)
        sample = _opt_int(payload.get("sample"))
        trials = _opt_int(payload.get("trials"))
        policies = _opt_policy_list(payload.get("policies"))
        fake = payload.get("fake") is True
        budget = float(payload.get("budget", 0) or 0)

        if not fake:
            if not budget > 0:
                raise ValueError("A positive budget is required for a real run")
            confirm_raw = payload.get("confirm_estimate_usd")
            if confirm_raw is None:
                raise ValueError("Estimate the run and confirm the amount before starting")
            confirmed = float(confirm_raw)
            fresh = api.estimate_dispatch(cfg, sample=sample, trials=trials, policies=policies)
            if fresh["usd_high"] > confirmed + 1e-9:
                raise ValueError(
                    "The estimate has changed since you last saw it "
                    f"(now ${fresh['usd_high']:.4f} high vs. confirmed ${confirmed:.4f}); "
                    "estimate again before running"
                )

        if not self.lock.acquire(blocking=False):
            raise ValueError("Another dispatch run is already in progress")
        try:
            job_id = uuid.uuid4().hex
            stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            out = self.results / cfg.name / (("fake-" if fake else "") + stamp + "-" + job_id[:8])
            now = datetime.now(UTC).isoformat()
            record: dict[str, Any] = {
                "id": job_id,
                "created": now,
                "config": str(cfg_path.relative_to(self.root)),
                "sample": sample,
                "trials": trials,
                "policies": policies,
                "budget_usd": budget,
                "fake": fake,
                "confirm_estimate_usd": payload.get("confirm_estimate_usd"),
                "state": "running",
                "error": None,
                "run_dir": str(out),
                "progress": None,
                "started_at": now,
                "finished_at": None,
            }
            self._save_job(record)
            self._current_id = job_id
        except Exception:
            self.lock.release()
            raise
        thread = threading.Thread(
            target=self._execute,
            args=(job_id, cfg, sample, trials, policies, budget, fake, out),
            daemon=True,
        )
        thread.start()
        return {"id": job_id, "run_dir": str(out)}

    def cancel(self) -> dict[str, Any]:
        cancel_event = self._cancel
        if cancel_event is None:
            raise ValueError("No dispatch run is in progress")
        cancel_event.set()
        return {"state": "cancelling"}

    def _execute(
        self,
        job_id: str,
        cfg: Any,
        sample: int | None,
        trials: int | None,
        policies: list[str] | None,
        budget: float,
        fake: bool,
        out: Path,
    ) -> None:
        cancel = threading.Event()
        self._cancel = cancel
        last_progress: dict[str, Any] | None = None
        state = "failed"
        error: str | None = None

        def on_progress(p: Progress) -> None:
            nonlocal last_progress
            last_progress = p.to_dict()
            record = self._load_job(job_id) or {"id": job_id}
            record["progress"] = last_progress
            record["state"] = "running"
            self._save_job(record)

        try:
            run_dir = api.run_dispatch(
                cfg,
                out_dir=out,
                budget_usd=budget,
                sample=sample,
                trials=trials,
                policies=policies,
                fake=fake,
                progress=on_progress,
                cancel=cancel,
            )
            api.summarize(run_dir)
            state = last_progress.get("state", "done") if last_progress else "done"
        except Exception as exc:  # keep the thread from dying silently
            error = str(exc)
            state = "failed"
        finally:
            record = self._load_job(job_id) or {"id": job_id}
            record.update(
                state=state,
                error=error,
                progress=last_progress if last_progress is not None else record.get("progress"),
                finished_at=datetime.now(UTC).isoformat(),
            )
            self._save_job(record)
            self._current_id = None
            self._cancel = None
            self.lock.release()
            if out.exists() and state in ("done", "over_budget", "cancelled", "failed"):
                from model_routing.backup import auto_backup

                auto_backup(out)
