"""Measured task difficulty from calibration runs, and pre-registration blocks.

``calibration_table(run_dirs)`` folds one or more *real* dispatch runs into a
per-task table of pass rates by candidate model (every ``spawn_static`` and
cascade first-attempt counts as a sample for the model that ran it).  The
human ``difficulty`` labels in ``tasks.jsonl`` did not track what models
find hard (2026-09-22 pilot: the cheapest model passed 8/8 "hard" tasks), so
the confirmatory run stratifies on *measured* labels instead:

* ``easy``   - the cheapest candidate passed every trial
* ``medium`` - the cheapest candidate passed some but not all trials, or
               passed none while a mid-tier candidate passed
* ``hard``   - no candidate below the strongest one ever passed
* ``unsolved`` - nothing passed (flagged; probably a task defect)

``relabel_tasks(path, table)`` rewrites ``difficulty`` in the JSONL in place
and records the measured rates under a ``measured`` key so the label's
provenance is in the file.  ``preregistration_block(cfg, ...)`` renders the
``[preregistration]`` TOML table the report checks a confirmatory run against.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from model_routing.dispatch.runner import DispatchConfig, taskset_sha256

_TIER_ORDER = ("haiku", "luna", "sonnet", "terra", "opus", "sol", "fable")


def _tier(candidate: str) -> int:
    low = candidate.lower()
    for i, key in enumerate(_TIER_ORDER):
        if key in low:
            return i
    return len(_TIER_ORDER)


def calibration_table(run_dirs: list[str | Path]) -> dict[str, dict[str, Any]]:
    """``{task_id: {"by_candidate": {cand: {"n", "passes"}}, "difficulty": ...}}``.

    Only outcomes whose policy is a single fresh session on a fixed candidate
    contribute (``static*`` policies, and the first attempt of a cascade via
    its ``chosen_candidate`` when it never escalated), so the measurement is of
    the *model*, not of a router.  Fake runs are refused.
    """
    by_task: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for run_dir in run_dirs:
        run_dir = Path(run_dir)
        meta_path = run_dir / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        if meta.get("fake"):
            raise ValueError(f"{run_dir}: fake run; calibration needs real model outcomes")
        outcomes_path = run_dir / "outcomes.jsonl"
        if not outcomes_path.exists():
            continue
        with outcomes_path.open() as f:
            for line in f:
                if not line.strip():
                    continue
                o = json.loads(line)
                policy = str(o.get("policy", ""))
                cand = o.get("chosen_candidate")
                if not cand:
                    continue
                static = policy.startswith("static")
                cascade_first = (
                    int(o.get("escalations", 0)) == 0
                    and any(s.get("role") == "worker" for s in o.get("sessions", []))
                    and policy in ("D", "D_ideal")
                )
                if not (static or cascade_first):
                    continue
                cell = by_task[o["task_id"]][cand]
                cell[0] += 1
                cell[1] += int(bool(o.get("passed")))
    table: dict[str, dict[str, Any]] = {}
    for task_id, cands in by_task.items():
        by_cand = {
            c: {"n": n, "passes": p, "pass_rate": (p / n if n else 0.0)}
            for c, (n, p) in sorted(cands.items(), key=lambda kv: _tier(kv[0]))
        }
        table[task_id] = {"by_candidate": by_cand, "difficulty": _measured_label(by_cand)}
    return table


def _measured_label(by_cand: dict[str, dict[str, Any]]) -> str:
    if not by_cand:
        return "unknown"
    ordered = sorted(by_cand.items(), key=lambda kv: _tier(kv[0]))
    cheapest, cheapest_stats = ordered[0]
    if cheapest_stats["n"] and cheapest_stats["passes"] == cheapest_stats["n"]:
        return "easy"
    if cheapest_stats["passes"] > 0:
        return "medium"
    below_strongest = ordered[:-1] if len(ordered) > 1 else ordered
    if any(stats["passes"] > 0 for _, stats in below_strongest[1:]):
        return "medium"
    if any(stats["passes"] > 0 for _, stats in ordered):
        return "hard"
    return "unsolved"


def relabel_tasks(tasks_path: str | Path, table: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Rewrite ``difficulty`` (and a ``measured`` provenance field) for every task
    in ``table``; tasks without calibration data are left untouched.  Returns
    ``{"relabelled": n, "unchanged": m, "uncalibrated": k}``."""
    tasks_path = Path(tasks_path)
    lines = tasks_path.read_text().splitlines()
    out: list[str] = []
    counts = {"relabelled": 0, "unchanged": 0, "uncalibrated": 0}
    stamp = datetime.now(UTC).date().isoformat()
    for line in lines:
        if not line.strip() or line.startswith("#"):
            out.append(line)
            continue
        raw = json.loads(line)
        entry = table.get(raw.get("id"))
        if entry is None or entry["difficulty"] in ("unknown", "unsolved"):
            counts["uncalibrated"] += 1
            out.append(line)
            continue
        new_label = entry["difficulty"]
        raw["measured"] = {
            "labelled_on": stamp,
            "pass_rates": {c: s["pass_rate"] for c, s in entry["by_candidate"].items()},
            "n": {c: s["n"] for c, s in entry["by_candidate"].items()},
        }
        if raw.get("difficulty") != new_label:
            raw["difficulty_human"] = raw.get("difficulty", "unknown")
            raw["difficulty"] = new_label
            counts["relabelled"] += 1
        else:
            counts["unchanged"] += 1
        out.append(json.dumps(raw, ensure_ascii=False))
    tasks_path.write_text("\n".join(out) + "\n")
    return counts


