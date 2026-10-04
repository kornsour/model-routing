"""exp07 harness: CLI freeze, the advisor request log and evidence rule, pooled
task sets, the CLI-version guard, the evidence-gated note, and the analysis."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from test_dispatch_ladder import ScriptedProvider, fix, make_task  # noqa: I001 (sibling module)
from test_dispatch_runner import _outcomes, _run  # noqa: I001

from model_routing import cli_freeze
from model_routing.dispatch import advisor_log, exp07
from model_routing.dispatch import runner as runner_mod
from model_routing.dispatch.agents import ClaudeAgentProvider
from model_routing.dispatch.policies import LADDER_ADVISOR_EVIDENCE_NOTE, LADDER_ADVISOR_NOTE
from model_routing.dispatch.runner import load_dispatch_config

ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------- #
# CLI freeze
# --------------------------------------------------------------------------- #


def test_freeze_and_unfreeze_keep_other_settings(tmp_path: Path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"theme": "dark", "env": {"FOO": "1"}}))
    assert not cli_freeze.is_frozen(path)
    assert cli_freeze.freeze(path) is True
    assert cli_freeze.freeze(path) is False
    data = json.loads(path.read_text())
    assert data["env"] == {"FOO": "1", "DISABLE_AUTOUPDATER": "1"} and data["theme"] == "dark"
    assert cli_freeze.is_frozen(path)
    assert cli_freeze.unfreeze(path) is True
    assert json.loads(path.read_text()) == {"theme": "dark", "env": {"FOO": "1"}}
    assert cli_freeze.unfreeze(path) is False


def test_freeze_creates_settings_and_unfreeze_drops_empty_env(tmp_path: Path):
    path = tmp_path / "nested" / "settings.json"
    cli_freeze.freeze(path)
    assert json.loads(path.read_text()) == {"env": {"DISABLE_AUTOUPDATER": "1"}}
    cli_freeze.unfreeze(path)
    assert json.loads(path.read_text()) == {}


def test_runner_sessions_never_auto_update():
    env = runner_mod._with_harness_python({"PATH": "/usr/bin"})
    assert env["DISABLE_AUTOUPDATER"] == "1"


# --------------------------------------------------------------------------- #
# Evidence rule
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "tail",
    [
        "FAILED tests/test_x.py::test_a - AssertionError",
        "===== 2 failed, 10 passed in 0.3s =====",
        "E       assert 1 == 2",
        "--- FAIL: TestParse (0.00s)",
        "FAIL\texample.com/pkg\t0.01s",
        "not ok 3 - parses dates",
        "# fail 2",
        "Your work was checked and not accepted:\nvisible tests fail",
        "ValueError: bad input\nretrying\nValueError: bad input",
    ],
)
def test_evidence_present(tail: str):
    assert advisor_log.evidence_label(tail) == "evidence_present"


@pytest.mark.parametrize(
    "tail",
    [
        "",
        "===== 12 passed in 0.3s =====",
        "ok 1 - parses dates\n# pass 4\n# fail 0",
        "I'll read the module first.",
        "ValueError: one\nValueError: two",
        "0 failed",
    ],
)
def test_no_evidence(tail: str):
    assert advisor_log.evidence_label(tail) == "no_evidence"


def test_label_only_reads_the_last_4000_chars():
    old_failure = "FAILED tests/test_x.py::test_a\n"
    assert advisor_log.evidence_label(old_failure + "x" * 5000) == "no_evidence"


# --------------------------------------------------------------------------- #
# Stream source
# --------------------------------------------------------------------------- #


def _stream(*events: dict[str, Any]) -> str:
    return "\n".join(json.dumps(e) for e in events)


def _user(*blocks: Any) -> dict[str, Any]:
    return {"type": "user", "message": {"content": list(blocks)}}


def _assistant(*blocks: Any) -> dict[str, Any]:
    return {"type": "assistant", "message": {"content": list(blocks)}}


def test_requests_from_stream_labels_each_request():
    stdout = _stream(
        _user({"type": "text", "text": "FAILED brief mentions a failure but is not output"}),
        _assistant({"type": "text", "text": "Reading."}),
        _assistant({"type": "server_tool_use", "name": "advisor", "input": {}}),
        _user({"type": "tool_result", "content": [{"type": "text", "text": "1 failed, 2 passed"}]}),
        _assistant({"type": "tool_use", "name": "advisor", "input": {"q": "why"}}),
        {"type": "result", "result": "done"},
    )
    reqs = advisor_log.requests_from_stream(stdout)
    assert [r["label"] for r in reqs] == ["no_evidence", "evidence_present"]
    assert [r["assistant_turn"] for r in reqs] == [2, 3]
    assert reqs[1]["question"] == '{"q": "why"}'
    assert all(r["source"] == "stream" and r["rule"] == advisor_log.RULE_VERSION for r in reqs)


def test_no_requests_without_advisor_calls():
    stdout = _stream(_assistant({"type": "tool_use", "name": "Edit", "input": {}}))
    assert advisor_log.requests_from_stream(stdout) == []


# --------------------------------------------------------------------------- #
# Hook source
# --------------------------------------------------------------------------- #


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A"], cwd=repo, check=True
    )
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"],
        cwd=repo,
        check=True,
    )
    return repo


def test_hook_records_request_with_diff_and_label(tmp_path: Path):
    repo = _git_repo(tmp_path)
    (repo / "a.py").write_text("x = 2\n")
    (repo / "new.py").write_text("y = 3\n")
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        _stream(
            _user({"type": "text", "text": "The brief."}),
            _assistant({"type": "text", "text": "Running tests."}),
            _user({"type": "tool_result", "content": "FAILED tests/test_a.py::t"}),
        )
    )
    payload = {
        "cwd": str(repo),
        "transcript_path": str(transcript),
        "session_id": "s1",
        "tool_name": "advisor",
        "tool_input": {},
    }
    assert advisor_log.hook_main(json.dumps(payload)) == 0
    rows = advisor_log.read_and_clear(repo)
    assert len(rows) == 1
    row = rows[0]
    assert row["brief"] == "The brief."
    assert "-x = 1" in row["diff"] and "+x = 2" in row["diff"] and "+++ b/new.py" in row["diff"]
    assert ".advisor_log" not in row["diff"]
    assert row["label"] == "evidence_present" and row["source"] == "hook"
    assert "Running tests." in row["worker_tail"] and "FAILED" in row["tool_tail"]
    assert advisor_log.read_and_clear(repo) == []


def test_hook_never_fails_the_session(tmp_path: Path):
    assert advisor_log.hook_main("not json") == 0
    assert advisor_log.hook_main(json.dumps({"cwd": str(tmp_path / "missing")})) == 0


def test_hook_settings_and_cli_args():
    settings = advisor_log.hook_settings("/py")
    hook = settings["hooks"]["PreToolUse"][0]
    assert hook["matcher"] == "advisor"
    assert hook["hooks"][0]["command"] == '"/py" -m model_routing.dispatch.advisor_log hook'
    common: dict[str, Any] = dict(
        system=None,
        effort=None,
        max_turns=5,
        resume_session=None,
        fork=False,
        tools=True,
        max_budget_usd=1.0,
        advisor="claude-opus-5-5",
    )
    args = ClaudeAgentProvider().build_args("s", "p", request_log=True, **common)
    assert "PreToolUse" in args[args.index("--settings") + 1]
    assert "--settings" not in ClaudeAgentProvider().build_args("s", "p", **common)


def test_grading_ignores_the_log_dir():
    from model_routing.dispatch.grading import _is_ignored

    assert _is_ignored(".advisor_log/requests.jsonl")


# --------------------------------------------------------------------------- #
# Pooled task sets, version guard, evidence-gated note
# --------------------------------------------------------------------------- #


def test_real_exp07_configs_load_the_pooled_set():
    from model_routing.dispatch.tasks import load_agent_tasks

    cfg = load_dispatch_config(ROOT / "experiments/exp07-evidence-prompt/exp07.toml")
    tasks = runner_mod._select_tasks(cfg, load_agent_tasks, None)
    assert len(tasks) == 52
    assert not {"ha-archive-birchwood-05", "ha-verify-suite-16", "hc-history-csv-05"} & {
        t.id for t in tasks
    }
    notes = {p["name"]: p.get("advisor_note") for p in cfg.policies}
    assert notes == {
        "ladder_evidence": "evidence",
        "ladder_noforce": "standard",
        "static_sonnet": None,
    }
    for name in ("exp07_hook_smoke.toml", "exp07_pilot.toml"):
        load_dispatch_config(ROOT / "experiments/exp07-evidence-prompt" / name)


def _write_tasks(path: Path, ids: list[str]) -> None:
    path.write_text("".join(json.dumps({"id": i}) + "\n" for i in ids))


def _pooled_cfg(tmp_path: Path, extra: str) -> Path:
    _write_tasks(tmp_path / "a.jsonl", ["t1", "t2"])
    _write_tasks(tmp_path / "b.jsonl", ["t3", "t4"])
    path = tmp_path / "cfg.toml"
    path.write_text(
        f"""
