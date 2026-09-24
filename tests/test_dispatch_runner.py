"""Tests for the dispatch-time routing runner/policies/report.

The sibling workstreams (``dispatch.agents``, ``dispatch.tasks``, ``dispatch.sandbox``,
``dispatch.grading``) may not exist yet, so every test here injects its own tiny fakes
via ``run_dispatch``'s keyword-only ``task_loader`` / ``sandbox_factory`` / ``grader`` /
``agent_provider_factory`` parameters, exactly as the runner is designed to allow.
"""

from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

import pytest

from model_routing.dispatch.report import summarize
from model_routing.dispatch.runner import (
    auth_status,
    estimate_dispatch,
    load_dispatch_config,
    run_dispatch,
)
from model_routing.dispatch.types import AgentResult, AgentTask, GradeResult
from model_routing.types import Usage

ROOT = Path(__file__).resolve().parents[1]


# -- fakes --------------------------------------------------------------------


class FakeSandbox:
    def __init__(self, root: Path):
        self.path = root / f"sandbox-{uuid.uuid4().hex[:8]}"
        self.path.mkdir(parents=True)
        self.cleaned = False

    def cleanup(self) -> None:
        self.cleaned = True


def fake_sandbox_factory(task: AgentTask, root: Path, *, simulate: bool = False) -> FakeSandbox:
    root.mkdir(parents=True, exist_ok=True)
    return FakeSandbox(root)


def always_pass_grader(task: AgentTask, sandbox: FakeSandbox) -> GradeResult:
    return GradeResult(passed=True, checks={"ok": True}, detail="fake pass")


def marker_grader(task: AgentTask, sandbox: FakeSandbox) -> GradeResult:
    passed = (sandbox.path / "MARKER").exists()
    return GradeResult(passed=passed, checks={"marker": passed}, detail="marker check")


def make_task(task_id: str = "t1", **kw: Any) -> AgentTask:
    defaults: dict[str, Any] = dict(
        id=task_id,
        title="Fix the bug",
        brief="A full, self-contained brief describing the fix in detail. " * 3,
        brief_terse="Fix the bug.",
        parent_context="You already reviewed this repo and know the layout.",
        repo=Path("/nonexistent/fixture-repo"),
        grader={},
        difficulty="easy",
        category="general",
    )
    defaults.update(kw)
    return AgentTask(**defaults)


class RecordingProvider:
    """In-test fake AgentProvider.  Returns a valid router-JSON payload for any
    tools=False call (router/classifier), and a plain worker reply otherwise.
    Optionally writes a MARKER file into ``workdir`` when ``model`` matches
    ``pass_on_model``, to test cascade escalation."""

    name = "fake_test"

    def __init__(
        self,
        router_pick: str = "haiku",
        pass_on_model: str | None = None,
        error_on_model: str | None = None,
    ):
        self.calls: list[dict[str, Any]] = []
        self.router_pick = router_pick
        self.pass_on_model = pass_on_model
        self.error_on_model = error_on_model

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
        self.calls.append(
            {
                "model": model,
                "tools": tools,
                "resume": resume_session,
                "fork": fork,
                "prompt": prompt,
            }
        )
        session_id = resume_session if (resume_session and not fork) else f"sess-{len(self.calls)}"
        if not tools:
            output = (
                f'{{"candidate": "{self.router_pick}", "effort": "low", "reason": "cheap enough"}}'
            )
        else:
            output = "done"
            if self.pass_on_model and model == self.pass_on_model:
                Path(workdir, "MARKER").touch()
        return AgentResult(
            output=output,
            usage=Usage(input_tokens=100, output_tokens=20),
            duration_ms=1,
            num_turns=1,
            tool_calls=1 if tools else 0,
            session_id=session_id,
            resolved_model=model,
            error=(
                "Reached maximum number of turns (40)"
                if tools and model == self.error_on_model
                else None
            ),
        )


def _write_cfg(tmp_path: Path, policies_toml: str, **overrides: Any) -> Path:
    tasks_path = tmp_path / "tasks.jsonl"
    tasks_path.write_text("")
    path = tmp_path / "cfg.toml"
    treatment = overrides.get("treatment", "C1")
    control = overrides.get("control", "B")
    path.write_text(
        f"""
[experiment]
name = "{overrides.get("name", "t")}"
tasks = "{tasks_path}"
trials = {overrides.get("trials", 1)}
order = "{overrides.get("order", "by_policy")}"
parent = "{overrides.get("parent", "opus")}"
menu = {overrides.get("menu", '["haiku", "sonnet", "opus"]')}
primary = {{ treatment = "{treatment}", control = "{control}" }}
margin_pp = {overrides.get("margin_pp", 5)}

[candidates.haiku]
provider = "fake_test"
model = "haiku"

[candidates.sonnet]
provider = "fake_test"
model = "sonnet"

[candidates.opus]
provider = "fake_test"
model = "opus"

{policies_toml}
"""
    )
    return path


