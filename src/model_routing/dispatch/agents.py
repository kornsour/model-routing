"""Agent providers for dispatch-time routing: Claude Code, Codex, and a fake.

These are *agentic* sessions - tools enabled, multiple turns, resumable -
unlike ``model_routing.providers.claude_cli`` / ``codex_cli``, which make one
suppressed-tools call and never resume.  The flag sets below trade the single-
shot providers' minimalism for exactly what dispatch policies need: a session
id to resume (A / A_switch / C1), a fork that keeps the parent reusable (C1),
and tools confined to ``workdir`` so an agent can actually do the task.

Why the CLI and not an SDK, and why subscription auth is scrubbed the same
way: see ``providers/claude_cli.py``'s docstring - it all still applies here.

Parsing note: ``claude -p --output-format stream-json`` emits one JSON object
per line (``system``, ``assistant``, ``user``, ``result``, ...).  Only the
final ``result`` event carries session totals (usage, cost, turns); summing
per-``assistant``-message usage would double count retries and is wrong.
Tool calls are not in ``result``, so they are counted separately by walking
``assistant`` events for ``tool_use`` content blocks.  Codex's
``codex exec --json`` stream has no single terminal totals event; usage comes
from ``turn.completed`` (thread-cumulative: see ``CodexAgentProvider``).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from model_routing.dispatch.types import AgentProvider, AgentResult
from model_routing.types import Usage

DEFAULT_AGENT_SYSTEM_PROMPT = (
    "You are a careful autonomous coding agent working headless, with no "
    "human to ask. Work only inside the current directory; never read or "
    "write files outside it. Make the smallest change that satisfies the "
    "brief, run any visible checks the brief describes (the test suite runs "
    "with `python -m pytest -q`), and stop once the task is done - do not "
    "keep exploring after it passes."
)

# Enough to read, edit, and run a Python test suite; nothing that reaches
# outside the sandbox (no curl/network, no rm -rf, no arbitrary shell).
CLAUDE_AGENT_FILE_TOOLS: tuple[str, ...] = ("Read", "Edit", "Write", "Glob", "Grep")
CLAUDE_AGENT_BASH_ALLOWLIST: tuple[str, ...] = (
    "Bash(python:*)",
    "Bash(python3:*)",
    "Bash(pytest:*)",
    "Bash(git status)",
    "Bash(git status:*)",
    "Bash(ls:*)",
    "Bash(cat:*)",
)

_FAKE_NS = uuid.UUID("6f6f3b5a-6e5a-4a3a-9a5a-2f6a1e0c9d3b")


# --------------------------------------------------------------------------- #
# Claude Code
# --------------------------------------------------------------------------- #


class ClaudeAgentProvider:
    """``claude -p`` with tools, resume/fork, and stream-json parsing."""

    name = "claude_cli"

    def __init__(
        self,
        binary: str = "claude",
        env: dict[str, str] | None = None,
        default_system: str = DEFAULT_AGENT_SYSTEM_PROMPT,
    ):
        self.binary = binary
        self.env = env
        self.default_system = default_system

    def build_args(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None,
        effort: str | None,
        max_turns: int,
        resume_session: str | None,
        fork: bool,
        tools: bool,
        max_budget_usd: float,
    ) -> list[str]:
        args = [
            self.binary,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--model",
            model,
            "--max-turns",
            str(max_turns),
            "--max-budget-usd",
            str(max_budget_usd),
            "--setting-sources",
            "",
            "--strict-mcp-config",
            "--system-prompt",
            system or self.default_system,
        ]
        if effort:
            args += ["--effort", effort]
        if resume_session:
            args += ["--resume", resume_session]
            if fork:
                # --fork-session only makes sense alongside --resume/--continue.
                args.append("--fork-session")
        if tools:
            args += ["--allowedTools", *CLAUDE_AGENT_FILE_TOOLS, *CLAUDE_AGENT_BASH_ALLOWLIST]
            # acceptEdits auto-approves the file edits Write/Edit would
            # otherwise prompt for; everything else stays gated by the
            # --allowedTools allowlist above, so nothing outside it runs.
            args += ["--permission-mode", "acceptEdits"]
        else:
            args += ["--tools", ""]
        return args

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
        args = self.build_args(
            model,
            prompt,
            system=system,
            effort=effort,
            max_turns=max_turns,
            resume_session=resume_session,
            fork=fork,
            tools=tools,
            max_budget_usd=max_budget_usd,
        )
        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                args,
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
                stdin=subprocess.DEVNULL,
                env=self.env,
            )
        except subprocess.TimeoutExpired:
            return AgentResult(
                output="",
                usage=Usage(),
                duration_ms=int((time.monotonic() - t0) * 1000),
                error="timeout",
            )
        wall_ms = int((time.monotonic() - t0) * 1000)
        result = parse_claude_stream(proc.stdout, wall_ms, stderr=proc.stderr)
        if result.error is None and proc.returncode != 0:
            result.error = f"exit {proc.returncode}: {(proc.stderr or '').strip()[-300:]}"
        return result


_USAGE_LIMIT_RE = re.compile(
    r"usage limit reached(?:\|(?P<epoch>\d{9,11}))?"
    r"|(?:usage|spend|spending|monthly|weekly|session) limit"
    r"|limit resets"
    r"|rate.?limit"
    r"|\b429\b"
    r"|out of extra usage",
    re.IGNORECASE,
)
"""Every wording the Claude CLI has used for an account limit.  Seen on
2026-09-23: "You've hit your monthly spend limit · raise it at ... · your
session limit resets 5:40pm (America/Detroit)" (no epoch, so the runner
polls).  Keep this broad: a limit graded as a fail poisons a whole run."""


_ACCOUNT_LIMIT_REPLY_RE = re.compile(
    r"usage limit reached|hit your [\w ]{0,20}limit|limit resets|out of extra usage",
    re.IGNORECASE,
)
"""Stricter than ``_USAGE_LIMIT_RE``: for a result *not* flagged as an error, only
the account-limit wordings count (never "rate limit"/"429", which a worker on a
retry task may legitimately write), and only on a short, at-most-one-turn reply."""


def usage_limit_in_reply(text: str, num_turns: int) -> float | None:
    """A limit notice returned as an ordinary (``is_error: false``) result.  The
    CLI has flagged these as errors in every run so far; this guards the
    6-8 hour confirmatory run against a wording or flag change grading a
    limit hit as a fail."""
    if num_turns > 1 or not text or len(text) > 400:
        return None
    if not _ACCOUNT_LIMIT_REPLY_RE.search(text):
        return None
    return usage_limit_reset_at(text) or 0.0


_PROVIDER_OUTAGE_RE = re.compile(
    r"API Error: (?:5\d\d|Connection|Request timed out)"
    r"|overloaded_error|\bOverloaded\b|api_error|internal server error"
    r"|ECONNRESET|ECONNREFUSED|ETIMEDOUT|ENOTFOUND|EAI_AGAIN|socket hang up|fetch failed",
    re.IGNORECASE,
)
"""Server-side or network failures (5xx, overloaded, dropped connections) that
survived the CLI's own retries.  They measure the provider's availability,
not the model, so the runner pauses and redoes the cell like a usage limit.
Deliberately excludes 4xx (a request the harness or the model made bad), the
turn cap, the wall-clock ``timeout`` and the per-session budget cap, which are
graded outcomes under intention to treat."""


def is_provider_outage(text: str | None) -> bool:
    """True when ``text`` (an error message or stderr) reports a provider outage."""
    return bool(text) and _PROVIDER_OUTAGE_RE.search(text or "") is not None


def usage_limit_reset_at(text: str) -> float | None:
    """If ``text`` (a result/error message or stderr) says the subscription or
    API usage limit was hit, return the reset time as a unix timestamp when the
    message carries one (``Claude AI usage limit reached|<epoch>``), else 0.0
    (limit hit, reset time unknown).  ``None`` means it is not a limit error.
    A limit hit is a *pause* condition for the runner, never a graded fail."""
    if not text:
        return None
    m = _USAGE_LIMIT_RE.search(text)
    if not m:
        return None
    epoch = m.groupdict().get("epoch")
    return float(epoch) if epoch else 0.0


def parse_claude_stream(stdout: str, wall_ms: int, stderr: str = "") -> AgentResult:
    """Fold ``--output-format stream-json`` events into one :class:`AgentResult`.

    Mirrors ``providers.claude_cli.parse_result`` for the final ``result``
    event's usage/cost/model fields (including the 1-hour cache-write split),
    and additionally counts ``tool_use`` content blocks across ``assistant``
    events, which single-shot ``--output-format json`` never has because
    ``--tools ""`` disables tools there.
    """
    tool_calls = 0
    result_event: dict[str, Any] | None = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = ev.get("type")
        if kind == "assistant":
            content = ((ev.get("message") or {}).get("content")) or []
            tool_calls += sum(
                1
                for block in content
                if isinstance(block, dict) and block.get("type") == "tool_use"
            )
        elif kind == "result":
            result_event = ev
    if result_event is None:
        err_tail = (stderr or "").strip()[-300:]
        detail = f"missing result event: {err_tail}" if err_tail else "missing result event"
        reset = usage_limit_reset_at((stderr or "") + "\n" + stdout[-2000:])
        return AgentResult(
            output="",
            usage=Usage(),
            duration_ms=wall_ms,
            tool_calls=tool_calls,
            error="usage_limit" if reset is not None else detail,
            raw={"usage_limit_reset_at": reset} if reset is not None else None,
        )
    data = result_event
    u = data.get("usage") or {}
    usage = Usage(
        input_tokens=int(u.get("input_tokens", 0)),
        cache_read=int(u.get("cache_read_input_tokens", 0)),
        cache_write=int(u.get("cache_creation_input_tokens", 0)),
        output_tokens=int(u.get("output_tokens", 0)),
        reasoning=int((u.get("output_tokens_details") or {}).get("thinking_tokens", 0)),
        cache_write_1h=int((u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens", 0)),
    )
    model_usage = data.get("modelUsage") or {}
    resolved = None
    if model_usage:
        key = list(model_usage)[-1]
        resolved = model_usage[key].get("canonicalModel") or key
    error = None
    reset: float | None = None
    if data.get("is_error"):
        text = data.get("result")
        if not text:
            errors = data.get("errors")
            text = "; ".join(errors) if errors else "error"
        error = str(text)[:500]
        reset = usage_limit_reset_at(str(text) + "\n" + (stderr or ""))
        if reset is not None:
            error = "usage_limit"
        elif not is_provider_outage(error) and is_provider_outage(stderr):
            error = f"{error} [stderr: {(stderr or '').strip()[-200:]}]"
    else:
        reset = usage_limit_in_reply(str(data.get("result") or ""), int(data.get("num_turns") or 0))
        if reset is not None:
            error = "usage_limit"
    return AgentResult(
        output=str(data.get("result", "")),
        usage=usage,
        duration_ms=int(data.get("duration_ms", wall_ms)),
        num_turns=int(data.get("num_turns", 0)),
        tool_calls=tool_calls,
        session_id=data.get("session_id"),
        resolved_model=resolved,
        cost_usd_reported=float(data["total_cost_usd"]) if "total_cost_usd" in data else None,
        error=error,
        raw={
            "stop_reason": data.get("stop_reason"),
            "num_turns": data.get("num_turns"),
            "session_id": data.get("session_id"),
            "terminal_reason": data.get("terminal_reason"),
            "modelUsage": model_usage or None,
            "permission_denials": len(data.get("permission_denials") or []),
            "usage_limit_reset_at": reset,
        },
    )


# --------------------------------------------------------------------------- #
# Codex
# --------------------------------------------------------------------------- #

CODEX_CLI_VERSION_CHECKED = "0.154.0"
"""The ``codex-cli`` version the flags below were checked against (``--help`` of
``codex exec``, ``codex exec resume`` and ``codex exec fork``, and the
``rust-v0.154.0`` source of ``codex-rs/exec``)."""

# Applied to every Codex session (fresh, resume, fork), so a run measures the
# model and the task rather than the operator's local Codex setup - the
# counterpart of the Claude track's ``--setting-sources "" --strict-mcp-config``.
# Every flag and value was validated against 0.154.0's config loader (an
# unknown feature or value is a hard error there).
CODEX_ISOLATION_ARGS: tuple[str, ...] = (
    "--ignore-user-config",  # no ~/.codex/config.toml (auth still comes from CODEX_HOME)
    "--ignore-rules",  # no user execpolicy rules: approved prefixes would run *outside* the sandbox
    "--skip-git-repo-check",
    # Nothing that reaches past the sandbox, spawns sub-agents on other models,
    # or carries state between trials (memories).
    "--disable",
    "plugins",
    "--disable",
    "apps",
    "--disable",
    "memories",
    "--disable",
    "multi_agent",
    "--disable",
    "image_generation",
    "--disable",
    "browser_use",
    "--disable",
    "computer_use",
    "-c",
    'web_search="disabled"',
    "-c",
    "sandbox_workspace_write.network_access=false",
)

# ``tools=False`` (router / classifier calls).  Claude gets ``--tools ""``;
# Codex has no switch that removes every tool, so: the read-only sandbox (the
# hard guarantee - no file can change), the shell tools switched off, and a
# one-line notice appended to the prompt so the model does not burn turns on
# tool calls that would be refused anyway.
CODEX_NO_TOOLS_ARGS: tuple[str, ...] = ("--disable", "shell_tool", "--disable", "unified_exec")
CODEX_NO_TOOLS_NOTICE = (
    "\n\n(Answer from this conversation alone: do not run commands, read files, "
    "or modify any files.)"
)

_CODEX_TOOL_ITEM_TYPES = frozenset(
    {
        "file_change",
        "command_execution",
        "mcp_tool_call",
        "collab_tool_call",
        "web_search",
        "local_shell_call",
    }
)
_CODEX_USAGE_KEYS: tuple[str, ...] = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


class CodexAgentProvider:
    """``codex exec`` / ``codex exec resume`` / ``codex exec fork`` with JSONL parsing.

    Checked against codex-cli 0.154.0 (``CODEX_CLI_VERSION_CHECKED``).  How each
    part of the dispatch contract maps onto that CLI:

    * **Sandbox.**  ``resume`` and ``fork`` accept neither ``-s`` nor ``-C``, but
      they do *not* inherit the original session's sandbox either: 0.154.0
      builds the resumed/forked thread's sandbox and cwd from the *current*
      invocation's config (``thread_resume_params_from_config`` in
      ``codex-rs/exec/src/lib.rs``).  So every call passes
      ``-c sandbox_mode=...`` explicitly (fresh sessions also get ``-s``), and
      the process cwd is ``workdir``.  Without it a resumed ``tools=True``
      worker (A / A_switch) would fall back to the default sandbox, and a
      resumed ``tools=False`` router could get a writable one.
    * **Fork.**  0.154.0 has ``codex exec fork <id>``: a new thread seeded
      with the parent's history, the parent left untouched - the same
      semantics as Claude's ``--resume --fork-session``, so ``fork=True`` uses
      it.  ``raw`` records ``forked`` and ``forked_from``.
    * **No tools.**  ``tools=False`` means a read-only sandbox plus
      ``CODEX_NO_TOOLS_ARGS`` plus ``CODEX_NO_TOOLS_NOTICE`` on the prompt; a
      no-tools call can never change a file, but unlike Claude's
      ``--tools ""`` the model may still *attempt* a tool call (counted in
      ``tool_calls``).
    * **Turn cap.**  Codex has no ``--max-turns``.  The provider streams the
      JSONL and stops the session (whole process group) once it has made more
      than ``max_turns`` tool calls - an approximation: Claude counts model
      turns, and one Codex turn can batch several tool calls, so the Codex
      cap binds no later than Claude's.  ``error = "max_turns"``.
    * **Spend cap.**  No ``--max-budget-usd`` equivalent and no stable config
      knob (``token_budget`` / ``rollout_budget`` are "under development" in
      0.154.0), so ``max_budget_usd`` is ignored and the budget is policed
      only *between* sessions by the runner; the wall-clock ``timeout_s`` is
      the only hard stop inside one.  ``error = "timeout"``.
    * **Usage.**  ``turn.completed`` carries the *thread's cumulative* totals,
      and resume/fork seed those totals from the parent's rollout
      (``codex-rs/core/src/session/mod.rs``), so a resumed or forked session
      would re-bill its parent.  The provider subtracts the parent's last
      known totals (from an earlier call on this instance, else the parent's
      rollout file).  When the stream has no totals (timeout, cap, failed
      turn) the tokens actually spent are read back from the session's
      rollout file under ``$CODEX_HOME/sessions`` so an interrupted session is
      still billed (intention to treat).  ``raw["usage_source"]`` says which.

    Every failure mode returns an :class:`AgentResult` with ``error`` set and
    never raises, so the runner grades the sandbox as the agent left it.
    """

    name = "codex_cli"

    def __init__(self, binary: str = "codex", env: dict[str, str] | None = None):
        self.binary = binary
        self.env = env
        # thread id -> last cumulative raw usage totals seen for it, so a later
        # resume/fork of that thread is billed only its own tokens.
        self._thread_totals: dict[str, dict[str, int]] = {}

    def build_args(
        self,
        model: str,
        prompt: str,
        *,
        workdir: Path,
        system: str | None,
        effort: str | None,
        resume_session: str | None,
        tools: bool,
        fork: bool = False,
    ) -> list[str]:
        full_prompt = prompt if not system else f"<context>\n{system}\n</context>\n\n{prompt}"
        if not tools:
            full_prompt += CODEX_NO_TOOLS_NOTICE
        sandbox = "workspace-write" if tools else "read-only"
        if resume_session:
            # No -s/-C on resume/fork: the sandbox comes from -c below and the
            # cwd from the process cwd (run() uses workdir).
            args = [self.binary, "exec", "fork" if fork else "resume", resume_session]
        else:
            args = [self.binary, "exec", "-s", sandbox, "-C", str(workdir)]
        args += ["--json", *CODEX_ISOLATION_ARGS, "-c", f'sandbox_mode="{sandbox}"']
        args += ["-m", model]
        if effort:
            args += ["-c", f'model_reasoning_effort="{effort}"']
        if not tools:
            args += list(CODEX_NO_TOOLS_ARGS)
        args.append(full_prompt)
        return args

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
        del max_budget_usd  # no native or config equivalent; see class docstring
        args = self.build_args(
            model,
            prompt,
            workdir=workdir,
            system=system,
            effort=effort,
            resume_session=resume_session,
            tools=tools,
            fork=fork,
        )
        t0 = time.monotonic()
        try:
            returncode, stdout, stderr, stopped = _run_codex_process(
                args, workdir=workdir, env=self.env, timeout_s=timeout_s, max_tool_calls=max_turns
            )
        except OSError as exc:  # binary missing, bad cwd, ...
            return AgentResult(
                output="",
                usage=Usage(),
                duration_ms=int((time.monotonic() - t0) * 1000),
                error=f"spawn failed: {exc}"[:500],
                raw={"usage_source": "none"},
            )
        wall_ms = int((time.monotonic() - t0) * 1000)
        result = parse_codex_stream(stdout, wall_ms)
        raw = dict(result.raw or {})

        # Usage: the stream's cumulative totals, else the rollout file's; then
        # subtract what the parent thread had already been billed.
        totals = raw.get("usage_total")
        source = "stream" if totals else "none"
        if totals is None and result.session_id:
            totals = _rollout_totals(result.session_id, self.env)
            source = "rollout" if totals else "none"
        baseline = None
        if resume_session:
            baseline = self._thread_totals.get(resume_session)
            if baseline is None:
                baseline = _rollout_totals(resume_session, self.env)
            raw["usage_baseline_known"] = baseline is not None
        if totals is not None:
            own = {
                k: max(int(totals.get(k, 0)) - int((baseline or {}).get(k, 0)), 0)
                for k in _CODEX_USAGE_KEYS
            }
            result.usage = _codex_usage(own)
            if result.session_id:
                self._thread_totals[result.session_id] = {
                    k: int(totals.get(k, 0)) for k in _CODEX_USAGE_KEYS
                }
        raw["usage_source"] = source

        if stopped is not None:
            result.error = stopped
        elif result.error is None and returncode != 0:
            result.error = f"exit {returncode}: {(stderr or '').strip()[-300:]}"
        if result.error is None and not result.output and not result.session_id:
            result.error = "no agent_message / thread id in output"
        if resume_session:
            raw["forked"] = bool(fork)
            raw["resumed_from"] = resume_session
            if fork:
                raw["forked_from"] = resume_session
        raw["sandbox"] = "workspace-write" if tools else "read-only"
        result.raw = raw
        return result


def _codex_usage(u: dict[str, Any]) -> Usage:
    """Codex's ``input_tokens`` includes the cached part; ``Usage`` keeps them disjoint."""
    cached = int(u.get("cached_input_tokens", 0))
    return Usage(
        input_tokens=max(int(u.get("input_tokens", 0)) - cached, 0),
        cache_read=cached,
        cache_write=int(u.get("cache_write_input_tokens", 0)),
        output_tokens=int(u.get("output_tokens", 0)),
        reasoning=int(u.get("reasoning_output_tokens", 0)),
    )


