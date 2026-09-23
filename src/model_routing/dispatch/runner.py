"""Dispatch runner: config loading, no-spend estimates, and the sequential executor.

See ``docs/experiments/dispatch-routing.md``.  This module owns ``DispatchConfig``,
``load_dispatch_config``, ``estimate_dispatch``, ``run_dispatch`` and ``auth_status``;
the actual policy logic (what sessions a policy issues, in what order) lives in
``model_routing.dispatch.policies`` and is invoked here per (task, trial, policy) cell.

Three sibling modules are owned by other workstreams and may not exist yet while this
is being built in parallel: ``agents`` (``AgentProvider`` implementations + auth check),
``sandbox`` (``Sandbox.create``) and ``grading`` (``grade_sandbox``).  Every reference to
them is a *lazy* import inside a function, and every place this module needs one of
their behaviours takes an injectable keyword-only override (``task_loader``,
``sandbox_factory``, ``grader``, ``agent_provider_factory``) so the runner is fully
testable with tiny in-test fakes before those modules land.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import platform
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from model_routing import __version__
from model_routing.auth import AuthConfig, parse_auth
from model_routing.dispatch import policies as policies_mod
from model_routing.dispatch.report import summarize
from model_routing.dispatch.types import (
    AgentResult,
    AgentTask,
    DispatchOutcome,
    GradeResult,
    Progress,
    SessionRecord,
)
from model_routing.pricing import PriceTable
from model_routing.types import Candidate, Usage


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class DispatchConfig:
    name: str
    tasks: Path
    candidates: dict[str, Candidate]
    policies: list[dict[str, Any]]
    parent: str
    menu: list[str]
    trials: int = 1
    order: str = "by_policy"
    hypothesis: str = ""
    primary: dict[str, str] = field(default_factory=lambda: {"treatment": "C1", "control": "B"})
    margin_pp: float = 5.0
    max_budget_per_session_usd: float = 2.0
    difficulties: tuple[str, ...] = ()
    """Restrict the task set to these human difficulty labels (calibration runs,
    e.g. "can the cheapest model already pass the hard tasks?").  Policies still
    never see the label; this only chooses which tasks run."""
    seed: int = 0
    """Seeds task sampling and, for ``order = "randomized"``, the per-block policy
    order.  Recorded in ``meta.json`` so a run can be reproduced exactly."""
    max_turns: int = 30
    """Turn cap passed to every agent session.  ``AgentTask.max_turns`` is a
    human guess and is *not* used: the 2026-09-22 pilot saw the cheapest model
    need 12-23 turns on tasks labelled 8-12, so a per-task cap would create
    failures unrelated to the model choice being measured."""
    preregistration: dict[str, Any] | None = None
    """The ``[preregistration]`` table, if any: what was frozen before the
    confirmatory run (``taskset_sha256``, ``n_tasks``, ``trials``, ``margin_pp``,
    ``primary``, ``registered_at``, ``doc``).  The report compares the run
    against it and only calls a run *confirmatory* when everything matches;
    see ``dispatch-preregister`` to produce the table."""
    auth: dict[str, AuthConfig] = field(default_factory=lambda: {"*": AuthConfig()})
    source: Path | None = None

    def auth_for(self, provider: str) -> AuthConfig:
        return self.auth.get(provider, self.auth["*"])

    def validate(self) -> None:
        if self.parent not in self.candidates:
            raise ValueError(f"parent {self.parent!r} is not a defined candidate")
        for m in self.menu:
            if m not in self.candidates:
                raise ValueError(f"menu entry {m!r} is not a defined candidate")
        names = [p["name"] for p in self.policies]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate policy names: {names}")
        valid_kinds = {
            "in_session",
            "spawn_static",
            "spawn_parent_pick",
            "spawn_parent_pick_inline",
            "spawn_classifier",
            "spawn_cascade",
        }
        if self.order not in ("by_policy", "by_task", "randomized"):
            raise ValueError(f"order must be by_policy | by_task | randomized, got {self.order!r}")
        if self.max_turns < 1:
            raise ValueError("max_turns must be >= 1")
        for p in self.policies:
            kind = p.get("kind")
            if kind not in valid_kinds:
                raise ValueError(f"policy {p['name']!r}: unknown kind {kind!r}")
            if "candidate" in p and p["candidate"] not in self.candidates:
                raise ValueError(f"policy {p['name']!r}: unknown candidate {p['candidate']!r}")
            if "switch_to" in p and p["switch_to"] not in self.candidates:
                raise ValueError(f"policy {p['name']!r}: unknown switch_to {p['switch_to']!r}")
            for c in p.get("chain", []):
                if c not in self.candidates:
                    raise ValueError(f"policy {p['name']!r}: unknown chain member {c!r}")
            classifier = p.get("classifier")
            if classifier and classifier != "heuristic" and classifier not in self.candidates:
                raise ValueError(f"policy {p['name']!r}: unknown classifier {classifier!r}")
        allowed_targets = set(names) | {"oracle"}
        for key in ("treatment", "control"):
            target = self.primary.get(key)
            if target not in allowed_targets:
                raise ValueError(f"primary.{key} {target!r} is not a policy name or 'oracle'")
        prices = PriceTable.load()
        missing = sorted({c.model for c in self.candidates.values() if prices.get(c.model) is None})
        if missing:
            raise ValueError(f"no price rows for candidate models: {missing}")


def load_dispatch_config(path: str | Path) -> DispatchConfig:
    import tomllib

    path = Path(path)
    data = tomllib.loads(path.read_text())
    exp = data["experiment"]
    candidates = {
        name: Candidate(
            name=name,
            provider=spec["provider"],
            model=spec["model"],
            effort=spec.get("effort"),
            extra={k: v for k, v in spec.items() if k not in ("provider", "model", "effort")},
        )
        for name, spec in data.get("candidates", {}).items()
    }
    tasks_path = Path(exp["tasks"])
    if not tasks_path.is_absolute():
        root = next(
            (p for p in path.resolve().parents if (p / "pyproject.toml").exists()), Path.cwd()
        )
        tasks_path = root / tasks_path
    cfg = DispatchConfig(
        name=exp["name"],
        tasks=tasks_path,
        candidates=candidates,
        policies=list(data.get("policies", [])),
        parent=str(exp["parent"]),
        menu=list(exp.get("menu", [])),
        trials=int(exp.get("trials", 1)),
        order=str(exp.get("order", "by_policy")),
        hypothesis=str(exp.get("hypothesis", "")),
        primary=dict(exp.get("primary", {"treatment": "C1", "control": "B"})),
        margin_pp=float(exp.get("margin_pp", 5.0)),
        max_budget_per_session_usd=float(exp.get("max_budget_per_session_usd", 2.0)),
        difficulties=tuple(str(d) for d in exp.get("difficulties", [])),
        seed=int(exp.get("seed", 0)),
        max_turns=int(exp.get("max_turns", 30)),
        preregistration=(
            dict(data["preregistration"]) if isinstance(data.get("preregistration"), dict) else None
        ),
        auth=parse_auth(data.get("auth", {})),
        source=path,
    )
    cfg.validate()
    return cfg


_TASKSET_IGNORED_DIRS = {"private", "__pycache__", ".pytest_cache", ".ruff_cache", ".git"}


def taskset_sha256(tasks_path: str | Path) -> str:
    """One hash over the whole task set: the JSONL plus every fixture, hidden test,
    setup/mutant/solution overlay under its directory (``private/`` and caches
    excluded).  Pre-registration freezes this value; the report refuses to call a
    run confirmatory if the task set changed after registration."""
    tasks_path = Path(tasks_path)
    root = tasks_path.parent
    h = hashlib.sha256()
    if not root.is_dir():
        if tasks_path.exists():
            h.update(tasks_path.read_bytes())
        return h.hexdigest()
    for f in sorted(root.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(root)
        if any(part in _TASKSET_IGNORED_DIRS for part in rel.parts):
            continue
        h.update(str(rel).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


# -- estimate (no spend) ----------------------------------------------------
# Typical agentic-session token profiles.  These are *assumptions*, not
# measurements: dispatch sessions run tools over several turns, so their token
# footprint is much larger than a single-shot call and depends on the task.
# ``estimate_dispatch`` states them explicitly in its ``assumptions`` list.
WORKER_USAGE = Usage(
    input_tokens=4000, cache_read=25000, cache_write=15000, output_tokens=3000, cache_write_1h=15000
)
SETUP_USAGE = Usage(input_tokens=1500, cache_write=1500, output_tokens=100, cache_write_1h=1500)
ROUTER_USAGE = Usage(input_tokens=900, cache_read=20000, output_tokens=150)
INLINE_ROUTER_USAGE = Usage(input_tokens=120, output_tokens=40)
"""Marginal tokens of an inline pick (menu + instruction in, one JSON line out)."""

MIN_OBSERVED_SESSIONS = 5
"""Below this many real sessions for a (model, role), the estimator keeps the
assumed profile rather than trusting a couple of outliers."""


@dataclass
class ObservedProfile:
    """Median / p90 token usage of real (non-fake) sessions for one (model, role)."""

    model: str
    role: str
    n: int
    median: Usage
    p90: Usage
    median_cost_usd: float


def _usage_quantile(usages: list[Usage], q: float) -> Usage:
    def quant(values: list[int]) -> int:
        values = sorted(values)
        if not values:
            return 0
        pos = (len(values) - 1) * q
        lo = int(pos)
        hi = min(lo + 1, len(values) - 1)
        return int(values[lo] + (values[hi] - values[lo]) * (pos - lo))

    return Usage(
        input_tokens=quant([u.input_tokens for u in usages]),
        cache_read=quant([u.cache_read for u in usages]),
        cache_write=quant([u.cache_write for u in usages]),
        output_tokens=quant([u.output_tokens for u in usages]),
        reasoning=quant([u.reasoning for u in usages]),
        cache_write_1h=quant([u.cache_write_1h for u in usages]),
    )


def observed_profiles(
    results_dir: str | Path | None = "results",
) -> dict[tuple[str, str], ObservedProfile]:
    """Scan every real dispatch run's ``sessions.jsonl`` under ``results_dir`` and
    return per-(model, role) token profiles.  Fake runs (``meta.fake``) and sessions
    that errored are skipped.  Returns ``{}`` when there is no history."""
    if results_dir is None:
        return {}
    root = Path(results_dir)
    if not root.is_dir():
        return {}
    by_key: dict[tuple[str, str], list[tuple[Usage, float]]] = {}
    for sessions in sorted(root.glob("*/*/sessions.jsonl")):
        run_dir = sessions.parent
        meta_path = run_dir / "meta.json"
        try:
            meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        except json.JSONDecodeError:
            continue
        if meta.get("fake") or run_dir.name.startswith("fake-"):
            continue
        with sessions.open() as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("error"):
                    continue
                u = rec.get("usage") or {}
                usage = Usage(
                    input_tokens=int(u.get("input_tokens", 0)),
                    cache_read=int(u.get("cache_read", 0)),
                    cache_write=int(u.get("cache_write", 0)),
                    output_tokens=int(u.get("output_tokens", 0)),
                    reasoning=int(u.get("reasoning", 0)),
                    cache_write_1h=int(u.get("cache_write_1h", 0)),
                )
                if usage.prompt_tokens == 0 and usage.output_tokens == 0:
                    continue
                key = (str(rec.get("model", "")), str(rec.get("role", "")))
                by_key.setdefault(key, []).append((usage, float(rec.get("cost_usd_list", 0.0))))
    out: dict[tuple[str, str], ObservedProfile] = {}
    for (model, role), rows in by_key.items():
        usages = [u for u, _ in rows]
        out[(model, role)] = ObservedProfile(
            model=model,
            role=role,
            n=len(rows),
            median=_usage_quantile(usages, 0.5),
            p90=_usage_quantile(usages, 0.9),
            median_cost_usd=statistics.median(c for _, c in rows),
        )
    return out


def _scale_usage(u: Usage, scale: float) -> Usage:
    return Usage(
        input_tokens=int(u.input_tokens * scale),
        cache_read=int(u.cache_read * scale),
        cache_write=int(u.cache_write * scale),
        output_tokens=int(u.output_tokens * scale),
        reasoning=int(u.reasoning * scale),
        cache_write_1h=int(u.cache_write_1h * scale),
    )


def _select_policies(cfg: DispatchConfig, policies: list[str] | None) -> list[dict[str, Any]]:
    if not policies:
        return list(cfg.policies)
    by_name = {p["name"]: p for p in cfg.policies}
    missing = [n for n in policies if n not in by_name]
    if missing:
        raise ValueError(f"unknown policies: {missing}")
    return [by_name[n] for n in policies]


def _select_tasks(
    cfg: DispatchConfig, loader: Callable[..., list[Any]], sample: int | None
) -> list[Any]:
    if not cfg.difficulties:
        return loader(cfg.tasks, sample=sample, seed=cfg.seed)
    tasks = [
        t for t in loader(cfg.tasks, sample=None, seed=cfg.seed) if t.difficulty in cfg.difficulties
    ]
    return tasks[:sample] if sample else tasks


def _estimate_task_count(
    cfg: DispatchConfig, sample: int | None, task_loader: Callable[..., list[Any]] | None
) -> int:
    if sample and not cfg.difficulties:
        return sample
    loader = task_loader
    if loader is None:
        try:
            from model_routing.dispatch.tasks import load_agent_tasks as loader
        except ImportError:
            loader = None
    if loader is not None:
        try:
            tasks = _select_tasks(cfg, loader, sample)
            return len(tasks)
        except Exception:
            pass
    if cfg.tasks.exists():
        n = sum(1 for line in cfg.tasks.open() if line.strip())
        if n:
            return n
    return 1


_ASSUMED_ROLE_PROFILE = {"worker": WORKER_USAGE, "setup": SETUP_USAGE, "router": ROUTER_USAGE}


def _policy_estimate(
    cfg: DispatchConfig,
    spec: dict[str, Any],
    prices: PriceTable,
    observed: dict[tuple[str, str], ObservedProfile] | None = None,
) -> tuple[float, float, float, int]:
    """(low, mid, high, sessions) for one policy.  When ``observed`` has at least
    ``MIN_OBSERVED_SESSIONS`` real sessions for a (model, role), mid uses the
    observed median and high the observed p90; otherwise the assumed profile is
    scaled by 1.0x / 1.8x.  Low is always 0.6x of mid."""
    observed = observed or {}

    def cost(cand_name: str, scale: float, profile: Usage) -> float:
        cand = cfg.candidates[cand_name]
        price = prices.get(cand.model)
        if price is None:
            return 0.0
        role = next((r for r, p in _ASSUMED_ROLE_PROFILE.items() if p is profile), None)
        obs = observed.get((cand.model, role)) if role else None
        if obs is not None and obs.n >= MIN_OBSERVED_SESSIONS:
            if scale <= 0.6:
                return price.cost(obs.median) * 0.6
            if scale >= 1.8:
                return price.cost(obs.p90)
            return price.cost(obs.median)
        return price.cost(_scale_usage(profile, scale))

    kind = spec["kind"]
    if kind == "in_session":
        worker_cand = spec.get("switch_to", cfg.parent)

        def total(scale: float) -> float:
            return cost(cfg.parent, scale, SETUP_USAGE) + cost(worker_cand, scale, WORKER_USAGE)

        return total(0.6), total(1.0), total(1.8), 2
    if kind == "spawn_static":
        cand_name = spec["candidate"]

        def total(scale: float) -> float:
            return cost(cand_name, scale, WORKER_USAGE)

        return total(0.6), total(1.0), total(1.8), 1
    if kind == "spawn_parent_pick":
        picked_guess = cfg.menu[0] if cfg.menu else cfg.parent

        def total(scale: float) -> float:
            return (
                cost(cfg.parent, scale, SETUP_USAGE)
                + cost(cfg.parent, scale, ROUTER_USAGE)
                + cost(picked_guess, scale, WORKER_USAGE)
            )

        return total(0.6), total(1.0), total(1.8), 3
    if kind == "spawn_parent_pick_inline":
        picked_guess = cfg.menu[0] if cfg.menu else cfg.parent

        def total(scale: float) -> float:
            return (
                cost(cfg.parent, scale, SETUP_USAGE)
                + cost(cfg.parent, scale, INLINE_ROUTER_USAGE)
                + cost(picked_guess, scale, WORKER_USAGE)
            )

        return total(0.6), total(1.0), total(1.8), 3
    if kind == "spawn_classifier":
        classifier = spec.get("classifier", "heuristic")
        picked_guess = cfg.menu[0] if cfg.menu else cfg.parent

        def total(scale: float) -> float:
            router_cost = (
                0.0 if classifier == "heuristic" else cost(classifier, scale, ROUTER_USAGE)
            )
            return router_cost + cost(picked_guess, scale, WORKER_USAGE)

        sessions = 1 if classifier == "heuristic" else 2
        return total(0.6), total(1.0), total(1.8), sessions
    if kind == "spawn_cascade":
        chain = spec.get("chain") or [cfg.parent]
        low = cost(chain[0], 0.6, WORKER_USAGE)
        half = chain[: max(1, len(chain) // 2 + 1)]
        mid = sum(cost(c, 1.0, WORKER_USAGE) for c in half)
        high = sum(cost(c, 1.8, WORKER_USAGE) for c in chain)
        return low, mid, high, len(chain)
    raise ValueError(f"unknown policy kind {kind!r}")


def estimate_dispatch(
    cfg: DispatchConfig,
    *,
    sample: int | None = None,
    trials: int | None = None,
    policies: list[str] | None = None,
    task_loader: Callable[..., list[Any]] | None = None,
    history_dir: str | Path | None = "results",
) -> dict[str, Any]:
    """No-spend estimate.  ``history_dir`` (default ``results/``) supplies observed
    per-(model, role) token profiles from earlier real runs; pass ``None`` to use
    the assumed profiles only.  The ``assumptions`` list says which was used."""
    prices = PriceTable.load()
    run_trials = trials or cfg.trials
    selected = _select_policies(cfg, policies)
    n_tasks = _estimate_task_count(cfg, sample, task_loader)
    cells = n_tasks * run_trials * len(selected)
    observed = observed_profiles(history_dir)
    usd_low = usd_mid = usd_high = 0.0
    sessions = 0
    by_policy: dict[str, float] = {}
    for spec in selected:
        low, mid, high, sess = _policy_estimate(cfg, spec, prices, observed)
        n = n_tasks * run_trials
        usd_low += low * n
        usd_mid += mid * n
        usd_high += high * n
        sessions += sess * n
        by_policy[spec["name"]] = mid * n
    polic_word = "y" if len(selected) == 1 else "ies"
    used_models = {c.model for name, c in cfg.candidates.items()}
    calibrated = sorted(
        f"{m}/{r} (n={p.n}, median ${p.median_cost_usd:.3f})"
        for (m, r), p in observed.items()
        if m in used_models and p.n >= MIN_OBSERVED_SESSIONS
    )
    assumptions = [
        f"{n_tasks} task(s) x {run_trials} trial(s) x {len(selected)} selected polic{polic_word}.",
        (
            "Observed token profiles from earlier real runs used for: "
            + "; ".join(calibrated)
            + ". mid = observed median session, high = observed p90, low = 0.6x median."
            if calibrated
            else "No observed history for these models (or fewer than "
            f"{MIN_OBSERVED_SESSIONS} sessions): using the assumed profiles below."
        ),
        "Assumed agentic worker-session token profile where no history exists: "
        f"input={WORKER_USAGE.input_tokens}, cache_read={WORKER_USAGE.cache_read}, "
        f"cache_write={WORKER_USAGE.cache_write}, output={WORKER_USAGE.output_tokens} tokens; "
        "router/setup sessions use a much smaller, mostly-cached profile.",
        "Without history, low/mid/high = 0.6x / 1.0x / 1.8x of the mid profile.",
        "C1_inline bills only the marginal tokens of the pick (menu + one JSON line); "
        "the brief-writing turn it rides on is recorded but not billed.",
        "Policy D (cascade): low assumes the cheapest model always passes, mid assumes about half "
        "the chain escalates, high assumes every task escalates through the whole chain.",
        "Router/classifier calls are billed as role=router; a 'heuristic' classifier is free "
        "(no call).",
        "Parent-seeding (role=setup) sessions are counted in spend here but excluded from the "
        "cost-per-completed-task headline metric.",
        "No calls are made to produce this estimate.",
    ]
    return {
        "cells": cells,
        "sessions": sessions,
        "usd_low": usd_low,
        "usd_mid": usd_mid,
        "usd_high": usd_high,
        "by_policy": by_policy,
        "assumptions": assumptions,
    }


# -- run (spends, sequentially) ---------------------------------------------


class _FakeAgentProvider:
    """Deterministic no-spend stand-in used when ``fake=True`` and no
    ``agent_provider_factory`` is injected.  Tests should prefer writing their own
    tiny fake (see module docstring); this exists so ``--fake`` CLI runs and
    ``make dispatch-sim`` work without depending on ``dispatch.agents``."""

    name = "fake"

    def run(
        self,
        model: str,
        prompt: str,
        *,
        workdir: Path,
        system: str | None = None,
        effort: str | None = None,
        max_turns: int = 30,
        resume_session: str | None = None,
        fork: bool = False,
        tools: bool = True,
        max_budget_usd: float = 2.0,
        timeout_s: int = 1200,
    ) -> AgentResult:
        n = max(len(prompt), 1)
        usage = Usage(
            input_tokens=max(n // 4, 50),
            cache_read=800 if resume_session else 0,
            cache_write=0 if resume_session else 300,
            output_tokens=max(n // 8, 30),
        )
        session_id = (
            resume_session if (resume_session and not fork) else f"fake-{uuid.uuid4().hex[:12]}"
        )
        eff = effort or "default"
        return AgentResult(
            output=f'{{"candidate": "{model}", "effort": "{eff}", "reason": "fake"}}',
            usage=usage,
            duration_ms=5,
            num_turns=1,
            tool_calls=1 if tools else 0,
            session_id=session_id,
            resolved_model=model,
            cost_usd_reported=None,
        )


def _with_harness_python(env: dict[str, str] | None) -> dict[str, str]:
    """Put this interpreter's bin dir first on the agents' PATH.

    Fixture repos are tested with pytest, which lives in the harness venv; the
    system ``python3`` usually lacks it and ``python`` is often only a shell
    alias.  Without this, every agent burns turns discovering how to run the
    tests - a cost unrelated to the model choice being measured.
    """
    env = dict(os.environ if env is None else env)
    bin_dir = str(Path(sys.executable).parent)
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    return env


def _fake_provider_factory(name: str, env: dict[str, str] | None = None) -> Any:
    """Prefer the tiered fake in ``agents`` (applies ``.fake_solution`` overlays so
    simulated pass rates vary by model); fall back to the minimal in-module fake."""
    try:
        from model_routing.dispatch.agents import make_agent_provider
    except ImportError:
        return _FakeAgentProvider()
    return make_agent_provider("fake", env=env)


def _real_provider_factory(name: str, env: dict[str, str] | None = None) -> Any:
    from model_routing.dispatch.agents import make_agent_provider

    return make_agent_provider(name, env=env)


def _tool_version(binary: str) -> str | None:
    exe = {"claude_cli": "claude", "codex_cli": "codex"}.get(binary, binary)
    if not shutil.which(exe):
        return None
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=20)
        return out.stdout.strip().splitlines()[0] if out.stdout else None
    except (subprocess.SubprocessError, OSError):
        return None


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10
        )
        sha = out.stdout.strip()
        return sha or None
    except (subprocess.SubprocessError, OSError):
        return None


def _menu_text(cfg: DispatchConfig, prices: PriceTable) -> str:
    parent_price = prices.get(cfg.candidates[cfg.parent].model)
    parent_in = parent_price.input if parent_price else None
    lines = []
    for name in cfg.menu:
        cand = cfg.candidates[name]
        price = prices.get(cand.model)
        rel = f"{price.input / parent_in:.2f}x" if price and parent_in else "?"
        effort = f", effort={cand.effort}" if cand.effort else ""
        lines.append(f"- {name} (relative input price {rel}{effort})")
    return "\n".join(lines)


def _build_plan(
    order: str,
    selected: list[dict[str, Any]],
    tasks: list[AgentTask],
    trials: int,
    seed: int = 0,
) -> list[tuple[dict[str, Any], AgentTask, int]]:
    """``by_policy``: every cell of policy 1, then policy 2, ... (cheap to reason
    about, but confounds policy with clock time and provider drift).  ``by_task``:
    every policy for task 1, then task 2, ... in config order.  ``randomized``:
    like ``by_task`` but each (task, trial) block runs its policies in a
    seeded random order - a randomized block design, so no policy is
    systematically first or last.  Sessions are still strictly sequential."""
    plan: list[tuple[dict[str, Any], AgentTask, int]] = []
    if order in ("by_task", "randomized"):
        for trial in range(trials):
            for task in tasks:
                block = list(selected)
                if order == "randomized":
                    random.Random(f"{seed}:{task.id}:{trial}").shuffle(block)
                for spec in block:
                    plan.append((spec, task, trial))
    else:
        for spec in selected:
            for trial in range(trials):
                for task in tasks:
                    plan.append((spec, task, trial))
    return plan


def _safe_cleanup(sandbox: Any) -> None:
    with contextlib.suppress(Exception):
        sandbox.cleanup()


def _noop_cleanup(sandboxes: list[Any]) -> None:
    return None


def _cleanup_all(sandboxes: list[Any]) -> None:
    for sandbox in sandboxes:
        _safe_cleanup(sandbox)


def _write_meta(
    cfg: DispatchConfig,
    out_dir: Path,
    tasks: list[AgentTask],
    selected: list[dict[str, Any]],
    trials: int,
    budget_usd: float,
    fake: bool,
    sample: int | None,
) -> None:
    if cfg.source and cfg.source.exists():
        shutil.copy(cfg.source, out_dir / "config.toml")
    meta = {
        "experiment": cfg.name,
        "hypothesis": cfg.hypothesis,
        "primary": cfg.primary,
        "margin_pp": cfg.margin_pp,
        "started_at": datetime.now(UTC).isoformat(),
        "harness_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_sha": _git_sha(),
        "config_sha256": (
            hashlib.sha256(cfg.source.read_bytes()).hexdigest()
            if cfg.source and cfg.source.exists()
            else None
        ),
        "tasks": str(cfg.tasks),
        "taskset_sha256": taskset_sha256(cfg.tasks),
        "n_tasks": len(tasks),
        "trials": trials,
        "order": cfg.order,
        "seed": cfg.seed,
        "max_turns": cfg.max_turns,
        "preregistration": cfg.preregistration,
        "sample": sample,
        "budget_usd": budget_usd,
        "fake": fake,
        "parent": cfg.parent,
        "menu": cfg.menu,
        "candidates": {k: vars(v) for k, v in cfg.candidates.items()},
        "policies": selected,
        "task_manifest": [
            {"id": t.id, "title": t.title, "difficulty": t.difficulty, "category": t.category}
            for t in tasks
        ],
        "cli_versions": {name: _tool_version(name) for name in ("claude_cli", "codex_cli")},
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, default=str))


def run_dispatch(
    cfg: DispatchConfig,
    *,
    out_dir: Path,
    budget_usd: float,
    sample: int | None = None,
    trials: int | None = None,
    policies: list[str] | None = None,
    fake: bool = False,
    progress: Callable[[Progress], None] | None = None,
    cancel: threading.Event | None = None,
    task_loader: Callable[..., list[AgentTask]] | None = None,
    sandbox_factory: Callable[..., Any] | None = None,
    grader: Callable[[AgentTask, Any], GradeResult] | None = None,
    agent_provider_factory: Callable[[str, dict[str, str] | None], Any] | None = None,
    keep_sandboxes: bool = False,
    verbose: bool = True,
) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sandboxes").mkdir(parents=True, exist_ok=True)
    prices = PriceTable.load()
    selected_policies = _select_policies(cfg, policies)
    run_trials = trials or cfg.trials

    task_loader_fn: Callable[..., list[AgentTask]]
    if task_loader is not None:
        task_loader_fn = task_loader
    else:
        from model_routing.dispatch.tasks import load_agent_tasks as task_loader_fn
    loaded_tasks: list[AgentTask] = _select_tasks(cfg, task_loader_fn, sample)
    if not loaded_tasks:
        raise ValueError("no tasks loaded")

    sandbox_factory_fn: Callable[..., Any]
    if sandbox_factory is not None:
        sandbox_factory_fn = sandbox_factory
    else:
        from model_routing.dispatch.sandbox import Sandbox

        sandbox_factory_fn = Sandbox.create

    grader_fn: Callable[[AgentTask, Any], GradeResult]
    if grader is not None:
        grader_fn = grader
    else:
        from model_routing.dispatch.grading import grade_sandbox

        grader_fn = grade_sandbox

    provider_factory_fn: Callable[[str, dict[str, str] | None], Any]
    if agent_provider_factory is not None:
        provider_factory_fn = agent_provider_factory
    elif fake:
        provider_factory_fn = _fake_provider_factory
    else:
        provider_factory_fn = _real_provider_factory

    provider_cache: dict[str, Any] = {}

    def provider_for(candidate_name: str) -> Any:
        cand = cfg.candidates[candidate_name]
        if cand.provider not in provider_cache:
            env = _with_harness_python(cfg.auth_for(cand.provider).child_env(cand.provider))
            provider_cache[cand.provider] = provider_factory_fn(cand.provider, env)
        return provider_cache[cand.provider]

    menu_text = _menu_text(cfg, prices)
    _write_meta(cfg, out_dir, loaded_tasks, selected_policies, run_trials, budget_usd, fake, sample)

    sessions_fh = (out_dir / "sessions.jsonl").open("a")
    outcomes_fh = (out_dir / "outcomes.jsonl").open("a")

    state = {"spent_usd": 0.0, "seq": 0}
    # The Claude CLI's ``total_cost_usd`` is cumulative across a resumed (even
    # forked) session: a router call resumed from a $0.086 setup reports
    # $0.169 for its own $0.083.  Track each session id's cumulative figure so
    # every SessionRecord carries only its own reported cost.
    reported_cumulative: dict[str, float] = {}
    total_cells = len(selected_policies) * run_trials * len(loaded_tasks)
    done_cells = 0
    run_state = "running"
    stop_message = ""

    def emit_progress(current: str, message: str = "") -> None:
        if progress is None:
            return
        progress(
            Progress(
                run_dir=str(out_dir),
                state=run_state,  # type: ignore[arg-type]
                total=total_cells,
                done=done_cells,
                spent_usd=state["spent_usd"],
                budget_usd=budget_usd,
                current=current,
                message=message,
            )
        )

    def make_run_session(
        policy_name: str, trial: int, task_id: str
    ) -> Callable[..., SessionRecord]:
        def run_session(
            candidate: str,
            *,
            role: str,
            prompt: str,
            workdir: Path,
            system: str | None = None,
            resume_session: str | None = None,
            fork: bool = False,
            tools: bool = True,
            resumed_from: str | None = None,
            max_turns: int | None = None,
            bill: Callable[[AgentResult], Usage] | None = None,
        ) -> SessionRecord:
            """``bill`` maps the finished call to the usage actually charged to the
            task (inline router: only the marginal pick tokens); the full usage and
            list cost are always recorded alongside it."""
            # Simulated spend is list price of made-up tokens; a budget cannot bind it.
            if not fake and state["spent_usd"] >= budget_usd:
                raise BudgetExceeded(
                    f"budget exhausted (${state['spent_usd']:.4f} >= ${budget_usd:.2f})"
                )
            cand = cfg.candidates[candidate]
            provider = provider_for(candidate)
            state["seq"] += 1
            started = time.time()
            result: AgentResult = provider.run(
                cand.model,
                prompt,
                workdir=workdir,
                system=system,
                effort=cand.effort,
                max_turns=max_turns or cfg.max_turns,
                resume_session=resume_session,
                fork=fork,
                tools=tools,
                max_budget_usd=cfg.max_budget_per_session_usd,
                timeout_s=1200,
            )
            price_model = (
                result.resolved_model
                if result.resolved_model and prices.get(result.resolved_model)
                else cand.model
            )
            reported = result.cost_usd_reported
            if reported is not None:
                prior = reported_cumulative.get(resume_session or "", 0.0)
                if result.session_id:
                    reported_cumulative[result.session_id] = reported
                reported = max(0.0, reported - prior)
            cost = prices.cost(price_model, result.usage) if prices.get(price_model) else 0.0
            if cost == 0.0 and reported:
                # The Claude CLI zeroes ``usage`` on a budget-capped result while
                # still reporting dollars; never price a paid session at $0.
                cost = reported
            billed: float | None = None
            if bill is not None:
                billed_usage = bill(result)
                billed = prices.cost(price_model, billed_usage) if prices.get(price_model) else 0.0
                billed = min(billed, cost) if cost else billed
            rec = SessionRecord(
                task_id=task_id,
                policy=policy_name,
                trial=trial,
                role=role,  # type: ignore[arg-type]
                candidate=candidate,
                provider=cand.provider,
                model=cand.model,
                effort=cand.effort,
                usage=result.usage,
                cost_usd_list=cost,
                duration_ms=result.duration_ms,
                num_turns=result.num_turns,
                tool_calls=result.tool_calls,
                session_id=result.session_id,
                resumed_from=resumed_from,
                cost_usd_reported=reported,
                resolved_model=result.resolved_model,
                error=result.error,
                output=result.output,
                seq=state["seq"],
                started_at=started,
                raw=result.raw,
                cost_usd_billed=billed,
            )
            sessions_fh.write(json.dumps(rec.to_dict(), default=str) + "\n")
            sessions_fh.flush()
            state["spent_usd"] += cost
            if verbose:
                print(
                    f"  [{state['seq']:4d}] {task_id:<20} {policy_name:<16} {role:<10} "
                    f"{candidate:<12} ${cost:.4f} {rec.duration_ms}ms"
                    + (f" ERROR: {rec.error[:60]}" if rec.error else "")
                )
            emit_progress(f"{task_id} · {policy_name} · trial {trial} · {role}({candidate})")
            if not fake and state["spent_usd"] > budget_usd:
                raise BudgetExceeded(f"spent ${state['spent_usd']:.4f} > budget ${budget_usd:.2f}")
            return rec

        return run_session

    def run_visible_checker(
        task: AgentTask, sandbox: Any, mode: str = "visible"
    ) -> tuple[bool, str]:
        """Checker policy D escalates on.  Never shows hidden tests to the agent.

        ``visible`` (deployable): something in scope changed, nothing out of
        scope changed, and the visible suite passes.  The visible suite passes
        on the untouched repo by design, so the diff checks are what catch an
        agent that gave up.  ``hidden`` (upper bound, not deployable): grade a
        throwaway copy of the sandbox with the hidden tests - a perfect checker.
        """
        from model_routing.dispatch import grading
        from model_routing.dispatch.sandbox import Sandbox

        if mode == "hidden":
            with tempfile.TemporaryDirectory() as tmp:
                copy = Path(tmp) / "sandbox"
                shutil.copytree(sandbox.path, copy, symlinks=True)
                g = grading.grade_sandbox(task, Sandbox(task=task, path=copy))
            return g.passed, "The previous attempt did not pass the checks."
        try:
            changed: list[str] | None = grading.changed_files(sandbox.path)
        except (subprocess.CalledProcessError, OSError):
            changed = None  # not a git sandbox (injected test fixtures): skip diff checks
        if changed is not None:
            if not changed:
                return False, "No files were changed; the task is not done."
            allowed = task.grader.get("allowed_paths") or ["*"]
            if not grading.check_scope(changed, allowed):
                return False, f"Files changed outside the allowed scope: {', '.join(changed)}"
        cmd = task.grader.get("visible_cmd") or grading.default_visible_cmd()
        return grading.run_cmd(list(cmd), Path(sandbox.path), 300)

    outcomes: list[DispatchOutcome] = []
    try:
        plan = _build_plan(cfg.order, selected_policies, loaded_tasks, run_trials, cfg.seed)
        for policy_spec, task, trial in plan:
            if cancel is not None and cancel.is_set():
                run_state = "cancelled"
                stop_message = "cancelled"
                break
            emit_progress(f"{task.id} · {policy_spec['name']} · trial {trial}", "starting")
            cell_ctx = policies_mod.PolicyRunContext(
                cfg=cfg,
                run_session=make_run_session(policy_spec["name"], trial, task.id),
                new_sandbox=lambda t, sf=sandbox_factory_fn: sf(
                    t, out_dir / "sandboxes", simulate=fake
                ),
                grade=lambda t, sb, g=grader_fn: g(t, sb),
                run_visible_checker=run_visible_checker,
                menu_text=menu_text,
                cleanup=_noop_cleanup if keep_sandboxes else _cleanup_all,
            )
            outcome = policies_mod.run_policy(policy_spec, task, trial, cell_ctx)
            done_cells += 1
            outcomes.append(outcome)
            outcomes_fh.write(json.dumps(outcome.to_dict(), default=str) + "\n")
            outcomes_fh.flush()
            if verbose:
                mark = "PASS" if outcome.passed else "FAIL"
                print(
                    f"  {mark} {outcome.policy}/{outcome.task_id} trial {outcome.trial} "
                    f"(${outcome.cost_usd:.4f})"
                )
    except BudgetExceeded as e:
        run_state = "over_budget"
        stop_message = str(e)
        if verbose:
            print(f"STOPPED: {e}")
    except Exception as e:
        # Still leave a summary of whatever finished; the web app expects one.
        sessions_fh.close()
        outcomes_fh.close()
        run_state = "failed"
        emit_progress("", f"{type(e).__name__}: {e}")
        summarize(out_dir)
        raise
    finally:
        sessions_fh.close()
        outcomes_fh.close()

    if run_state == "running":
        run_state = "done"
    emit_progress("", stop_message)

    summarize(out_dir)
    return out_dir


def auth_status() -> dict[str, dict[str, Any]]:
    """Keyed by track (``claude`` / ``codex``) as documented in ``dispatch.api``."""
    result: dict[str, dict[str, Any]] = {}
    for track, name in (("claude", "claude_cli"), ("codex", "codex_cli")):
        try:
            from model_routing.dispatch.agents import auth_check

            result[track] = auth_check(name)
        except Exception as e:
            result[track] = {
                "installed": False,
                "logged_in": None,
                "detail": f"dispatch.agents not available yet: {e}",
            }
    return result
