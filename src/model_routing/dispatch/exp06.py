"""exp06 analysis: Stage 0 labels and the H0 gate, the ladder arms against the
static arms by stratum, computed arms, and escalation quality.

    uv run python -m model_routing.dispatch.exp06 \\
        --calibration results/exp06_calibrate/<stamp> \\
        --ladder results/exp06_ladder/<stamp> --out results/exp06_analysis.md

Definitions follow ``docs/paper/exp06-route-on-evidence.md`` (sections 3, 7.1,
7.2, 7.4, 7.5).  The static arms come from the calibration run(s); every
number is recomputed from ``outcomes.jsonl``.  Intervals are 95% task-clustered
bootstrap intervals (all trials of a task resampled together, 2,000 draws,
fixed seed).
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

MID = "static_sonnet"
FRONTIER = "static_opus"
STATIC_ARMS = (MID, FRONTIER)
DRAWS = 2000
SEED = 20260929
MARGIN_PP = 10.0
EASY_COST_BOUND = 1.5

Cell = dict[str, Any]
Cells = dict[str, dict[tuple[str, int], Cell]]


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def _capped(session: dict[str, Any]) -> bool:
    return "maximum number of turns" in str(session.get("error") or "").lower()


def _cell(o: dict[str, Any]) -> Cell:
    sessions = o.get("sessions") or []
    headline = [s for s in sessions if s.get("role") in ("worker", "router", "escalation")]
    advisor_calls = sum(int((s.get("raw") or {}).get("advisor_calls") or 0) for s in headline)
    advisor_cost = sum(
        float((s.get("raw") or {}).get("other_model_cost_usd") or 0.0) for s in headline
    )
    events = o.get("cascade_checks") or []
    first_worker = next((e for e in events if e.get("event") == "worker"), None)
    handoff = next((e for e in events if e.get("event") == "handoff"), None)
    verifier = [e for e in events if e.get("event") == "verifier"]
    return {
        "task": o["task_id"],
        "trial": int(o["trial"]),
        "passed": bool(o["passed"]),
        "cost": float(o["cost_usd"]),
        "capped": any(_capped(s) for s in headline),
        "sessions": len(headline),
        "turns": sum(int(s.get("num_turns") or 0) for s in headline),
        "advisor_calls": advisor_calls,
        "voluntary_advisor_calls": int(first_worker["advisor_calls"]) if first_worker else 0,
        "forced_check": any(e.get("event") == "forced_check" for e in events),
        "advisor_cost": advisor_cost,
        "handoff": handoff is not None,
        "trigger": handoff.get("trigger") if handoff else None,
        "verifier_ok": verifier[-1]["ok"] if verifier else None,
        "verifier_runs": len(verifier),
        "escalation_cost": sum(
            float(s.get("headline_cost_usd", s.get("cost_usd_list", 0.0)))
            for s in headline
            if s.get("role") == "escalation"
        ),
    }


def load_cells(run_dirs: Iterable[str | Path]) -> Cells:
    cells: Cells = {}
    for run_dir in run_dirs:
        path = Path(run_dir) / "outcomes.jsonl"
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            o = json.loads(line)
            arm = cells.setdefault(o["policy"], {})
            c = _cell(o)
            arm[(c["task"], c["trial"])] = c
    return cells


# --------------------------------------------------------------------------- #
# Labels and H0
# --------------------------------------------------------------------------- #


def label(mid_passes: int, frontier_passes: int, trials: int = 3) -> str:
    """Section 7.1: easy (mid-tier passes every trial), hard (mid-tier at most
    1 of 3, frontier at least 2 of 3), unsolved (neither model passes more than
    1 of 3), medium (everything else, i.e. the mid-tier passes 2 of 3).  A task
    the mid-tier passes 2 of 3 is medium whatever the frontier does: it is
    solvable, so it is not excluded as unsolved."""
    low = trials // 3
    if mid_passes == trials:
        return "easy"
    if mid_passes <= low and frontier_passes >= trials - low:
        return "hard"
    if mid_passes <= low and frontier_passes <= low:
        return "unsolved"
    return "medium"


def task_table(cells: Cells) -> dict[str, dict[str, Any]]:
    tasks = sorted({t for arm in STATIC_ARMS for (t, _) in cells.get(arm, {})})
    out: dict[str, dict[str, Any]] = {}
    for t in tasks:
        row: dict[str, Any] = {}
        for arm in STATIC_ARMS:
            cs = [c for (task, _), c in cells.get(arm, {}).items() if task == t]
            row[arm] = {
                "n": len(cs),
                "passes": sum(c["passed"] for c in cs),
                "mean_cost": sum(c["cost"] for c in cs) / len(cs) if cs else None,
                "capped": sum(c["capped"] for c in cs),
            }
        n = min(row[a]["n"] for a in STATIC_ARMS)
        row["label"] = (
            label(row[MID]["passes"], row[FRONTIER]["passes"], n) if n == 3 else "incomplete"
        )
        out[t] = row
    return out


def h0(table: dict[str, dict[str, Any]]) -> dict[str, Any]:
    labelled = [t for t, r in table.items() if r["label"] != "incomplete"]
    counts: dict[str, int] = {}
    for t in labelled:
        counts[table[t]["label"]] = counts.get(table[t]["label"], 0) + 1
    hard = counts.get("hard", 0)
    registered = len(labelled) - counts.get("unsolved", 0)
    need = max(10, math.ceil(0.10 * registered))
    return {
        "counts": counts,
        "tasks": len(labelled),
        "registered_set": registered,
        "hard": hard,
        "required": need,
        "met": hard >= need,
        "hard_share": hard / registered if registered else 0.0,
    }


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #


def _cpt(cs: list[Cell]) -> float | None:
    passes = sum(c["passed"] for c in cs)
    return sum(c["cost"] for c in cs) / passes if passes else None


def _pct(values: list[float], q: float) -> float:
    s = sorted(values)
    idx = (len(s) - 1) * q
    lo, hi = math.floor(idx), math.ceil(idx)
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def _bootstrap(
    tasks: list[str], stat: Callable[[list[str]], float | None], draws: int = DRAWS
) -> tuple[float | None, list[float] | None]:
    point = stat(tasks)
    if not tasks:
        return point, None
    rng = random.Random(SEED)
    vals: list[float] = []
    for _ in range(draws):
        sample = [tasks[rng.randrange(len(tasks))] for _ in tasks]
        v = stat(sample)
        if v is not None and math.isfinite(v):
            vals.append(v)
    if len(vals) < draws * 0.5:
        return point, None
    return point, [_pct(vals, 0.025), _pct(vals, 0.975)]


def _by_task(arm: dict[tuple[str, int], Cell]) -> dict[str, list[Cell]]:
    out: dict[str, list[Cell]] = {}
    for (t, _), c in arm.items():
        out.setdefault(t, []).append(c)
    return out


def arm_stats(arm: dict[tuple[str, int], Cell], tasks: list[str]) -> dict[str, Any]:
    bt = _by_task(arm)
    tasks = [t for t in tasks if t in bt]

    def cells_of(sample: list[str]) -> list[Cell]:
        return [c for t in sample for c in bt[t]]

    cs = cells_of(tasks)
    cpt, cpt_ci = _bootstrap(tasks, lambda s: _cpt(cells_of(s)))
    rate, rate_ci = _bootstrap(
        tasks,
        lambda s: sum(c["passed"] for c in cells_of(s)) / len(cells_of(s)) if s else None,
    )
    return {
        "tasks": len(tasks),
        "cells": len(cs),
        "passes": sum(c["passed"] for c in cs),
        "pass_rate": rate,
        "pass_rate_ci": rate_ci,
        "cost": sum(c["cost"] for c in cs),
        "mean_cost": sum(c["cost"] for c in cs) / len(cs) if cs else None,
        "cpt": cpt,
        "cpt_ci": cpt_ci,
        "capped": sum(c["capped"] for c in cs),
        "handoffs": sum(c["handoff"] for c in cs),
        "advisor_calls": sum(c["advisor_calls"] for c in cs),
        "advisor_cost": sum(c["advisor_cost"] for c in cs),
    }


def ratio(
    a: dict[tuple[str, int], Cell], b: dict[tuple[str, int], Cell], tasks: list[str]
) -> tuple[float | None, list[float] | None]:
    ba, bb = _by_task(a), _by_task(b)
    tasks = [t for t in tasks if t in ba and t in bb]

    def stat(s: list[str]) -> float | None:
        ca = _cpt([c for t in s for c in ba[t]])
        cb = _cpt([c for t in s for c in bb[t]])
        return ca / cb if ca is not None and cb else None

    return _bootstrap(tasks, stat)


def pass_diff(
    a: dict[tuple[str, int], Cell], b: dict[tuple[str, int], Cell], tasks: list[str]
) -> tuple[float | None, list[float] | None]:
    """Difference in completion (percentage points), a - b, task-clustered."""
    ba, bb = _by_task(a), _by_task(b)
    tasks = [t for t in tasks if t in ba and t in bb]

    def rate(cs: list[Cell]) -> float:
        return sum(c["passed"] for c in cs) / len(cs)

    def stat(s: list[str]) -> float | None:
        if not s:
            return None
        return 100 * (rate([c for t in s for c in ba[t]]) - rate([c for t in s for c in bb[t]]))

    return _bootstrap(tasks, stat)


def _verdict_above(ci: list[float] | None, bound: float) -> str:
    """Supported if the whole interval is above ``bound``, not supported if it is
    wholly below, otherwise inconclusive."""
    if ci is None:
        return "inconclusive"
    if ci[0] > bound:
        return "supported"
    if ci[1] < bound:
        return "not supported"
    return "inconclusive"


def _verdict_below(ci: list[float] | None, bound: float) -> str:
    if ci is None:
        return "inconclusive"
    if ci[1] < bound:
        return "supported"
    if ci[0] > bound:
        return "not supported"
    return "inconclusive"


# --------------------------------------------------------------------------- #
# Computed arms
# --------------------------------------------------------------------------- #


def perfect_trigger(cells: Cells) -> dict[tuple[str, int], Cell]:
    """Hand off exactly the cells the mid-tier failed: those cost the mid-tier
    cell plus the frontier cell and take the frontier's outcome."""
    out: dict[tuple[str, int], Cell] = {}
    for key, m in cells[MID].items():
        f = cells[FRONTIER].get(key)
        if f is None:
            continue
        if m["passed"]:
            out[key] = {**m, "handoff": False}
        else:
            out[key] = {**f, "cost": m["cost"] + f["cost"], "handoff": True}
    return out