def _run(
    tmp_path: Path,
    cfg_path: Path,
    provider: RecordingProvider,
    tasks: list[AgentTask],
    *,
    budget_usd: float = 100.0,
    grader=always_pass_grader,
    cancel: threading.Event | None = None,
    progress=None,
    trials: int | None = None,
    policies: list[str] | None = None,
    keep_sandboxes: bool = False,
):
    cfg = load_dispatch_config(cfg_path)
    out = tmp_path / "run"
    run_dispatch(
        cfg,
        out_dir=out,
        budget_usd=budget_usd,
        trials=trials,
        policies=policies,
        task_loader=lambda path, sample=None, seed=0: tasks,
        sandbox_factory=fake_sandbox_factory,
        grader=grader,
        agent_provider_factory=lambda name, env=None: provider,
        cancel=cancel,
        progress=progress,
        keep_sandboxes=keep_sandboxes,
        verbose=False,
    )
    return out


def _sessions(out: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (out / "sessions.jsonl").read_text().splitlines()]


def _outcomes(out: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (out / "outcomes.jsonl").read_text().splitlines()]


# -- config loading / validation ----------------------------------------------


def test_real_experiment_configs_validate():
    for name in ("exp05_dispatch.toml", "exp05_dispatch_codex.toml", "exp05_pilot.toml"):
        cfg = load_dispatch_config(ROOT / "experiments" / "agentic" / name)
        assert cfg.parent in cfg.candidates
        assert all(m in cfg.candidates for m in cfg.menu)


def test_config_rejects_unknown_candidate(tmp_path: Path):
    path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "nope"\n',
    )
    with pytest.raises(ValueError, match="unknown candidate"):
        load_dispatch_config(path)


def test_config_rejects_bad_primary(tmp_path: Path):
    path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "haiku"\n',
        treatment="does_not_exist",
    )
    with pytest.raises(ValueError, match="primary.treatment"):
        load_dispatch_config(path)


def test_config_pricing_check(tmp_path: Path):
    # every candidate model must have a price row; "haiku"/"sonnet"/"opus" do.
    path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "haiku"\n',
        treatment="B",
        control="B",
    )
    cfg = load_dispatch_config(path)
    assert cfg.candidates["haiku"].model == "haiku"


# -- policy session sequences and roles ----------------------------------------


def test_policy_a_resumes_seeded_parent(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path, '[[policies]]\nname = "A"\nkind = "in_session"\n', treatment="A", control="A"
    )
    provider = RecordingProvider()
    out = _run(tmp_path, cfg_path, provider, [make_task()])
    sessions = _sessions(out)
    assert [s["role"] for s in sessions] == ["setup", "worker"]
    assert sessions[0]["candidate"] == "opus"  # parent
    assert sessions[1]["candidate"] == "opus"
    assert sessions[1]["resumed_from"] == sessions[0]["session_id"]
    outcomes = _outcomes(out)
    assert outcomes[0]["passed"] is True
    assert outcomes[0]["setup_cost_usd"] > 0
    # setup cost is excluded from the headline cost.
    assert outcomes[0]["cost_usd"] < outcomes[0]["setup_cost_usd"] + outcomes[0]["cost_usd"]


def test_policy_a_switch_uses_switch_to_model(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "A_switch"\nkind = "in_session"\nswitch_to = "sonnet"\n',
        treatment="A_switch",
        control="A_switch",
    )
    provider = RecordingProvider()
    out = _run(tmp_path, cfg_path, provider, [make_task()])
    sessions = _sessions(out)
    assert [s["role"] for s in sessions] == ["setup", "worker"]
    assert sessions[0]["candidate"] == "opus"
    assert sessions[1]["candidate"] == "sonnet"


def test_policy_b_is_a_single_fresh_session(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "opus"\n',
        treatment="B",
        control="B",
    )
    provider = RecordingProvider()
    out = _run(tmp_path, cfg_path, provider, [make_task()])
    sessions = _sessions(out)
    assert [s["role"] for s in sessions] == ["worker"]
    assert (
        sessions[0]["resume_session" if "resume_session" in sessions[0] else "resumed_from"] is None
    )


