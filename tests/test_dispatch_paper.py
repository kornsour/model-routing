import json
from pathlib import Path
from typing import Any

from model_routing.cli import main
from model_routing.dispatch.paper import TODO, render_paper
from model_routing.dispatch.report import summarize

SECRET = "SECRET-MODEL-OUTPUT-do-not-publish"

# task -> (difficulty, category)
TASKS = {
    "t1": ("easy", "feature"),
    "t2": ("easy", "bugfix"),
    "t3": ("hard", "bugfix"),
    "t4": ("hard", "refactor"),
    "t5": ("medium", "feature"),
}
# (policy, candidate, cost, cost_full, router_cost) per cell
POLICIES = {
    "B": ("opus", 1.0, 1.0, 0.0),
    "C1_inline": ("haiku", 0.4, 0.9, 0.05),
    "static_haiku": ("haiku", 0.3, 0.3, 0.0),
    "static_sonnet": ("sonnet", 0.6, 0.6, 0.0),
}


def _passes(policy: str, task: str, trial: int) -> bool:
    if policy == "static_haiku":
        return TASKS[task][0] == "easy"
    if policy == "C1_inline":
        return not (task == "t4" and trial == 1)
    return True


def _session(task: str, policy: str, trial: int, role: str, cand: str, cost: float) -> dict:
    return {
        "task_id": task,
        "policy": policy,
        "trial": trial,
        "role": role,
        "candidate": cand,
        "provider": "claude_cli",
        "model": cand,
        "resolved_model": f"claude-{cand}-test",
        "cost_usd_list": cost,
        "cost_usd_reported": None,
        "error": None,
        "output": f"{SECRET} {policy} {task}",
    }


def _write_run(tmp_path: Path, name: str, *, error_cell: bool = True) -> Path:
    out = tmp_path / name
    out.mkdir(parents=True)
    outcomes: list[dict[str, Any]] = []
    sessions: list[dict[str, Any]] = []
    for task, (difficulty, category) in TASKS.items():
        for trial in range(2):
            for policy, (cand, cost, full, router) in POLICIES.items():
                errored = error_cell and policy == "B" and task == "t5" and trial == 1
                cell_sessions = [_session(task, policy, trial, "worker", cand, cost - router)]
                if router:
                    cell_sessions.append(_session(task, policy, trial, "router", "opus", full))
                if errored:
                    cell_sessions[0]["error"] = f"timeout {SECRET}"
                sessions += cell_sessions
                outcomes.append(
                    {
                        "task_id": task,
                        "policy": policy,
                        "trial": trial,
                        "passed": _passes(policy, task, trial),
                        "difficulty": difficulty,
                        "category": category,
                        "chosen_candidate": cand,
                        "escalations": 0,
                        "cost_usd": cost,
                        "cost_usd_full": full,
                        "errors": 1 if errored else 0,
                        "setup_cost_usd": 0.0,
                        "router_cost_usd": router,
                        "turns": 3,
                        "grade_detail": f"pytest said {SECRET}",
                        "files_changed": ["src/secret_file.py"],
                        "sessions": cell_sessions,
                    }
                )
    meta = {
        "experiment": "exp05_dispatch",
        "hypothesis": "C1_inline is cheaper than B.",
        "primary": {"treatment": "C1_inline", "control": "B"},
        "margin_pp": 10.0,
        "git_sha": "abc123def4567890",
        "config_sha256": "c" * 64,
        "taskset_sha256": "d" * 64,
        "harness_version": "0.1.0",
        "python": "3.12.0",
        "platform": "test",
        "n_tasks": len(TASKS),
        "trials": 2,
        "order": "randomized",
        "seed": 7,
        "max_turns": 40,
        "preregistration": None,
        "sample": None,
        "budget_usd": 5.0,
        "fake": False,
        "parent": "opus",
        "menu": ["haiku", "sonnet", "opus"],
        "candidates": {
            c: {"name": c, "provider": "claude_cli", "model": c, "effort": None}
            for c in ("haiku", "sonnet", "opus")
        },
        "policies": [
            {"name": "B", "kind": "spawn_static", "candidate": "opus"},
            {"name": "C1_inline", "kind": "spawn_parent_pick_inline"},
            {"name": "static_haiku", "kind": "spawn_static", "candidate": "haiku"},
            {"name": "static_sonnet", "kind": "spawn_static", "candidate": "sonnet"},
        ],
        "cli_versions": {"claude_cli": "9.9.9 (Claude Code)"},
        "started_at": "2026-09-23T00:00:00+00:00",
    }
    (out / "meta.json").write_text(json.dumps(meta))
    with (out / "outcomes.jsonl").open("w") as f:
        for o in outcomes:
            f.write(json.dumps(o) + "\n")
    with (out / "sessions.jsonl").open("w") as f:
        for s in sessions:
            f.write(json.dumps(s) + "\n")
    summarize(out)
    return out


def _saving(treat: str, ctrl: str, cost_key: str, run: Path) -> float:
    rows = [json.loads(line) for line in (run / "outcomes.jsonl").read_text().splitlines()]

    def cpt(policy: str) -> float:
        cells = [r for r in rows if r["policy"] == policy]
        return sum(r[cost_key] for r in cells) / sum(r["passed"] for r in cells)

    return (1 - cpt(treat) / cpt(ctrl)) * 100


