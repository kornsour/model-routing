"""exp06 ladder policy (``spawn_ladder``), the advisor rung's pricing, and the
Claude CLI's multi-model usage parsing.  Everything runs on injected fakes."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from test_dispatch_runner import (  # noqa: I001 (sibling test module)
    _outcomes,
    _run,
    _sessions,
    make_task,
    marker_grader,
)

from model_routing.dispatch.agents import ClaudeAgentProvider, parse_claude_stream
from model_routing.dispatch.policies import FORCED_CHECK_PROMPT
from model_routing.dispatch.runner import estimate_dispatch, load_dispatch_config
from model_routing.dispatch.types import AgentResult
from model_routing.pricing import PriceTable
from model_routing.types import Usage

PASSING_TEST = "def test_ok():\n    assert True\n"
FAILING_TEST = "def test_bad():\n    assert False\n"

# The visible check passes when MARKER exists (the "fix" is present).
MARKER_TASK_GRADER = {
    "visible_cmd": [
        "python3",
        "-c",
        "import pathlib,sys; sys.exit(0 if pathlib.Path('MARKER').exists() else 1)",
    ]
}

Step = Callable[[Path], dict[str, Any]]


def fix(test_body: str = PASSING_TEST, marker: bool = True) -> Step:
    def step(workdir: Path) -> dict[str, Any]:
        (workdir / ".verifier").mkdir(exist_ok=True)
        (workdir / ".verifier" / "test_gen.py").write_text(test_body)
        if marker:
            (workdir / "MARKER").touch()
        return {}

    return step


def say(output: str = "done", **kw: Any) -> Step:
    return lambda workdir: {"output": output, **kw}


class ScriptedProvider:
    """Plays a script per model: each call pops that model's next step."""

    name = "fake_test"

    def __init__(self, script: dict[str, list[Step]], advisor_calls: int = 0):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls: list[dict[str, Any]] = []
        self.advisor_calls = advisor_calls

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
        advisor: str | None = None,
    ) -> AgentResult:
        self.calls.append(
            {
                "model": model,
                "prompt": prompt,
                "resume": resume_session,
                "workdir": str(workdir),
                "advisor": advisor,
            }
        )
        steps = self.script.get(model) or []
        extra = steps.pop(0)(Path(workdir)) if steps else {}
        session_id = resume_session or f"sess-{len(self.calls)}"
        raw = {"advisor_calls": extra.get("advisor_calls", self.advisor_calls if advisor else 0)}
        if extra.get("other_model_usage"):
            raw["other_model_usage"] = extra["other_model_usage"]
        return AgentResult(
            output=extra.get("output", "done"),
            usage=Usage(input_tokens=1000, output_tokens=100),
            duration_ms=1,
            num_turns=3,
            tool_calls=2,
            session_id=session_id,
            resolved_model=model,
            error=extra.get("error"),
            raw=raw,
        )


def _cfg(tmp_path: Path, policy: str) -> Path:
    tasks_path = tmp_path / "tasks.jsonl"
    tasks_path.write_text("")
    path = tmp_path / "cfg.toml"
    path.write_text(
        f"""
[experiment]
name = "ladder"
tasks = "{tasks_path}"
parent = "sonnet"
menu = ["sonnet", "opus"]
primary = {{ treatment = "L", control = "L" }}

[candidates.sonnet]
provider = "fake_test"
model = "sonnet"

[candidates.sonnet_adv]
provider = "fake_test"
model = "sonnet"
advisor = "opus"

[candidates.opus]
provider = "fake_test"
model = "opus"

[[policies]]
name = "L"
kind = "spawn_ladder"
frontier = "opus"
{policy}
"""
    )
    return path


LADDER = (
    'worker = "sonnet_adv"\nforced_check = true\nverifier = "verifier"\nk = 2\n'
    'handoff = "clean"\nescalate = true\n'
)


def _go(tmp_path: Path, policy: str, provider: ScriptedProvider):
    task = make_task(grader=MARKER_TASK_GRADER)
    out = _run(tmp_path, _cfg(tmp_path, policy), cast(Any, provider), [task], grader=marker_grader)
    return _sessions(out), _outcomes(out)[0]