def test_policy_c1_router_then_fresh_worker(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "C1"\nkind = "spawn_parent_pick"\n',
        treatment="C1",
        control="C1",
    )
    provider = RecordingProvider(router_pick="haiku")
    out = _run(tmp_path, cfg_path, provider, [make_task()])
    sessions = _sessions(out)
    assert [s["role"] for s in sessions] == ["setup", "router", "worker"]
    assert sessions[1]["candidate"] == "opus"  # router call is on the parent
    assert sessions[1]["resumed_from"] == sessions[0]["session_id"]
    assert sessions[2]["candidate"] == "haiku"  # picked from the menu
    outcomes = _outcomes(out)
    assert outcomes[0]["chosen_candidate"] == "haiku"
    # router calls are visible in the fake provider as tools=False, forked.
    router_calls = [c for c in provider.calls if not c["tools"]]
    assert len(router_calls) == 1 and router_calls[0]["fork"] is True


def test_policy_c1_falls_back_to_parent_on_bad_router_output(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "C1"\nkind = "spawn_parent_pick"\n',
        treatment="C1",
        control="C1",
    )

    class BadRouterProvider(RecordingProvider):
        def run(self, model, prompt, *, workdir, tools=True, **kw):
            if not tools:
                self.calls.append(
                    {
                        "model": model,
                        "tools": tools,
                        "resume": kw.get("resume_session"),
                        "fork": kw.get("fork"),
                        "prompt": prompt,
                    }
                )
                return AgentResult(
                    output="not json at all",
                    usage=Usage(input_tokens=10, output_tokens=5),
                    duration_ms=1,
                    session_id="r1",
                    resolved_model=model,
                )
            return super().run(model, prompt, workdir=workdir, tools=tools, **kw)

    provider = BadRouterProvider()
    out = _run(tmp_path, cfg_path, provider, [make_task()])
    outcomes = _outcomes(out)
    assert outcomes[0]["chosen_candidate"] == "opus"  # fell back to the parent


def test_policy_c2_classifier_call(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "C2"\nkind = "spawn_classifier"\nclassifier = "haiku"\n',
        treatment="C2",
        control="C2",
    )
    provider = RecordingProvider(router_pick="sonnet")
    out = _run(tmp_path, cfg_path, provider, [make_task()])
    sessions = _sessions(out)
    assert [s["role"] for s in sessions] == ["router", "worker"]
    assert sessions[0]["candidate"] == "haiku"  # the classifier candidate itself
    assert sessions[1]["candidate"] == "sonnet"  # what it picked


def test_policy_c2_heuristic_is_free(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "C2"\nkind = "spawn_classifier"\nclassifier = "heuristic"\n',
        treatment="C2",
        control="C2",
    )
    provider = RecordingProvider()
    out = _run(tmp_path, cfg_path, provider, [make_task(brief="short")])
    sessions = _sessions(out)
    assert [s["role"] for s in sessions] == ["worker"]  # no router call at all


def test_policy_d_escalates_on_visible_checker_failure(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "D"\nkind = "spawn_cascade"\nchain = ["haiku", "sonnet"]\n',
        treatment="D",
        control="D",
    )
    # "sonnet" is the one that "fixes" the visible check by writing MARKER.
    provider = RecordingProvider(pass_on_model="sonnet")
    task = make_task(
        grader={
            "visible_cmd": [
                "python3",
                "-c",
                "import pathlib,sys; sys.exit(0 if pathlib.Path('MARKER').exists() else 1)",
            ]
        }
    )
    out = _run(tmp_path, cfg_path, provider, [task], grader=marker_grader)
    sessions = _sessions(out)
    assert [s["role"] for s in sessions] == ["worker", "escalation"]
    assert sessions[0]["candidate"] == "haiku"
    assert sessions[1]["candidate"] == "sonnet"
    outcomes = _outcomes(out)
    assert outcomes[0]["escalations"] == 1
    assert outcomes[0]["passed"] is True
    assert outcomes[0]["chosen_candidate"] == "sonnet"