def _is_codex_tool_item(line: str) -> bool:
    if '"item.completed"' not in line:
        return False
    try:
        ev = json.loads(line)
    except json.JSONDecodeError:
        return False
    return ((ev.get("item") or {}).get("type")) in _CODEX_TOOL_ITEM_TYPES


def _kill_process_group(proc: subprocess.Popen[str]) -> None:
    """Stop codex *and* whatever it spawned (a hung test run, a shell)."""
    for sig, grace in ((signal.SIGTERM, 5.0), (signal.SIGKILL, 5.0)):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=grace)
            return
        except subprocess.TimeoutExpired:
            continue


def _run_codex_process(
    args: list[str],
    *,
    workdir: Path,
    env: dict[str, str] | None,
    timeout_s: float,
    max_tool_calls: int | None,
) -> tuple[int | None, str, str, str | None]:
    """Run ``args`` streaming stdout; return ``(returncode, stdout, stderr, stopped)``.

    ``stopped`` is ``"timeout"`` when the wall clock ran out and ``"max_turns"``
    when the session made more than ``max_tool_calls`` tool calls; in both cases
    the whole process group was killed and the output captured *so far* is
    returned, so the caller still gets the thread id (and can bill the tokens).
    """
    proc = subprocess.Popen(
        args,
        cwd=str(workdir),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,  # own process group, so a kill reaches every child
    )
    out_lines: list[str] = []
    err_chunks: list[str] = []
    cap_hit = threading.Event()

    def read_stdout() -> None:
        assert proc.stdout is not None
        tools_seen = 0
        for line in proc.stdout:
            out_lines.append(line)
            if max_tool_calls and _is_codex_tool_item(line):
                tools_seen += 1
                if tools_seen > max_tool_calls:
                    cap_hit.set()

    def read_stderr() -> None:
        assert proc.stderr is not None
        err_chunks.append(proc.stderr.read())

    readers = [
        threading.Thread(target=read_stdout, daemon=True),
        threading.Thread(target=read_stderr, daemon=True),
    ]
    for t in readers:
        t.start()
    deadline = time.monotonic() + timeout_s
    stopped: str | None = None
    while True:
        try:
            proc.wait(timeout=0.2)
            break
        except subprocess.TimeoutExpired:
            pass
        if cap_hit.is_set():
            stopped = "max_turns"
        elif time.monotonic() >= deadline:
            stopped = "timeout"
        if stopped:
            _kill_process_group(proc)
            break
    for t in readers:
        t.join(timeout=10)  # a detached grandchild holding the pipe must not hang us
    return proc.returncode, "".join(out_lines), "".join(err_chunks), stopped


