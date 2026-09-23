"""White-paper draft generator: ``render_paper(run_dirs, out=...)`` -> Markdown.

Fills the skeleton of a short empirical paper (abstract, question, methods,
results, robustness, threats, reproducibility, appendix) from one or more
dispatch run directories (``meta.json``, ``summary.json``, ``outcomes.jsonl``,
``sessions.jsonl``).  Interpretation is left to the author as explicit
``[TODO: author]`` placeholders; every number is computed here.

Rules:

* Deterministic and stdlib-only.  The statistics come from
  ``report.summarize`` (seeded bootstrap / permutation), so re-rendering the
  same runs gives the same file byte for byte.
* **No model output.**  Session ``output`` fields, grader output and file
  lists are dropped on load; the only model-produced value in the draft is
  the router's parsed pick (``chosen_candidate``).
* Several run directories are pooled: outcomes are concatenated with a
  ``run`` column, trial indices are renumbered so (task, trial) cells stay
  unique, and the pooled statistics are recomputed.  A pooled analysis is not
  part of any pre-registration and the draft says so.
"""

from __future__ import annotations

import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from model_routing.dispatch.report import summarize

TODO = "[TODO: author]"
REPO_ROOT = Path(__file__).resolve().parents[3]
DESIGN_DOC = REPO_ROOT / "docs" / "experiments" / "dispatch-routing.md"
PREREG_DOC = REPO_ROOT / "docs" / "experiments" / "preregistration-exp05.md"

