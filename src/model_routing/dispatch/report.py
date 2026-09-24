"""Dispatch report: ``summarize(run_dir)`` -> ``summary.json`` + ``summary.md``.

Paired, task-clustered bootstrap comparisons for the pre-registered hypotheses
(see ``docs/experiments/dispatch-routing.md``).  Verdicts are one of
``supported`` / ``not supported`` / ``inconclusive``:

* non-inferior on pass rate  <=>  lower bound of the paired pass-rate delta
  (treatment - control, in points) exceeds ``-margin_pp``.
* a real saving  <=>  the 95% CI on the cost-saving fraction lies entirely
  above zero.
* ``supported``     = non-inferior AND a real saving.
* ``not supported`` = the CI shows the treatment is *clearly* worse: the upper
  bound of the pass-rate delta is below ``-margin_pp``, or the upper bound of
  the saving CI is below zero (a real cost increase).  A lower bound below the
  margin alone is not evidence of harm - it is too little data.
* ``inconclusive``  = everything else (too little data, or the CIs straddle
  the thresholds).

Alongside the intervals every comparison carries p-values so a reader can
apply their own threshold:

* ``p_saving``   - two-sided, task-clustered permutation (label-swap) test of
  the cost-per-completed-task saving under H0 "the two policies are
  exchangeable within a task".  Trials of one task swap together.
* ``p_pass``     - the same permutation test for the pass-rate delta.
* ``p_noninf``   - one-sided bootstrap p-value for H0 "treatment is worse
  than control by at least the margin" (share of bootstrap draws with
  delta <= -margin).  Small means non-inferiority is supported.
* ``p_adjusted`` - Holm step-down adjustment of ``p_saving`` across the
  secondary hypotheses (H-D2..H-D7), which are exploratory.  H-D1 is the
  single pre-registered primary comparison and is not adjusted.

A run is ``confirmatory`` only when ``meta.preregistration`` exists and the
task-set hash, trials, task count, margin and primary comparison all match
it and the run is not fake; otherwise it is ``exploratory`` and the summary
says which field deviated.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

HEADLINE_ROLES = ("worker", "router", "escalation")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open() as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _outcome_cost(o: dict[str, Any]) -> float:
    return float(o.get("cost_usd", 0.0))


def _percentile(values: list[float], q: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    frac = pos - lo
    return values[lo] * (1 - frac) + values[hi] * frac


def _paired_stats(
    treatment: dict[tuple[str, int], dict[str, Any]],
    control: dict[tuple[str, int], dict[str, Any]],
    keys: list[tuple[str, int]],
) -> tuple[float, float | None]:
    """(pass delta in points, saving fraction or None when undefined) over ``keys``."""
    n = len(keys)
    if not n:
        return 0.0, None
    t_passes = sum(bool(treatment[k]["passed"]) for k in keys)
    c_passes = sum(bool(control[k]["passed"]) for k in keys)
    delta_pp = (t_passes - c_passes) / n * 100
    if not (t_passes and c_passes):
        return delta_pp, None
    t_cpt = sum(_outcome_cost(treatment[k]) for k in keys) / t_passes
    c_cpt = sum(_outcome_cost(control[k]) for k in keys) / c_passes
    return delta_pp, (1 - t_cpt / c_cpt) if c_cpt else None


def _bootstrap(
    label: str,
    treatment: dict[tuple[str, int], dict[str, Any]],
    control: dict[tuple[str, int], dict[str, Any]],
    margin_pp: float = 5.0,
    draws: int = 2000,
) -> tuple[list[float], list[float], int, float | None]:
    """Task-clustered paired bootstrap.  Returns (delta_pass_ci_pp, saving_ci,
    n_task_clusters, p_noninferiority).  ``p_noninferiority`` is the share of
    draws in which treatment is worse than control by at least ``margin_pp``:
    a one-sided bootstrap p-value for the non-inferiority null."""
    keys = sorted(treatment.keys() & control.keys())
    tasks = sorted({k[0] for k in keys})
    if len(tasks) < 2:
        return [0.0, 0.0], [0.0, 0.0], len(tasks), None
    by_task = {t: [k for k in keys if k[0] == t] for t in tasks}
    seed = int.from_bytes(hashlib.sha256(label.encode()).digest()[:8])
    rng = random.Random(seed)
    pass_deltas: list[float] = []
    savings: list[float] = []
    for _ in range(draws):
        selected = [k for _ in tasks for k in by_task[rng.choice(tasks)]]
        if not selected:
            continue
        delta_pp, saving = _paired_stats(treatment, control, selected)
        pass_deltas.append(delta_pp)
        if saving is not None:
            savings.append(saving)
    pass_ci = [_percentile(pass_deltas, 0.025), _percentile(pass_deltas, 0.975)]
    saving_ci = (
        [_percentile(savings, 0.025), _percentile(savings, 0.975)] if savings else [0.0, 0.0]
    )
    p_noninf = sum(d <= -margin_pp for d in pass_deltas) / len(pass_deltas) if pass_deltas else None
    return pass_ci, saving_ci, len(tasks), p_noninf


def _permutation_p_values(
    label: str,
    treatment: dict[tuple[str, int], dict[str, Any]],
    control: dict[tuple[str, int], dict[str, Any]],
    draws: int = 2000,
) -> tuple[float | None, float | None]:
    """Task-clustered label-swap permutation test: (p_saving, p_pass), two-sided.

    Under H0 the two policies are exchangeable within a task, so swapping the
    treatment/control labels of every trial of a task (all of them together,
    to respect clustering) is as likely as not.  p = share of the 2^k
    relabellings (sampled) whose |statistic| is at least the observed one,
    with the observed labelling counted once (so p >= 1/(draws+1)).  The cost
    statistic is the *log* ratio of cost per completed task, which is
    antisymmetric under a full label swap; the saving fraction (1 - ratio) is
    not, and would make the two-sided test depend on which side is called
    treatment."""
    keys = sorted(treatment.keys() & control.keys())
    tasks = sorted({k[0] for k in keys})
    if len(tasks) < 2:
        return None, None
    by_task = {t: [k for k in keys if k[0] == t] for t in tasks}
    obs_delta, obs_saving = _paired_stats(treatment, control, keys)
    obs_log = _log_ratio(obs_saving)
    seed = int.from_bytes(hashlib.sha256((label + "|perm").encode()).digest()[:8])
    rng = random.Random(seed)
    ge_saving = 0
    n_saving = 0
    ge_pass = 0
    for _ in range(draws):
        flip = {t: rng.random() < 0.5 for t in tasks}
        t_side: dict[tuple[str, int], dict[str, Any]] = {}
        c_side: dict[tuple[str, int], dict[str, Any]] = {}
        for t, ks in by_task.items():
            for k in ks:
                if flip[t]:
                    t_side[k], c_side[k] = control[k], treatment[k]
                else:
                    t_side[k], c_side[k] = treatment[k], control[k]
        delta, saving = _paired_stats(t_side, c_side, keys)
        if abs(delta) >= abs(obs_delta) - 1e-12:
            ge_pass += 1
        perm_log = _log_ratio(saving)
        if obs_log is not None and perm_log is not None:
            n_saving += 1
            if abs(perm_log) >= abs(obs_log) - 1e-12:
                ge_saving += 1
    p_pass = (ge_pass + 1) / (draws + 1)
    p_saving = (ge_saving + 1) / (n_saving + 1) if obs_log is not None and n_saving else None
    return p_saving, p_pass


def _log_ratio(saving: float | None) -> float | None:
    """log(treatment cpt / control cpt) from a saving fraction; None when undefined."""
    if saving is None or saving >= 1.0:
        return None
    return math.log(1.0 - saving)


def holm_adjust(p_values: list[float | None]) -> list[float | None]:
    """Holm step-down adjusted p-values (family-wise error control).  ``None``
    entries (undefined tests) are left alone and not counted in the family."""
    idx = [i for i, p in enumerate(p_values) if p is not None]
    m = len(idx)
    out: list[float | None] = list(p_values)
    if not m:
        return out
    order = sorted(idx, key=lambda i: p_values[i])  # type: ignore[arg-type]
    running = 0.0
    for rank, i in enumerate(order):
        p = p_values[i]
        assert p is not None
        adjusted = min(1.0, (m - rank) * p)
        running = max(running, adjusted)
        out[i] = running
    return out


def _verdict(delta_pass_ci: list[float], saving_ci: list[float], margin_pp: float) -> str:
    non_inferior = delta_pass_ci[0] > -margin_pp
    clearly_inferior = delta_pass_ci[1] < -margin_pp
    real_saving = saving_ci[0] > 0
    real_cost_increase = saving_ci[1] < 0
    if non_inferior and real_saving:
        return "supported"
    if clearly_inferior or real_cost_increase:
        return "not supported"
    return "inconclusive"


def _sentence(
    treatment: str,
    control: str,
    delta_pass_pp: float,
    delta_pass_ci: list[float],
    saving: float,
    saving_ci: list[float],
    margin_pp: float,
    verdict: str,
) -> str:
    """One plain-English line.  ``saving`` and ``saving_ci`` are fractions (0.3 = 30%
    cheaper per completed task); the CI is re-oriented to match the wording."""
    lo, hi = saving_ci[0] * 100, saving_ci[1] * 100
    if saving >= 0:
        cost_clause = (
            f"cut cost per completed task by {saving * 100:.0f}% (95% CI {lo:.0f}% to {hi:.0f}%)"
        )
    else:
        cost_clause = (
            f"raised cost per completed task by {-saving * 100:.0f}% "
            f"(95% CI {-hi:.0f}% to {-lo:.0f}%)"
        )
    pass_clause = (
        f"changed pass rate by {delta_pass_pp:+.0f} pts "
        f"(95% CI {delta_pass_ci[0]:+.0f} to {delta_pass_ci[1]:+.0f})"
    )
    margin_clause = {
        "supported": f"non-inferior within {margin_pp:.0f} pts and a real saving → supported.",
        "not supported": (
            f"clearly worse by more than {margin_pp:.0f} pts or clearly more expensive"
            " → not supported."
        ),
        "inconclusive": "the intervals are too wide to call → inconclusive.",
    }[verdict]
    return f"{treatment} vs {control}: {cost_clause} and {pass_clause}; {margin_clause}"


def _policy_stats(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    passes = sum(bool(r["passed"]) for r in rows)
    total_cost = sum(_outcome_cost(r) for r in rows)
    router_cost = sum(float(r.get("router_cost_usd", 0.0)) for r in rows)
    setup_cost = sum(float(r.get("setup_cost_usd", 0.0)) for r in rows)
    escalations = sum(int(r.get("escalations", 0)) for r in rows)
    errors = sum(int(r.get("errors", 0)) for r in rows)
    fallbacks = sum(int(bool(r.get("router_fallback", False))) for r in rows)
    full_cost = sum(float(r.get("cost_usd_full", r.get("cost_usd", 0.0))) for r in rows)
    turns = [int(r.get("turns", 0)) for r in rows]
    by_diff: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    model_mix: dict[str, int] = defaultdict(int)
    for r in rows:
        by_diff[r.get("difficulty", "unknown")][0] += 1
        by_diff[r.get("difficulty", "unknown")][1] += int(bool(r["passed"]))
        cand = r.get("chosen_candidate")
        if cand:
            model_mix[cand] += 1
    pass_rate = passes / n if n else 0.0
    n_boot = _bootstrap_single_group(name, rows)
    cost_per_task = total_cost / n if n else 0.0
    cost_per_pass = total_cost / passes if passes else None
    cost_per_pass_ci = _cost_per_pass_ci(name, rows)
    return {
        "name": name,
        "n": n,
        "pass_rate": pass_rate,
        "pass_ci": n_boot,
        "cost_per_task": cost_per_task,
        "cost_per_pass": cost_per_pass,
        "cost_per_pass_ci": cost_per_pass_ci,
        "router_share": (router_cost / total_cost) if total_cost else 0.0,
        "escalation_rate": (escalations / n) if n else 0.0,
        "error_rate": (errors / n) if n else 0.0,
        "router_fallback_rate": (fallbacks / n) if n else 0.0,
        "cost_per_task_full": full_cost / n if n else 0.0,
        "mean_turns": statistics.fmean(turns) if turns else 0.0,
        "setup_cost_usd": setup_cost,
        "by_difficulty": {k: {"n": v[0], "passes": v[1]} for k, v in by_diff.items()},
        "model_mix": {k: v / n for k, v in model_mix.items()} if n else {},
    }


def _bootstrap_single_group(
    label: str, rows: list[dict[str, Any]], draws: int = 1000
) -> list[float]:
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_task[r["task_id"]].append(r)
    tasks = sorted(by_task)
    if len(tasks) < 2:
        rate = sum(bool(r["passed"]) for r in rows) / len(rows) if rows else 0.0
        return [rate, rate]
    seed = int.from_bytes(hashlib.sha256((label + "|pass").encode()).digest()[:8])
    rng = random.Random(seed)
    rates = []
    for _ in range(draws):
        selected = [r for t in tasks for r in by_task[rng.choice(tasks)]]
        n = len(selected)
        rates.append(sum(bool(r["passed"]) for r in selected) / n if n else 0.0)
    return [_percentile(rates, 0.025), _percentile(rates, 0.975)]


def _cost_per_pass_ci(
    label: str, rows: list[dict[str, Any]], draws: int = 1000
) -> list[float] | None:
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_task[r["task_id"]].append(r)
    tasks = sorted(by_task)
    if len(tasks) < 2:
        return None
    seed = int.from_bytes(hashlib.sha256((label + "|cpp").encode()).digest()[:8])
    rng = random.Random(seed)
    vals = []
    for _ in range(draws):
        selected = [r for t in tasks for r in by_task[rng.choice(tasks)]]
        passes = sum(bool(r["passed"]) for r in selected)
        if passes:
            vals.append(sum(_outcome_cost(r) for r in selected) / passes)
    if not vals:
        return None
    return [_percentile(vals, 0.025), _percentile(vals, 0.975)]


def _oracle_rows(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cheapest ``spawn_static`` candidate that passed, per (task, trial); computed, not run."""
    statics = [o for o in outcomes if o.get("policy", "").startswith("static")]
    by_cell: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for o in statics:
        by_cell[(o["task_id"], o["trial"])].append(o)
    rows = []
    for (task_id, trial), cell in by_cell.items():
        passing = [o for o in cell if o["passed"]]
        best = min(passing, key=_outcome_cost) if passing else None
        rows.append(
            {
                "task_id": task_id,
                "trial": trial,
                "policy": "oracle",
                "passed": best is not None,
                "cost_usd": _outcome_cost(best) if best else 0.0,
                "router_cost_usd": 0.0,
                "setup_cost_usd": 0.0,
                "escalations": 0,
                "turns": best.get("turns", 0) if best else 0,
                "difficulty": cell[0].get("difficulty", "unknown"),
                "chosen_candidate": best.get("chosen_candidate") if best else None,
            }
        )
    return rows