def _codex_home(env: dict[str, str] | None) -> Path:
    home = (env or {}).get("CODEX_HOME") or os.environ.get("CODEX_HOME")
    return Path(home) if home else Path.home() / ".codex"


def _rollout_totals(thread_id: str, env: dict[str, str] | None) -> dict[str, int] | None:
    """Last cumulative ``total_token_usage`` recorded in a thread's rollout file.

    Codex persists every session to
    ``$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<timestamp>-<thread id>.jsonl`` and
    appends a ``token_count`` event after each model response, so this is the
    spend up to the moment the session stopped even when the JSONL stream never
    got to ``turn.completed``.  Returns ``None`` when there is no such file or it
    has no token count.  Reads only ``token_count`` lines.
    """
    if not re.fullmatch(r"[0-9A-Za-z-]+", thread_id or ""):
        return None
    sessions = _codex_home(env) / "sessions"
    if not sessions.is_dir():
        return None
    matches = sorted(sessions.glob(f"*/*/*/rollout-*{thread_id}.jsonl")) or sorted(
        sessions.rglob(f"rollout-*{thread_id}.jsonl")
    )
    last: dict[str, Any] | None = None
    for path in matches[-1:]:
        try:
            with path.open() as fh:
                for line in fh:
                    if '"token_count"' not in line:
                        continue
                    try:
                        payload = json.loads(line).get("payload") or {}
                    except json.JSONDecodeError:
                        continue
                    total = (payload.get("info") or {}).get("total_token_usage")
                    if isinstance(total, dict):
                        last = total
        except OSError:
            return None
    if last is None:
        return None
    return {k: int(last.get(k, 0)) for k in _CODEX_USAGE_KEYS}