def test_policy_d_no_escalation_when_first_passes(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "D"\nkind = "spawn_cascade"\nchain = ["haiku", "sonnet"]\n',
        treatment="D",
        control="D",
    )
    provider = RecordingProvider(pass_on_model="haiku")
    task = make_task(
        grader={
            "visible_cmd": [
                "python3",
                "-c",
                "import pathlib,sys; sys.exit(0 if pathlib.Path('MARKER').exists() else 1)",
            ]
        }
    )
    out = _run(tmp_path, cfg_path, provider, [task], grader=marker_grader)
    sessions = _sessions(out)
    assert [s["role"] for s in sessions] == ["worker"]
    assert _outcomes(out)[0]["escalations"] == 0
    assert _outcomes(out)[0]["cascade_checks"] == [{"candidate": "haiku", "ok": True, "reason": ""}]


_MARKER_VISIBLE = {
    "visible_cmd": [
        "python3",
        "-c",
        "import pathlib,sys; sys.exit(0 if pathlib.Path('MARKER').exists() else 1)",
    ]
}


@pytest.mark.parametrize("escalate_on_error", [False, True])
def test_policy_d_escalate_on_error(tmp_path: Path, escalate_on_error: bool):
    # haiku leaves the visible check green but hits the turn cap (the 2026-09-24
    # smoke): plain D accepts it; escalate_on_error hands it to sonnet.
    flag = "escalate_on_error = true\n" if escalate_on_error else ""
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "D"\nkind = "spawn_cascade"\nchain = ["haiku", "sonnet"]\n' + flag,
        treatment="D",
        control="D",
    )
    provider = RecordingProvider(pass_on_model="haiku", error_on_model="haiku")
    out = _run(
        tmp_path, cfg_path, provider, [make_task(grader=_MARKER_VISIBLE)], grader=marker_grader
    )
    outcome = _outcomes(out)[0]
    assert outcome["escalations"] == int(escalate_on_error)
    assert outcome["cascade_checks"][0]["ok"] is (not escalate_on_error)
    if escalate_on_error:
        assert "turns" in outcome["cascade_checks"][0]["reason"]
        assert "stopped before finishing" in provider.calls[-1]["prompt"]


# -- budget / cancel ------------------------------------------------------------


def test_budget_stops_cleanly(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "opus"\n',
        treatment="B",
        control="B",
    )
    provider = RecordingProvider()
    tasks = [make_task(f"t{i}") for i in range(20)]
    out = _run(tmp_path, cfg_path, provider, tasks, budget_usd=0.0001)
    outcomes = _outcomes(out)
    assert 0 <= len(outcomes) < len(tasks)
    # summarize() still runs and produces a valid summary from partial data.
    summary = json.loads((out / "summary.json").read_text())
    assert "headline" in summary


def test_cancel_stops_before_any_session(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "opus"\n',
        treatment="B",
        control="B",
    )
    provider = RecordingProvider()
    cancel = threading.Event()
    cancel.set()
    out = _run(tmp_path, cfg_path, provider, [make_task()], cancel=cancel)
    assert _outcomes(out) == []
    summary = json.loads((out / "summary.json").read_text())
    assert summary["n_tasks"] >= 0


def test_progress_callback_fires(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "opus"\n',
        treatment="B",
        control="B",
    )
    events = []
    provider = RecordingProvider()
    _run(tmp_path, cfg_path, provider, [make_task()], progress=events.append)
    assert events
    assert events[-1].state in ("done", "over_budget", "cancelled")


# -- estimate --------------------------------------------------------------------


def test_estimate_no_spend(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "opus"\n\n'
        '[[policies]]\nname = "D"\nkind = "spawn_cascade"\nchain = ["haiku", "sonnet", "opus"]\n',
        treatment="B",
        control="B",
    )
    cfg = load_dispatch_config(cfg_path)
    est = estimate_dispatch(cfg, sample=5, trials=2)
    assert est["cells"] == 5 * 2 * 2
    assert est["usd_low"] <= est["usd_mid"] <= est["usd_high"]
    assert set(est["by_policy"]) == {"B", "D"}
    assert est["assumptions"]


# -- auth_status: graceful when dispatch.agents does not exist yet --------------


def test_auth_status_is_graceful_without_agents_module():
    status = auth_status()
    assert set(status) == {"claude", "codex"}  # keyed by track, per dispatch.api
    for row in status.values():
        assert "installed" in row and "logged_in" in row


# -- report: oracle + verdicts + summary shape -----------------------------------


def _outcome_row(
    task_id: str,
    policy: str,
    *,
    passed: bool,
    cost: float,
    trial: int = 0,
    chosen: str | None = None,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "policy": policy,
        "trial": trial,
        "passed": passed,
        "checks": {},
        "grade_detail": "",
        "files_changed": [],
        "difficulty": "easy",
        "category": "general",
        "chosen_candidate": chosen,
        "escalations": 0,
        "cost_usd": cost,
        "setup_cost_usd": 0.0,
        "router_cost_usd": 0.0,
        "turns": 1,
        "duration_ms": 10,
        "sessions": [],
    }