def _rough_power_note(
    n_tasks: int, n_paired: int, margin_pp: float, discordant_rate: float | None
) -> str:
    """Paired non-inferiority sizing (McNemar approximation, true difference 0):
    n ≈ (z_α + z_β)² · p_disc / δ², where p_disc is the share of task-trials on
    which the two policies disagree.  Uses the observed rate when there is one."""
    delta = margin_pp / 100
    if delta <= 0:
        return "margin_pp must be positive to size a run."
    z_alpha, z_beta = 1.96, 0.84  # one-sided 2.5% (matches the 95% CI), 80% power
    observed = discordant_rate is not None and discordant_rate > 0
    p_disc = discordant_rate if observed and discordant_rate is not None else 0.2
    n_needed = math.ceil((z_alpha + z_beta) ** 2 * p_disc / delta**2)
    source = f"observed discordance {p_disc:.0%}" if observed else "assumed discordance 20%"
    verdict = "enough" if n_paired >= n_needed else "too few"
    return (
        f"Primary comparison needs about {n_needed} paired task-trials to resolve a "
        f"{margin_pp:.0f}-pt margin at 95%/80% power ({source}); this run has {n_paired} "
        f"across {n_tasks} distinct tasks - {verdict}. Repeated trials of one task help less "
        "than new tasks because they are clustered. Treat 'inconclusive' at small n as "
        "expected, not as a null result."
    )