DIFFICULTY_ORDER = ["easy", "medium", "hard", "unsolved", "unknown"]
ROUTING_KINDS = {
    "spawn_parent_pick",
    "spawn_parent_pick_inline",
    "spawn_classifier",
    "spawn_cascade",
}
# Outcome fields the draft may use.  Everything else (session transcripts,
# grader output, changed-file lists) is dropped when a run is loaded.
OUTCOME_FIELDS = (
    "task_id",
    "policy",
    "trial",
    "passed",
    "checks",
    "difficulty",
    "category",
    "chosen_candidate",
    "escalations",
    "cost_usd",
    "cost_usd_full",
    "errors",
    "setup_cost_usd",
    "router_cost_usd",
    "turns",
)
SESSION_FIELDS = (
    "task_id",
    "policy",
    "trial",
    "role",
    "candidate",
    "provider",
    "model",
    "effort",
    "resolved_model",
    "cost_usd_list",
    "cost_usd_reported",
    "headline_cost_usd",
)


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _load_run(run_dir: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if (run_dir / "meta.json").exists():
        meta = json.loads((run_dir / "meta.json").read_text())
    if (run_dir / "summary.json").exists():
        summary = json.loads((run_dir / "summary.json").read_text())
    else:
        summary = summarize(run_dir)
    outcomes = [
        {k: o[k] for k in OUTCOME_FIELDS if k in o} for o in _load_jsonl(run_dir / "outcomes.jsonl")
    ]
    sessions = []
    for s in _load_jsonl(run_dir / "sessions.jsonl"):
        row = {k: s[k] for k in SESSION_FIELDS if k in s}
        row["errored"] = bool(s.get("error"))
        sessions.append(row)
    return {
        "dir": run_dir,
        "meta": meta,
        "summary": summary,
        "outcomes": outcomes,
        "sessions": sessions,
    }


def _run_labels(run_dirs: list[Path]) -> list[str]:
    names = [p.name for p in run_dirs]
    if len(set(names)) == len(names):
        return names
    return [f"{p.parent.name}/{p.name}" for p in run_dirs]


def _resummarize(meta: dict[str, Any], outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Run ``report.summarize`` on a synthetic run dir (same statistics code)."""
    with tempfile.TemporaryDirectory(prefix="dispatch-paper-") as tmp:
        d = Path(tmp)
        (d / "meta.json").write_text(json.dumps(meta, default=str))
        with (d / "outcomes.jsonl").open("w") as f:
            for o in outcomes:
                f.write(json.dumps(o) + "\n")
        (d / "sessions.jsonl").write_text("")
        return summarize(d)


def _pool(runs: list[dict[str, Any]], labels: list[str]) -> tuple[dict, list, dict]:
    """(meta, outcomes-with-run-column, summary) for one run or several pooled."""
    if len(runs) == 1:
        run = runs[0]
        outcomes = [dict(o, run=labels[0]) for o in run["outcomes"]]
        return run["meta"], outcomes, run["summary"]
    outcomes: list[dict[str, Any]] = []
    offset = 0
    for run, label in zip(runs, labels, strict=True):
        trials = [int(o.get("trial", 0)) for o in run["outcomes"]]
        for o in run["outcomes"]:
            outcomes.append(dict(o, run=label, trial=offset + int(o.get("trial", 0))))
        offset += (max(trials) + 1) if trials else 0
    base = runs[0]["meta"]
    meta = dict(base)
    meta.update(
        experiment=f"{base.get('experiment', 'dispatch')} (pooled, {len(runs)} runs)",
        n_tasks=len({o["task_id"] for o in outcomes}),
        trials=offset,
        fake=any(r["meta"].get("fake") for r in runs),
    )
    return meta, outcomes, _resummarize(meta, outcomes)


# --------------------------------------------------------------------------
# formatting helpers
# --------------------------------------------------------------------------


def _money(x: float | None) -> str:
    return "-" if x is None else f"${x:.4f}"


def _pct(x: float | None, digits: int = 0) -> str:
    return "-" if x is None else f"{x * 100:.{digits}f}%"


def _p(p: float | None) -> str:
    if p is None:
        return "-"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def _ci_pct(ci: list[float] | None) -> str:
    return "-" if not ci else f"{ci[0] * 100:.0f}-{ci[1] * 100:.0f}%"


def _ci_money(ci: list[float] | None) -> str:
    return "-" if not ci else f"{_money(ci[0])}-{_money(ci[1])}"


def _table(header: list[str], rows: list[list[str]], align: list[str] | None = None) -> list[str]:
    align = align or ["l"] * len(header)
    sep = ["---:" if a == "r" else "---" for a in align]
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(sep) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out


def _diff_key(d: str) -> tuple[int, str]:
    return (DIFFICULTY_ORDER.index(d) if d in DIFFICULTY_ORDER else len(DIFFICULTY_ORDER), d)


def _doc_paragraph(path: Path, starts_with: str) -> str | None:
    """The paragraph of ``path`` beginning with ``starts_with`` (joined), or None."""
    try:
        text = path.read_text()
    except OSError:
        return None
    for para in text.split("\n\n"):
        stripped = para.strip()
        if stripped.startswith(starts_with):
            return " ".join(line.strip() for line in stripped.splitlines())
    return None


def _doc_section_first_paragraph(path: Path, heading: str) -> str | None:
    try:
        text = path.read_text()
    except OSError:
        return None
    marker = f"\n{heading}\n"
    if marker not in text:
        return None
    rest = text.split(marker, 1)[1].strip()
    para = rest.split("\n\n", 1)[0]
    return " ".join(line.strip() for line in para.splitlines())


# --------------------------------------------------------------------------
# computations over outcomes (all deterministic)
# --------------------------------------------------------------------------


def _paired_point(
    outcomes: list[dict[str, Any]], treatment: str, control: str, cost_key: str = "cost_usd"
) -> dict[str, Any] | None:
    cells: dict[str, dict[tuple[str, int], dict[str, Any]]] = defaultdict(dict)
    for o in outcomes:
        if o["policy"] in (treatment, control):
            cells[o["policy"]][(o["task_id"], int(o["trial"]))] = o
    keys = sorted(cells[treatment].keys() & cells[control].keys())
    if not keys:
        return None
    t = [cells[treatment][k] for k in keys]
    c = [cells[control][k] for k in keys]
    tp = sum(bool(o["passed"]) for o in t)
    cp = sum(bool(o["passed"]) for o in c)

    def cost(o: dict[str, Any]) -> float:
        return float(o.get(cost_key, o.get("cost_usd", 0.0)))

    saving = None
    if tp and cp:
        t_cpt = sum(cost(o) for o in t) / tp
        c_cpt = sum(cost(o) for o in c) / cp
        saving = (1 - t_cpt / c_cpt) * 100 if c_cpt else None
    return {"n_paired": len(keys), "delta_pass_pp": (tp - cp) / len(keys) * 100, "saving": saving}


def _pass_table(
    outcomes: list[dict[str, Any]], policies: list[str], field: str
) -> tuple[list[str], dict[tuple[str, str], tuple[int, int]]]:
    counts: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    groups: set[str] = set()
    for o in outcomes:
        g = str(o.get(field) or "unknown")
        groups.add(g)
        counts[(g, o["policy"])][0] += 1
        counts[(g, o["policy"])][1] += int(bool(o["passed"]))
    ordered = sorted(groups, key=_diff_key) if field == "difficulty" else sorted(groups)
    return ordered, {k: (v[0], v[1]) for k, v in counts.items()}


def _upper_bounds(meta: dict[str, Any]) -> set[str]:
    """Policies that use information a deployed system would not have."""
    return {
        str(p.get("name"))
        for p in meta.get("policies", [])
        if isinstance(p, dict) and p.get("escalate_on") == "hidden"
    }


def _pareto(rows: list[dict[str, Any]], exclude: set[str] | None = None) -> set[str]:
    """Names not dominated on (higher pass rate, lower cost per completed task)."""
    exclude = exclude or set()
    pts = [r for r in rows if r.get("cost_per_pass") is not None and r["name"] not in exclude]
    front = set()
    for p in pts:
        dominated = any(
            q is not p
            and q["pass_rate"] >= p["pass_rate"]
            and q["cost_per_pass"] <= p["cost_per_pass"]
            and (q["pass_rate"] > p["pass_rate"] or q["cost_per_pass"] < p["cost_per_pass"])
            for q in pts
        )
        if not dominated:
            front.add(p["name"])
    return front


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------


def render_paper(run_dirs: list[Path], *, out: Path) -> Path:
    """Write a Markdown paper draft for ``run_dirs`` to ``out``; return ``out``."""
    run_dirs = [Path(d) for d in run_dirs]
    if not run_dirs:
        raise ValueError("render_paper needs at least one run directory")
    runs = [_load_run(d) for d in run_dirs]
    labels = _run_labels(run_dirs)
    meta, outcomes, summary = _pool(runs, labels)
    pooled = len(runs) > 1
    text = "\n".join(_render(runs, labels, meta, outcomes, summary, pooled)) + "\n"
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    return out


def _render(
    runs: list[dict[str, Any]],
    labels: list[str],
    meta: dict[str, Any],
    outcomes: list[dict[str, Any]],
    summary: dict[str, Any],
    pooled: bool,
) -> list[str]:
    primary = meta.get("primary") or {"treatment": "C1_inline", "control": "B"}
    treat, ctrl = primary.get("treatment", "C1_inline"), primary.get("control", "B")
    margin = float(meta.get("margin_pp", 5.0))
    comps = summary.get("comparisons") or []
    h_d1 = next((c for c in comps if c["id"] == "H-D1"), None)
    policies = summary.get("policies") or []
    policy_names = [p["name"] for p in policies]
    kinds = {p.get("name"): p.get("kind", "") for p in meta.get("policies", [])}
    sessions = [s for r in runs for s in r["sessions"]]
    task_ids = sorted({o["task_id"] for o in outcomes})
    n_cells = len(outcomes)
    spend = sum(
        float(o.get("cost_usd", 0.0)) + float(o.get("setup_cost_usd", 0.0)) for o in outcomes
    )
    fake = any(bool(r["meta"].get("fake")) for r in runs)
    statuses = [
        (label, r["summary"].get("confirmatory"), r["summary"].get("preregistration") or {})
        for label, r in zip(labels, runs, strict=True)
    ]
    confirmatory = (not pooled) and bool(statuses[0][1])
    L: list[str] = []

    # ---- title + provenance -------------------------------------------------
    L += [
        f"# {TODO} title: dispatch-time model routing ({meta.get('experiment', 'dispatch')})",
        "",
        "> Draft generated by `model-routing dispatch-paper` from "
        + ", ".join(f"`{lab}`" for lab in labels)
        + ". Numbers are computed; regenerate rather than edit them. "
        f"Prose marked `{TODO}` needs the author.",
    ]
    if fake:
        L += [
            ">",
            "> **SIMULATED DATA.** At least one run used the fake agent provider; these "
            "numbers exercise the pipeline and are not evidence about any model.",
        ]
    status_word = "CONFIRMATORY" if confirmatory else "EXPLORATORY"
    L += [">", f"> **Analysis status: {status_word}.**"]
    if pooled:
        L.append(
            f"> Pooled analysis of {len(runs)} runs (outcomes concatenated with a `run` column, "
            "trials renumbered); pooling is not part of any pre-registration."
        )
    L.append("")

    # ---- abstract -----------------------------------------------------------
    L += ["## Abstract", ""]
    L.append(
        f"We ran {len(task_ids)} tasks x {meta.get('trials', 1)} trial(s) under "
        f"{len(policies)} dispatch policies ({n_cells} graded cells, "
        f"{_money(spend)} list-price spend including setup)."
    )
    if h_d1:
        L.append(
            f"Primary comparison (H-D1, {treat} vs {ctrl}): cost per completed task changed by "
            f"{-h_d1['saving_pct']:+.0f}% (saving {h_d1['saving_pct']:.0f}%, 95% CI "
            f"{h_d1['saving_ci'][0]:.0f}% to {h_d1['saving_ci'][1]:.0f}%, p_saving = "
            f"{_p(h_d1.get('p_saving'))}); pass rate changed by {h_d1['delta_pass_pp']:+.1f} pts "
            f"(95% CI {h_d1['delta_pass_ci'][0]:+.1f} to {h_d1['delta_pass_ci'][1]:+.1f}, "
            f"non-inferiority margin {margin:.0f} pts, p_noninf = {_p(h_d1.get('p_noninf'))}). "
            f"Verdict: **{h_d1['verdict']}** ({status_word.lower()})."
        )
    else:
        L.append(f"No primary comparison: the run lacks outcomes for {treat!r} and/or {ctrl!r}.")
    L += ["", f"{TODO} 150-word prose abstract: motivation, what was done, what it means.", ""]

    # ---- background / question ----------------------------------------------
    L += ["## 1. Background and question", ""]
    question = _doc_section_first_paragraph(PREREG_DOC, "## Question")
    if question:
        L += [f"> {question}", ""]
    hyp = _doc_paragraph(DESIGN_DOC, "**Primary hypothesis (H-D1).**") or (
        f"**Primary hypothesis (H-D1).** {meta.get('hypothesis', '')}"
    )
    L += [
        "Primary hypothesis, quoted from `docs/experiments/dispatch-routing.md`:",
        "",
        f"> {hyp}",
        "",
        f"Non-inferiority margin used by this analysis: **{margin:.0f} percentage points** "
        f"(`margin_pp` in `meta.json`). Primary comparison: `{treat}` (treatment) vs "
        f"`{ctrl}` (control).",
        "",
        f"{TODO} related work and why dispatch time is the right place to route.",
        "",
    ]

    # ---- methods --------------------------------------------------------------
    L += ["## 2. Methods", "", "### 2.1 Design", ""]
    L.append(
        f"Paired design: every sampled task runs under every selected policy for the same "
        f"number of trials ({meta.get('trials', 1)}). Ordering: `order = "
        f'"{meta.get("order", "unknown")}"`, seed `{meta.get("seed", "-")}` (a seeded '
        "randomized block per (task, trial) when randomized); sessions run strictly "
        f"sequentially. Turn cap: {meta.get('max_turns', '-')} per session for every policy. "
        f"Parent model: `{meta.get('parent', '-')}`; router menu: "
        + ", ".join(f"`{m}`" for m in meta.get("menu", []))
        + "."
    )
    L += ["", "### 2.2 Policies run", ""]
    rows = []
    for p in policies:
        cand = next((q for q in meta.get("policies", []) if q.get("name") == p["name"]), {})
        detail = ", ".join(f"{k}={v}" for k, v in sorted(cand.items()) if k not in ("name", "kind"))
        rows.append(
            [f"`{p['name']}`", f"`{kinds.get(p['name'], '?')}`", detail or "-", str(p["n"])]
        )
    L += _table(["policy", "kind", "parameters", "cells"], rows, ["l", "l", "l", "r"])

    L += ["", "### 2.3 Task set", ""]
    task_diff: dict[str, str] = {}
    task_cat: dict[str, str] = {}
    for o in outcomes:
        task_diff.setdefault(o["task_id"], str(o.get("difficulty") or "unknown"))
        task_cat.setdefault(o["task_id"], str(o.get("category") or "unknown"))
    hist = Counter(task_diff.values())
    L.append(
        f"{len(task_ids)} distinct tasks. Difficulty labels as stored with the task set at run "
        "time (measured from a calibration run when `dispatch-calibration --write` was used; "
        f"{TODO} confirm which calibration run produced them)."
    )
    L.append("")
    L += _table(
        ["difficulty", "tasks", "histogram"],
        [[d, str(hist[d]), "#" * hist[d]] for d in sorted(hist, key=_diff_key)],
        ["l", "r", "l"],
    )
    cats = Counter(task_cat.values())
    L += ["", "Categories: " + ", ".join(f"{c} ({n})" for c, n in sorted(cats.items())) + "."]
    repos = _task_repos(runs, set(task_ids))
    if repos:
        L.append(
            "Fixture repos: "
            + ", ".join(f"`{r}` ({n} tasks)" for r, n in sorted(repos.items()))
            + "."
        )
    else:
        L.append(f"Fixture repos: task file not found at render time; {TODO} list them.")
    L += [
        "",
        "Grading is deterministic: a cell passes when the hidden tests pass, the visible tests "
        "still pass, and no file outside the task's allowed paths changed. No LLM judge.",
        "",
        "### 2.4 Pre-registration and provenance",
        "",
    ]
    for label, conf, prereg in statuses:
        devs = prereg.get("deviations") or []
        state = "confirmatory" if conf else "exploratory"
        L.append(f"- `{label}`: **{state}**" + (f"; deviations: {'; '.join(devs)}" if devs else ""))
    L.append("")
    prov_rows = []
    for label, r in zip(labels, runs, strict=True):
        m = r["meta"]
        cli = m.get("cli_versions") or {}
        prov_rows.append(
            [
                f"`{label}`",
                f"`{str(m.get('taskset_sha256', '-'))[:16]}`",
                f"`{str(m.get('config_sha256', '-'))[:16]}`",
                f"`{str(m.get('git_sha', '-'))[:12]}`",
                "; ".join(f"{k} {v}" for k, v in sorted(cli.items())) or "-",
                str(m.get("started_at", "-")),
            ]
        )
    L += _table(
        ["run", "taskset_sha256", "config_sha256", "git_sha", "CLI versions", "started"],
        prov_rows,
    )
    L += ["", "Full hashes are in section 6.", "", "### 2.5 Models actually resolved", ""]
    L.append(
        "Per candidate, the model id each session reported (from `sessions.jsonl`), so alias "
        "drift is visible:"
    )
    L.append("")
    L += _resolved_models_table(meta, sessions)
    L += [
        "",
        "### 2.6 Pricing and billing",
        "",
        "Every session is priced at list price from `src/model_routing/data/pricing.toml` "
        "(uncached input, cache read, cache write, output). Setup sessions that seed a parent "
        "context are a sunk cost: reported, excluded from the headline. Router calls are billed "
        "to the task. `C1_inline` bills only the pick's marginal tokens (chars/4); section 4.1 "
        "re-bills its whole brief-writing turn.",
    ]
    reported = sum(1 for s in sessions if s.get("cost_usd_reported") is not None)
    L.append(
        f"{reported} of {len(sessions)} sessions carried a CLI-reported cost for cross-checking."
    )
    L += ["", "### 2.7 Intention to treat and errors", ""]
    L.append(
        "Every planned (task, policy, trial) cell counts once. Provider errors are graded on "
        "whatever state the sandbox is in, and their cost counts."
    )
    L.append("")
    err_rows = []
    for p in policies:
        cells = [o for o in outcomes if o["policy"] == p["name"]]
        errored = sum(1 for o in cells if int(o.get("errors", 0)) > 0)
        err_rows.append([p["name"], str(len(cells)), str(errored), _pct(p.get("error_rate"), 1)])
    L += _table(
        ["policy", "cells", "cells with errors", "error rate"], err_rows, ["l", "r", "r", "r"]
    )
    err_sessions = sum(1 for s in sessions if s.get("errored"))
    L += ["", f"Sessions ending in a provider error: {err_sessions} of {len(sessions)}.", ""]

    # ---- results ----------------------------------------------------------------
    L += ["## 3. Results", "", f"**{summary.get('headline', '')}**", ""]
    L += ["### 3.1 Policies", ""]
    rows = []
    for p in policies:
        rows.append(
            [
                p["name"],
                str(p["n"]),
                f"{_pct(p['pass_rate'])} ({_ci_pct(p.get('pass_ci'))})",
                _money(p["cost_per_task"]),
                f"{_money(p.get('cost_per_pass'))} ({_ci_money(p.get('cost_per_pass_ci'))})",
                _pct(p.get("router_share")),
                f"{p.get('escalation_rate', 0.0):.2f}",
                _pct(p.get("error_rate"), 1),
                f"{p.get('mean_turns', 0.0):.1f}",
            ]
        )
    L += _table(
        [
            "policy",
            "n",
            "pass rate (95% CI)",
            "cost/task",
            "cost/completed task (95% CI)",
            "router share",
            "escalations/cell",
            "error rate",
            "mean turns",
        ],
        rows,
        ["l", "r", "r", "r", "r", "r", "r", "r", "r"],
    )
    L += [
        "",
        "Intervals: 95% task-clustered bootstrap (trials of a task resampled together).",
        "",
        "### 3.2 Comparisons",
        "",
    ]
    rows = []
    for c in comps:
        rows.append(
            [
                c["id"],
                c.get("role", "-"),
                f"{c['treatment']} vs {c['control']}",
                str(c["n_paired"]),
                f"{c['saving_pct']:.0f}% ({c['saving_ci'][0]:.0f} to {c['saving_ci'][1]:.0f})",
                _p(c.get("p_saving")),
                _p(c.get("p_adjusted")),
                f"{c['delta_pass_pp']:+.1f} ({c['delta_pass_ci'][0]:+.1f} to "
                f"{c['delta_pass_ci'][1]:+.1f})",
                _p(c.get("p_pass")),
                _p(c.get("p_noninf")),
                c["verdict"],
            ]
        )
    L += _table(
        [
            "id",
            "role",
            "comparison",
            "n paired",
            "saving (95% CI)",
            "p_saving",
            "p_adj",
            "delta pass pts (95% CI)",
            "p_pass",
            "p_noninf",
            "verdict",
        ],
        rows,
        ["l", "l", "l", "r", "r", "r", "r", "r", "r", "r", "l"],
    )
    L += [
        "",
        "p_saving / p_pass: two-sided task-clustered permutation tests; p_noninf: one-sided "
        "bootstrap p for 'worse by at least the margin'; p_adj: Holm-adjusted p_saving across "
        "the secondary (exploratory) hypotheses. Only H-D1 is confirmatory.",
        "",
        f"Power: {summary.get('power_note', '-')}",
        "",
        f"{TODO} interpret the primary result and each secondary one in a sentence.",
        "",
        "### 3.3 Pass rate by measured difficulty",
        "",
    ]
    L += _pass_rate_section(outcomes, policy_names, "difficulty")
    L += ["", "### 3.4 Pass rate by task category", ""]
    L += _pass_rate_section(outcomes, policy_names, "category")
    L += ["", "### 3.5 Router overhead", ""]
    L += _router_overhead(outcomes, policy_names)
    L += ["", "### 3.6 Oracle bound", ""]
    L += _oracle_section(summary, comps, treat, ctrl)
    L += ["", "### 3.7 Model mix chosen by routing policies", ""]
    L += _model_mix(outcomes, policy_names, kinds)
    L += ["", "### 3.8 Cost vs pass rate (Pareto view)", ""]
    L += _pareto_section(policies, summary.get("oracle"), _upper_bounds(meta))

    # ---- robustness ---------------------------------------------------------------
    L += ["", "## 4. Robustness", ""]
    L += _robustness(meta, outcomes, treat, ctrl, h_d1)

    # ---- threats --------------------------------------------------------------------
    L += ["", "## 5. Threats to validity", ""]
    L += _threats(meta, runs, statuses, sessions, outcomes, fake, pooled)

    # ---- reproducibility -----------------------------------------------------------
    L += ["", "## 6. Reproducibility", ""]
    L += _reproducibility(runs, labels)

    # ---- appendix ---------------------------------------------------------------------
    L += ["", "## Appendix A. Per-task pass/fail matrix", ""]
    L += _matrix(outcomes, policy_names, pooled)
    return L


# --------------------------------------------------------------------------
# section helpers
# --------------------------------------------------------------------------


def _task_repos(runs: list[dict[str, Any]], task_ids: set[str]) -> dict[str, int]:
    repo_of: dict[str, str] = {}
    for r in runs:
        path = r["meta"].get("tasks")
        if not path:
            continue
        p = Path(path)
        if not p.is_absolute():
            p = REPO_ROOT / p
        for row in _load_jsonl(p) if p.is_file() else []:
            if row.get("id") in task_ids and row.get("repo"):
                repo_of.setdefault(row["id"], str(row["repo"]))
    return dict(Counter(repo_of.values()))


def _resolved_models_table(meta: dict[str, Any], sessions: list[dict[str, Any]]) -> list[str]:
    by_cand: dict[str, Counter[str]] = defaultdict(Counter)
    roles: dict[str, Counter[str]] = defaultdict(Counter)
    for s in sessions:
        cand = str(s.get("candidate") or "-")
        by_cand[cand][str(s.get("resolved_model") or s.get("model") or "unreported")] += 1
        roles[cand][str(s.get("role") or "-")] += 1
    if not by_cand:
        return ["No sessions recorded."]
    rows = []
    configured = meta.get("candidates") or {}
    for cand in sorted(by_cand):
        cfg = configured.get(cand) or {}
        conf = f"{cfg.get('provider', '?')}:{cfg.get('model', '?')}"
        if cfg.get("effort"):
            conf += f" (effort {cfg['effort']})"
        rows.append(
            [
                f"`{cand}`",
                conf if cfg else "-",
                ", ".join(f"`{m}` x{n}" for m, n in sorted(by_cand[cand].items())),
                ", ".join(f"{r} {n}" for r, n in sorted(roles[cand].items())),
            ]
        )
    return _table(["candidate", "configured", "resolved model ids (sessions)", "roles"], rows)


def _pass_rate_section(
    outcomes: list[dict[str, Any]], policy_names: list[str], field: str
) -> list[str]:
    groups, counts = _pass_table(outcomes, policy_names, field)
    rows = []
    for g in groups:
        row = [g]
        for name in policy_names:
            n, k = counts.get((g, name), (0, 0))
            row.append(f"{k}/{n} ({k / n:.0%})" if n else "-")
        rows.append(row)
    return _table([field, *policy_names], rows, ["l"] + ["r"] * len(policy_names))


def _router_overhead(outcomes: list[dict[str, Any]], policy_names: list[str]) -> list[str]:
    rows = []
    for name in policy_names:
        cells = [o for o in outcomes if o["policy"] == name]
        router = sum(float(o.get("router_cost_usd", 0.0)) for o in cells)
        if router <= 0:
            continue
        total = sum(float(o.get("cost_usd", 0.0)) for o in cells)
        full = sum(float(o.get("cost_usd_full", o.get("cost_usd", 0.0))) for o in cells)
        full_router = router + (full - total)
        rows.append(
            [
                name,
                _money(router / len(cells)),
                _pct(router / total if total else None),
                _pct(full_router / full if full else None),
            ]
        )
    if not rows:
        return ["No policy in this run paid for a router call."]
    return [
        *_table(
            ["policy", "router cost/cell", "router share (as billed)", "router share (full turn)"],
            rows,
            ["l", "r", "r", "r"],
        ),
        "",
        "The full-turn column bills the whole recorded router turn (`cost_usd_full`); it only "
        "differs for policies that bill marginal pick tokens (`C1_inline`).",
    ]


def _oracle_section(
    summary: dict[str, Any], comps: list[dict[str, Any]], treat: str, ctrl: str
) -> list[str]:
    oracle = summary.get("oracle")
    if not oracle:
        return ["No `static_*` policies ran, so no oracle bound is computed."]
    out = [
        "The oracle takes, per (task, trial), the cheapest `static_*` policy that passed "
        "(computed in hindsight, not deployable): pass rate "
        f"{_pct(oracle['pass_rate'])}, cost per completed task "
        f"{_money(oracle.get('cost_per_pass'))}.",
    ]
    h_d7 = next((c for c in comps if c["id"] == "H-D7"), None)
    h_d1 = next((c for c in comps if c["id"] == "H-D1"), None)
    if h_d7:
        out.append(
            f"Oracle vs `{ctrl}`: saving {h_d7['saving_pct']:.0f}% (95% CI "
            f"{h_d7['saving_ci'][0]:.0f}% to {h_d7['saving_ci'][1]:.0f}%)."
        )
        if h_d1 and h_d7["saving_pct"] > 0:
            out.append(
                f"`{treat}` recovers {h_d1['saving_pct'] / h_d7['saving_pct']:.0%} of the "
                "oracle's saving (point estimates)."
            )
    return [" ".join(out)]


def _model_mix(
    outcomes: list[dict[str, Any]], policy_names: list[str], kinds: dict[str, str]
) -> list[str]:
    rows = []
    for name in policy_names:
        cells = [o for o in outcomes if o["policy"] == name]
        mix = Counter(str(o.get("chosen_candidate") or "none") for o in cells)
        if kinds.get(name) not in ROUTING_KINDS and len(mix) < 2:
            continue
        passed = Counter(str(o.get("chosen_candidate") or "none") for o in cells if o["passed"])
        rows.append(
            [
                name,
                f"`{kinds.get(name, '?')}`",
                ", ".join(
                    f"{c} {n / len(cells):.0%} ({passed[c]}/{n} passed)"
                    for c, n in sorted(mix.items())
                ),
            ]
        )
    if not rows:
        return ["No routing policy ran."]
    return [
        *_table(["policy", "kind", "final model: share of cells (passes)"], rows),
        "",
        "For cascades the final model is the last one escalated to. The pick is the router's "
        "parsed choice only; router text is not reproduced.",
    ]


def _pareto_section(
    policies: list[dict[str, Any]], oracle: dict[str, Any] | None, upper: set[str]
) -> list[str]:
    front = _pareto(policies, upper)
    entries = [dict(p) for p in policies]
    if oracle:
        entries.append(dict(oracle, name="oracle (computed)"))
    entries.sort(
        key=lambda p: (p.get("cost_per_pass") is None, p.get("cost_per_pass") or 0.0, p["name"])
    )
    rows = [
        [
            p["name"],
            _money(p.get("cost_per_pass")),
            _pct(p["pass_rate"]),
            _money(p["cost_per_task"]),
            _pareto_label(p["name"], front, upper),
        ]
        for p in entries
    ]
    return [
        *_table(
            ["policy", "cost/completed task", "pass rate", "cost/task", "Pareto-efficient"],
            rows,
            ["l", "r", "r", "r", "l"],
        ),
        "",
        "Sorted by cost per completed task. Oracle and hidden-test cascades are upper "
        "bounds and excluded from the frontier. A policy is dominated when another deployable "
        "policy has at least its pass rate at no more cost (strictly better on one).",
        "",
        f"{TODO} figure: cost per completed task (x) vs pass rate (y), same data.",
    ]


def _pareto_label(name: str, front: set[str], upper: set[str]) -> str:
    if name.startswith("oracle"):
        return "not deployable (oracle)"
    if name in upper:
        return "not deployable (upper bound)"
    return "yes" if name in front else "dominated"


def _robustness(
    meta: dict[str, Any],
    outcomes: list[dict[str, Any]],
    treat: str,
    ctrl: str,
    h_d1: dict[str, Any] | None,
) -> list[str]:
    out = ["### 4.1 Pessimistic router billing", ""]
    marginal = _paired_point(outcomes, treat, ctrl, "cost_usd")
    full = _paired_point(outcomes, treat, ctrl, "cost_usd_full")
    if marginal is None or full is None:
        out.append(f"Not computable: no paired `{treat}`/`{ctrl}` cells.")
    else:
        rebilled = [
            dict(o, cost_usd=float(o.get("cost_usd_full", o.get("cost_usd", 0.0))))
            for o in outcomes
        ]
        pess = _resummarize(meta, rebilled)
        p_h = next((c for c in pess.get("comparisons", []) if c["id"] == "H-D1"), None)

        def fmt_saving(s: float | None) -> str:
            return "-" if s is None else f"{s:.1f}%"

        rows = [
            [
                "as billed (marginal pick tokens)",
                fmt_saving(marginal["saving"]),
                f"{h_d1['saving_ci'][0]:.0f}% to {h_d1['saving_ci'][1]:.0f}%" if h_d1 else "-",
                _p(h_d1.get("p_saving")) if h_d1 else "-",
                h_d1["verdict"] if h_d1 else "-",
            ],
            [
                "pessimistic (whole router turn, `cost_usd_full`)",
                fmt_saving(full["saving"]),
                f"{p_h['saving_ci'][0]:.0f}% to {p_h['saving_ci'][1]:.0f}%" if p_h else "-",
                _p(p_h.get("p_saving")) if p_h else "-",
                p_h["verdict"] if p_h else "-",
            ],
        ]
        out += _table(
            ["billing", f"{treat} vs {ctrl} saving", "95% CI", "p_saving", "verdict"],
            rows,
            ["l", "r", "r", "r", "l"],
        )
        out += [
            "",
            "Pass rates are unchanged by billing; only cost moves. "
            f"{TODO} say which billing a real spawner would see.",
        ]
    out += ["", "### 4.2 Excluding errored cells", ""]
    errored = [o for o in outcomes if int(o.get("errors", 0)) > 0]
    if not errored:
        out.append(
            "No cell had a provider error, so the intention-to-treat and per-protocol estimates "
            "are identical."
        )
        return out
    clean = [o for o in outcomes if int(o.get("errors", 0)) == 0]
    itt = _paired_point(outcomes, treat, ctrl)
    pp = _paired_point(clean, treat, ctrl)
    rows = []
    for label, est in (("intention to treat (all cells)", itt), ("errored cells excluded", pp)):
        if est is None:
            rows.append([label, "-", "-", "-"])
            continue
        saving = "-" if est["saving"] is None else f"{est['saving']:.1f}%"
        rows.append([label, str(est["n_paired"]), saving, f"{est['delta_pass_pp']:+.1f}"])
    out += _table(["analysis", "n paired", "saving", "delta pass pts"], rows, ["l", "r", "r", "r"])
    out += [
        "",
        f"{len(errored)} errored cell(s) excluded (paired cells drop from both arms). Point "
        f"estimates only; the confirmatory analysis is intention to treat. {TODO} comment.",
    ]
    return out


def _threats(
    meta: dict[str, Any],
    runs: list[dict[str, Any]],
    statuses: list[tuple[str, Any, dict[str, Any]]],
    sessions: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    fake: bool,
    pooled: bool,
) -> list[str]:
    orders = sorted({str(r["meta"].get("order", "unknown")) for r in runs})
    resolved = sum(1 for s in sessions if s.get("resolved_model"))
    devs = sorted({d for _, _, p in statuses for d in (p.get("deviations") or [])})
    errored = sum(1 for o in outcomes if int(o.get("errors", 0)) > 0)
    providers = sorted(
        {str(c.get("provider")) for r in runs for c in (r["meta"].get("candidates") or {}).values()}
    )
    ran = {o["policy"] for o in outcomes}
    items = [
        (
            "Clock-time / provider drift",
            "seeded randomized block order per (task, trial); sequential sessions.",
            f"order = {', '.join(orders)}.",
        ),
        (
            "Model alias drift",
            "resolved model id per session; CLI versions and git SHA in meta.json.",
            f"{resolved}/{len(sessions)} sessions report a resolved id (section 2.5).",
        ),
        (
            "Task-set or config edits after registration",
            "taskset_sha256 and config_sha256 checked against [preregistration].",
            "deviations: " + ("; ".join(devs) if devs else "none") + ".",
        ),
        (
            "Guessed difficulty labels",
            "labels measured by a calibration run (dispatch-calibration).",
            f"{TODO} cite the calibration run.",
        ),
        (
            "Brief-quality confound in routing",
            "C1_inline's worker gets the same canned brief as B.",
            "C1_inline ran." if "C1_inline" in ran else "C1_inline did not run.",
        ),
        (
            "Router overhead overstated (or understated)",
            "C1_inline bills marginal pick tokens; C1 keeps the full router call.",
            "both billings in section 4.1.",
        ),
        (
            "Selective reporting",
            "metric, margin, trials, ordering, policies fixed before the run; "
            "Holm for secondaries.",
            "pooled runs are exploratory."
            if pooled
            else ("run is confirmatory." if statuses[0][1] else "run is exploratory."),
        ),
        (
            "Silent failures",
            "provider errors graded as-is and counted (intention to treat).",
            f"{errored} errored cell(s); see sections 2.7 and 4.2.",
        ),
        (
            "External validity of synthetic tasks",
            "fixture repos written for the study, not harvested production work.",
            f"{TODO} argue how representative the tasks are.",
        ),
        (
            "chars/4 token approximation",
            "C1_inline's marginal router tokens are estimated as characters / 4.",
            f"{TODO} bound the error against a tokenizer.",
        ),
        (
            "Subscription vs API billing",
            "runs use the operator's subscription login; costs are list API prices.",
            f"{TODO} state what an API-key user or a subscription user actually pays.",
        ),
        (
            "Single vendor",
            "one model family per track; the codex track is a separate replication.",
            f"providers in this run: {', '.join(providers) or 'unknown'}.",
        ),
    ]
    if fake:
        items.insert(
            0,
            (
                "Simulated data",
                "none: the fake provider exercises the pipeline only.",
                "at least one run is fake; nothing here is evidence.",
            ),
        )
    return [
        f"- [ ] **{name}.** Control: {control} This run: {evidence} {TODO} residual risk."
        for name, control, evidence in items
    ]


def _reproducibility(runs: list[dict[str, Any]], labels: list[str]) -> list[str]:
    out: list[str] = []
    for label, r in zip(labels, runs, strict=True):
        m = r["meta"]
        names = [p.get("name") for p in m.get("policies", []) if p.get("name")]
        cmd = [
            "uv run model-routing dispatch-run",
            f"experiments/agentic/{m.get('experiment', 'exp05_dispatch')}.toml",
            f"--budget-usd {m.get('budget_usd', '<usd>')}",
        ]
        if m.get("sample"):
            cmd.append(f"--sample {m['sample']}")
        cmd.append(f"--trials {m.get('trials', 1)}")
        if names:
            cmd.append(f"--policies {','.join(names)}")
        if m.get("fake"):
            cmd.append("--fake")
        cli = m.get("cli_versions") or {}
        out += [
            f"### `{label}`",
            "",
            "```bash",
            f"git checkout {m.get('git_sha', '<git_sha>')}",
            "make setup",
            "uv run model-routing dispatch-estimate "
            f"experiments/agentic/{m.get('experiment', 'exp05_dispatch')}.toml",
            " \\\n  ".join(cmd),
            "```",
            "",
            f"- taskset_sha256: `{m.get('taskset_sha256', '-')}`",
            f"- config_sha256: `{m.get('config_sha256', '-')}` (the config as run is archived "
            "as `config.toml` in the run directory)",
            f"- git_sha: `{m.get('git_sha', '-')}`; harness {m.get('harness_version', '-')}; "
            f"Python {m.get('python', '-')}; {m.get('platform', '-')}",
            "- CLI versions: " + ("; ".join(f"{k} {v}" for k, v in sorted(cli.items())) or "-"),
            f"- seed {m.get('seed', '-')}, order {m.get('order', '-')}, "
            f"max_turns {m.get('max_turns', '-')}, started {m.get('started_at', '-')}",
            "",
        ]
    out += [
        "Rebuild the statistics and this draft:",
        "",
        "```bash",
        "make dispatch-report RUN=<run_dir>",
        'make dispatch-paper RUNS="' + " ".join(f"<{lab}>" for lab in labels) + '" OUT=<draft.md>',
        "```",
    ]
    return out


def _matrix(outcomes: list[dict[str, Any]], policy_names: list[str], pooled: bool) -> list[str]:
    cells: dict[tuple[str, str], dict[str, list[tuple[int, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for o in outcomes:
        mark = "P" if o["passed"] else "F"
        if int(o.get("errors", 0)) > 0:
            mark += "!"
        cells[(str(o.get("run", "")), o["task_id"])][o["policy"]].append((int(o["trial"]), mark))
    header = (["run"] if pooled else []) + ["task", "difficulty", *policy_names]
    diff = {o["task_id"]: str(o.get("difficulty") or "unknown") for o in outcomes}
    rows = []
    for (run, task), by_policy in sorted(cells.items()):
        row = ([run] if pooled else []) + [task, diff.get(task, "unknown")]
        for name in policy_names:
            marks = [m for _, m in sorted(by_policy.get(name, []))]
            row.append(" ".join(marks) if marks else "-")
        rows.append(row)
    return [
        "One mark per trial, in trial order: P = passed, F = failed, ! = the cell had a "
        "provider error (graded as-is).",
        "",
        *_table(header, rows),
    ]