def render_calibration(table: dict[str, dict[str, Any]]) -> str:
    cands: list[str] = []
    for entry in table.values():
        for c in entry["by_candidate"]:
            if c not in cands:
                cands.append(c)
    cands.sort(key=_tier)
    header = "| task | " + " | ".join(cands) + " | measured |"
    lines = [header, "|---|" + "---:|" * len(cands) + "---|"]
    for task_id, entry in sorted(table.items()):
        cells = []
        for c in cands:
            s = entry["by_candidate"].get(c)
            cells.append(f"{s['passes']}/{s['n']}" if s else "-")
        lines.append(f"| {task_id} | " + " | ".join(cells) + f" | {entry['difficulty']} |")
    hist: dict[str, int] = defaultdict(int)
    for entry in table.values():
        hist[entry["difficulty"]] += 1
    lines += ["", "Measured labels: " + ", ".join(f"{k}={v}" for k, v in sorted(hist.items()))]
    cheapest = cands[0] if cands else None
    if cheapest:
        n = sum(e["by_candidate"].get(cheapest, {}).get("n", 0) for e in table.values())
        p = sum(e["by_candidate"].get(cheapest, {}).get("passes", 0) for e in table.values())
        if n:
            lines.append(
                f"Cheapest candidate ({cheapest}) pass rate over the set: {p}/{n} = {p / n:.0%}. "
                "Target for routing headroom: about 50-70%."
            )
    return "\n".join(lines) + "\n"


def preregistration_block(
    cfg: DispatchConfig,
    *,
    n_tasks: int | None = None,
    doc: str = "docs/experiments/preregistration-exp05.md",
    now: datetime | None = None,
) -> str:
    """The ``[preregistration]`` TOML table freezing this config's design against
    the current task set.  Paste it into the experiment TOML *before* the
    confirmatory run; the report then checks the run against it."""
    stamp = (now or datetime.now(UTC)).replace(microsecond=0).isoformat()
    if n_tasks is None:
        n_tasks = sum(1 for line in cfg.tasks.open() if line.strip() and not line.startswith("#"))
    treatment = cfg.primary.get("treatment", "C1")
    control = cfg.primary.get("control", "B")
    return (
        "[preregistration]\n"
        f'registered_at = "{stamp}"\n'
        f'doc = "{doc}"\n'
        f'taskset_sha256 = "{taskset_sha256(cfg.tasks)}"\n'
        f"n_tasks = {n_tasks}\n"
        f"trials = {cfg.trials}\n"
        f"margin_pp = {cfg.margin_pp:g}\n"
        f'order = "{cfg.order}"\n'
        f'primary = {{ treatment = "{treatment}", control = "{control}" }}\n'
    )
