"""Local experiment plans and durable job lifecycle. No network calls during estimation."""

from __future__ import annotations

import hashlib
import json
import math
import threading
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from model_routing.cli import _providers_for
from model_routing.config import ExperimentConfig
from model_routing.pricing import PriceTable
from model_routing.runner import Runner
from model_routing.store import connect, index_run
from model_routing.types import Candidate

MODELS = {
    "anthropic": ("claude_cli", ("claude-haiku-4-5", "claude-sonnet-5", "claude-opus-5")),
    "openai": ("codex_cli", ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")),
}


def configuration(root: Path, spec: dict[str, Any]) -> ExperimentConfig:
    vendor = spec.get("vendor", "anthropic")
    track = spec.get("track", "adoption")
    if vendor not in MODELS or track not in ("adoption", "research"):
        raise ValueError("Unknown vendor or track")
    provider, models = MODELS[vendor]
    candidates = {
        n: Candidate(n, provider, m)
        for n, m in zip(("small", "mid", "strong"), models, strict=True)
    }
    candidates["strong_low"] = Candidate("strong_low", provider, models[2], effort="low")
    mapping = dict(easy="small", medium="mid", hard="strong", default="strong")
    routers: list[dict[str, Any]] = [
        dict(name="all_" + n, kind="static", candidate=n) for n in candidates
    ]
    routers += [
        dict(name="heuristic", kind="heuristic", map=mapping),
        dict(name="classifier", kind="classifier", classifier="small", map=mapping),
        dict(
            name="confidence_cascade",
            kind="cascade",
            chain=["small", "mid", "strong"],
            escalate_on="confidence",
        ),
    ]
    if track == "research":
        routers += [
            dict(name="oracle_labels", kind="oracle", map=mapping),
            dict(
                name="answer_key_cascade",
                kind="cascade",
                chain=["small", "mid", "strong"],
                escalate_on="grader",
            ),
        ]
    order = spec.get("order", "by_router")
    trials = int(spec.get("trials", 3))
    limit = int(spec.get("limit", 12))
    if order not in ("by_router", "by_task") or not 1 <= trials <= 20 or not 1 <= limit <= 1000:
        raise ValueError("Invalid order, trials (1–20), or task limit (1–1000)")
    for key, default in [("min_quality", 0.95), ("max_drop", 0.02), ("min_saving", 0.10)]:
        value = float(spec.get(key, default))
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{key} must be between 0 and 1")
    cfg = ExperimentConfig(
        name=f"{track}_{vendor}",
        tasks=root / "tasks/llm/knowledge_work.jsonl",
        candidates=candidates,
        routers=routers,
        trials=trials,
        limit=limit,
        order=order,
        hypothesis="Same-vendor savings subject to a quality gate",
    )
    cfg.validate()
    return cfg


def fingerprint(cfg: ExperimentConfig) -> str:
    digest = hashlib.sha256(cfg.tasks.read_bytes())
    for context in sorted((cfg.tasks.parent / "context").glob("*")):
        if context.is_file():
            digest.update(context.name.encode())
            digest.update(context.read_bytes())
    digest.update(json.dumps(asdict(cfg), sort_keys=True, default=str).encode())
    prices = PriceTable.load()
    digest.update(
        json.dumps({m: vars(prices.get(m)) for m in prices.models()}, sort_keys=True).encode()
    )
    return digest.hexdigest()


class Lab:
    def __init__(self, root: Path, results: Path):
        self.root, self.results = root, results
        self.db = results / "index.sqlite"
        self.lock = threading.Lock()
        with connect(self.db) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, created TEXT NOT NULL, state TEXT NOT NULL,
                spec TEXT NOT NULL, estimate REAL, run_path TEXT, error TEXT)""")
            conn.execute(
                "UPDATE jobs SET state='interrupted', error='Server restarted; run is partial' "
                "WHERE state='running'"
            )

    def jobs(self) -> list[dict[str, Any]]:
        with connect(self.db) as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM jobs ORDER BY created DESC")]

    def estimate(self, spec: dict[str, Any]) -> dict[str, Any]:
        cfg = configuration(self.root, spec)
        ident = uuid.uuid4().hex
        out = self.results / cfg.name / ("estimate-" + ident)
        runner = Runner(
            cfg, _providers_for(cfg, True), PriceTable.load(), out, sample=cfg.limit, verbose=False
        )
        runner.run()
        saved = dict(spec)
        for key, value in dict(
            track="adoption",
            vendor="anthropic",
            limit=12,
            trials=3,
            order="by_router",
            min_quality=0.95,
            max_drop=0.02,
            min_saving=0.10,
        ).items():
            saved.setdefault(key, value)
        saved["task_hash"] = fingerprint(cfg)
        with connect(self.db) as conn:
            conn.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?,?,?)",
                (
                    ident,
                    datetime.now(UTC).isoformat(),
                    "estimated",
                    json.dumps(saved),
                    runner.spent_usd,
                    None,
                    None,
                ),
            )
        return dict(
            id=ident,
            estimate=runner.spent_usd,
            tasks=len(runner.tasks),
            routers=len(runner.routers),
            models=[asdict(c) for c in cfg.candidates.values()],
        )

    def start(self, ident: str, budget: float, fake: bool = False) -> None:
        if not math.isfinite(budget) or budget <= 0:
            raise ValueError("A positive finite budget is required")
        if not self.lock.acquire(blocking=False):
            raise ValueError("Another experiment is running; calls must stay sequential")
        try:
            with connect(self.db) as conn:
                row = conn.execute("SELECT * FROM jobs WHERE id=?", (ident,)).fetchone()
                if row is None or row["state"] != "estimated":
                    raise ValueError("Estimate this configuration before starting it")
                spec = json.loads(row["spec"])
                cfg = configuration(self.root, spec)
                if fingerprint(cfg) != spec["task_hash"]:
                    raise ValueError(
                        "Configuration, tasks, context, or prices changed; estimate again"
                    )
                spec["budget_usd"] = budget
                spec["fake"] = fake
                out = self.results / cfg.name / (("fake-" if fake else "") + ident)
                conn.execute(
                    "UPDATE jobs SET state='running', spec=?, run_path=? WHERE id=?",
                    (json.dumps(spec), str(out), ident),
                )
            threading.Thread(target=self._run, args=(ident, spec, out), daemon=True).start()
        except Exception:
            self.lock.release()
            raise

    def _run(self, ident: str, spec: dict[str, Any], out: Path) -> None:
        state, error = "failed", None
        try:
            cfg = configuration(self.root, spec)
            runner = Runner(
                cfg,
                _providers_for(cfg, spec["fake"]),
                PriceTable.load(),
                out,
                budget_usd=spec["budget_usd"],
                sample=cfg.limit,
                verbose=False,
            )
            meta_path = out / "meta.json"
            meta = json.loads(meta_path.read_text())
            meta["lab_spec"] = spec
            meta_path.write_text(json.dumps(meta, indent=2))
            runner.run()
            expected = len(runner.tasks) * len(runner.routers) * cfg.trials
            state = "completed" if len(runner.outcomes) == expected else "budget_stopped"
        except Exception as exc:
            error = str(exc)
        finally:
            try:
                with connect(self.db) as conn:
                    if (out / "outcomes.jsonl").exists():
                        index_run(conn, out)
                    conn.execute(
                        "UPDATE jobs SET state=?, error=? WHERE id=?", (state, error, ident)
                    )
                if (out / "outcomes.jsonl").exists():
                    from model_routing.backup import auto_backup

                    auto_backup(out)
            finally:
                self.lock.release()