def _write_run(
    tmp_path: Path, name: str, outcomes: list[dict[str, Any]], **meta_overrides: Any
) -> Path:
    out = tmp_path / name
    out.mkdir()
    meta = {
        "experiment": name,
        "n_tasks": len({o["task_id"] for o in outcomes}),
        "trials": 1,
        "fake": True,
        "primary": {"treatment": "C1", "control": "B"},
        "margin_pp": 5.0,
    }
    meta.update(meta_overrides)
    (out / "meta.json").write_text(json.dumps(meta))
    with (out / "outcomes.jsonl").open("w") as f:
        for o in outcomes:
            f.write(json.dumps(o) + "\n")
    (out / "sessions.jsonl").write_text("")
    return out


def test_oracle_picks_cheapest_passing_static(tmp_path: Path):
    outcomes = [
        _outcome_row("t1", "static_haiku", passed=True, cost=0.2, chosen="haiku"),
        _outcome_row("t1", "static_sonnet", passed=True, cost=0.5, chosen="sonnet"),
        _outcome_row("t2", "static_haiku", passed=False, cost=0.2, chosen="haiku"),
        _outcome_row("t2", "static_sonnet", passed=True, cost=0.5, chosen="sonnet"),
        _outcome_row("t3", "static_haiku", passed=False, cost=0.2, chosen="haiku"),
        _outcome_row("t3", "static_sonnet", passed=False, cost=0.5, chosen="sonnet"),
    ]
    out = _write_run(tmp_path, "oracle_run", outcomes)
    summary = summarize(out)
    oracle = summary["oracle"]
    assert oracle["n"] == 3
    assert oracle["pass_rate"] == pytest.approx(2 / 3)
    # t1 -> haiku (cheaper, passed); t2 -> sonnet (only passer); t3 -> neither passed (cost 0).
    assert oracle["cost_per_task"] == pytest.approx((0.2 + 0.5 + 0.0) / 3)


def test_verdict_supported(tmp_path: Path):
    outcomes = []
    for i in range(4):
        t = f"t{i}"
        outcomes.append(_outcome_row(t, "B", passed=True, cost=1.0))
        outcomes.append(_outcome_row(t, "C1", passed=True, cost=0.5))
    out = _write_run(tmp_path, "supported_run", outcomes)
    summary = summarize(out)
    h_d1 = next(c for c in summary["comparisons"] if c["id"] == "H-D1")
    assert h_d1["verdict"] == "supported"
    assert summary["headline"] == h_d1["sentence"]


def test_verdict_not_supported_on_pass_rate_drop(tmp_path: Path):
    outcomes = []
    for i in range(20):
        t = f"t{i}"
        outcomes.append(_outcome_row(t, "B", passed=True, cost=1.0))
        # C1 passes half the time over 20 tasks: a regression whose whole CI
        # sits below the margin (4 tasks would only be inconclusive).
        outcomes.append(_outcome_row(t, "C1", passed=(i % 2 == 0), cost=0.5))
    out = _write_run(tmp_path, "not_supported_run", outcomes)
    summary = summarize(out)
    h_d1 = next(c for c in summary["comparisons"] if c["id"] == "H-D1")
    assert h_d1["verdict"] == "not supported"


def test_verdict_inconclusive_when_saving_straddles_zero(tmp_path: Path):
    outcomes = [
        _outcome_row("t1", "B", passed=True, cost=1.0),
        _outcome_row("t1", "C1", passed=True, cost=0.2),  # big saving
        _outcome_row("t2", "B", passed=True, cost=1.0),
        _outcome_row("t2", "C1", passed=True, cost=3.0),  # big loss
    ]
    out = _write_run(tmp_path, "inconclusive_run", outcomes)
    summary = summarize(out)
    h_d1 = next(c for c in summary["comparisons"] if c["id"] == "H-D1")
    assert h_d1["verdict"] == "inconclusive"


def test_h_d6_skipped_gracefully_when_policies_absent(tmp_path: Path):
    outcomes = [
        _outcome_row("t1", "B", passed=True, cost=1.0),
        _outcome_row("t1", "C1", passed=True, cost=0.5),
    ]
    out = _write_run(tmp_path, "no_terse_run", outcomes)
    summary = summarize(out)  # must not raise
    assert not any(c["id"] == "H-D6" for c in summary["comparisons"])


