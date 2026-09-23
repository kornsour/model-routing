"""Policy implementations: ``A``, ``A_switch``, ``B``, ``C1``, ``C1_inline``, ``C2``, ``D``,
``static``.

Each policy function takes a policy spec (one ``[[policies]]`` table from the config),
the ``AgentTask`` and trial number, and a ``PolicyRunContext`` (supplied by
``model_routing.dispatch.runner.run_dispatch``) that provides everything the policy needs
without depending directly on the sandbox/agent/grading modules:

* ``run_session(candidate, *, role, prompt, workdir, ...) -> SessionRecord`` — invokes the
  agent, prices the call, appends it to ``sessions.jsonl`` and checks the budget.  The
  runner owns pricing/budget/logging so every policy call is billed identically.
* ``new_sandbox(task) -> Sandbox`` — a fresh sandbox copy of the task's fixture repo.
* ``grade(task, sandbox) -> GradeResult`` — deterministic grading of a finished sandbox.
* ``run_visible_checker(task, sandbox) -> (passed, tail)`` — runs only the task's visible
  command (never hidden tests); used by policy D to decide whether to escalate.
* ``menu_text`` — the candidate menu with relative prices, for router/classifier prompts.
* ``cleanup(sandboxes)`` — tears down the sandboxes used by one outcome (a no-op when the
  run keeps sandboxes for inspection).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from model_routing.dispatch.types import (
    AgentResult,
    AgentTask,
    DispatchOutcome,
    GradeResult,
    SessionRecord,
)
from model_routing.types import Usage

if TYPE_CHECKING:
    from model_routing.dispatch.runner import DispatchConfig

RunSession = Callable[..., SessionRecord]


@dataclass
class PolicyRunContext:
    cfg: DispatchConfig
    run_session: RunSession
    new_sandbox: Callable[[AgentTask], Any]
    grade: Callable[[AgentTask, Any], GradeResult]
    run_visible_checker: Callable[..., tuple[bool, str]]
    menu_text: str
    cleanup: Callable[[list[Any]], None]


SETUP_PROMPT = (
    "{parent_context}\n\n"
    "Acknowledge that you have this context loaded and are ready to keep working in this "
    "repository. Reply with a short confirmation only; do not make any changes yet."
)

ROUTER_PROMPT_C1 = (
    "You are about to hand off the following piece of work to a fresh agent session. Given the "
    "menu of candidate models below (prices relative to your own), pick the cheapest one you are "
    "confident can complete it correctly.\n\n"
    "Menu:\n{menu}\n\n"
    "Work to hand off:\n{brief}\n\n"
    "Respond with JSON only, no other text, in exactly this shape:\n"
    '{{"candidate": "<menu name>", "effort": "<low|default|high>", "reason": "<one sentence>"}}'
)

ROUTER_PROMPT_C1_INLINE = (
    "You are about to hand off the following piece of work to a fresh agent session, which "
    "will not see this conversation. Write the self-contained brief you would give it (goal, "
    "files, acceptance criteria, constraints) based on everything you know from this session.\n\n"
    "Work to hand off:\n{title}\n\n"
    "Then, on the very last line of your reply and nothing after it, choose which model the "
    "fresh session should run on. Pick the cheapest one from the menu you are confident can "
    "complete the work correctly (prices are relative to your own):\n{menu}\n\n"
    "Last line, JSON only, exactly this shape:\n"
    '{{"candidate": "<menu name>", "effort": "<low|default|high>", "reason": "<one sentence>"}}'
)
"""The parent writes the brief *and* the pick in one turn, which is what a
real spawner does.  Only the pick's marginal tokens are billed to the task
(``_inline_router_marginal_usage``); the brief-writing turn is the sunk cost
of spawning at all, and the fresh worker still gets the canned ``task.brief``
so that C1_inline and B differ *only* in the model, not in brief quality."""

CLASSIFIER_PROMPT_C2 = (
    "Rate how much model capability the following task brief needs, and pick the cheapest "
    "candidate from the menu below that can do it. You do not have any other context.\n\n"
    "Menu:\n{menu}\n\nBrief:\n{brief}\n\n"
    'Respond with JSON only: {{"candidate": "<menu name>"}}'
)

_JSON_RE = re.compile(r"\{[^{}]*\}(?!.*\{[^{}]*\})", re.DOTALL)
"""The last brace-delimited object in the output: an inline router reply is a brief
(which may itself contain braces in code) followed by the pick JSON on its final line."""


def _brief(task: AgentTask, spec: dict[str, Any]) -> str:
    return task.brief_terse if spec.get("brief") == "terse" else task.brief


def _parse_json_choice(output: str) -> dict[str, Any] | None:
    m = _JSON_RE.search(output)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _parse_router_choice(
    output: str, menu: list[str], fallback: str
) -> tuple[str, str | None, bool]:
    """Return (candidate, effort, fallback_used).  Falls back to ``fallback`` (the parent
    model) on unparseable or out-of-menu output; the raw text stays in the router
    session's ``output`` field so a fallback can always be reconstructed from the log."""
    data = _parse_json_choice(output)
    if data and data.get("candidate") in menu:
        effort = data.get("effort")
        return str(data["candidate"]), (str(effort) if effort else None), False
    return fallback, None, True


