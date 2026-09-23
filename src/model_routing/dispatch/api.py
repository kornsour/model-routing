"""Public entry points the CLI and the web app call.  Implemented in ``runner``,
``report`` and ``harvest``; this module only re-exports them with fixed
signatures so the web app and CLI can be built in parallel with the runner.

Contract (do not change signatures without updating every caller):

``load_dispatch_config(path) -> DispatchConfig``
    Parse ``experiments/agentic/*.toml`` (see exp05_dispatch.toml).

``estimate_dispatch(cfg, *, sample=None, trials=None, policies=None) -> dict``
    No spend.  Returns ``{"cells": int, "sessions": int, "usd_low": float,
    "usd_mid": float, "usd_high": float, "by_policy": {name: usd_mid},
    "assumptions": [str, ...]}``.

``run_dispatch(cfg, *, out_dir, budget_usd, sample=None, trials=None,
policies=None, fake=False, progress=None, cancel=None) -> Path``
    Runs sequentially, writes ``sessions.jsonl``, ``outcomes.jsonl``,
    ``meta.json``, then ``summary.json`` + ``summary.md`` via ``summarize``.
    ``progress`` is called with a ``Progress`` after every session.
    ``cancel`` is a ``threading.Event``; checked between sessions.
    ``fake=True`` uses the fake agent provider (no spend).

``summarize(run_dir) -> dict``
    (Re)build ``summary.json`` / ``summary.md`` from the JSONL files and
    return the summary dict.  Shape::

        {"experiment": str, "run_dir": str, "fake": bool, "spent_usd": float,
         "n_tasks": int, "trials": int,
         "policies": [{"name", "n", "pass_rate", "pass_ci": [lo, hi],
                       "cost_per_task", "cost_per_pass", "cost_per_pass_ci",
                       "router_share", "escalation_rate", "mean_turns",
                       "setup_cost_usd", "by_difficulty": {...},
                       "model_mix": {candidate: share}}],
         "oracle": {...same keys...} | None,
         "comparisons": [{"id": "H-D1", "treatment", "control",
                          "delta_pass_pp", "delta_pass_ci",
                          "saving_pct", "saving_ci", "verdict", "sentence"}],
         "headline": str}

``auth_status() -> dict``
    ``{"claude": {"installed": bool, "logged_in": bool | None, "detail": str},
       "codex":  {...}}`` - no spend, no network beyond the CLIs' own checks.

``harvest_chips(projects_dir, out_path) -> int``
    Scan local Claude Code transcripts for spawned task chips; write JSONL
    candidates; return how many were written.
"""

from __future__ import annotations

from model_routing.dispatch.harvest import harvest_chips
from model_routing.dispatch.report import summarize
from model_routing.dispatch.runner import (
    DispatchConfig,
    auth_status,
    estimate_dispatch,
    load_dispatch_config,
    run_dispatch,
)

__all__ = [
    "DispatchConfig",
    "auth_status",
    "estimate_dispatch",
    "harvest_chips",
    "load_dispatch_config",
    "run_dispatch",
    "summarize",
]