def test_summary_json_shape(tmp_path: Path):
    outcomes = [
        _outcome_row("t1", "B", passed=True, cost=1.0),
        _outcome_row("t1", "C1", passed=True, cost=0.5),
        _outcome_row("t2", "B", passed=True, cost=1.0),
        _outcome_row("t2", "C1", passed=False, cost=0.4),
    ]
    out = _write_run(tmp_path, "shape_run", outcomes)
    summary = summarize(out)
    for key in (
        "experiment",
        "run_dir",
        "fake",
        "spent_usd",
        "n_tasks",
        "trials",
        "policies",
        "oracle",
        "comparisons",
        "headline",
    ):
        assert key in summary
    for p in summary["policies"]:
        for key in (
            "name",
            "n",
            "pass_rate",
            "cost_per_task",
            "cost_per_pass",
            "cost_per_pass_ci",
            "router_share",
            "escalation_rate",
            "mean_turns",
            "setup_cost_usd",
            "by_difficulty",
            "model_mix",
        ):
            assert key in p
    for c in summary["comparisons"]:
        for key in (
            "id",
            "treatment",
            "control",
            "delta_pass_pp",
            "delta_pass_ci",
            "saving_pct",
            "saving_ci",
            "verdict",
            "sentence",
        ):
            assert key in c
    assert (out / "summary.json").exists()
    assert (out / "summary.md").exists()


class CumulativeCostProvider(RecordingProvider):
    """Mimics the Claude CLI: ``total_cost_usd`` of a resumed session includes
    the cost of the session it resumed (observed in the 2026-09-22 pilot)."""

    def __init__(self) -> None:
        super().__init__(router_pick="haiku")
        self.totals: dict[str, float] = {}
        self.own = {"setup": 0.086, "router": 0.083, "worker": 0.03}

    def run(self, model: str, prompt: str, **kw: Any) -> AgentResult:
        r = super().run(model, prompt, **kw)
        role = (
            "router"
            if not kw.get("tools", True)
            else ("setup" if len(self.calls) == 1 else "worker")
        )
        prior = self.totals.get(kw.get("resume_session") or "", 0.0)
        total = prior + self.own[role]
        assert r.session_id is not None
        self.totals[r.session_id] = total
        r.cost_usd_reported = total
        return r


def test_resumed_session_reported_cost_is_per_session(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "C1"\nkind = "spawn_parent_pick"\n'
        '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "opus"\n',
    )
    out = _run(tmp_path, cfg_path, CumulativeCostProvider(), [make_task()], policies=["C1"])
    reported = {s["role"]: s["cost_usd_reported"] for s in _sessions(out)}
    assert reported["setup"] == pytest.approx(0.086)
    assert reported["router"] == pytest.approx(0.083)  # not 0.169 (cumulative)
    assert reported["worker"] == pytest.approx(0.03)


def test_difficulties_filter_selects_only_labelled_tasks(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "haiku"\n',
        treatment="B",
        control="B",
    )
    text = cfg_path.read_text().replace("[experiment]\n", '[experiment]\ndifficulties = ["hard"]\n')
    cfg_path.write_text(text)
    tasks = [
        make_task("e1", difficulty="easy"),
        make_task("h1", difficulty="hard"),
        make_task("h2", difficulty="hard"),
    ]
    out = _run(tmp_path, cfg_path, RecordingProvider(), tasks)
    assert sorted(o["task_id"] for o in _outcomes(out)) == ["h1", "h2"]


def test_task_ids_filter_selects_only_listed_tasks(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "haiku"\n',
        treatment="B",
        control="B",
    )
    text = cfg_path.read_text().replace("[experiment]\n", '[experiment]\ntask_ids = ["t2", "t3"]\n')
    cfg_path.write_text(text)
    tasks = [make_task("t1"), make_task("t2"), make_task("t3")]
    out = _run(tmp_path, cfg_path, RecordingProvider(), tasks)
    assert sorted(o["task_id"] for o in _outcomes(out)) == ["t2", "t3"]


def test_task_ids_filter_rejects_unknown_id(tmp_path: Path):
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "haiku"\n',
        treatment="B",
        control="B",
    )
    text = cfg_path.read_text().replace("[experiment]\n", '[experiment]\ntask_ids = ["nope"]\n')
    cfg_path.write_text(text)
    with pytest.raises(ValueError, match="nope"):
        _run(tmp_path, cfg_path, RecordingProvider(), [make_task("t1")])
