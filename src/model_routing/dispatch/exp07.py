"""exp07 analysis: the evidence-gated advisor instruction.

    uv run python -m model_routing.dispatch.exp07 --runs results/exp07_evidence_prompt/<stamp> \\
        --out results/exp07_analysis.md --json results/exp07_analysis.json

Implements ``docs/experiments/exp07-evidence-prompt/preregistration.md``:

* **Labels** are exp06's measured labels, recomputed with exp06's rule
  (``exp06.label``) from the ``measured`` pass rates stored in the task files.
  The 45 easy tasks are the primary set; medium and hard are descriptive.
* **E1** (primary): on easy tasks, cost per completed task of
  ``ladder_evidence`` over ``ladder_noforce`` has a 97.5% upper bound below
  1.0, and the paired completion difference has a 97.5% lower bound above
  -10 points (the draft's -5, changed before registration). Both parts must hold.
* **E2**: ``ladder_evidence`` over ``static_sonnet`` on easy tasks, upper bound
  below 1.25.
* **E3**: the share of advisor requests labelled ``evidence_present`` is
  higher under ``ladder_evidence`` than ``ladder_noforce`` (lower bound of the
  difference above 0). Fewer than 20 ``ladder_evidence`` requests on easy
  tasks: descriptive only.
* E2 and E3 are one family: Holm-adjusted one-sided bootstrap p-values at
  alpha 0.025. A secondary is supported only if its interval clears the bound
  *and* its adjusted p-value is below 0.025.

Intervals are 95% task-clustered bootstrap (2,000 draws, fixed seed), so each
bound is a one-sided 97.5% bound. Verdicts: supported (the interval clears the
bound), not supported (the interval lies wholly on the wrong side), otherwise
inconclusive.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from model_routing.dispatch import exp06

EVIDENCE = "ladder_evidence"
STANDARD = "ladder_noforce"
STATIC = "static_sonnet"
ARMS = (EVIDENCE, STANDARD, STATIC)
TASK_FILES = ("tasks/exp06/tasks.jsonl", "tasks/exp06/tasks_ext.jsonl")
NONINF_MARGIN_PP = 10.0
E2_BOUND = 1.25
FEW_EVENTS = 20
ALPHA = 0.025
DRAWS = exp06.DRAWS
SEED = exp06.SEED

Cell = dict[str, Any]


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def task_labels(task_files: Iterable[str | Path]) -> dict[str, dict[str, Any]]:
    """exp06 protocol labels from each task's stored calibration pass rates."""
    out: dict[str, dict[str, Any]] = {}
    for f in task_files:
        for line in Path(f).read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            m = row.get("measured") or {}
            rates, n = m.get("pass_rates") or {}, m.get("n") or {}
            if "sonnet" not in rates or "opus" not in rates:
                continue
            mid = round(rates["sonnet"] * n["sonnet"])
            top = round(rates["opus"] * n["opus"])
            out[row["id"]] = {
                "label": exp06.label(mid, top, int(n["sonnet"])),
                "sonnet_rate": rates["sonnet"],
                "opus_rate": rates["opus"],
            }
    return out