def test_paper_has_every_section_and_key_numbers(tmp_path: Path):
    run = _write_run(tmp_path, "run1")
    out = render_paper([run], out=tmp_path / "draft.md")
    text = out.read_text()
    for heading in (
        "## Abstract",
        "## 1. Background and question",
        "## 2. Methods",
        "### 2.3 Task set",
        "### 2.4 Pre-registration and provenance",
        "### 2.5 Models actually resolved",
        "### 2.7 Intention to treat and errors",
        "## 3. Results",
        "### 3.2 Comparisons",
        "### 3.3 Pass rate by measured difficulty",
        "### 3.4 Pass rate by task category",
        "### 3.5 Router overhead",
        "### 3.6 Oracle bound",
        "### 3.7 Model mix chosen by routing policies",
        "### 3.8 Cost vs pass rate (Pareto view)",
        "## 4. Robustness",
        "## 5. Threats to validity",
        "## 6. Reproducibility",
        "## Appendix A. Per-task pass/fail matrix",
    ):
        assert heading in text, heading
    assert TODO in text
    assert "EXPLORATORY" in text
    assert "no [preregistration] table in the config" in text

    summary = json.loads((run / "summary.json").read_text())
    h_d1 = next(c for c in summary["comparisons"] if c["id"] == "H-D1")
    assert summary["headline"] in text
    assert f"saving {h_d1['saving_pct']:.0f}%" in text
    assert "| H-D1 | primary | C1_inline vs B |" in text
    assert "non-inferiority margin 10 pts" in text
    # 5 tasks: 2 easy, 1 medium, 2 hard.
    assert "| easy | 2 | ## |" in text
    assert "| medium | 1 | # |" in text
    assert "| hard | 2 | ## |" in text
    # static_haiku passes only easy tasks: 0/4 on hard.
    assert "| hard | 4/4 (100%) | 3/4 (75%) | 0/4 (0%) | 4/4 (100%) |" in text
    # Resolved model ids come from sessions.jsonl.
    assert "`claude-haiku-test` x" in text
    # Provenance and reproducibility.
    assert "d" * 64 in text and "c" * 64 in text and "abc123def4567890" in text
    assert "9.9.9 (Claude Code)" in text
    assert "--trials 2" in text and "--policies B,C1_inline,static_haiku,static_sonnet" in text
    # Appendix: C1_inline failed t4 on trial 1 only.
    t4 = next(line for line in text.splitlines() if line.startswith("| t4 |"))
    assert t4 == "| t4 | hard | P P | P F | F F | P P |"
    # Errored cell is flagged and counted.
    t5 = next(line for line in text.splitlines() if line.startswith("| t5 |"))
    assert "P P!" in t5
    assert "| B | 10 | 1 | 10.0% |" in text


def test_robustness_rebills_c1_inline_and_drops_errored_cells(tmp_path: Path):
    run = _write_run(tmp_path, "run1")
    text = render_paper([run], out=tmp_path / "draft.md").read_text()
    marginal = _saving("C1_inline", "B", "cost_usd", run)
    pessimistic = _saving("C1_inline", "B", "cost_usd_full", run)
    assert marginal != pessimistic
    assert f"| as billed (marginal pick tokens) | {marginal:.1f}% |" in text
    assert f"| pessimistic (whole router turn, `cost_usd_full`) | {pessimistic:.1f}% |" in text
    # Per-protocol: the errored B cell (t5 trial 1) drops from both arms.
    assert "| errored cells excluded | 9 |" in text
    assert "| intention to treat (all cells) | 10 |" in text
    # Router overhead: C1_inline share as billed vs the full recorded turn.
    assert "| C1_inline | $0.0500 | 12% |" in text


def test_paper_never_includes_model_output(tmp_path: Path):
    run = _write_run(tmp_path, "run1")
    text = render_paper([run], out=tmp_path / "draft.md").read_text()
    assert SECRET not in text
    assert "secret_file" not in text


def test_paper_is_deterministic(tmp_path: Path):
    run = _write_run(tmp_path, "run1")
    a = render_paper([run], out=tmp_path / "a.md").read_text()
    b = render_paper([run], out=tmp_path / "b.md").read_text()
    assert a == b


def test_pooled_runs_add_run_column_and_are_exploratory(tmp_path: Path):
    r1 = _write_run(tmp_path / "x", "20260901", error_cell=False)
    r2 = _write_run(tmp_path / "y", "20260902", error_cell=False)
    text = render_paper([r1, r2], out=tmp_path / "pooled.md").read_text()
    assert "Pooled analysis of 2 runs" in text
    assert "| run | task | difficulty | B |" in text
    assert "| 20260901 | t1 |" in text and "| 20260902 | t1 |" in text
    # Pooled pairs: 5 tasks x 2 trials x 2 runs.
    assert "| H-D1 | primary | C1_inline vs B | 20 |" in text
    assert "No cell had a provider error" in text


def test_cli_dispatch_paper(tmp_path: Path, capsys):
    run = _write_run(tmp_path, "run1")
    out = tmp_path / "findings" / "draft.md"
    assert main(["dispatch-paper", str(run), "--out", str(out)]) == 0
    assert out.is_file()
    assert "paper draft:" in capsys.readouterr().out
