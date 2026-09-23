"""Validate every task in ``tasks/agentic/tasks.jsonl``.

For each task:

1. Grade the untouched fixture repo - it must fail (the bug/gap is real, or
   the missing test/feature is genuinely missing).
2. Grade the repo with the task's solution overlay applied - it must pass
   (the task is solvable, and the grader isn't too strict).

CI enforces this through ``tests/test_dispatch_tasks.py``.  Run directly with
``python scripts/validate_agentic_tasks.py`` (a thin wrapper around ``main``).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from model_routing.dispatch.grading import grade_sandbox
from model_routing.dispatch.sandbox import Sandbox
from model_routing.dispatch.tasks import load_agent_tasks
from model_routing.dispatch.types import AgentTask

TASKS_JSONL = Path(__file__).resolve().parents[3] / "tasks" / "agentic" / "tasks.jsonl"


def _apply_solution(task: AgentTask, sandbox: Sandbox) -> None:
    solution = Path(task.grader["solution_overlay"])
    shutil.copytree(solution, sandbox.path, dirs_exist_ok=True)


def check_untouched(task: AgentTask, root: Path) -> list[str]:
    """The untouched repo must fail grading overall, but (unless the task is
    tagged ``fixes-failing-visible-test``, which none currently are) its own
    visible test suite must already be green."""
    errors: list[str] = []
    sandbox = Sandbox.create(task, root)
    try:
        grade = grade_sandbox(task, sandbox)
        if grade.passed:
            errors.append(f"{task.id}: untouched repo unexpectedly PASSED grading ({grade.checks})")
        if "fixes-failing-visible-test" not in task.tags and not grade.checks.get(
            "visible_tests", False
        ):
            errors.append(f"{task.id}: visible tests do not pass on the untouched repo")
    finally:
        sandbox.cleanup()
    return errors


def check_solution_passes(task: AgentTask, root: Path) -> str | None:
    """Returns an error message, or ``None`` if repo+solution correctly passes."""
    sandbox = Sandbox.create(task, root)
    try:
        _apply_solution(task, sandbox)
        grade = grade_sandbox(task, sandbox)
        if not grade.passed:
            return (
                f"{task.id}: repo+solution FAILED grading\n"
                f"  checks: {grade.checks}\n  detail: {grade.detail}"
            )
        return None
    finally:
        sandbox.cleanup()


def validate_all(tasks: list[AgentTask]) -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agentic-validate-") as tmp:
        root = Path(tmp)
        for task in tasks:
            errors.extend(check_untouched(task, root))
            err = check_solution_passes(task, root)
            if err:
                errors.append(err)
    return errors


def main(tasks_jsonl: Path = TASKS_JSONL) -> int:
    tasks = load_agent_tasks(tasks_jsonl)
    print(f"validating {len(tasks)} tasks from {tasks_jsonl}")
    errors = validate_all(tasks)
    if errors:
        print(f"\n{len(errors)} FAILURES:\n")
        for err in errors:
            print(f"- {err}")
        return 1
    print("all tasks validated: untouched fails, solution passes, visible tests green.")
    return 0