def random_matched(
    cells: Cells, rate: float, tasks: list[str], draws: int = DRAWS
) -> dict[str, Any]:
    """Hand off a random ``rate`` share of cells (same cost model as
    ``perfect_trigger``), averaged over seeded draws."""
    keys = sorted(k for k in cells[MID] if k in cells[FRONTIER] and k[0] in tasks)
    k_off = round(rate * len(keys))
    rng = random.Random(SEED)
    rates: list[float] = []
    cpts: list[float] = []
    for _ in range(draws):
        off = set(rng.sample(keys, k_off)) if k_off else set()
        cs = []
        for key in keys:
            m, f = cells[MID][key], cells[FRONTIER][key]
            cs.append({"passed": f["passed"], "cost": m["cost"] + f["cost"]} if key in off else m)
        rates.append(sum(c["passed"] for c in cs) / len(cs))
        v = _cpt(cs)
        if v is not None:
            cpts.append(v)
    return {
        "handoff_rate": rate,
        "handoffs": k_off,
        "pass_rate": sum(rates) / len(rates) if rates else None,
        "cpt": sum(cpts) / len(cpts) if cpts else None,
        "cpt_range": [_pct(cpts, 0.025), _pct(cpts, 0.975)] if cpts else None,
    }


def oracle(cells: Cells, *, per_trial: bool = False) -> dict[tuple[str, int], Cell]:
    """Cheapest static arm that passed: per task by majority of trials (the
    headline), or per task and trial (the most generous bound)."""
    out: dict[tuple[str, int], Cell] = {}
    by = {arm: _by_task(cells[arm]) for arm in STATIC_ARMS}
    for t in sorted(set(by[MID]) & set(by[FRONTIER])):
        if per_trial:
            for key in cells[MID]:
                if key[0] != t or key not in cells[FRONTIER]:
                    continue
                opts = [cells[a][key] for a in STATIC_ARMS]
                passing = [c for c in opts if c["passed"]]
                out[key] = min(passing or opts, key=lambda c: c["cost"])
            continue

        def mean_cost(arm: str, task: str = t) -> float:
            return sum(c["cost"] for c in by[arm][task]) / len(by[arm][task])

        majority = [
            a for a in STATIC_ARMS if sum(c["passed"] for c in by[a][t]) * 2 > len(by[a][t])
        ]
        pick = min(majority or list(STATIC_ARMS), key=mean_cost)
        for c in by[pick][t]:
            out[(t, c["trial"])] = c
    return out


