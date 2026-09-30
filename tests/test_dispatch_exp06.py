"""exp06 analysis on synthetic run directories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from model_routing.dispatch import exp06


def outcome(
    task: str,
    policy: str,
    trial: int,
    passed: bool,
    cost: float,
    *,
    handoff: str | None = None,
    advisor: int = 0,
    capped: bool = False,
    verifier_ok: bool | None = None,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = [{"event": "worker", "advisor_calls": advisor}]
    if verifier_ok is not None:
        events.append({"event": "verifier", "ok": verifier_ok, "reason": ""})
    sessions = [
        {
            "role": "worker",
            "num_turns": 40 if capped else 5,
            "error": "Reached maximum number of turns (40)" if capped else None,
            "raw": {"advisor_calls": advisor, "other_model_cost_usd": 0.1 * advisor},
            "headline_cost_usd": cost,
        }
    ]
    if handoff:
        events.append({"event": "handoff", "trigger": handoff, "mode": "clean"})
        sessions.append({"role": "escalation", "headline_cost_usd": 0.0, "raw": {}})
    return {
        "task_id": task,
        "policy": policy,
        "trial": trial,
        "passed": passed,
        "cost_usd": cost,
        "escalations": int(bool(handoff)),
        "cascade_checks": events,
        "sessions": sessions,
    }


def write_run(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.mkdir(parents=True)
    (path / "outcomes.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


# Sonnet / Opus pass patterns per task over 3 trials.
PATTERNS = {
    "easy1": ([1, 1, 1], [1, 1, 1]),
    "easy2": ([1, 1, 1], [1, 1, 0]),
    "hard1": ([0, 0, 1], [1, 1, 1]),
    "hard2": ([0, 0, 0], [1, 1, 0]),
    "med1": ([1, 1, 0], [1, 1, 1]),
    "uns1": ([0, 0, 0], [0, 1, 0]),
}


@pytest.fixture
def runs(tmp_path: Path) -> tuple[Path, Path]:
    cal: list[dict[str, Any]] = []
    for t, (s, o) in PATTERNS.items():
        for i in range(3):
            cal.append(outcome(t, "static_sonnet", i + 1, bool(s[i]), 0.2))
            cal.append(outcome(t, "static_opus", i + 1, bool(o[i]), 1.0))
    lad: list[dict[str, Any]] = []
    for t, (s, o) in PATTERNS.items():
        for i in range(3):
            need = not s[i]
            lad.append(
                outcome(
                    t,
                    "ladder",
                    i + 1,
                    bool(o[i]) if need else True,
                    1.3 if need else 0.35,
                    handoff="verifier" if need else None,
                    advisor=1,
                    verifier_ok=not need,
                )
            )
    return write_run(tmp_path / "cal", cal), write_run(tmp_path / "lad", lad)


@pytest.mark.parametrize(
    "mid,frontier,expected",
    [
        (3, 0, "easy"),
        (3, 3, "easy"),
        (1, 2, "hard"),
        (0, 3, "hard"),
        (2, 3, "medium"),
        (2, 0, "medium"),
        (1, 1, "unsolved"),
        (0, 1, "unsolved"),
        (0, 0, "unsolved"),
    ],
)
def test_labels(mid: int, frontier: int, expected: str):
    assert exp06.label(mid, frontier) == expected


def test_table_and_h0(runs: tuple[Path, Path]):
    cells = exp06.load_cells([runs[0]])
    table = exp06.task_table(cells)
    assert {t: r["label"] for t, r in table.items()} == {
        "easy1": "easy",
        "easy2": "easy",
        "hard1": "hard",
        "hard2": "hard",
        "med1": "medium",
        "uns1": "unsolved",
    }
    gate = exp06.h0(table)
    assert gate["hard"] == 2 and gate["required"] == 10 and not gate["met"]
    assert gate["registered_set"] == 5
    assert gate["hard_share"] == pytest.approx(0.4)


def test_perfect_trigger_and_oracle(runs: tuple[Path, Path]):
    cells = exp06.load_cells([runs[0]])
    pt = exp06.perfect_trigger(cells)
    assert pt[("hard1", 1)]["cost"] == pytest.approx(1.2) and pt[("hard1", 1)]["passed"]
    assert pt[("hard1", 3)]["cost"] == pytest.approx(0.2)
    assert pt[("easy1", 1)]["passed"] and not pt[("easy1", 1)]["handoff"]
    orc = exp06.oracle(cells)
    assert orc[("easy2", 1)]["cost"] == pytest.approx(0.2)  # sonnet cheaper and passes
    assert orc[("hard2", 1)]["cost"] == pytest.approx(1.0)  # only opus has a majority
    per_trial = exp06.oracle(cells, per_trial=True)
    assert per_trial[("hard1", 3)]["cost"] == pytest.approx(0.2)
    assert per_trial[("hard2", 3)]["cost"] == pytest.approx(0.2)  # nobody passed: cheapest


def test_random_matched(runs: tuple[Path, Path]):
    cells = exp06.load_cells([runs[0]])
    rm = exp06.random_matched(cells, 0.0, ["easy1", "hard1"], draws=10)
    assert rm["handoffs"] == 0 and rm["pass_rate"] == pytest.approx(4 / 6)
    full = exp06.random_matched(cells, 1.0, ["easy1", "hard1"], draws=10)
    assert full["pass_rate"] == pytest.approx(1.0)
    assert full["cpt"] == pytest.approx(6 * 1.2 / 6)


def test_escalation_quality_and_verifier(runs: tuple[Path, Path]):
    cells = exp06.load_cells([runs[0], runs[1]])
    table = exp06.task_table(cells)
    q = exp06.escalation_quality(cells["ladder"], cells, table)
    per_trial = q["trial"]
    # Sonnet failed 9 of 18 cells; the ladder handed off exactly those.
    assert per_trial["needed"] == 9 and per_trial["cells"] == 18
    assert per_trial["handoff"]["recall"] == 1.0 and per_trial["handoff"]["precision"] == 1.0
    assert per_trial["advisor"]["fired"] == 18
    assert per_trial["advisor"]["precision"] == pytest.approx(0.5)
    v = exp06.verifier_accuracy(cells["ladder"])
    assert v["accepted"] == 9 and v["false_accepts"] == 0


def test_analyze_and_render(runs: tuple[Path, Path]):
    result = exp06.analyze([runs[0]], [runs[1]])
    assert result["ladder_arms"] == ["ladder"]
    c = result["comparisons"]["ladder"]
    d, _ = c["hard_pass_diff_vs_mid"]
    assert d == pytest.approx(100 * (5 / 6 - 1 / 6))
    assert set(c["L1"]) == {"condition_1", "condition_2", "condition_3", "overall"}
    reg = result["stats"]["registered"]
    assert reg["static_sonnet"]["tasks"] == 5
    assert reg["perfect_trigger"]["handoffs"] > 0
    text = exp06.render(result)
    assert "H0 **not met**" in text and "| ladder |" in text
    out = runs[0].parent / "a.md"
    assert (
        exp06.main(["--calibration", str(runs[0]), "--ladder", str(runs[1]), "--out", str(out)])
        == 0
    )
    assert out.read_text().startswith("# exp06 analysis")


def test_bootstrap_needs_enough_finite_draws():
    point, ci = exp06._bootstrap([], lambda s: None)
    assert point is None and ci is None
    point, ci = exp06._bootstrap(["a", "b"], lambda s: 1.0, draws=50)
    assert point == 1.0 and ci == [1.0, 1.0]


def test_verdicts():
    assert exp06._verdict_above([11, 30], 10) == "supported"
    assert exp06._verdict_above([-5, 9], 10) == "not supported"
    assert exp06._verdict_above([5, 30], 10) == "inconclusive"
    assert exp06._verdict_below([0.5, 0.9], 1.0) == "supported"
    assert exp06._verdict_below([1.1, 2.0], 1.0) == "not supported"
    assert exp06._verdict_below(None, 1.0) == "inconclusive"


def test_labels_come_from_calibration_even_when_the_ladder_reruns_a_static_arm(tmp_path: Path):
    cal = [outcome("t", "static_sonnet", i, i != 1, 0.2) for i in range(3)]
    cal += [outcome("t", "static_opus", i, True, 1.0) for i in range(3)]
    lad = [outcome("t", "static_sonnet", i, True, 0.3) for i in range(3)]
    result = exp06.analyze([write_run(tmp_path / "c", cal)], [write_run(tmp_path / "l", lad)])
    assert result["tasks"]["t"]["label"] == "medium"
    reg = result["stats"]["registered"]
    assert reg["static_sonnet"]["mean_cost"] == pytest.approx(0.3)
    assert reg["static_sonnet_calibration"]["mean_cost"] == pytest.approx(0.2)