def _comparison(
    comp_id: str,
    treatment_name: str,
    control_name: str,
    by_policy_rows: dict[str, dict[tuple[str, int], dict[str, Any]]],
    margin_pp: float,
) -> dict[str, Any] | None:
    if treatment_name not in by_policy_rows or control_name not in by_policy_rows:
        return None
    t_rows = by_policy_rows[treatment_name]
    c_rows = by_policy_rows[control_name]
    if not t_rows or not c_rows:
        return None
    label = f"{comp_id}:{treatment_name}:{control_name}"
    pass_ci, saving_ci, clusters, p_noninf = _bootstrap(label, t_rows, c_rows, margin_pp)
    p_saving, p_pass = _permutation_p_values(label, t_rows, c_rows)
    verdict = _verdict(pass_ci, saving_ci, margin_pp) if clusters >= 2 else "inconclusive"
    keys = sorted(t_rows.keys() & c_rows.keys())
    t_pass = sum(bool(t_rows[k]["passed"]) for k in keys) / len(keys) if keys else 0.0
    c_pass = sum(bool(c_rows[k]["passed"]) for k in keys) / len(keys) if keys else 0.0
    t_passes = sum(bool(t_rows[k]["passed"]) for k in keys)
    c_passes = sum(bool(c_rows[k]["passed"]) for k in keys)
    t_cost = sum(_outcome_cost(t_rows[k]) for k in keys)
    c_cost = sum(_outcome_cost(c_rows[k]) for k in keys)
    saving = (
        1 - (t_cost / t_passes) / (c_cost / c_passes) if t_passes and c_passes and c_cost else 0.0
    )
    discordant = (
        sum(bool(t_rows[k]["passed"]) != bool(c_rows[k]["passed"]) for k in keys) / len(keys)
        if keys
        else 0.0
    )
    return {
        "id": comp_id,
        "treatment": treatment_name,
        "control": control_name,
        "n_paired": len(keys),
        "task_clusters": clusters,
        "delta_pass_pp": (t_pass - c_pass) * 100,
        "delta_pass_ci": pass_ci,
        "saving_pct": saving * 100,
        "saving_ci": [saving_ci[0] * 100, saving_ci[1] * 100],
        "discordant_rate": discordant,
        "p_saving": p_saving,
        "p_pass": p_pass,
        "p_noninf": p_noninf,
        "p_adjusted": None,
        "role": "primary" if comp_id == "H-D1" else "secondary (exploratory)",
        "verdict": verdict,
        "sentence": _sentence(
            treatment_name,
            control_name,
            (t_pass - c_pass) * 100,
            pass_ci,
            saving,
            saving_ci,
            margin_pp,
            verdict,
        ),
    }