# --------------------------------------------------------------------------- #
# Escalation quality
# --------------------------------------------------------------------------- #


def escalation_quality(
    arm: dict[tuple[str, int], Cell], cells: Cells, table: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Recall and precision of escalation against measured need (section 7.4):
    need = the mid-tier failed that trial (``trial``) or the majority of its
    trials (``majority``).  Reported for handoffs, any advisor call, and
    voluntary advisor calls (in the first worker session, before any forced
    check)."""
    out: dict[str, Any] = {}
    for need_kind in ("trial", "majority"):

        def needed(key: tuple[str, int], need_kind: str = need_kind) -> bool | None:
            if need_kind == "trial":
                m = cells[MID].get(key)
                return None if m is None else not m["passed"]
            r = table.get(key[0])
            if r is None or r[MID]["n"] == 0:
                return None
            return r[MID]["passes"] * 2 < r[MID]["n"]

        keyed = [(k, c, needed(k)) for k, c in arm.items()]
        keyed = [(k, c, n) for k, c, n in keyed if n is not None]
        n_need = sum(1 for _, _, n in keyed if n)
        res: dict[str, Any] = {"cells": len(keyed), "needed": n_need}
        res["base_rate"] = n_need / len(keyed) if keyed else None
        for signal in ("handoff", "advisor", "voluntary_advisor"):

            def fired(c: Cell, s: str = signal) -> bool:
                if s == "handoff":
                    return c["handoff"]
                if s == "advisor":
                    return c["advisor_calls"] > 0 or c["handoff"]
                return c["voluntary_advisor_calls"] > 0

            hits = [(c, n) for _, c, n in keyed if fired(c)]
            tp = sum(1 for _, n in hits if n)
            res[signal] = {
                "fired": len(hits),
                "recall": tp / n_need if n_need else None,
                "precision": tp / len(hits) if hits else None,
            }
        out[need_kind] = res
    return out


def verifier_accuracy(arm: dict[tuple[str, int], Cell]) -> dict[str, Any]:
    """Verifier false-accept rate: the last verifier check passed, there was no
    handoff, and the hidden tests failed."""
    accepted = [c for c in arm.values() if c["verifier_ok"] is True and not c["handoff"]]
    false_accept = [c for c in accepted if not c["passed"]]
    return {
        "accepted": len(accepted),
        "false_accepts": len(false_accept),
        "false_accept_rate": len(false_accept) / len(accepted) if accepted else None,
    }


# --------------------------------------------------------------------------- #
# Whole analysis
# --------------------------------------------------------------------------- #


def analyze(calibration: list[str | Path], ladder: list[str | Path]) -> dict[str, Any]:
    cells = load_cells([*calibration, *ladder])
    table = task_table(cells)
    gate = h0(table)
    strata: dict[str, list[str]] = {}
    for t, r in table.items():
        strata.setdefault(r["label"], []).append(t)
    registered = sorted(t for t, r in table.items() if r["label"] not in ("unsolved", "incomplete"))
    all_tasks = sorted(table)
    cells["perfect_trigger"] = perfect_trigger(cells)
    cells["oracle"] = oracle(cells)
    cells["oracle_per_trial"] = oracle(cells, per_trial=True)
    arms = [a for a in cells if a not in ("oracle", "oracle_per_trial")]
    scopes = {"registered": registered, "all": all_tasks, **strata}
    stats: dict[str, dict[str, Any]] = {}
    for scope, tasks in scopes.items():
        stats[scope] = {
            a: arm_stats(cells[a], tasks) for a in [*arms, "oracle", "oracle_per_trial"]
        }
    ladder_arms = [a for a in arms if a not in (*STATIC_ARMS, "perfect_trigger")]
    comparisons: dict[str, Any] = {}
    for a in [*ladder_arms, "perfect_trigger"]:
        c: dict[str, Any] = {}
        c["hard_pass_diff_vs_mid"] = pass_diff(cells[a], cells[MID], strata.get("hard", []))
        c["easy_cpt_ratio_vs_mid"] = ratio(cells[a], cells[MID], strata.get("easy", []))
        c["cpt_ratio_vs_frontier"] = ratio(cells[a], cells[FRONTIER], registered)
        c["pooled_cpt_ratio_vs_mid"] = ratio(cells[a], cells[MID], registered)
        c["pass_diff_vs_frontier"] = pass_diff(cells[a], cells[FRONTIER], registered)
        c["pass_diff_vs_mid"] = pass_diff(cells[a], cells[MID], registered)
        c["medium_cpt_ratio_vs_mid"] = ratio(cells[a], cells[MID], strata.get("medium", []))
        v1 = _verdict_above(c["hard_pass_diff_vs_mid"][1], MARGIN_PP)
        v2 = _verdict_below(c["easy_cpt_ratio_vs_mid"][1], EASY_COST_BOUND)
        v3 = _verdict_below(c["cpt_ratio_vs_frontier"][1], 1.0)
        verdicts = [v1, v2, v3]
        if "not supported" in verdicts:
            overall = "not supported"
        elif all(v == "supported" for v in verdicts):
            overall = "supported"
        else:
            overall = "inconclusive"
        c["L1"] = {"condition_1": v1, "condition_2": v2, "condition_3": v3, "overall": overall}
        c["L1_ceiling_noninferior"] = (
            c["pass_diff_vs_frontier"][1] is not None
            and c["pass_diff_vs_frontier"][1][0] > -MARGIN_PP
        )
        comparisons[a] = c
    quality = {a: escalation_quality(cells[a], cells, table) for a in ladder_arms}
    verif = {
        a: verifier_accuracy(cells[a])
        for a in ladder_arms
        if any(c["verifier_runs"] for c in cells[a].values())
    }
    rm = None
    if "explore_handoff_clean" in cells:
        eh = [c for k, c in cells["explore_handoff_clean"].items() if k[0] in registered]
        rate = sum(c["handoff"] for c in eh) / len(eh) if eh else 0.0
        rm = random_matched(cells, rate, registered)
    uncapped: dict[str, Any] = {}
    for a in arms:
        kept = {k: c for k, c in cells[a].items() if not c["capped"]}
        uncapped[a] = arm_stats(kept, registered)
    return {
        "tasks": table,
        "h0": gate,
        "strata": {k: sorted(v) for k, v in strata.items()},
        "stats": stats,
        "comparisons": comparisons,
        "escalation_quality": quality,
        "verifier": verif,
        "random_matched": rm,
        "sensitivity_uncapped": uncapped,
        "arms": arms,
        "ladder_arms": ladder_arms,
    }


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _m(x: float | None, digits: int = 3) -> str:
    return "n/a" if x is None else f"${x:.{digits}f}"


def _r(x: float | None, digits: int = 2) -> str:
    return "n/a" if x is None else f"{x:.{digits}f}"


def _ci(ci: list[float] | None, fmt: Callable[[float], str]) -> str:
    return "n/a" if ci is None else f"[{fmt(ci[0])}, {fmt(ci[1])}]"


def _p(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def render(a: dict[str, Any]) -> str:
    lines: list[str] = ["# exp06 analysis", ""]
    g = a["h0"]
    lines += [
        "## Stage 0: labels and H0",
        "",
        "| task | Sonnet passes | Opus passes | Sonnet mean cost | Opus mean cost | label |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for t, r in a["tasks"].items():
        lines.append(
            f"| {t} | {r[MID]['passes']}/{r[MID]['n']} "
            f"| {r[FRONTIER]['passes']}/{r[FRONTIER]['n']} "
            f"| {_m(r[MID]['mean_cost'])} | {_m(r[FRONTIER]['mean_cost'])} | {r['label']} |"
        )
    lines += [
        "",
        f"Label counts: {json.dumps(g['counts'], sort_keys=True)}. Hard tasks: {g['hard']} "
        f"(H0 requires {g['required']}); H0 **{'met' if g['met'] else 'not met'}**. "
        f"Hard share of the set excluding unsolved tasks: {_p(g['hard_share'])}.",
        "",
    ]
    for scope in ["registered", *sorted(k for k in a["strata"] if k != "incomplete")]:
        rows = a["stats"].get(scope)
        if not rows:
            continue
        n = next(iter(rows.values()))["tasks"]
        lines += [
            f"## Arms: {scope} ({n} tasks)",
            "",
            "| arm | cells | pass rate [95% CI] | cost per completed task [95% CI] "
            "| mean cost / cell | handoffs | advisor calls | turn-capped |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for arm, s in rows.items():
            if not s["cells"]:
                continue
            lines.append(
                f"| {arm} | {s['cells']} | {_p(s['pass_rate'])} {_ci(s['pass_rate_ci'], _p)} "
                f"| {_m(s['cpt'])} {_ci(s['cpt_ci'], _m)} | {_m(s['mean_cost'])} "
                f"| {s['handoffs']} | {s['advisor_calls']} | {s['capped']} |"
            )
        lines.append("")
    lines += ["## L1 and the cost ratios", ""]
    lines += [
        "| arm | hard: completion vs Sonnet (pts) | easy: cpt / Sonnet | whole set: cpt / Opus "
        "| pooled cpt / Sonnet | completion vs Opus (pts) | L1 (c1, c2, c3 -> overall) |",
        "|---|---|---|---|---|---|---|",
    ]

    def pts(x: float) -> str:
        return f"{x:+.1f}"

    for arm, c in a["comparisons"].items():
        d, dci = c["hard_pass_diff_vs_mid"]
        e, eci = c["easy_cpt_ratio_vs_mid"]
        f, fci = c["cpt_ratio_vs_frontier"]
        pr, prci = c["pooled_cpt_ratio_vs_mid"]
        po, poci = c["pass_diff_vs_frontier"]
        v = c["L1"]
        lines.append(
            f"| {arm} | {'n/a' if d is None else pts(d)} {_ci(dci, pts)} | {_r(e)} {_ci(eci, _r)} "
            f"| {_r(f)} {_ci(fci, _r)} | {_r(pr)} {_ci(prci, _r)} "
            f"| {'n/a' if po is None else pts(po)} {_ci(poci, pts)} "
            f"| {v['condition_1']}, {v['condition_2']}, {v['condition_3']} -> **{v['overall']}** |"
        )
    lines.append("")
    rm = a.get("random_matched")
    if rm:
        lines += [
            "## Random matched trigger (L6 comparison)",
            "",
            f"Handing off a random {_p(rm['handoff_rate'])} of cells ({rm['handoffs']} cells, "
            f"the explore_handoff_clean rate): pass rate {_p(rm['pass_rate'])}, cost per "
            f"completed task {_m(rm['cpt'])} (2.5-97.5% of draws {_ci(rm['cpt_range'], _m)}).",
            "",
        ]
    lines += ["## Escalation quality", ""]
    for arm, q in a["escalation_quality"].items():
        for need_kind, res in q.items():
            lines.append(
                f"- **{arm}**, need = Sonnet failed ({need_kind}): {res['needed']} of "
                f"{res['cells']} cells needed help (base rate {_p(res['base_rate'])}). "
                + "; ".join(
                    f"{sig.replace('_', ' ')} fired {res[sig]['fired']}x, recall "
                    f"{_p(res[sig]['recall'])}, precision {_p(res[sig]['precision'])}"
                    for sig in ("handoff", "advisor", "voluntary_advisor")
                )
            )
    lines.append("")
    if a["verifier"]:
        lines += ["## Verifier", ""]
        for arm, v in a["verifier"].items():
            lines.append(
                f"- {arm}: accepted {v['accepted']} cells without a handoff; "
                f"{v['false_accepts']} of them failed the hidden tests "
                f"(false-accept rate {_p(v['false_accept_rate'])})."
            )
        lines.append("")
    lines += ["## Sensitivity: turn-capped cells excluded (registered set)", ""]
    lines += ["| arm | cells | pass rate | cost per completed task |", "|---|---:|---:|---:|"]
    for arm, s in a["sensitivity_uncapped"].items():
        if s["cells"]:
            lines.append(f"| {arm} | {s['cells']} | {_p(s['pass_rate'])} | {_m(s['cpt'])} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calibration", nargs="+", required=True)
    ap.add_argument("--ladder", nargs="*", default=[])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    result = analyze(args.calibration, args.ladder)
    text = render(result)
    if args.out:
        args.out.write_text(text)
    else:
        print(text)
    if args.json:
        args.json.write_text(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