[experiment]
name = "p"
tasks = "{tmp_path / "a.jsonl"}"
extra_tasks = ["{tmp_path / "b.jsonl"}"]
{extra}
parent = "sonnet"
primary = {{ treatment = "B", control = "B" }}

[candidates.sonnet]
provider = "fake_test"
model = "sonnet"

[[policies]]
name = "B"
kind = "spawn_static"
candidate = "sonnet"
"""
    )
    return path


def _id_loader(path: Path, sample: int | None = None, seed: int = 0) -> list[Any]:
    return [make_task(json.loads(line)["id"]) for line in Path(path).read_text().splitlines()]


def test_pooled_tasks_and_exclusions(tmp_path: Path):
    cfg = load_dispatch_config(_pooled_cfg(tmp_path, 'exclude_task_ids = ["t2"]'))
    assert [t.id for t in runner_mod._select_tasks(cfg, _id_loader, None)] == ["t1", "t3", "t4"]
    bad = load_dispatch_config(_pooled_cfg(tmp_path, 'exclude_task_ids = ["nope"]'))
    with pytest.raises(ValueError):
        runner_mod._select_tasks(bad, _id_loader, None)
    _write_tasks(tmp_path / "b.jsonl", ["t1"])
    dup = load_dispatch_config(_pooled_cfg(tmp_path, ""))
    _write_tasks(tmp_path / "b.jsonl", ["t1"])
    with pytest.raises(ValueError, match="more than one task file"):
        runner_mod._select_tasks(dup, _id_loader, None)


def test_cli_version_change_stops_between_cells(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from test_dispatch_runner import RecordingProvider, _write_cfg

    # Calls: meta.json (claude, codex), the run start, then one per cell. The version
    # changes after the second cell has started.
    versions = iter(["2.1.285"] * 5 + ["2.1.290"] * 100)
    monkeypatch.setattr(runner_mod, "_tool_version", lambda name: next(versions))
    cfg_path = _write_cfg(
        tmp_path,
        '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "opus"\n',
        treatment="B",
        control="B",
    )
    # _write_cfg uses provider "fake_test"; the guard watches claude_cli/codex_cli only, so
    # point one candidate at claude_cli for this test.
    text = cfg_path.read_text().replace(
        '[candidates.opus]\nprovider = "fake_test"', '[candidates.opus]\nprovider = "claude_cli"'
    )
    cfg_path.write_text(text)
    out = _run(tmp_path, cfg_path, RecordingProvider(), [make_task(f"t{i}") for i in range(4)])
    assert len(_outcomes(out)) == 2
    pauses = [json.loads(line) for line in (out / "pauses.jsonl").read_text().splitlines()]
    assert pauses[-1]["reason"] == "cli_version"
    assert "2.1.285 -> 2.1.290" in pauses[-1]["detail"]


def test_evidence_note_replaces_the_standard_note(tmp_path: Path):
    from test_dispatch_ladder import MARKER_TASK_GRADER, _cfg, marker_grader

    policy = (
        'worker = "sonnet_adv"\nverifier = "verifier"\nk = 2\nhandoff = "clean"\n'
        'advisor_note = "evidence"\n'
    )
    provider = ScriptedProvider({"sonnet": [fix()]}, advisor_calls=1)
    task = make_task(grader=MARKER_TASK_GRADER)
    _run(tmp_path, _cfg(tmp_path, policy), cast(Any, provider), [task], grader=marker_grader)
    prompt = provider.calls[0]["prompt"]
    assert LADDER_ADVISOR_EVIDENCE_NOTE in prompt and LADDER_ADVISOR_NOTE not in prompt
    with pytest.raises(ValueError):
        load_dispatch_config(_cfg(tmp_path, 'worker = "sonnet_adv"\nadvisor_note = "loud"\n'))


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #


def _tasks_file(path: Path, labels: dict[str, tuple[int, int]]) -> Path:
    rows = []
    for tid, (sonnet, opus) in labels.items():
        rows.append(
            {
                "id": tid,
                "measured": {
                    "pass_rates": {"sonnet": sonnet / 3, "opus": opus / 3},
                    "n": {"sonnet": 3, "opus": 3},
                },
            }
        )
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def _cell(task: str, arm: str, trial: int, passed: bool, cost: float, labels: list[str]) -> dict:
    reqs = [
        {"source": "stream", "assistant_turn": i + 1, "label": lab} for i, lab in enumerate(labels)
    ]
    return {
        "task_id": task,
        "policy": arm,
        "trial": trial,
        "passed": passed,
        "cost_usd": cost,
        "cascade_checks": [{"event": "worker", "advisor_calls": len(labels)}],
        "sessions": [
            {
                "role": "worker",
                "num_turns": 5,
                "raw": {"advisor_calls": len(labels), "advisor_requests": reqs},
            }
        ],
    }


def _exp07_run(tmp_path: Path, evidence_requests: int) -> tuple[Path, Path]:
    tasks = {f"e{i}": (3, 3) for i in range(12)} | {"h": (0, 3), "u": (0, 0)}
    tfile = _tasks_file(tmp_path / "tasks.jsonl", tasks)
    rows = []
    for t in tasks:
        for trial in range(3):
            rows.append(_cell(t, "static_sonnet", trial, t != "u", 0.30, []))
            rows.append(
                _cell(t, "ladder_noforce", trial, t != "u", 0.55, ["no_evidence", "no_evidence"])
            )
            ev = ["evidence_present"] * evidence_requests if trial == 0 else []
            rows.append(_cell(t, "ladder_evidence", trial, t != "u", 0.32, ev))
    run = tmp_path / "run"
    run.mkdir()
    (run / "outcomes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return run, tfile


def test_exp07_analysis_verdicts(tmp_path: Path):
    run, tfile = _exp07_run(tmp_path, evidence_requests=2)
    a = exp07.analyze([run], [tfile])
    assert a["easy_tasks"] == 12 and a["other_tasks"] == ["h"]
    assert a["E1"]["cost_ratio"] == pytest.approx(0.32 / 0.55)
    assert a["E1"]["verdict"] == "supported"
    assert a["E2"]["ratio"] == pytest.approx(0.32 / 0.30)
    assert a["E2"]["verdict"] == "supported"
    assert a["E3"]["evidence_arm_requests_easy"] == 24
    assert a["E3"]["share_diff"] == pytest.approx(1.0)
    assert a["E3"]["verdict"] == "supported"
    assert a["arms"]["ladder_evidence"]["requests_per_cell"]["max"] == 2
    text = exp07.render(a)
    assert "**supported**" in text and "| h | hard |" in text
    out = tmp_path / "a.md"
    assert exp07.main(["--runs", str(run), "--tasks", str(tfile), "--out", str(out)]) == 0
    assert out.read_text().startswith("# exp07 analysis")


def test_exp07_few_events_rule(tmp_path: Path):
    run, tfile = _exp07_run(tmp_path, evidence_requests=1)
    a = exp07.analyze([run], [tfile])
    assert a["E3"]["evidence_arm_requests_easy"] == 12
    assert a["E3"]["verdict"] == "descriptive (few events)"
    assert a["E3"]["p_holm"] is None


def test_holm():
    adj = exp07.holm({"E2": 0.01, "E3": 0.02})
    assert adj == {"E2": pytest.approx(0.02), "E3": pytest.approx(0.02)}
    assert exp07.holm({"E2": 0.03, "E3": None}) == {"E2": pytest.approx(0.03), "E3": None}


def test_labels_match_the_preregistration():
    labels = exp07.task_labels([ROOT / f for f in exp07.TASK_FILES])
    counts: dict[str, int] = {}
    for v in labels.values():
        counts[v["label"]] = counts.get(v["label"], 0) + 1
    assert counts == {"easy": 45, "medium": 2, "hard": 5, "unsolved": 3}


# --------------------------------------------------------------------------- #
# Logged-out CLI pauses instead of grading failures
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Failed to authenticate: OAuth session expired and could not be refreshed", True),
        ("OAuth token has expired", True),
        ("authentication_error: invalid x-api-key", True),
        ("Not logged in. Please run /login", True),
        ("Reached maximum number of turns (40)", False),
        ("API Error: 529 overloaded", False),
        (None, False),
    ],
)
def test_is_auth_failure(text: str | None, expected: bool):
    from model_routing.dispatch.agents import is_auth_failure

    assert is_auth_failure(text) is expected


def test_logged_out_cli_pauses_and_retries_the_cell(tmp_path: Path):
    from test_dispatch_runner import (
        RecordingProvider,
        _write_cfg,
        always_pass_grader,
        fake_sandbox_factory,
    )

    from model_routing.dispatch.runner import run_dispatch
    from model_routing.dispatch.types import AgentResult
    from model_routing.types import Usage

    class LoggedOutOnce(RecordingProvider):
        def run(self, model: str, prompt: str, **kw: Any) -> AgentResult:
            if not self.calls:
                self.calls.append({"model": model})
                return AgentResult(
                    output="",
                    usage=Usage(),
                    duration_ms=1,
                    error="Failed to authenticate: OAuth session expired",
                )
            return super().run(model, prompt, **kw)

    cfg = load_dispatch_config(
        _write_cfg(
            tmp_path,
            '[[policies]]\nname = "B"\nkind = "spawn_static"\ncandidate = "opus"\n',
            treatment="B",
            control="B",
        )
    )
    slept: list[float] = []
    out = tmp_path / "run"
    run_dispatch(
        cfg,
        out_dir=out,
        budget_usd=100.0,
        task_loader=lambda path, sample=None, seed=0: [make_task("t1"), make_task("t2")],
        sandbox_factory=fake_sandbox_factory,
        grader=always_pass_grader,
        agent_provider_factory=lambda name, env=None: LoggedOutOnce(),
        verbose=False,
        sleep=slept.append,
    )
    outcomes = _outcomes(out)
    assert [o["passed"] for o in outcomes] == [True, True]  # nothing graded as a failure
    assert len(slept) == 1
    pauses = [json.loads(line) for line in (out / "pauses.jsonl").read_text().splitlines()]
    assert pauses[0]["reason"] == "auth"