def preregistration_check(meta: dict[str, Any]) -> dict[str, Any]:
    """Compare a run's ``meta.json`` with the ``[preregistration]`` table it was
    run with.  Returns ``{"confirmatory": bool, "registered": bool,
    "deviations": [...]}``.  Every deviation is a reason the run is exploratory."""
    reg = meta.get("preregistration")
    if not isinstance(reg, dict) or not reg:
        return {
            "confirmatory": False,
            "registered": False,
            "deviations": ["no [preregistration] table in the config"],
        }
    deviations: list[str] = []
    if meta.get("fake"):
        deviations.append("fake provider run")
    checks = [
        ("taskset_sha256", meta.get("taskset_sha256"), reg.get("taskset_sha256")),
        ("trials", meta.get("trials"), reg.get("trials")),
        ("margin_pp", meta.get("margin_pp"), reg.get("margin_pp")),
        ("primary", meta.get("primary"), reg.get("primary")),
        ("order", meta.get("order"), reg.get("order")),
    ]
    for name, actual, expected in checks:
        if expected is None:
            deviations.append(f"{name} not registered")
        elif actual != expected:
            deviations.append(f"{name}: run has {actual!r}, registered {expected!r}")
    n_reg = reg.get("n_tasks")
    n_run = meta.get("n_tasks")
    if n_reg is None:
        deviations.append("n_tasks not registered")
    elif n_run is None or int(n_run) < int(n_reg):
        deviations.append(f"n_tasks: run has {n_run!r}, registered at least {n_reg!r}")
    selected = {p.get("name") for p in meta.get("policies", []) if isinstance(p, dict)}
    primary = meta.get("primary") or {}
    for key in ("treatment", "control"):
        name = primary.get(key)
        if selected and name not in selected and name != "oracle":
            deviations.append(f"primary {key} {name!r} was not among the selected policies")
    return {"confirmatory": not deviations, "registered": True, "deviations": deviations}


