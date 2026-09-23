"""Tests for ``model_routing.dispatch.agents``.

Fixtures under ``tests/fixtures/dispatch/`` are event streams captured from
two real, tiny, budget-capped calls (one ``claude -p``, one ``codex exec``;
costs are noted in the workstream report) with paths/ids sanitized, plus a
couple of synthetic streams (a clean success, a Codex ``turn.failed``) built
in the same shape to cover paths the two real calls did not happen to hit.
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
import time
from pathlib import Path

from model_routing.dispatch.agents import (
    CODEX_NO_TOOLS_NOTICE,
    ClaudeAgentProvider,
    CodexAgentProvider,
    FakeAgentProvider,
    auth_check,
    make_agent_provider,
    parse_claude_stream,
    parse_codex_stream,
)
from model_routing.types import Usage

FIXTURES = Path(__file__).parent / "fixtures" / "dispatch"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text()


# --------------------------------------------------------------------------- #
# Claude: arg building
# --------------------------------------------------------------------------- #


def test_claude_build_args_minimal_no_tools_no_resume():
    args = ClaudeAgentProvider().build_args(
        "sonnet",
        "do the thing",
        system=None,
        effort=None,
        max_turns=5,
        resume_session=None,
        fork=False,
        tools=False,
        max_budget_usd=1.5,
    )
    assert args[:3] == ["claude", "-p", "do the thing"]
    assert "--output-format" in args and args[args.index("--output-format") + 1] == "stream-json"
    assert "--verbose" in args
    assert "--no-session-persistence" not in args  # sessions must stay resumable
    assert args[args.index("--tools") + 1] == ""
    assert "--allowedTools" not in args
    assert "--resume" not in args and "--fork-session" not in args
    assert args[args.index("--max-budget-usd") + 1] == "1.5"


def test_claude_build_args_tools_on_uses_allowlist_and_accept_edits():
    args = ClaudeAgentProvider().build_args(
        "opus",
        "fix the bug",
        system=None,
        effort=None,
        max_turns=10,
        resume_session=None,
        fork=False,
        tools=True,
        max_budget_usd=2.0,
    )
    assert "--tools" not in args  # tools=True means we DON'T disable tools
    allowed_idx = args.index("--allowedTools")
    allowed = args[allowed_idx + 1 : args.index("--permission-mode")]
    for tool in ("Read", "Edit", "Write", "Glob", "Grep"):
        assert tool in allowed
    assert any(a.startswith("Bash(python") for a in allowed)
    assert any(a.startswith("Bash(pytest") for a in allowed)
    assert any(a.startswith("Bash(git status") for a in allowed)
    assert args[args.index("--permission-mode") + 1] == "acceptEdits"


def test_claude_build_args_resume_and_fork():
    args = ClaudeAgentProvider().build_args(
        "sonnet",
        "continue",
        system=None,
        effort=None,
        max_turns=5,
        resume_session="ssn-123",
        fork=True,
        tools=False,
        max_budget_usd=1.0,
    )
    assert args[args.index("--resume") + 1] == "ssn-123"
    assert "--fork-session" in args


def test_claude_build_args_resume_without_fork_omits_fork_flag():
    args = ClaudeAgentProvider().build_args(
        "sonnet",
        "continue",
        system=None,
        effort=None,
        max_turns=5,
        resume_session="ssn-123",
        fork=False,
        tools=False,
        max_budget_usd=1.0,
    )
    assert args[args.index("--resume") + 1] == "ssn-123"
    assert "--fork-session" not in args


def test_claude_build_args_effort_and_default_system_prompt():
    provider = ClaudeAgentProvider()
    args = provider.build_args(
        "sonnet",
        "hi",
        system=None,
        effort="high",
        max_turns=3,
        resume_session=None,
        fork=False,
        tools=False,
        max_budget_usd=1.0,
    )
    assert args[args.index("--effort") + 1] == "high"
    assert args[args.index("--system-prompt") + 1] == provider.default_system
    assert "only inside the current" in provider.default_system


# --------------------------------------------------------------------------- #
# Codex: arg building
# --------------------------------------------------------------------------- #


def _codex_args(
    *,
    model: str = "gpt-5.6-luna",
    prompt: str = "do it",
    system: str | None = None,
    effort: str | None = None,
    resume_session: str | None = None,
    tools: bool = True,
    fork: bool = False,
) -> list[str]:
    return CodexAgentProvider().build_args(
        model,
        prompt,
        workdir=Path("/sandbox/task"),
        system=system,
        effort=effort,
        resume_session=resume_session,
        tools=tools,
        fork=fork,
    )


def _flag_values(args, flag):
    return [args[i + 1] for i, a in enumerate(args) if a == flag]


def test_codex_build_args_fresh_session_workspace_write():
    args = _codex_args(prompt="create hello.txt", effort="low", tools=True)
    assert args[:3] == ["codex", "exec", "-s"]
    assert args[args.index("-s") + 1] == "workspace-write"
    assert args[args.index("-C") + 1] == "/sandbox/task"
    assert 'sandbox_mode="workspace-write"' in _flag_values(args, "-c")
    assert args[args.index("-m") + 1] == "gpt-5.6-luna"
    assert 'model_reasoning_effort="low"' in args
    assert "--json" in args
    assert args[-1] == "create hello.txt"
    assert "shell_tool" not in args


def test_codex_build_args_isolation_flags_on_every_invocation_shape():
    shapes: list[tuple[bool, str | None, bool]] = [
        (True, None, False),
        (False, None, False),
        (True, "t-1", False),
        (False, "t-1", True),
    ]
    for tools, resume, fork in shapes:
        kw = (tools, resume, fork)
        args = _codex_args(tools=tools, resume_session=resume, fork=fork)
        for flag in ("--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "--json"):
            assert flag in args, (kw, flag)
        disabled = _flag_values(args, "--disable")
        for feature in ("plugins", "apps", "memories", "multi_agent"):
            assert feature in disabled, (kw, feature)
        assert 'web_search="disabled"' in _flag_values(args, "-c")
        assert "sandbox_workspace_write.network_access=false" in _flag_values(args, "-c")


def test_codex_build_args_no_tools_is_read_only_without_shell():
    args = _codex_args(prompt="look only", tools=False)
    assert args[args.index("-s") + 1] == "read-only"
    assert 'sandbox_mode="read-only"' in _flag_values(args, "-c")
    assert {"shell_tool", "unified_exec"} <= set(_flag_values(args, "--disable"))
    assert args[-1] == "look only" + CODEX_NO_TOOLS_NOTICE


def test_codex_build_args_resume_sets_sandbox_via_config_not_flags():
    args = _codex_args(
        model="gpt-5.6-terra", prompt="keep going", resume_session="thread-abc", tools=True
    )
    assert args[:4] == ["codex", "exec", "resume", "thread-abc"]
    # `codex exec resume` has no -s/-C; 0.154.0 takes the resumed thread's
    # sandbox from the current config, so it must be passed with -c or a
    # resumed worker would lose write access.
    assert "-s" not in args
    assert "-C" not in args
    assert 'sandbox_mode="workspace-write"' in _flag_values(args, "-c")
    assert args[args.index("-m") + 1] == "gpt-5.6-terra"
    assert args[-1] == "keep going"


def test_codex_build_args_resumed_router_without_tools_is_read_only():
    args = _codex_args(resume_session="thread-abc", tools=False)
    assert args[:4] == ["codex", "exec", "resume", "thread-abc"]
    assert 'sandbox_mode="read-only"' in _flag_values(args, "-c")
    assert 'sandbox_mode="workspace-write"' not in _flag_values(args, "-c")
    assert "shell_tool" in _flag_values(args, "--disable")


def test_codex_build_args_fork_uses_native_fork_subcommand_read_only():
    args = _codex_args(resume_session="thread-abc", fork=True, tools=False)
    assert args[:4] == ["codex", "exec", "fork", "thread-abc"]
    assert "-s" not in args and "-C" not in args
    assert 'sandbox_mode="read-only"' in _flag_values(args, "-c")


def test_codex_build_args_fork_without_resume_is_a_fresh_session():
    args = _codex_args(fork=True, tools=True)
    assert args[:2] == ["codex", "exec"]
    assert "fork" not in args[:4] and "resume" not in args[:4]


def test_codex_build_args_prepends_context_like_single_shot_provider():
    args = _codex_args(prompt="question", system="the brief", tools=True)
    assert args[-1].startswith("<context>\nthe brief\n</context>")


# --------------------------------------------------------------------------- #
# Claude: stream parsing
# --------------------------------------------------------------------------- #


def test_parse_claude_stream_budget_exhausted_real_capture():
    stdout = _read("claude_stream_haiku_budget_exhausted.jsonl")
    r = parse_claude_stream(stdout, wall_ms=4763)
    assert r.error is not None and "budget" in r.error.lower()
    assert r.session_id == "ssn-claude-sanitized-1"
    assert r.cost_usd_reported == 0.051103
    assert r.tool_calls == 1  # one Write tool_use block
    assert r.num_turns == 1
    assert r.raw is not None and r.raw["terminal_reason"] == "budget_exhausted"
    assert r.raw["permission_denials"] == 0
    # Real-world quirk: on a mid-stream budget cutoff the top-level `usage`
    # object in the final `result` event is zeroed even though `modelUsage`
    # (and the reported cost) reflect the real spend - see the module
    # docstring's parsing note and the workstream report.
    assert r.usage == Usage()
    assert r.resolved_model == "claude-haiku-4-5"


def test_parse_claude_stream_success():
    stdout = _read("claude_stream_sonnet_success.jsonl")
    r = parse_claude_stream(stdout, wall_ms=2431)
    assert r.error is None
    assert r.output == "Done - tests pass."
    assert r.session_id == "ssn-claude-sanitized-2"
    assert r.resolved_model == "claude-sonnet-5"
    assert r.num_turns == 4
    assert r.tool_calls == 2  # Edit + Bash
    assert r.usage.input_tokens == 826
    assert r.usage.cache_read == 4055
    assert r.usage.cache_write == 3200
    assert r.usage.cache_write_1h == 3200
    assert r.usage.output_tokens == 95
    assert r.cost_usd_reported == 0.016213


def test_parse_claude_stream_missing_result_event():
    r = parse_claude_stream('{"type":"system","subtype":"init"}\n', wall_ms=10)
    assert r.error is not None and "missing result event" in r.error


def test_parse_claude_stream_unparseable_lines_are_skipped():
    stdout = "not json\n{not valid json either}\n" + _read("claude_stream_sonnet_success.jsonl")
    r = parse_claude_stream(stdout, wall_ms=1)
    assert r.error is None
    assert r.session_id == "ssn-claude-sanitized-2"


def test_claude_run_reports_timeout(monkeypatch, tmp_path):
    import subprocess

    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=1)

    monkeypatch.setattr("model_routing.dispatch.agents.subprocess.run", fake_run)
    provider = ClaudeAgentProvider()
    result = provider.run("sonnet", "hi", workdir=tmp_path, timeout_s=1)
    assert result.error == "timeout"
    assert result.usage == Usage()


def test_claude_run_flags_nonzero_exit_without_result_event(monkeypatch, tmp_path):
    class FakeProc:
        stdout = ""
        stderr = "not logged in"
        returncode = 1

    monkeypatch.setattr("model_routing.dispatch.agents.subprocess.run", lambda *a, **k: FakeProc())
    provider = ClaudeAgentProvider()
    result = provider.run("sonnet", "hi", workdir=tmp_path)
    assert result.error is not None
    assert "missing result event" in result.error


# --------------------------------------------------------------------------- #
# Codex: stream parsing
# --------------------------------------------------------------------------- #


def test_parse_codex_stream_success_real_capture():
    stdout = _read("codex_stream_luna_success.jsonl")
    r = parse_codex_stream(stdout, wall_ms=4950)
    assert r.error is None
    assert r.output == "Created hello.txt containing hi."
    assert r.session_id == "thread-codex-sanitized-1"
    assert r.num_turns == 1
    assert r.tool_calls == 1  # one file_change
    assert r.usage.input_tokens == 27704 - 19968
    assert r.usage.cache_read == 19968
    assert r.usage.output_tokens == 105
    assert r.usage.reasoning == 13
    assert r.cost_usd_reported is None  # Codex never reports a dollar figure


def test_parse_codex_stream_turn_failed():
    stdout = _read("codex_stream_turn_failed.jsonl")
    r = parse_codex_stream(stdout, wall_ms=100)
    assert r.error is not None and "overloaded" in r.error
    assert r.session_id == "thread-codex-sanitized-2"


def test_parse_codex_stream_turn_failed_structured_error():
    stdout = (
        '{"type":"thread.started","thread_id":"t-9"}\n'
        '{"type":"turn.failed","error":{"message":"quota"}}\n'
    )
    r = parse_codex_stream(stdout, wall_ms=1)
    assert r.error == "quota"


def test_parse_codex_stream_retried_error_event_is_not_fatal():
    lines = _read("codex_stream_luna_success.jsonl").splitlines()
    lines.insert(2, json.dumps({"type": "error", "message": "Reconnecting... 1/5"}))
    r = parse_codex_stream("\n".join(lines), wall_ms=1)
    assert r.error is None
    assert r.raw is not None and r.raw["stream_errors"] == ["Reconnecting... 1/5"]


def test_parse_codex_stream_error_event_without_turn_completed_is_fatal():
    stdout = (
        '{"type":"thread.started","thread_id":"t-9"}\n{"type":"error","message":"auth expired"}\n'
    )
    assert parse_codex_stream(stdout, wall_ms=1).error == "auth expired"


# --------------------------------------------------------------------------- #
# Codex: running a (fake) codex binary - timeout, turn cap, usage accounting
# --------------------------------------------------------------------------- #


def _fake_codex(tmp_path: Path, body: str) -> str:
    """A stand-in ``codex`` executable: a Python script that ignores its args
    (they are appended to ``args.txt``) and runs ``body``."""
    script = tmp_path / "fake_codex.py"
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys, time\n"
        "from pathlib import Path\n"
        f"Path({str(tmp_path / 'args.txt')!r}).open('a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "def emit(ev):\n"
        "    print(json.dumps(ev), flush=True)\n" + textwrap.dedent(body)
    )
    script.chmod(0o755)
    return str(script)


def _usage_ev(inp, cached, out):
    return {
        "type": "turn.completed",
        "usage": {
            "input_tokens": inp,
            "cached_input_tokens": cached,
            "cache_write_input_tokens": 0,
            "output_tokens": out,
            "reasoning_output_tokens": 0,
        },
    }


def test_codex_run_success_via_binary(tmp_path):
    fixture = FIXTURES / "codex_stream_luna_success.jsonl"
    binary = _fake_codex(tmp_path, f"sys.stdout.write(open({str(fixture)!r}).read())\n")
    result = CodexAgentProvider(binary=binary).run("gpt-5.6-luna", "hi", workdir=tmp_path)
    assert result.error is None
    assert result.session_id == "thread-codex-sanitized-1"
    assert result.usage.cache_read == 19968
    assert result.raw is not None and result.raw["usage_source"] == "stream"


def test_codex_run_flags_nonzero_exit(tmp_path):
    fixture = FIXTURES / "codex_stream_luna_success.jsonl"
    binary = _fake_codex(
        tmp_path,
        f"sys.stdout.write(open({str(fixture)!r}).read())\nsys.stderr.write('boom')\nsys.exit(1)\n",
    )
    result = CodexAgentProvider(binary=binary).run("gpt-5.6-luna", "hi", workdir=tmp_path)
    assert result.error is not None and result.error.startswith("exit 1")


def test_codex_run_missing_binary_returns_error_result(tmp_path):
    result = CodexAgentProvider(binary=str(tmp_path / "nope")).run(
        "gpt-5.6-luna", "hi", workdir=tmp_path
    )
    assert result.error is not None and result.error.startswith("spawn failed")
    assert result.usage == Usage()


def test_codex_run_resume_and_fork_bill_only_their_own_tokens(tmp_path):
    # Codex reports thread-cumulative totals, and resume/fork seed them from the
    # parent: setup reports 1000 in / 200 cached / 50 out, then the resumed call
    # reports 1600 / 500 / 80 - of which only 600 / 300 / 30 are its own.
    binary = _fake_codex(
        tmp_path,
        """
        argv = sys.argv[1:]
        if argv[1] in ("resume", "fork"):
            tid = argv[2] if argv[1] == "resume" else "t-forked"
            emit({"type": "thread.started", "thread_id": tid})
            emit({"type": "turn.started"})
            emit({"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}})
            emit(RESUMED_USAGE)
        else:
            emit({"type": "thread.started", "thread_id": "t-setup"})
            emit({"type": "turn.started"})
            emit({"type": "item.completed", "item": {"type": "agent_message", "text": "ready"}})
            emit(SETUP_USAGE)
        """.replace("RESUMED_USAGE", repr(_usage_ev(1600, 500, 80))).replace(
            "SETUP_USAGE", repr(_usage_ev(1000, 200, 50))
        ),
    )
    provider = CodexAgentProvider(binary=binary, env={"CODEX_HOME": str(tmp_path / "ch")})
    setup = provider.run("gpt-5.6-sol", "seed", workdir=tmp_path)
    assert setup.usage == Usage(input_tokens=800, cache_read=200, output_tokens=50)

    resumed = provider.run("gpt-5.6-sol", "go", workdir=tmp_path, resume_session="t-setup")
    assert resumed.session_id == "t-setup"
    assert resumed.usage == Usage(input_tokens=300, cache_read=300, output_tokens=30)
    assert resumed.raw is not None
    assert resumed.raw["forked"] is False and resumed.raw["usage_baseline_known"] is True

    # The resume above moved t-setup's totals to 1600/500/80; a fork reporting
    # exactly those seeded totals has spent nothing of its own.
    forked = provider.run(
        "gpt-5.6-sol", "pick", workdir=tmp_path, resume_session="t-setup", fork=True, tools=False
    )
    assert forked.session_id == "t-forked"
    assert forked.raw is not None
    assert forked.raw["forked"] is True and forked.raw["forked_from"] == "t-setup"
    assert forked.raw["sandbox"] == "read-only"
    assert forked.usage.output_tokens == 0
    calls = [json.loads(x) for x in (tmp_path / "args.txt").read_text().splitlines()]
    assert calls[2][:3] == ["exec", "fork", "t-setup"]


def test_codex_run_timeout_kills_and_keeps_thread_id(tmp_path):
    binary = _fake_codex(
        tmp_path,
        """
        emit({"type": "thread.started", "thread_id": "t-slow"})
        emit({"type": "turn.started"})
        time.sleep(60)
        """,
    )
    t0 = time.monotonic()
    result = CodexAgentProvider(binary=binary).run(
        "gpt-5.6-luna", "hi", workdir=tmp_path, timeout_s=1
    )
    assert time.monotonic() - t0 < 20
    assert result.error == "timeout"
    assert result.session_id == "t-slow"  # usable result: runner grades the sandbox as-is
    assert result.raw is not None and result.raw["usage_source"] == "none"


def test_codex_run_timeout_bills_tokens_from_rollout(tmp_path):
    codex_home = tmp_path / "codex_home"
    day = codex_home / "sessions" / "2026" / "09" / "23"
    day.mkdir(parents=True)
    rollout = day / "rollout-2026-09-23T10-00-00-t-roll.jsonl"
    token_count = {
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {
                "total_token_usage": {
                    "input_tokens": 5000,
                    "cached_input_tokens": 3000,
                    "cache_write_input_tokens": 0,
                    "output_tokens": 400,
                    "reasoning_output_tokens": 100,
                    "total_tokens": 5400,
                }
            },
        },
    }
    rollout.write_text(
        json.dumps({"type": "session_meta", "payload": {}}) + "\n" + json.dumps(token_count) + "\n"
    )
    binary = _fake_codex(
        tmp_path,
        """
        emit({"type": "thread.started", "thread_id": "t-roll"})
        time.sleep(60)
        """,
    )
    provider = CodexAgentProvider(binary=binary, env={**os.environ, "CODEX_HOME": str(codex_home)})
    result = provider.run("gpt-5.6-luna", "hi", workdir=tmp_path, timeout_s=1)
    assert result.error == "timeout"
    assert result.raw is not None and result.raw["usage_source"] == "rollout"
    assert result.usage == Usage(
        input_tokens=2000, cache_read=3000, output_tokens=400, reasoning=100
    )


def test_codex_run_stops_at_turn_cap(tmp_path):
    binary = _fake_codex(
        tmp_path,
        """
        emit({"type": "thread.started", "thread_id": "t-loop"})
        emit({"type": "turn.started"})
        for i in range(50):
            emit({"type": "item.completed", "item": {"type": "command_execution", "command": "ls"}})
            time.sleep(0.05)
        emit({"type": "turn.completed", "usage": {}})
        """,
    )
    result = CodexAgentProvider(binary=binary).run(
        "gpt-5.6-luna", "hi", workdir=tmp_path, max_turns=3, timeout_s=30
    )
    assert result.error == "max_turns"
    assert result.session_id == "t-loop"
    assert 3 < result.tool_calls < 50


# --------------------------------------------------------------------------- #
# Fake provider: determinism, tiering, solution application
# --------------------------------------------------------------------------- #


def test_fake_provider_is_deterministic(tmp_path):
    p = FakeAgentProvider()
    r1 = p.run("haiku", "same prompt", workdir=tmp_path)
    r2 = p.run("haiku", "same prompt", workdir=tmp_path)
    assert r1.usage == r2.usage
    assert r1.num_turns == r2.num_turns
    assert r1.session_id == r2.session_id
    assert r1.tool_calls == r2.tool_calls


def test_fake_provider_usage_scales_with_tier(tmp_path):
    p = FakeAgentProvider()
    haiku = p.run("haiku", "x" * 100, workdir=tmp_path)
    sonnet = p.run("sonnet", "x" * 100, workdir=tmp_path)
    opus = p.run("opus", "x" * 100, workdir=tmp_path)
    assert haiku.usage.output_tokens < sonnet.usage.output_tokens < opus.usage.output_tokens

    luna = p.run("gpt-5.6-luna", "x" * 100, workdir=tmp_path)
    terra = p.run("gpt-5.6-terra", "x" * 100, workdir=tmp_path)
    sol = p.run("gpt-5.6-sol", "x" * 100, workdir=tmp_path)
    assert luna.usage.output_tokens < terra.usage.output_tokens < sol.usage.output_tokens


def test_fake_provider_usage_scales_with_prompt_length(tmp_path):
    p = FakeAgentProvider()
    short = p.run("sonnet", "hi", workdir=tmp_path)
    long = p.run("sonnet", "hi " * 2000, workdir=tmp_path)
    assert short.usage.input_tokens < long.usage.input_tokens


def test_fake_provider_resume_keeps_session_id_without_fork(tmp_path):
    p = FakeAgentProvider()
    r = p.run("sonnet", "continue", workdir=tmp_path, resume_session="parent-1", fork=False)
    assert r.session_id == "parent-1"


def test_fake_provider_resume_with_fork_gets_new_session_id(tmp_path):
    p = FakeAgentProvider()
    r = p.run("sonnet", "continue", workdir=tmp_path, resume_session="parent-1", fork=True)
    assert r.session_id != "parent-1"
    # deterministic: forking again with the same args gets the same new id
    r2 = p.run("sonnet", "continue", workdir=tmp_path, resume_session="parent-1", fork=True)
    assert r.session_id == r2.session_id


def test_fake_provider_resume_different_model_still_works(tmp_path):
    p = FakeAgentProvider()
    r1 = p.run("haiku", "continue", workdir=tmp_path, resume_session="parent-1")
    r2 = p.run("opus", "continue", workdir=tmp_path, resume_session="parent-1")
    assert r1.error is None and r2.error is None
    assert r1.session_id == r2.session_id == "parent-1"
    assert r1.usage.output_tokens != r2.usage.output_tokens


def test_fake_provider_no_solution_dir_leaves_task_unsolved(tmp_path):
    p = FakeAgentProvider()
    r = p.run("opus", "solve it", workdir=tmp_path, tools=True)
    assert r.raw is not None and r.raw["solution_applied"] is False
    assert "unsolved" in r.output


def test_fake_provider_applies_solution_and_always_cleans_up(tmp_path):
    sol_dir = tmp_path / ".fake_solution"
    (sol_dir / "src").mkdir(parents=True)
    (sol_dir / "src" / "fix.py").write_text("return total\n")

    p = FakeAgentProvider()
    # Strong model + a prompt/model pair whose stable hash rolls under the
    # tier's success probability - opus's tier probability is high (0.88), so
    # scanning a few prompt variants deterministically finds a passing one.
    applied = None
    for i in range(20):
        prompt = f"solve it variant {i}"
        r = p.run("opus", prompt, workdir=tmp_path, tools=True)
        if r.raw and r.raw["solution_applied"]:
            applied = r
            break
        # .fake_solution is removed after each attempt; recreate for the next.
        sol_dir.mkdir(parents=True, exist_ok=True)
        (sol_dir / "src").mkdir(parents=True, exist_ok=True)
        (sol_dir / "src" / "fix.py").write_text("return total\n")

    assert applied is not None
    assert (tmp_path / "src" / "fix.py").read_text() == "return total\n"
    assert not sol_dir.exists()  # always deleted, win or lose


def test_fake_provider_solution_not_applied_when_tools_false(tmp_path):
    sol_dir = tmp_path / ".fake_solution"
    (sol_dir / "marker.txt").parent.mkdir(parents=True, exist_ok=True)
    (sol_dir / "marker.txt").write_text("x")
    p = FakeAgentProvider()
    r = p.run("opus", "router call", workdir=tmp_path, tools=False)
    assert r.raw is not None and r.raw["solution_applied"] is False
    assert sol_dir.exists()  # untouched: only tools=True calls consume it


def test_fake_provider_unknown_model_defaults_to_mid_tier(tmp_path):
    p = FakeAgentProvider()
    r = p.run("some-new-model-nobody-has-priced-yet", "hi", workdir=tmp_path)
    assert r.error is None


# --------------------------------------------------------------------------- #
# Factory + auth_check
# --------------------------------------------------------------------------- #


def test_make_agent_provider_returns_right_types():
    assert make_agent_provider("claude_cli").name == "claude_cli"
    assert make_agent_provider("codex_cli").name == "codex_cli"
    assert make_agent_provider("fake").name == "fake"


def test_make_agent_provider_rejects_unknown_name():
    try:
        make_agent_provider("not_a_provider")
    except ValueError as e:
        assert "not_a_provider" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_make_agent_provider_passes_env_through():
    env = {"PATH": "/usr/bin"}
    p = make_agent_provider("claude_cli", env=env)
    assert p.env is env  # type: ignore[attr-defined]


def test_auth_check_fake_needs_no_auth():
    result = auth_check("fake")
    assert result == {"installed": True, "logged_in": None, "detail": "fake provider needs no auth"}


def test_auth_check_unknown_provider():
    result = auth_check("nope")
    assert result["installed"] is False


def test_auth_check_missing_binary(monkeypatch):
    monkeypatch.setattr("model_routing.dispatch.agents.shutil.which", lambda _b: None)
    result = auth_check("claude_cli")
    assert result["installed"] is False
    assert "PATH" in result["detail"]


def test_auth_check_claude_parses_json_status(monkeypatch):
    class FakeProc:
        returncode = 0
        stdout = json.dumps(
            {"loggedIn": True, "authMethod": "claude.ai", "email": "should-not-leak@example.com"}
        )
        stderr = ""

    monkeypatch.setattr("model_routing.dispatch.agents.shutil.which", lambda _b: "/usr/bin/claude")
    monkeypatch.setattr("model_routing.dispatch.agents.subprocess.run", lambda *a, **k: FakeProc())
    result = auth_check("claude_cli")
    assert result == {
        "installed": True,
        "logged_in": True,
        "detail": "authMethod=claude.ai",
    }
    assert "should-not-leak" not in json.dumps(result)


def test_auth_check_codex_parses_status_text(monkeypatch):
    class FakeProc:
        returncode = 0
        stdout = "Logged in using ChatGPT\n"
        stderr = ""

    monkeypatch.setattr("model_routing.dispatch.agents.shutil.which", lambda _b: "/usr/bin/codex")
    monkeypatch.setattr("model_routing.dispatch.agents.subprocess.run", lambda *a, **k: FakeProc())
    result = auth_check("codex_cli")
    assert result["installed"] is True
    assert result["logged_in"] is True


def test_auth_check_timeout(monkeypatch):
    import subprocess

    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=10)

    monkeypatch.setattr("model_routing.dispatch.agents.shutil.which", lambda _b: "/usr/bin/claude")
    monkeypatch.setattr("model_routing.dispatch.agents.subprocess.run", fake_run)
    result = auth_check("claude_cli")
    assert result["logged_in"] is None
    assert "timed out" in result["detail"]
