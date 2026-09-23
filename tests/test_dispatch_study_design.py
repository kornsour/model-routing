"""Tests for the study-design machinery added for the confirmatory run:

* ``C1_inline`` bills only the marginal tokens of the pick;
* ``order = "randomized"`` is a seeded randomized block design;
* ``meta.json`` carries the task-set hash and the pre-registration table;
* the report computes permutation p-values, Holm adjustment and a
  confirmatory/exploratory status;
* the estimator prefers observed token profiles when history exists;
* calibration turns static outcomes into measured difficulty labels.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_dispatch_runner import (
    RecordingProvider,
    _outcome_row,
    _outcomes,
    _run,
    _sessions,
    _write_cfg,
    _write_run,
    make_task,
)

from model_routing.dispatch import calibration
from model_routing.dispatch.report import (
    _permutation_p_values,
    holm_adjust,
    preregistration_check,
    summarize,
)
from model_routing.dispatch.runner import (
    _build_plan,
    estimate_dispatch,
    load_dispatch_config,
    observed_profiles,
    taskset_sha256,
)
from model_routing.dispatch.types import AgentResult
from model_routing.types import Usage

# -- C1_inline ---------------------------------------------------------------


class InlineRouterProvider(RecordingProvider):
    """Returns a long brief followed by the pick JSON on the last line, with a
    realistic (large) usage so the marginal billing is visibly smaller."""

    def run(self, model: str, prompt: str, *, workdir: Path, tools: bool = True, **kw: Any):
        r = super().run(model, prompt, workdir=workdir, tools=tools, **kw)
        if not tools:
            brief = "Here is the brief.\n" + "Change {this} and {that}. " * 40 + "\n"
            r.output = brief + '{"candidate": "haiku", "effort": "low", "reason": "trivial"}'
            r.usage = Usage(input_tokens=200, cache_read=30000, output_tokens=900)
        return r


def test_c1_inline_bills_marginal_pick_only(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "C1_inline"\nkind = "spawn_parent_pick_inline"\n',
        treatment="C1_inline",
        control="C1_inline",
    )
    provider = InlineRouterProvider()
    out = _run(tmp_path, cfg_path, provider, [make_task()])
    sessions = _sessions(out)
    assert [s["role"] for s in sessions] == ["setup", "router", "worker"]
    router = sessions[1]
    assert router["cost_usd_billed"] is not None
    assert 0 < router["cost_usd_billed"] < router["cost_usd_list"]
    assert router["headline_cost_usd"] == router["cost_usd_billed"]
    outcomes = _outcomes(out)
    assert outcomes[0]["chosen_candidate"] == "haiku"  # parsed the *last* JSON object
    assert outcomes[0]["cost_usd"] < outcomes[0]["cost_usd_full"]
    # the worker still ran on the canned brief, not on the parent-written one
    worker_call = [c for c in provider.calls if c["tools"]][-1]
    assert worker_call["prompt"].startswith("A full, self-contained brief")


# -- ordering ------------------------------------------------------------------


def test_randomized_order_is_a_seeded_block_design():
    specs = [{"name": n} for n in ("A", "B", "C")]
    tasks = [make_task("t1"), make_task("t2"), make_task("t3"), make_task("t4")]
    plan = _build_plan("randomized", specs, tasks, trials=2, seed=7)
    assert len(plan) == 3 * 4 * 2
    # every (task, trial) block holds each policy exactly once, contiguously
    for i in range(0, len(plan), 3):
        block = plan[i : i + 3]
        assert len({s["name"] for s, _, _ in block}) == 3
        assert len({(t.id, tr) for _, t, tr in block}) == 1
    orders = {tuple(s["name"] for s, _, _ in plan[i : i + 3]) for i in range(0, len(plan), 3)}
    assert len(orders) > 1, "policies should not always run in the same order"
    assert plan == _build_plan("randomized", specs, tasks, trials=2, seed=7)  # reproducible
    assert plan != _build_plan("randomized", specs, tasks, trials=2, seed=8)


def test_config_rejects_unknown_order(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path, '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "opus"\n'
    )
    cfg_path.write_text(cfg_path.read_text().replace('order = "by_policy"', 'order = "shuffled"'))
    with pytest.raises(ValueError, match="order must be"):
        load_dispatch_config(cfg_path)


# -- meta: task-set hash, seed, max_turns, preregistration -----------------------


def test_taskset_hash_changes_when_any_file_changes(tmp_path: Path):
    root = tmp_path / "agentic"
    (root / "hidden" / "t1" / "tests").mkdir(parents=True)
    (root / "private").mkdir()
    tasks = root / "tasks.jsonl"
    tasks.write_text('{"id": "t1"}\n')
    (root / "hidden" / "t1" / "tests" / "test_hidden.py").write_text("def test(): pass\n")
    (root / "private" / "harvested.jsonl").write_text("secret\n")
    h1 = taskset_sha256(tasks)
    (root / "private" / "harvested.jsonl").write_text("other secret\n")
    assert taskset_sha256(tasks) == h1, "private/ must not affect the hash"
    (root / "hidden" / "t1" / "tests" / "test_hidden.py").write_text("def test(): assert 1\n")
    assert taskset_sha256(tasks) != h1


def test_meta_records_design_fields_and_max_turns_reaches_provider(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "opus"\n',
        treatment="B",
        control="B",
    )
    text = cfg_path.read_text().replace(
        "[experiment]\n", "[experiment]\nseed = 3\nmax_turns = 41\n"
    )
    text += (
        '\n[preregistration]\nregistered_at = "2026-09-23T00:00:00+00:00"\n'
        'taskset_sha256 = "abc"\nn_tasks = 1\ntrials = 1\nmargin_pp = 10\norder = "by_policy"\n'
        'primary = { treatment = "C1", control = "B" }\n'
    )
    cfg_path.write_text(text)

    class TurnsProvider(RecordingProvider):
        def run(self, model, prompt, *, workdir, max_turns=30, **kw):
            self.calls.append({"max_turns": max_turns, "tools": kw.get("tools", True)})
            return AgentResult(
                output="done",
                usage=Usage(input_tokens=1, output_tokens=1),
                duration_ms=1,
                session_id="s",
                resolved_model=model,
            )

    provider = TurnsProvider()
    out = _run(tmp_path, cfg_path, provider, [make_task()])
    meta = json.loads((out / "meta.json").read_text())
    assert meta["seed"] == 3
    assert meta["max_turns"] == 41
    assert len(meta["taskset_sha256"]) == 64
    assert meta["preregistration"]["taskset_sha256"] == "abc"
    assert provider.calls[0]["max_turns"] == 41


# -- report: p-values, Holm, confirmatory status --------------------------------


def _cells(rows: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    return {(r["task_id"], r["trial"]): r for r in rows}


def test_permutation_p_small_for_consistent_saving_and_large_for_noise():
    t_rows = [_outcome_row(f"t{i}", "C1", passed=True, cost=0.5) for i in range(12)]
    c_rows = [_outcome_row(f"t{i}", "B", passed=True, cost=1.0) for i in range(12)]
    p_saving, p_pass = _permutation_p_values("x", _cells(t_rows), _cells(c_rows))
    assert p_saving is not None and p_saving < 0.01
    assert p_pass == pytest.approx(1.0)  # identical pass rates: nothing to reject
    # symmetric noise: half the tasks favour each side by the same amount
    t_rows = [
        _outcome_row(f"t{i}", "C1", passed=True, cost=0.5 if i % 2 else 1.5) for i in range(12)
    ]
    c_rows = [_outcome_row(f"t{i}", "B", passed=True, cost=1.0) for i in range(12)]
    p_saving, _ = _permutation_p_values("y", _cells(t_rows), _cells(c_rows))
    assert p_saving is not None and p_saving > 0.2


def test_holm_adjustment_is_monotone_and_bounded():
    assert holm_adjust([0.01, 0.04, 0.03, None]) == [
        pytest.approx(0.03),
        pytest.approx(0.06),
        pytest.approx(0.06),
        None,
    ]
    assert holm_adjust([]) == []
    assert holm_adjust([None, None]) == [None, None]


def test_summary_marks_run_exploratory_without_preregistration(tmp_path: Path):
    outcomes = [
        _outcome_row("t1", "B", passed=True, cost=1.0),
        _outcome_row("t1", "C1", passed=True, cost=0.5),
        _outcome_row("t2", "B", passed=True, cost=1.0),
        _outcome_row("t2", "C1", passed=True, cost=0.4),
    ]
    out = _write_run(tmp_path, "expl", outcomes)
    summary = summarize(out)
    assert summary["confirmatory"] is False
    assert "no [preregistration]" in summary["preregistration"]["deviations"][0]
    h_d1 = summary["comparisons"][0]
    for key in ("p_saving", "p_pass", "p_noninf", "p_adjusted", "role"):
        assert key in h_d1
    assert h_d1["role"] == "primary"
    md = (out / "summary.md").read_text()
    assert "exploratory" in md and "p_saving" in md


def test_preregistration_check_matches_and_reports_deviations():
    reg = {
        "taskset_sha256": "h",
        "trials": 3,
        "margin_pp": 10.0,
        "primary": {"treatment": "C1_inline", "control": "B"},
        "order": "randomized",
        "n_tasks": 60,
    }
    meta = {
        "fake": False,
        "taskset_sha256": "h",
        "trials": 3,
        "margin_pp": 10.0,
        "primary": {"treatment": "C1_inline", "control": "B"},
        "order": "randomized",
        "n_tasks": 60,
        "policies": [{"name": "C1_inline"}, {"name": "B"}],
        "preregistration": reg,
    }
    assert preregistration_check(meta) == {
        "confirmatory": True,
        "registered": True,
        "deviations": [],
    }
    changed = {**meta, "taskset_sha256": "different", "trials": 1, "n_tasks": 30}
    res = preregistration_check(changed)
    assert res["confirmatory"] is False
    assert any(d.startswith("taskset_sha256") for d in res["deviations"])
    assert any(d.startswith("trials") for d in res["deviations"])
    assert any(d.startswith("n_tasks") for d in res["deviations"])
    assert preregistration_check({**meta, "fake": True})["deviations"] == ["fake provider run"]


# -- estimator: observed history ------------------------------------------------


def _write_history(root: Path, model: str, n: int, *, fake: bool = False) -> None:
    run = root / "exp" / (f"fake-{model}" if fake else f"20260101-{model}")
    run.mkdir(parents=True)
    (run / "meta.json").write_text(json.dumps({"fake": fake}))
    with (run / "sessions.jsonl").open("w") as f:
        for i in range(n):
            f.write(
                json.dumps(
                    {
                        "model": model,
                        "role": "worker",
                        "error": None,
                        "cost_usd_list": 0.5 + i * 0.01,
                        "usage": {
                            "input_tokens": 10,
                            "cache_read": 400_000 + i * 1000,
                            "cache_write": 20_000,
                            "output_tokens": 4_000,
                            "reasoning": 0,
                            "cache_write_1h": 20_000,
                        },
                    }
                )
                + "\n"
            )


def test_observed_profiles_skip_fake_runs_and_feed_the_estimate(tmp_path: Path):
    hist = tmp_path / "results"
    _write_history(hist, "opus", 8)
    _write_history(hist, "haiku", 3)  # below MIN_OBSERVED_SESSIONS
    _write_history(hist, "sonnet", 20, fake=True)
    profiles = observed_profiles(hist)
    assert set(profiles) == {("opus", "worker"), ("haiku", "worker")}
    assert profiles[("opus", "worker")].n == 8
    assert profiles[("opus", "worker")].median.cache_read >= 400_000

    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "opus"\n',
        treatment="B",
        control="B",
    )
    cfg = load_dispatch_config(cfg_path)
    with_history = estimate_dispatch(cfg, sample=2, history_dir=hist)
    without = estimate_dispatch(cfg, sample=2, history_dir=None)
    assert with_history["usd_mid"] > without["usd_mid"]  # observed Opus sessions are bigger
    assert any("Observed token profiles" in a for a in with_history["assumptions"])
    assert any("No observed history" in a for a in without["assumptions"])


# -- calibration -----------------------------------------------------------------


def test_calibration_table_labels_from_static_outcomes(tmp_path: Path):
    rows = [
        _outcome_row("easy1", "static_haiku", passed=True, cost=0.1, chosen="haiku"),
        _outcome_row("easy1", "static_haiku", passed=True, cost=0.1, chosen="haiku", trial=1),
        _outcome_row("med1", "static_haiku", passed=False, cost=0.1, chosen="haiku"),
        _outcome_row("med1", "static_haiku", passed=True, cost=0.1, chosen="haiku", trial=1),
        _outcome_row("hard1", "static_haiku", passed=False, cost=0.1, chosen="haiku"),
        _outcome_row("hard1", "static_sonnet", passed=False, cost=0.2, chosen="sonnet"),
        _outcome_row("hard1", "static_opus", passed=True, cost=0.5, chosen="opus"),
        _outcome_row("bad1", "static_haiku", passed=False, cost=0.1, chosen="haiku"),
        _outcome_row("bad1", "static_opus", passed=False, cost=0.5, chosen="opus"),
        _outcome_row("easy1", "C1", passed=False, cost=0.3, chosen="opus"),  # routers ignored
    ]
    out = _write_run(tmp_path, "cal", rows, fake=False)
    table = calibration.calibration_table([out])
    labels = {k: v["difficulty"] for k, v in table.items()}
    assert labels == {"easy1": "easy", "med1": "medium", "hard1": "hard", "bad1": "unsolved"}
    assert table["easy1"]["by_candidate"] == {"haiku": {"n": 2, "passes": 2, "pass_rate": 1.0}}
    text = calibration.render_calibration(table)
    assert "| hard1 | 0/1 | 0/1 | 1/1 | hard |" in text
    assert "Cheapest candidate (haiku)" in text

    tasks = tmp_path / "tasks.jsonl"
    tasks.write_text(
        "\n".join(
            json.dumps({"id": i, "difficulty": d})
            for i, d in [
                ("easy1", "hard"),
                ("med1", "medium"),
                ("hard1", "easy"),
                ("bad1", "hard"),
                ("none", "easy"),
            ]
        )
        + "\n"
    )
    counts = calibration.relabel_tasks(tasks, table)
    assert counts == {"relabelled": 2, "unchanged": 1, "uncalibrated": 2}
    rows2 = {json.loads(line)["id"]: json.loads(line) for line in tasks.read_text().splitlines()}
    assert rows2["easy1"]["difficulty"] == "easy" and rows2["easy1"]["difficulty_human"] == "hard"
    assert rows2["easy1"]["measured"]["pass_rates"] == {"haiku": 1.0}
    assert rows2["bad1"]["difficulty"] == "hard"  # unsolved: left for a human to look at
    assert "measured" not in rows2["none"]


def test_calibration_refuses_fake_runs(tmp_path: Path):
    out = _write_run(tmp_path, "fake_cal", [_outcome_row("t", "static_haiku", passed=True, cost=1)])
    with pytest.raises(ValueError, match="fake run"):
        calibration.calibration_table([out])


def test_preregistration_block_round_trips_through_toml(tmp_path: Path):
    import tomllib

    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "opus"\n'
        '[[policies]]\nname = "C1"\nkind = "spawn_parent_pick"\n',
        trials=3,
        margin_pp=10,
        order="randomized",
    )
    cfg = load_dispatch_config(cfg_path)
    block = calibration.preregistration_block(cfg, n_tasks=60)
    data = tomllib.loads(block)["preregistration"]
    assert data["n_tasks"] == 60 and data["trials"] == 3 and data["margin_pp"] == 10
    assert data["order"] == "randomized"
    assert data["primary"] == {"treatment": "C1", "control": "B"}
    assert data["taskset_sha256"] == taskset_sha256(cfg.tasks)