def _parse_classifier_choice(output: str, menu: list[str]) -> str | None:
    data = _parse_json_choice(output)
    if data and data.get("candidate") in menu:
        return str(data["candidate"])
    if menu:
        m = re.search(r"\b(" + "|".join(re.escape(x) for x in menu) + r")\b", output)
        if m:
            return m.group(1)
    return None


def _heuristic_pick(task: AgentTask, menu: list[str]) -> str:
    """Free (no call) size-based proxy: longer briefs get a more capable candidate."""
    if not menu:
        raise ValueError("heuristic classifier needs a non-empty menu")
    n = len(task.brief)
    if n < 400:
        idx = 0
    elif n < 1200:
        idx = 1
    else:
        idx = 2
    return menu[max(0, min(idx, len(menu) - 1))]


def _outcome(
    task: AgentTask,
    policy: str,
    trial: int,
    sessions: list[SessionRecord],
    grade: GradeResult,
    *,
    chosen: str | None = None,
    escalations: int = 0,
) -> DispatchOutcome:
    return DispatchOutcome(
        task_id=task.id,
        policy=policy,
        trial=trial,
        sessions=sessions,
        grade=grade,
        difficulty=task.difficulty,
        category=task.category,
        chosen_candidate=chosen,
        escalations=escalations,
    )


def _policy_in_session(
    name: str, spec: dict[str, Any], task: AgentTask, trial: int, ctx: PolicyRunContext
) -> DispatchOutcome:
    """A / A_switch: resume the seeded parent session; do the task there."""
    sandbox = ctx.new_sandbox(task)
    sessions: list[SessionRecord] = []
    try:
        setup = ctx.run_session(
            ctx.cfg.parent,
            role="setup",
            prompt=SETUP_PROMPT.format(parent_context=task.parent_context),
            workdir=sandbox.path,
            tools=True,
        )
        sessions.append(setup)
        worker_cand = spec.get("switch_to") or ctx.cfg.parent
        worker = ctx.run_session(
            worker_cand,
            role="worker",
            prompt=_brief(task, spec),
            workdir=sandbox.path,
            resume_session=setup.session_id,
            fork=False,
            tools=True,
            resumed_from=setup.session_id,
        )
        sessions.append(worker)
        grade = ctx.grade(task, sandbox)
        return _outcome(task, name, trial, sessions, grade, chosen=worker_cand)
    finally:
        ctx.cleanup([sandbox])


def _policy_spawn_static(
    name: str, spec: dict[str, Any], task: AgentTask, trial: int, ctx: PolicyRunContext
) -> DispatchOutcome:
    """B (kind=spawn_static, candidate=parent) and the static:<cand> baselines."""
    sandbox = ctx.new_sandbox(task)
    try:
        cand = spec["candidate"]
        worker = ctx.run_session(
            cand, role="worker", prompt=_brief(task, spec), workdir=sandbox.path, tools=True
        )
        grade = ctx.grade(task, sandbox)
        return _outcome(task, name, trial, [worker], grade, chosen=cand)
    finally:
        ctx.cleanup([sandbox])