def parse_codex_stream(stdout: str, wall_ms: int) -> AgentResult:
    """Fold ``codex exec --json`` JSONL events into one :class:`AgentResult`.

    Extends ``providers.codex_cli.parse_jsonl``'s usage normalization (Codex's
    ``input_tokens`` includes the cached portion; ``Usage`` keeps them
    disjoint) with turn counting and tool-call counting from ``item.completed``
    events, which the single-shot provider never sees tools to report.

    ``usage`` here is ``turn.completed``'s figure as-is, which Codex reports as
    the *thread's cumulative* total; the raw totals are kept in
    ``raw["usage_total"]`` so :class:`CodexAgentProvider` can subtract a
    resumed/forked parent's share.

    A top-level ``error`` event is not fatal by itself (0.154.0 also emits one
    for a transient stream error it then retries), so it only becomes
    ``error`` when the turn never completed; ``turn.failed`` always does.
    Every ``error`` message is kept in ``raw["stream_errors"]``.
    """
    output = ""
    usage = Usage()
    usage_total: dict[str, int] | None = None
    turn_failed: str | None = None
    stream_errors: list[str] = []
    session_id = None
    num_turns = 0
    tool_calls = 0
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = ev.get("type")
        if kind == "thread.started":
            session_id = ev.get("thread_id")
        elif kind == "turn.started":
            num_turns += 1
        elif kind == "item.completed":
            item = ev.get("item") or {}
            itype = item.get("type")
            if itype == "agent_message":
                output = str(item.get("text", ""))
            elif itype in _CODEX_TOOL_ITEM_TYPES:
                tool_calls += 1
        elif kind == "turn.completed":
            u = ev.get("usage") or {}
            usage_total = {k: int(u.get(k, 0)) for k in _CODEX_USAGE_KEYS}
            usage = _codex_usage(u)
        elif kind == "turn.failed":
            err = ev.get("error")
            msg = err.get("message") if isinstance(err, dict) else err
            turn_failed = str(msg or ev)[:500]
        elif kind == "error":
            stream_errors.append(str(ev.get("message") or ev.get("error") or ev)[:500])
    error = turn_failed
    if error is None and usage_total is None and stream_errors:
        error = stream_errors[-1]
    return AgentResult(
        output=output,
        usage=usage,
        duration_ms=wall_ms,
        num_turns=num_turns,
        tool_calls=tool_calls,
        session_id=session_id,
        resolved_model=None,
        cost_usd_reported=None,  # Codex reports no dollars; runner prices from pricing.toml
        error=error,
        raw={"thread_id": session_id, "usage_total": usage_total, "stream_errors": stream_errors},
    )