def test_accepted_after_forced_advisor_check(tmp_path: Path):
    provider = ScriptedProvider({"sonnet": [fix(), say()]})
    sessions, outcome = _go(tmp_path, LADDER, provider)
    assert [s["role"] for s in sessions] == ["worker", "worker"]
    assert provider.calls[0]["advisor"] == "opus"
    assert provider.calls[1]["prompt"] == FORCED_CHECK_PROMPT
    assert provider.calls[1]["resume"] == sessions[0]["session_id"]
    assert "ESCALATE:" in provider.calls[0]["prompt"]
    assert ".verifier/test_*.py" in provider.calls[0]["prompt"]
    assert outcome["passed"] and outcome["escalations"] == 0
    events = [e["event"] for e in outcome["cascade_checks"]]
    assert events == ["worker", "forced_check", "verifier"]
    assert outcome["cascade_checks"][-1]["ok"] is True


def test_no_forced_check_when_the_advisor_was_consulted(tmp_path: Path):
    provider = ScriptedProvider({"sonnet": [fix()]}, advisor_calls=2)
    sessions, outcome = _go(tmp_path, LADDER, provider)
    assert [s["role"] for s in sessions] == ["worker"]
    assert outcome["cascade_checks"][0]["advisor_calls"] == 2
    assert outcome["passed"]


def test_k_verifier_failures_hand_off_to_a_clean_checkout(tmp_path: Path):
    provider = ScriptedProvider(
        {
            "sonnet": [fix(FAILING_TEST, marker=False), say(), say()],
            "opus": [fix()],
        },
        advisor_calls=1,
    )
    sessions, outcome = _go(tmp_path, LADDER, provider)
    assert [s["role"] for s in sessions] == ["worker", "worker", "escalation"]
    assert "not accepted" in provider.calls[1]["prompt"]
    handoff = provider.calls[2]
    assert handoff["model"] == "opus" and handoff["resume"] is None
    assert handoff["workdir"] != provider.calls[0]["workdir"]
    assert "clean checkout" in handoff["prompt"]
    assert "acceptance checks" in handoff["prompt"]
    assert outcome["escalations"] == 1 and outcome["chosen_candidate"] == "opus"
    assert outcome["passed"]
    assert outcome["cascade_checks"][-1] == {
        "event": "handoff",
        "trigger": "verifier",
        "mode": "clean",
    }


def test_missing_generated_tests_fail_the_verifier(tmp_path: Path):
    def only_marker(workdir: Path) -> dict[str, Any]:
        (workdir / "MARKER").touch()
        return {}

    provider = ScriptedProvider({"sonnet": [only_marker, say()], "opus": [fix()]}, advisor_calls=1)
    _, outcome = _go(tmp_path, LADDER, provider)
    reasons = [e["reason"] for e in outcome["cascade_checks"] if e["event"] == "verifier"]
    assert all("No generated acceptance tests" in r for r in reasons)
    assert outcome["escalations"] == 1


def test_escalate_line_hands_off_immediately(tmp_path: Path):
    provider = ScriptedProvider(
        {"sonnet": [say("I tried.\nESCALATE: the spec needs a deeper refactor")], "opus": [fix()]},
        advisor_calls=1,
    )
    sessions, outcome = _go(tmp_path, LADDER, provider)
    assert [s["role"] for s in sessions] == ["worker", "escalation"]
    assert outcome["cascade_checks"][-1]["trigger"] == "escalate"
    assert "the spec needs a deeper refactor" in provider.calls[1]["prompt"]


def test_turn_cap_is_the_no_progress_trigger(tmp_path: Path):
    provider = ScriptedProvider(
        {"sonnet": [say(error="Reached maximum number of turns (40)")], "opus": [fix()]}
    )
    sessions, outcome = _go(tmp_path, LADDER, provider)
    assert [s["role"] for s in sessions] == ["worker", "escalation"]
    assert outcome["cascade_checks"][-1]["trigger"] == "no_progress"


def test_carry_keeps_the_working_tree(tmp_path: Path):
    policy = LADDER.replace('handoff = "clean"', 'handoff = "carry"')
    provider = ScriptedProvider(
        {"sonnet": [fix(FAILING_TEST, marker=False), say()], "opus": [fix()]}, advisor_calls=1
    )
    _, outcome = _go(tmp_path, policy, provider)
    assert provider.calls[-1]["workdir"] == provider.calls[0]["workdir"]
    assert "still in the working tree" in provider.calls[-1]["prompt"]
    assert outcome["passed"]


def test_advisor_only_arm_never_hands_off(tmp_path: Path):
    policy = 'worker = "sonnet_adv"\nforced_check = true\n'
    provider = ScriptedProvider({"sonnet": [say("ESCALATE: help"), say()]})
    sessions, outcome = _go(tmp_path, policy, provider)
    assert [s["role"] for s in sessions] == ["worker", "worker"]
    assert "ESCALATE:" not in provider.calls[0]["prompt"]
    assert ".verifier" not in provider.calls[0]["prompt"]
    assert outcome["escalations"] == 0 and not outcome["passed"]