def _policy_c1(
    name: str, spec: dict[str, Any], task: AgentTask, trial: int, ctx: PolicyRunContext
) -> DispatchOutcome:
    """C1: resume the parent (forked) to pick a candidate, then a fresh session on the pick."""
    setup_sandbox = ctx.new_sandbox(task)
    sandboxes = [setup_sandbox]
    try:
        setup = ctx.run_session(
            ctx.cfg.parent,
            role="setup",
            prompt=SETUP_PROMPT.format(parent_context=task.parent_context),
            workdir=setup_sandbox.path,
            tools=True,
        )
        router_prompt = ROUTER_PROMPT_C1.format(menu=ctx.menu_text, brief=_brief(task, spec))
        router = ctx.run_session(
            ctx.cfg.parent,
            role="router",
            prompt=router_prompt,
            workdir=setup_sandbox.path,
            resume_session=setup.session_id,
            fork=True,
            tools=False,
            resumed_from=setup.session_id,
        )
        picked, _effort, _fallback = _parse_router_choice(
            router.output, ctx.cfg.menu, ctx.cfg.parent
        )
        worker_sandbox = ctx.new_sandbox(task)
        sandboxes.append(worker_sandbox)
        worker = ctx.run_session(
            picked,
            role="worker",
            prompt=_brief(task, spec),
            workdir=worker_sandbox.path,
            tools=True,
        )
        grade = ctx.grade(task, worker_sandbox)
        return _outcome(task, name, trial, [setup, router, worker], grade, chosen=picked)
    finally:
        ctx.cleanup(sandboxes)