def _set_aside(run_dir: Path, outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Cells redone because an account limit or a provider outage hit them
    (deviation 1 of the exp05 pre-registration), per policy and reason, and
    the list-price spend on attempts that no graded outcome uses.  Sources:
    ``pauses.jsonl`` (live pauses) and ``outcomes.poisoned.jsonl`` (cells
    graded by an older harness and set aside on ``--resume``)."""
    from model_routing.dispatch.agents import is_provider_outage

    by_policy: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"usage_limit": 0, "provider_outage": 0, "wasted_usd": 0.0}
    )
    for p in _load_jsonl(run_dir / "pauses.jsonl"):
        by_policy[p["policy"]][p.get("reason", "usage_limit")] += 1
    for o in _load_jsonl(run_dir / "outcomes.poisoned.jsonl"):
        errs = [s.get("error") for s in o.get("sessions", [])]
        reason = "provider_outage" if any(is_provider_outage(e) for e in errs) else "usage_limit"
        by_policy[o["policy"]][reason] += 1

    def key(s: dict[str, Any]) -> tuple[Any, ...]:
        fields = ("policy", "task_id", "trial", "role", "candidate", "session_id", "cost_usd_list")
        return tuple(s.get(k) for k in fields)

    used = {key(s) for o in outcomes for s in o.get("sessions", [])}
    for name in ("sessions.jsonl", "sessions.poisoned.jsonl"):
        for s in _load_jsonl(run_dir / name):
            if key(s) not in used:
                by_policy[s.get("policy", "?")]["wasted_usd"] += float(s.get("cost_usd_list", 0.0))
    rows = {k: dict(v) for k, v in sorted(by_policy.items())}
    return {
        "usage_limit": sum(v["usage_limit"] for v in rows.values()),
        "provider_outage": sum(v["provider_outage"] for v in rows.values()),
        "wasted_usd": sum(v["wasted_usd"] for v in rows.values()),
        "by_policy": rows,
    }


def summarize(run_dir: str | Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    meta: dict[str, Any] = {}
    if (run_dir / "meta.json").exists():
        meta = json.loads((run_dir / "meta.json").read_text())
    outcomes = _load_jsonl(run_dir / "outcomes.jsonl")

    by_policy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for o in outcomes:
        by_policy[o["policy"]].append(o)

    oracle_rows = _oracle_rows(outcomes)
    oracle_stats = _policy_stats("oracle", oracle_rows) if oracle_rows else None

    policy_stats = [_policy_stats(name, rows) for name, rows in sorted(by_policy.items())]

    by_policy_cells: dict[str, dict[tuple[str, int], dict[str, Any]]] = {
        name: {(o["task_id"], o["trial"]): o for o in rows} for name, rows in by_policy.items()
    }
    if oracle_rows:
        by_policy_cells["oracle"] = {(o["task_id"], o["trial"]): o for o in oracle_rows}

    margin_pp = float(meta.get("margin_pp", 5.0))
    primary = meta.get("primary", {"treatment": "C1", "control": "B"})

    comparisons: list[dict[str, Any]] = []
    specs = [
        ("H-D1", primary.get("treatment", "C1"), primary.get("control", "B")),
        # Each pair is (expected winner, other), so "supported" always means the
        # hypothesis in docs/experiments/dispatch-routing.md held.
        ("H-D2", "B", "A"),
        ("H-D3", "A", "A_switch"),
        ("H-D4", "D", "C1"),
        ("H-D5", "C1", "C2"),
        ("H-D6", "static_haiku", "static_haiku_terse"),
        ("H-D7", "oracle", primary.get("control", "B")),
    ]
    for comp_id, treatment, control in specs:
        comp = _comparison(comp_id, treatment, control, by_policy_cells, margin_pp)
        if comp is not None:
            comparisons.append(comp)
    # Pre-specified subgroup (2026-09-24): H-D1 restricted to tasks whose
    # *measured* difficulty is "medium" (the cheapest model passed some but not
    # all calibration trials) - where routing has headroom by construction.
    medium_cells = {
        name: {k: o for k, o in cells.items() if o.get("difficulty") == "medium"}
        for name, cells in by_policy_cells.items()
    }
    comp = _comparison(
        "H-D1-medium",
        primary.get("treatment", "C1"),
        primary.get("control", "B"),
        medium_cells,
        margin_pp,
    )
    if comp is not None:
        comp["role"] = "pre-specified subgroup (measured medium)"
        comparisons.append(comp)
    secondary = [c for c in comparisons if c["id"] not in ("H-D1", "H-D1-medium")]
    for c, adj in zip(secondary, holm_adjust([c["p_saving"] for c in secondary]), strict=True):
        c["p_adjusted"] = adj
    prereg = preregistration_check(meta)

    h_d1 = next((c for c in comparisons if c["id"] == "H-D1"), None)
    n_tasks = int(meta.get("n_tasks", 0))
    if h_d1 is not None:
        headline = h_d1["sentence"]
    else:
        headline = (
            f"Not enough data for a headline: need outcomes for both "
            f"{primary.get('treatment', 'C1')!r} and {primary.get('control', 'B')!r} "
            "(run more tasks/trials, or select those policies)."
        )

    summary = {
        "experiment": meta.get("experiment", run_dir.name),
        "run_dir": str(run_dir),
        "fake": bool(meta.get("fake", False)),
        "spent_usd": sum(_outcome_cost(o) for o in outcomes)
        + sum(float(o.get("setup_cost_usd", 0.0)) for o in outcomes),
        "n_tasks": n_tasks,
        "trials": int(meta.get("trials", 1)),
        "policies": policy_stats,
        "oracle": oracle_stats,
        "comparisons": comparisons,
        "headline": headline,
        "confirmatory": prereg["confirmatory"],
        "preregistration": prereg,
        "set_aside": _set_aside(run_dir, outcomes),
        "power_note": _rough_power_note(
            n_tasks,
            int(h_d1["n_paired"]) if h_d1 else 0,
            margin_pp,
            h_d1.get("discordant_rate") if h_d1 else None,
        )
        if n_tasks
        else "No task count in meta.json.",
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (run_dir / "summary.md").write_text(_render_markdown(summary))
    return summary


def _fmt_money(x: float | None) -> str:
    return "-" if x is None else f"${x:.4f}"


def _render_markdown(summary: dict[str, Any]) -> str:
    lines = [f"# {summary['experiment']}", ""]
    lines.append(f"**{summary['headline']}**")
    prereg = summary.get("preregistration") or {}
    status = (
        "confirmatory (matches the pre-registration)"
        if summary.get("confirmatory")
        else ("exploratory: " + "; ".join(prereg.get("deviations") or ["not pre-registered"]))
    )
    lines += [
        "",
        f"Run: `{summary['run_dir']}` · tasks: {summary['n_tasks']} · trials: {summary['trials']} "
        f"· fake: {summary['fake']} · total spend: {_fmt_money(summary['spent_usd'])}",
        "",
        f"Status: **{status}**",
        "",
        "## Policies",
        "",
        "| policy | n | pass rate (95% CI) | cost/task | cost/pass (95% CI) | router share | "
        "escalation rate | error rate | router fallback | mean turns | setup cost |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for p in summary["policies"]:
        ci = p.get("pass_ci") or [p["pass_rate"], p["pass_rate"]]
        cpp_ci = p.get("cost_per_pass_ci")
        cpp = _fmt_money(p["cost_per_pass"])
        if cpp_ci:
            cpp += f" ({_fmt_money(cpp_ci[0])}-{_fmt_money(cpp_ci[1])})"
        lines.append(
            f"| {p['name']} | {p['n']} | {p['pass_rate']:.0%} ({ci[0]:.0%}-{ci[1]:.0%}) | "
            f"{_fmt_money(p['cost_per_task'])} | {cpp} | {p['router_share']:.0%} | "
            f"{p['escalation_rate']:.2f} | {p.get('error_rate', 0.0):.2f} | "
            f"{p.get('router_fallback_rate', 0.0):.2f} | "
            f"{p['mean_turns']:.1f} | {_fmt_money(p['setup_cost_usd'])} |"
        )
    if summary.get("oracle"):
        o = summary["oracle"]
        lines.append(
            f"| oracle (computed) | {o['n']} | {o['pass_rate']:.0%} | "
            f"{_fmt_money(o['cost_per_task'])} | {_fmt_money(o['cost_per_pass'])} | - | - | - | - "
            "| - | - |"
        )
    lines += [
        "",
        "## Comparisons",
        "",
        "Intervals are 95% task-clustered bootstrap.  p_saving / p_pass are two-sided "
        "task-clustered permutation p-values; p_noninf is the one-sided bootstrap p-value for "
        "'worse by at least the margin'; p_adj is Holm-adjusted p_saving across the secondary "
        "(exploratory) hypotheses.  H-D1 is the only pre-registered comparison.",
        "",
        "| id | role | treatment | control | n paired | saving % (95% CI) | p_saving | p_adj | "
        "Δpass pts (95% CI) | p_pass | p_noninf | verdict |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for c in summary["comparisons"]:
        lines.append(
            f"| {c['id']} | {c['role']} | {c['treatment']} | {c['control']} | {c['n_paired']} | "
            f"{c['saving_pct']:.0f} ({c['saving_ci'][0]:.0f} to {c['saving_ci'][1]:.0f}) | "
            f"{_fmt_p(c['p_saving'])} | {_fmt_p(c['p_adjusted'])} | "
            f"{c['delta_pass_pp']:+.0f} ({c['delta_pass_ci'][0]:+.0f} to "
            f"{c['delta_pass_ci'][1]:+.0f}) | {_fmt_p(c['p_pass'])} | {_fmt_p(c['p_noninf'])} | "
            f"{c['verdict']} |"
        )
    lines += ["", "Plain-English readings:", ""]
    for c in summary["comparisons"]:
        lines.append(f"- {c['sentence']}")
    lines += ["", "## Power", "", summary.get("power_note", "")]
    sa = summary.get("set_aside") or {}
    if sa.get("by_policy"):
        lines += [
            "",
            "## Redone cells (usage limits, provider outages)",
            "",
            "Not graded: the cell was redone. Wasted = list-price spend on attempts no "
            "graded outcome uses.",
            "",
            "| policy | usage limit | provider outage | wasted |",
            "|---|---:|---:|---:|",
        ]
        for name, v in sa["by_policy"].items():
            lines.append(
                f"| {name} | {v['usage_limit']} | {v['provider_outage']} | "
                f"{_fmt_money(v['wasted_usd'])} |"
            )
    return "\n".join(lines) + "\n"


def _fmt_p(p: float | None) -> str:
    if p is None:
        return "-"
    return "<0.001" if p < 0.001 else f"{p:.3f}"