# --------------------------------------------------------------------------- #
# Fake
# --------------------------------------------------------------------------- #

# Coarser than pricing.toml's rows on purpose: this only orders *tiers*, not
# exact models, so it keeps working if a new model alias appears.
_TIER_RANK: dict[str, int] = {
    "haiku": 1,
    "luna": 1,
    "terra": 2,
    "sonnet": 2,
    "sol": 3,
    "opus": 3,
    "fable": 4,
}
_TIER_QUALITY: dict[int, float] = {1: 0.45, 2: 0.70, 3: 0.88, 4: 0.95}
_TIER_TOKEN_MULT: dict[int, float] = {1: 1.0, 2: 1.4, 3: 2.0, 4: 2.6}


def _tier_rank(model: str) -> int:
    low = model.lower()
    for key in sorted(_TIER_RANK, key=len, reverse=True):
        if key in low:
            return _TIER_RANK[key]
    return 2  # unknown model: assume mid tier rather than crash


def _stable_unit_interval(*parts: str) -> float:
    """Deterministic pseudo-random float in [0, 1) from a stable hash."""
    digest = hashlib.sha256("\x00".join(parts).encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


class FakeAgentProvider:
    """Deterministic, no-subprocess stand-in for end-to-end dry runs.

    Usage scales with model tier (worse/cheaper models write more, thanks to
    retries and verbosity, but see fewer tokens of "thinking") and prompt
    length, never spends anything, and never touches the network. Whether the
    sandbox ends up passing is driven by ``workdir/.fake_solution/`` - see the
    module docstring in ``dispatch/types.py`` and the class-level contract
    note below - so this provider can simulate a whole dispatch run
    end-to-end without a task-set workstream's real fixtures yet.

    Contract for ``.fake_solution/``: a directory tree mirroring repo-relative
    paths, whose files should be copied over the sandbox repo on a simulated
    "pass". It is removed once applied; after a failed attempt it stays, so a
    cascade escalation in the same sandbox can still succeed.  Parent-seeding
    calls ("do not make any changes yet") never apply it.

    Simulated difficulty: each task gets a stable hardness in [0, 1) from the
    hash of its solution overlay; success probability falls with hardness and
    rises with model tier.  Router calls (``tools=False`` asking for a JSON
    ``candidate``) pick from the menu by estimated hardness - a resumed parent
    estimates it with little noise, a fresh classifier with a lot.  All of this
    exists only to exercise every code path; simulated numbers are not evidence.
    """

    name = "fake"

    def __init__(self, env: dict[str, str] | None = None):
        self.env = env  # unused; kept so make_agent_provider's signature is uniform

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
        del max_budget_usd, timeout_s  # no real spend or wall clock to bound
        tier = _tier_rank(model)
        mult = _TIER_TOKEN_MULT[tier]
        prompt_tokens = max(1, len(prompt) // 4)
        sys_tokens = len(system or "") // 4
        input_tokens = int(120 * mult) + prompt_tokens + sys_tokens
        output_tokens = int(180 * mult)
        reasoning = int(output_tokens * 0.25) if tier >= 2 else 0
        usage = Usage(input_tokens=input_tokens, output_tokens=output_tokens, reasoning=reasoning)

        turns_roll = _stable_unit_interval(prompt, model, "turns")
        num_turns = 1 + int(turns_roll * max(0, min(max_turns - 1, 4)))

        applied = False
        seeding = "do not make any changes yet" in prompt
        if tools and not seeding:
            applied = self._apply_fake_solution(workdir, model, prompt, resume_session)
        tool_calls = num_turns if tools else 0

        if resume_session and not fork:
            session_id = resume_session
        else:
            seed = f"{resume_session or ''}:{model}:{prompt}:{fork}"
            session_id = str(uuid.uuid5(_FAKE_NS, seed))

        if applied:
            output = f"[fake:{model}] applied simulated solution"
        elif tools:
            output = f"[fake:{model}] no .fake_solution available; task left unsolved"
        elif '"candidate"' in prompt:
            output = self._fake_router_choice(workdir, prompt, model, resume_session)
        else:
            output = f"[fake:{model}] router/no-tools call"

        return AgentResult(
            output=output,
            usage=usage,
            duration_ms=5 * num_turns,
            num_turns=num_turns,
            tool_calls=tool_calls,
            session_id=session_id,
            resolved_model=model,
            cost_usd_reported=None,
            error=None,
            raw={"tier": tier, "solution_applied": applied},
        )

    @staticmethod
    def _hardness(workdir: Path) -> float:
        sol_dir = workdir / ".fake_solution"
        if not sol_dir.is_dir():
            return 0.5
        h = hashlib.sha256()
        for src in sorted(sol_dir.rglob("*")):
            if src.is_file():
                h.update(str(src.relative_to(sol_dir)).encode())
                h.update(src.read_bytes())
        return int(h.hexdigest()[:8], 16) / 0xFFFFFFFF

    @classmethod
    def _fake_router_choice(
        cls, workdir: Path, prompt: str, model: str, resume_session: str | None
    ) -> str:
        menu = re.findall(r"^- (\S+) \(", prompt, flags=re.MULTILINE)
        if not menu:
            return f"[fake:{model}] router call without a menu"
        spread = 0.1 if resume_session else 0.35
        noise = (_stable_unit_interval(prompt, model, "route") - 0.5) * 2 * spread
        est = min(0.999, max(0.0, cls._hardness(workdir) + noise))
        pick = menu[min(len(menu) - 1, int(est * len(menu)))]
        return json.dumps({"candidate": pick, "effort": None, "reason": "simulated"})

    @classmethod
    def _apply_fake_solution(
        cls, workdir: Path, model: str, prompt: str, resume_session: str | None
    ) -> bool:
        sol_dir = workdir / ".fake_solution"
        if not sol_dir.is_dir():
            return False
        hardness = cls._hardness(workdir)
        prob = _TIER_QUALITY[_tier_rank(model)] - (hardness - 0.5) * 0.9
        prob = min(0.99, max(0.02, prob))
        roll = _stable_unit_interval(prompt, model, resume_session or "")
        if roll >= prob:
            return False
        for src in sol_dir.rglob("*"):
            if src.is_file():
                dest = workdir / src.relative_to(sol_dir)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
        shutil.rmtree(sol_dir, ignore_errors=True)
        return True


# --------------------------------------------------------------------------- #
# Factory + auth probe
# --------------------------------------------------------------------------- #

_PROVIDERS: dict[str, type] = {
    "claude_cli": ClaudeAgentProvider,
    "codex_cli": CodexAgentProvider,
    "fake": FakeAgentProvider,
}


def make_agent_provider(name: str, env: dict[str, str] | None = None) -> AgentProvider:
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"unknown agent provider {name!r}; expected one of {sorted(_PROVIDERS)}")
    return cls(env=env)


_AUTH_BINARY = {"claude_cli": "claude", "codex_cli": "codex"}


def auth_check(name: str) -> dict[str, Any]:
    """Cheap, read-only auth probe: ``{"installed", "logged_in", "detail"}``.

    Costs nothing and never triggers an interactive login flow - it only runs
    each CLI's own status subcommand (``claude auth status --json`` /
    ``codex login status``) with a short timeout. Never reads or prints an API
    key; ``claude auth status`` also returns the account email, which is
    dropped here rather than put in ``detail``. ``model_routing.dispatch``'s
    runner workstream wraps this as ``auth_status()``.
    """
    if name == "fake":
        return {"installed": True, "logged_in": None, "detail": "fake provider needs no auth"}
    binary = _AUTH_BINARY.get(name)
    if binary is None:
        return {"installed": False, "logged_in": None, "detail": f"unknown provider {name!r}"}
    path = shutil.which(binary)
    if not path:
        return {"installed": False, "logged_in": None, "detail": f"{binary!r} not found on PATH"}
    try:
        if name == "claude_cli":
            proc = subprocess.run(
                [binary, "auth", "status", "--json"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                stdin=subprocess.DEVNULL,
            )
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout or "status check failed").strip()[:200]
                return {"installed": True, "logged_in": None, "detail": detail}
            data = json.loads(proc.stdout)
            logged_in = bool(data.get("loggedIn"))
            return {
                "installed": True,
                "logged_in": logged_in,
                "detail": f"authMethod={data.get('authMethod', 'unknown')}",
            }
        else:  # codex_cli
            proc = subprocess.run(
                [binary, "login", "status"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                stdin=subprocess.DEVNULL,
            )
            # codex prints its status line on stderr (0.154.0), so read both streams.
            text = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            low = text.lower()
            logged_in = proc.returncode == 0 and "logged in" in low and "not logged in" not in low
            return {"installed": True, "logged_in": logged_in, "detail": text[:200]}
    except subprocess.TimeoutExpired:
        return {"installed": True, "logged_in": None, "detail": "status check timed out"}
    except (json.JSONDecodeError, OSError) as exc:
        return {"installed": True, "logged_in": None, "detail": f"status check failed: {exc}"}
