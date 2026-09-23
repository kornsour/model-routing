#!/usr/bin/env python3
"""Validate every task in ``tasks/agentic/tasks.jsonl``.

For each task:

1. Grade the untouched fixture repo - it must fail (the bug/gap is real, or
   the missing test/feature is genuinely missing).
2. Grade the repo with the task's solution overlay applied - it must pass
   (the task is solvable, and the grader isn't too strict).

This is also wired up as ``tests/test_dispatch_tasks.py`` so CI enforces it
on every change to the task set. Run directly with:

    python scripts/validate_agentic_tasks.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from model_routing.dispatch.grading import grade_sandbox  # noqa: E402
from model_routing.dispatch.sandbox import Sandbox  # noqa: E402
from model_routing.dispatch.tasks import load_agent_tasks  # noqa: E402
from model_routing.dispatch.types import AgentTask  # noqa: E402

TASKS_JSONL = REPO_ROOT / "tasks" / "agentic" / "tasks.jsonl"


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


def main() -> int:
    tasks = load_agent_tasks(TASKS_JSONL)
    print(f"validating {len(tasks)} tasks from {TASKS_JSONL}")
    errors = validate_all(tasks)
    if errors:
        print(f"\n{len(errors)} FAILURES:\n")
        for err in errors:
            print(f"- {err}")
        return 1
    print("all tasks validated: untouched fails, solution passes, visible tests green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