def test_explore_arm_without_advisor(tmp_path: Path):
    policy = 'worker = "sonnet"\nverifier = "verifier"\nk = 1\nhandoff = "clean"\n'
    provider = ScriptedProvider({"sonnet": [fix(FAILING_TEST)], "opus": [fix()]})
    sessions, outcome = _go(tmp_path, policy, provider)
    assert provider.calls[0]["advisor"] is None
    assert "advisor" not in provider.calls[0]["prompt"]
    assert [s["role"] for s in sessions] == ["worker", "escalation"]


def test_advisor_tokens_are_priced(tmp_path: Path):
    adv = {
        "claude-opus-5": {
            "input_tokens": 30000,
            "cache_read": 0,
            "cache_write": 0,
            "output_tokens": 1000,
        }
    }
    provider = ScriptedProvider(
        {"sonnet": [lambda w: {**fix()(w), "other_model_usage": adv}]}, advisor_calls=1
    )
    sessions, _ = _go(tmp_path, LADDER, provider)
    prices = PriceTable.load()
    own = prices.cost("sonnet", Usage(input_tokens=1000, output_tokens=100))
    advisor = prices.cost("claude-opus-5", Usage(input_tokens=30000, output_tokens=1000))
    assert sessions[0]["cost_usd_list"] == pytest.approx(own + advisor)
    assert sessions[0]["raw"]["other_model_cost_usd"] == pytest.approx(advisor)


def test_ladder_estimate_and_validation(tmp_path: Path):
    cfg = load_dispatch_config(_cfg(tmp_path, LADDER))
    est = estimate_dispatch(
        cfg, trials=1, task_loader=lambda *a, **k: [make_task()], history_dir=None
    )
    assert est["usd_high"] >= est["usd_mid"] >= est["usd_low"] > 0
    assert est["by_policy"]["L"] > 0
    bad = _cfg(tmp_path, 'worker = "gpt"\n')
    with pytest.raises(ValueError):
        load_dispatch_config(bad)


def test_build_args_passes_the_advisor():
    args = ClaudeAgentProvider().build_args(
        "sonnet",
        "hi",
        system=None,
        effort=None,
        max_turns=5,
        resume_session=None,
        fork=False,
        tools=True,
        max_budget_usd=1.0,
        advisor="opus",
    )
    assert args[args.index("--advisor") + 1] == "opus"
    plain = ClaudeAgentProvider().build_args(
        "sonnet",
        "hi",
        system=None,
        effort=None,
        max_turns=5,
        resume_session=None,
        fork=False,
        tools=True,
        max_budget_usd=1.0,
    )
    assert "--advisor" not in plain


def test_parse_splits_main_and_advisor_usage():
    events = [
        {
            "type": "assistant",
            "message": {"content": [{"type": "server_tool_use", "name": "advisor"}]},
        },
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Edit"}]}},
        {
            "type": "result",
            "result": "done",
            "num_turns": 5,
            "session_id": "s1",
            "total_cost_usd": 0.36,
            "usage": {
                "input_tokens": 12,
                "cache_read_input_tokens": 151327,
                "cache_creation_input_tokens": 33907,
                "output_tokens": 953,
            },
            "modelUsage": {
                "claude-opus-5": {
                    "inputTokens": 31119,
                    "outputTokens": 1253,
                    "cacheReadInputTokens": 0,
                    "cacheCreationInputTokens": 0,
                    "canonicalModel": "claude-opus-5",
                },
                "claude-sonnet-5": {
                    "inputTokens": 12,
                    "outputTokens": 953,
                    "cacheReadInputTokens": 151327,
                    "cacheCreationInputTokens": 33907,
                    "canonicalModel": "claude-sonnet-5",
                },
            },
        },
    ]
    res = parse_claude_stream("\n".join(json.dumps(e) for e in events), 10)
    assert res.resolved_model == "claude-sonnet-5"
    assert res.raw is not None
    assert res.raw["advisor_calls"] == 1
    assert res.raw["other_model_usage"] == {
        "claude-opus-5": {
            "input_tokens": 31119,
            "cache_read": 0,
            "cache_write": 0,
            "output_tokens": 1253,
        }
    }
    assert res.tool_calls == 1
