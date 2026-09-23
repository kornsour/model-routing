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
from ``turn.completed``, mirroring ``providers/codex_cli.py``.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
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
        return AgentResult(
            output="", usage=Usage(), duration_ms=wall_ms, tool_calls=tool_calls, error=detail
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
    if data.get("is_error"):
        text = data.get("result")
        if not text:
            errors = data.get("errors")
            text = "; ".join(errors) if errors else "error"
        error = str(text)[:500]
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
        },
    )


# --------------------------------------------------------------------------- #
# Codex
# --------------------------------------------------------------------------- #


class CodexAgentProvider:
    """``codex exec`` / ``codex exec resume`` with JSONL parsing.

    Two contract gaps versus Claude, both real CLI limitations (codex-cli
    0.154.0), not oversights here:

    * No ``--max-budget-usd`` equivalent - Codex never stops itself on spend,
      so the runner must police the budget from the outside (e.g. checking
      cost after each session, or a hard wall-clock ``timeout_s``).
    * No ``-s``/``-C`` (sandbox mode / working directory) on ``codex exec
      resume`` - a resumed session keeps the sandbox and directory it was
      started with. Callers must always resume a session in the same
      ``workdir`` it was created in.
    * No session fork: ``codex exec`` does have an undocumented-here ``fork``
      subcommand, but per this workstream's contract we do not use it -
      ``fork=True`` with a ``resume_session`` still just resumes in place
      (same session id continues), and that is recorded in ``raw``.
    """

    name = "codex_cli"

    def __init__(self, binary: str = "codex", env: dict[str, str] | None = None):
        self.binary = binary
        self.env = env

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
    ) -> list[str]:
        full_prompt = prompt if not system else f"<context>\n{system}\n</context>\n\n{prompt}"
        sandbox = "workspace-write" if tools else "read-only"
        if resume_session:
            args = [
                self.binary,
                "exec",
                "resume",
                resume_session,
                "--json",
                "--ignore-user-config",
                "--skip-git-repo-check",
                "-m",
                model,
            ]
        else:
            args = [
                self.binary,
                "exec",
                "--json",
                "--ignore-user-config",
                "--skip-git-repo-check",
                "-s",
                sandbox,
                "-C",
                str(workdir),
                "-m",
                model,
            ]
        if effort:
            args += ["-c", f'model_reasoning_effort="{effort}"']
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
        del max_turns, max_budget_usd  # codex exec has no native equivalent; see class docstring
        args = self.build_args(
            model,
            prompt,
            workdir=workdir,
            system=system,
            effort=effort,
            resume_session=resume_session,
            tools=tools,
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
        result = parse_codex_stream(proc.stdout, wall_ms)
        if result.error is None and proc.returncode != 0:
            result.error = f"exit {proc.returncode}: {(proc.stderr or '').strip()[-300:]}"
        if result.error is None and not result.output and not (result.raw or {}).get("session_id"):
            result.error = "no agent_message / thread id in output"
        if resume_session and fork:
            result.raw = {**(result.raw or {}), "fork_requested": True, "forked": False}
        return result


_CODEX_TOOL_ITEM_TYPES = frozenset(
    {"file_change", "command_execution", "mcp_tool_call", "web_search", "local_shell_call"}
)


def parse_codex_stream(stdout: str, wall_ms: int) -> AgentResult:
    """Fold ``codex exec --json`` JSONL events into one :class:`AgentResult`.

    Extends ``providers.codex_cli.parse_jsonl``'s usage normalization (Codex's
    ``input_tokens`` includes the cached portion; ``Usage`` keeps them
    disjoint) with turn counting and tool-call counting from ``item.completed``
    events, which the single-shot provider never sees tools to report.
    """
    output = ""
    usage = Usage()
    error = None
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
            cached = int(u.get("cached_input_tokens", 0))
            usage = Usage(
                input_tokens=max(int(u.get("input_tokens", 0)) - cached, 0),
                cache_read=cached,
                cache_write=int(u.get("cache_write_input_tokens", 0)),
                output_tokens=int(u.get("output_tokens", 0)),
                reasoning=int(u.get("reasoning_output_tokens", 0)),
            )
        elif kind in ("turn.failed", "error"):
            error = str(ev.get("error") or ev.get("message") or ev)[:500]
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
        raw={"thread_id": session_id},
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