def _approx_tokens(text: str) -> int:
    """Chars/4: a deliberately simple, stated approximation (no tokenizer at runtime)."""
    return max(1, len(text) // 4)


def _inline_router_marginal_usage(menu_text: str, result: AgentResult) -> Usage:
    """Tokens the model choice *added* to a brief-writing turn the parent runs anyway.

    Input: the menu and the pick instruction (uncached, since they are new text).
    Output: the JSON line with the pick.  Everything else in the turn - reading the
    parent context, writing the brief - is the cost of spawning at all and is
    recorded on the session but not billed to the task."""
    instruction = (
        "Then, on the very last line of your reply and nothing after it, choose which model the "
        "fresh session should run on. Pick the cheapest one from the menu you are confident can "
        "complete the work correctly (prices are relative to your own):\n"
        "Last line, JSON only, exactly this shape:\n"
        '{"candidate": "<menu name>", "effort": "<low|default|high>", "reason": "<one sentence>"}'
    )
    m = _JSON_RE.search(result.output or "")
    pick_text = m.group(0) if m else ""
    return Usage(
        input_tokens=_approx_tokens(menu_text + instruction),
        output_tokens=_approx_tokens(pick_text) if pick_text else 0,
    )


def _policy_c1_inline(
    name: str, spec: dict[str, Any], task: AgentTask, trial: int, ctx: PolicyRunContext
) -> DispatchOutcome:
    """C1_inline: the parent writes the brief and the pick in one forked turn; the task is
    billed only the marginal tokens of the pick (the realistic routing overhead).  The
    forked C1 (``_policy_c1``) stays as the pessimistic variant."""
    setup_sandbox = ctx.new_sandbox(task)
    sandboxes = [setup_sandbox]
    try:
        setup = ctx.run_session(
            ctx.cfg.parent,
            role="setup",
            prompt=SETUP_PROMPT.format(parent_context=task.parent_context),
            workdir=setup_sandbox.path,
            tools=True,
        )
        router_prompt = ROUTER_PROMPT_C1_INLINE.format(title=task.title, menu=ctx.menu_text)
        menu_text = ctx.menu_text
        router = ctx.run_session(
            ctx.cfg.parent,
            role="router",
            prompt=router_prompt,
            workdir=setup_sandbox.path,
            resume_session=setup.session_id,
            fork=True,
            tools=False,
            resumed_from=setup.session_id,
            bill=lambda result: _inline_router_marginal_usage(menu_text, result),
        )
        picked, _effort, _fallback = _parse_router_choice(
            router.output, ctx.cfg.menu, ctx.cfg.parent
        )
        worker_sandbox = ctx.new_sandbox(task)
        sandboxes.append(worker_sandbox)
        worker = ctx.run_session(
            picked,
            role="worker",
            prompt=_brief(task, spec),
            workdir=worker_sandbox.path,
            tools=True,
        )
        grade = ctx.grade(task, worker_sandbox)
        return _outcome(task, name, trial, [setup, router, worker], grade, chosen=picked)
    finally:
        ctx.cleanup(sandboxes)


def _policy_c2(
    name: str, spec: dict[str, Any], task: AgentTask, trial: int, ctx: PolicyRunContext
) -> DispatchOutcome:
    """C2: a classifier (or free heuristic) on the brief alone picks the model."""
    classifier = spec.get("classifier", "heuristic")
    sessions: list[SessionRecord] = []
    sandboxes: list[Any] = []
    try:
        if classifier == "heuristic":
            picked = _heuristic_pick(task, ctx.cfg.menu)
        else:
            cls_sandbox = ctx.new_sandbox(task)
            sandboxes.append(cls_sandbox)
            cls_prompt = CLASSIFIER_PROMPT_C2.format(menu=ctx.menu_text, brief=task.brief)
            cls = ctx.run_session(
                classifier, role="router", prompt=cls_prompt, workdir=cls_sandbox.path, tools=False
            )
            sessions.append(cls)
            picked = _parse_classifier_choice(cls.output, ctx.cfg.menu) or _heuristic_pick(
                task, ctx.cfg.menu
            )
        worker_sandbox = ctx.new_sandbox(task)
        sandboxes.append(worker_sandbox)
        worker = ctx.run_session(
            picked,
            role="worker",
            prompt=_brief(task, spec),
            workdir=worker_sandbox.path,
            tools=True,
        )
        sessions.append(worker)
        grade = ctx.grade(task, worker_sandbox)
        return _outcome(task, name, trial, sessions, grade, chosen=picked)
    finally:
        ctx.cleanup(sandboxes)


def _policy_d(
    name: str, spec: dict[str, Any], task: AgentTask, trial: int, ctx: PolicyRunContext
) -> DispatchOutcome:
    """D: cheapest-first cascade.  ``escalate_on = "visible"`` (default, deployable) checks
    diff + scope + visible tests; ``"hidden"`` uses the hidden tests as a perfect checker
    (an upper bound for any cascade, not a deployable policy).  The agent never sees
    hidden test output either way."""
    chain: list[str] = spec["chain"]
    sandbox = ctx.new_sandbox(task)
    try:
        sessions: list[SessionRecord] = []
        brief = _brief(task, spec)
        prompt = brief
        chosen = chain[0]
        escalations = 0
        for i, cand in enumerate(chain):
            role = "worker" if i == 0 else "escalation"
            rec = ctx.run_session(cand, role=role, prompt=prompt, workdir=sandbox.path, tools=True)
            sessions.append(rec)
            chosen = cand
            if i == len(chain) - 1:
                break
            ok, tail = ctx.run_visible_checker(task, sandbox, spec.get("escalate_on", "visible"))
            if ok:
                break
            escalations += 1
            prompt = (
                f"{brief}\n\nThe previous attempt failed the visible checks:\n{tail}\n"
                "Finish the task; the acceptance checks are stricter than the visible tests."
            )
        grade = ctx.grade(task, sandbox)
        return _outcome(task, name, trial, sessions, grade, chosen=chosen, escalations=escalations)
    finally:
        ctx.cleanup([sandbox])


_DISPATCH = {
    "in_session": _policy_in_session,
    "spawn_static": _policy_spawn_static,
    "spawn_parent_pick": _policy_c1,
    "spawn_parent_pick_inline": _policy_c1_inline,
    "spawn_classifier": _policy_c2,
    "spawn_cascade": _policy_d,
}


def run_policy(
    policy_spec: dict[str, Any], task: AgentTask, trial: int, ctx: PolicyRunContext
) -> DispatchOutcome:
    kind = policy_spec["kind"]
    name = policy_spec["name"]
    fn = _DISPATCH.get(kind)
    if fn is None:
        raise ValueError(f"unknown policy kind {kind!r}")
    return fn(name, policy_spec, task, trial, ctx)