def _requests(o: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per advisor request in a cell: the hook's log where it fired, else
    the stream (same order, same labels; the hook adds the diff)."""
    rows: list[dict[str, Any]] = []
    for s in o.get("sessions") or []:
        raw = s.get("raw") or {}
        hook = raw.get("advisor_hook_requests") or []
        stream = raw.get("advisor_requests") or []
        chosen = hook if hook else stream
        for i, r in enumerate(chosen):
            turn = r.get("assistant_turn")
            if turn is None and i < len(stream):
                turn = stream[i].get("assistant_turn")
            rows.append(
                {
                    "task": o["task_id"],
                    "trial": int(o["trial"]),
                    "arm": o["policy"],
                    "role": s.get("role"),
                    "turn": turn,
                    "label": r.get("label"),
                    "source": r.get("source"),
                }
            )
    return rows


def load(runs: Iterable[str | Path]) -> tuple[dict[str, dict[tuple[str, int], Cell]], list]:
    cells: dict[str, dict[tuple[str, int], Cell]] = {}
    requests: list[dict[str, Any]] = []
    hook_counts = {"hook": 0, "stream": 0}
    for run in runs:
        for line in (Path(run) / "outcomes.jsonl").read_text().splitlines():
            if not line.strip():
                continue
            o = json.loads(line)
            c = exp06._cell(o)
            reqs = _requests(o)
            c["requests"] = len(reqs)
            c["evidence_requests"] = sum(r["label"] == "evidence_present" for r in reqs)
            c["escalate"] = c["trigger"] == "escalate"
            c["advisor_input_tokens"] = sum(
                int(u.get("input_tokens", 0))
                for s in o.get("sessions") or []
                for m, u in ((s.get("raw") or {}).get("other_model_usage") or {}).items()
                if "opus" in m
            )
            for s in o.get("sessions") or []:
                raw = s.get("raw") or {}
                hook_counts["hook"] += len(raw.get("advisor_hook_requests") or [])
                hook_counts["stream"] += len(raw.get("advisor_requests") or [])
            cells.setdefault(o["policy"], {})[(c["task"], c["trial"])] = c
            requests.extend(reqs)
    return cells, [requests, hook_counts]


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #


def _draws(tasks: list[str], stat: Callable[[list[str]], float | None]) -> list[float]:
    rng = random.Random(SEED)
    out: list[float] = []
    for _ in range(DRAWS):
        sample = [tasks[rng.randrange(len(tasks))] for _ in tasks]
        v = stat(sample)
        if v is not None and math.isfinite(v):
            out.append(v)
    return out


def _p_one_sided(draws: list[float], bound: float, *, want_below: bool) -> float | None:
    """Share of bootstrap draws on the wrong side of the bound."""
    if not draws:
        return None
    wrong = sum(1 for d in draws if (d >= bound if want_below else d <= bound))
    return wrong / len(draws)


def holm(pvalues: dict[str, float | None]) -> dict[str, float | None]:
    present = sorted((p, k) for k, p in pvalues.items() if p is not None)
    m = len(present)
    adjusted: dict[str, float | None] = {k: None for k in pvalues}
    running = 0.0
    for i, (p, k) in enumerate(present):
        running = max(running, min(1.0, (m - i) * p))
        adjusted[k] = running
    return adjusted


def ratio_with_draws(
    a: dict[tuple[str, int], Cell], b: dict[tuple[str, int], Cell], tasks: list[str]
) -> tuple[float | None, list[float] | None, list[float]]:
    ba, bb = exp06._by_task(a), exp06._by_task(b)
    tasks = [t for t in tasks if t in ba and t in bb]

    def stat(s: list[str]) -> float | None:
        ca = exp06._cpt([c for t in s for c in ba[t]])
        cb = exp06._cpt([c for t in s for c in bb[t]])
        return ca / cb if ca is not None and cb else None

    point, ci = exp06._bootstrap(tasks, stat)
    return point, ci, (_draws(tasks, stat) if tasks else [])


def share_diff(
    a: dict[tuple[str, int], Cell], b: dict[tuple[str, int], Cell], tasks: list[str]
) -> tuple[float | None, list[float] | None, list[float]]:
    """Difference in the share of requests labelled evidence_present, a - b,
    pooled over each arm's requests, resampling tasks."""
    ba, bb = exp06._by_task(a), exp06._by_task(b)
    tasks = [t for t in tasks if t in ba and t in bb]

    def share(cs: list[Cell]) -> float | None:
        n = sum(c["requests"] for c in cs)
        return sum(c["evidence_requests"] for c in cs) / n if n else None

    def stat(s: list[str]) -> float | None:
        sa = share([c for t in s for c in ba[t]])
        sb = share([c for t in s for c in bb[t]])
        return sa - sb if sa is not None and sb is not None else None

    point, ci = exp06._bootstrap(tasks, stat)
    return point, ci, (_draws(tasks, stat) if tasks else [])


def _verdict_below(ci: list[float] | None, bound: float) -> str:
    return exp06._verdict_below(ci, bound)


def _verdict_above(ci: list[float] | None, bound: float) -> str:
    return exp06._verdict_above(ci, bound)


# --------------------------------------------------------------------------- #
# Whole analysis
# --------------------------------------------------------------------------- #


def analyze(runs: list[str | Path], task_files: Iterable[str | Path] = TASK_FILES) -> dict:
    labels = task_labels(task_files)
    cells, (requests, hook_counts) = load(runs)
    missing = [a for a in ARMS if a not in cells]
    if missing:
        raise ValueError(f"run(s) lack arm(s) {missing}")
    in_run = sorted({t for a in ARMS for (t, _) in cells[a]})
    easy = [t for t in in_run if labels.get(t, {}).get("label") == "easy"]
    other = [t for t in in_run if labels.get(t, {}).get("label") in ("medium", "hard")]

    # E1
    r1, r1_ci, _ = ratio_with_draws(cells[EVIDENCE], cells[STANDARD], easy)
    d1, d1_ci = exp06.pass_diff(cells[EVIDENCE], cells[STANDARD], easy)
    cost_v = _verdict_below(r1_ci, 1.0)
    comp_v = _verdict_above(d1_ci, -NONINF_MARGIN_PP)
    if "not supported" in (cost_v, comp_v):
        e1 = "not supported"
    elif cost_v == comp_v == "supported":
        e1 = "supported"
    else:
        e1 = "inconclusive"

    # E2
    r2, r2_ci, r2_draws = ratio_with_draws(cells[EVIDENCE], cells[STATIC], easy)
    p2 = _p_one_sided(r2_draws, E2_BOUND, want_below=True)

    # E3
    n_evidence_requests = sum(
        cells[EVIDENCE][k]["requests"] for k in cells[EVIDENCE] if k[0] in easy
    )
    s3, s3_ci, s3_draws = share_diff(cells[EVIDENCE], cells[STANDARD], easy)
    few = n_evidence_requests < FEW_EVENTS
    p3 = None if few else _p_one_sided(s3_draws, 0.0, want_below=False)

    adj = holm({"E2": p2, "E3": p3})

    def secondary(ci_verdict: str, p_adj: float | None) -> str:
        if ci_verdict == "supported" and (p_adj is None or p_adj >= ALPHA):
            return "inconclusive"
        return ci_verdict

    e2 = secondary(_verdict_below(r2_ci, E2_BOUND), adj["E2"])
    e3 = "descriptive (few events)" if few else secondary(_verdict_above(s3_ci, 0.0), adj["E3"])

    # Descriptive
    per_arm: dict[str, Any] = {}
    for arm in ARMS:
        cs = [c for k, c in cells[arm].items() if k[0] in easy]
        all_cs = list(cells[arm].values())
        reqs = [c["requests"] for c in all_cs]
        cost = sum(c["cost"] for c in all_cs)
        per_arm[arm] = {
            "easy": exp06.arm_stats(cells[arm], easy),
            "all": exp06.arm_stats(cells[arm], in_run),
            "requests_per_cell": {
                "mean": statistics.mean(reqs) if reqs else 0.0,
                "median": statistics.median(reqs) if reqs else 0.0,
                "p90": exp06._pct([float(x) for x in reqs], 0.9) if reqs else 0.0,
                "max": max(reqs, default=0),
                "zero_share": sum(1 for x in reqs if x == 0) / len(reqs) if reqs else None,
            },
            "advisor_cost_share": sum(c["advisor_cost"] for c in all_cs) / cost if cost else None,
            # Sanity check on the request count: a real advisor read costs at least
            # ~31k input tokens, so a median well below that means double counting.
            "advisor_input_per_call": (
                statistics.median(
                    c["advisor_input_tokens"] / c["advisor_calls"]
                    for c in all_cs
                    if c["advisor_calls"]
                )
                if any(c["advisor_calls"] for c in all_cs)
                else None
            ),
            "handoff_rate": sum(c["handoff"] for c in all_cs) / len(all_cs) if all_cs else None,
            "escalate_rate": sum(c["escalate"] for c in all_cs) / len(all_cs) if all_cs else None,
            "easy_evidence_share": (
                sum(c["evidence_requests"] for c in cs) / sum(c["requests"] for c in cs)
                if sum(c["requests"] for c in cs)
                else None
            ),
        }
    hard_table = [
        {
            "task": t,
            "label": labels[t]["label"],
            "calibrated_sonnet_rate": labels[t]["sonnet_rate"],
            **{
                arm: [cells[arm][k]["passed"] for k in sorted(cells[arm]) if k[0] == t]
                for arm in ARMS
            },
        }
        for t in other
    ]
    return {
        "tasks_in_run": len(in_run),
        "easy_tasks": len(easy),
        "other_tasks": other,
        "E1": {
            "cost_ratio": r1,
            "cost_ratio_ci": r1_ci,
            "cost_verdict": cost_v,
            "completion_diff_pts": d1,
            "completion_diff_ci": d1_ci,
            "completion_verdict": comp_v,
            "verdict": e1,
        },
        "E2": {"ratio": r2, "ci": r2_ci, "p": p2, "p_holm": adj["E2"], "verdict": e2},
        "E3": {
            "share_diff": s3,
            "ci": s3_ci,
            "p": p3,
            "p_holm": adj["E3"],
            "evidence_arm_requests_easy": n_evidence_requests,
            "verdict": e3,
        },
        "arms": per_arm,
        "hard_and_medium": hard_table,
        "requests": requests,
        "request_sources": hook_counts,
    }


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _r(x: float | None, d: int = 2) -> str:
    return "n/a" if x is None else f"{x:.{d}f}"


def _ci(ci: list[float] | None, d: int = 2) -> str:
    return "n/a" if ci is None else f"[{ci[0]:.{d}f}, {ci[1]:.{d}f}]"


def _pci(ci: list[float] | None) -> str:
    return "n/a" if ci is None else f"[{_p(ci[0])}, {_p(ci[1])}]"


def _p(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def _row(*cells: str) -> str:
    return "| " + " | ".join(cells) + " |"


def render(a: dict[str, Any]) -> str:
    e1, e2, e3 = a["E1"], a["E2"], a["E3"]
    holm2 = f"(p {_r(e2['p'], 3)}, Holm {_r(e2['p_holm'], 3)})"
    holm3 = (
        f"(p {_r(e3['p'], 3)}, Holm {_r(e3['p_holm'], 3)}; "
        f"{e3['evidence_arm_requests_easy']} evidence-arm requests)"
    )
    lines = [
        "# exp07 analysis",
        "",
        f"{a['tasks_in_run']} tasks in the run; {a['easy_tasks']} easy (primary set).",
        "",
        "## Hypotheses",
        "",
        _row("", "estimate [95% CI]", "bound", "verdict"),
        _row("---", "---", "---", "---"),
        _row(
            "E1 cost: cpt evidence / standard (easy)",
            f"{_r(e1['cost_ratio'])} {_ci(e1['cost_ratio_ci'])}",
            "upper < 1.0",
            e1["cost_verdict"],
        ),
        _row(
            "E1 completion: evidence - standard, pts (easy)",
            f"{_r(e1['completion_diff_pts'], 1)} {_ci(e1['completion_diff_ci'], 1)}",
            f"lower > -{NONINF_MARGIN_PP:g}",
            e1["completion_verdict"],
        ),
        _row("**E1**", "", "both", f"**{e1['verdict']}**"),
        _row(
            "E2: cpt evidence / static Sonnet (easy)",
            f"{_r(e2['ratio'])} {_ci(e2['ci'])}",
            f"upper < {E2_BOUND}",
            f"{e2['verdict']} {holm2}",
        ),
        _row(
            "E3: evidence-labelled share, evidence - standard (easy)",
            f"{_r(e3['share_diff'])} {_ci(e3['ci'])}",
            "lower > 0",
            f"{e3['verdict']} {holm3}",
        ),
        "",
        "## Arms",
        "",
        _row(
            "arm",
            "easy: pass [CI]",
            "easy: cpt [CI]",
            "all: cpt",
            "requests/cell mean, median, p90, max",
            "cells with no request",
            "advisor share of cost",
            "handoff",
            "ESCALATE",
            "evidence-labelled share (easy)",
        ),
        _row(*["---"] * 10),
    ]
    for arm, s in a["arms"].items():
        e, al, rq = s["easy"], s["all"], s["requests_per_cell"]
        lines.append(
            _row(
                arm,
                f"{_p(e['pass_rate'])} {_pci(e['pass_rate_ci'])}",
                f"${_r(e['cpt'], 3)} {_ci(e['cpt_ci'], 3)}",
                f"${_r(al['cpt'], 3)}",
                f"{rq['mean']:.2f}, {rq['median']:g}, {rq['p90']:.1f}, {rq['max']}",
                _p(rq["zero_share"]),
                _p(s["advisor_cost_share"]),
                _p(s["handoff_rate"]),
                _p(s["escalate_rate"]),
                _p(s["easy_evidence_share"]),
            )
        )
    lines += ["", "## Medium and hard tasks (descriptive)", ""]
    lines += [
        "| task | label | calibrated Sonnet pass rate | " + " | ".join(ARMS) + " |",
        "| --- | --- | --- | " + " | ".join("---" for _ in ARMS) + " |",
    ]
    for row in a["hard_and_medium"]:
        cells = " | ".join("".join("P" if x else "f" for x in row[arm]) for arm in ARMS)
        lines.append(
            f"| {row['task']} | {row['label']} | {_p(row['calibrated_sonnet_rate'])} | {cells} |"
        )
    lines += ["", "Advisor input tokens per counted request (median per cell; a real read is"]
    lines += ["at least ~31k, so much lower values mean the requests are over-counted):", ""]
    for arm, st_ in a["arms"].items():
        v = st_["advisor_input_per_call"]
        lines.append(f"- {arm}: {'n/a' if v is None else f'{v:,.0f}'}")
    src = a["request_sources"]
    lines += [
        "",
        "## Advisor requests",
        "",
        f"Logged by the hook: {src['hook']}; seen in the session streams: {src['stream']}.",
        "",
        "| task | trial | arm | role | turn | label | source |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in a["requests"]:
        lines.append(
            f"| {r['task']} | {r['trial']} | {r['arm']} | {r['role']} | {r['turn']} | {r['label']} "
            f"| {r['source']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--tasks", nargs="+", default=list(TASK_FILES))
    ap.add_argument("--out", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    result = analyze(args.runs, args.tasks)
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
