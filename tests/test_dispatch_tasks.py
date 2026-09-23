"""CI enforcement of the agentic task set (see ``scripts/validate_agentic_tasks.py``).

For every task in ``tasks/agentic/tasks.jsonl``: the untouched fixture repo
must fail grading (with its own visible suite already green), and the repo
with the task's solution overlay applied must pass grading. This is what
proves every task is both real and solvable, and it's parametrized per task
so a single broken task doesn't hide failures in the rest of the set.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from model_routing.dispatch.tasks import load_agent_tasks
from model_routing.dispatch.types import AgentTask
from scripts.validate_agentic_tasks import check_solution_passes, check_untouched

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_JSONL = REPO_ROOT / "tasks" / "agentic" / "tasks.jsonl"


def _load_tasks() -> list[AgentTask]:
    return load_agent_tasks(TASKS_JSONL)


TASKS = _load_tasks()


def test_task_set_is_nonempty():
    assert len(TASKS) >= 30


@pytest.mark.parametrize("task", TASKS, ids=[t.id for t in TASKS])
def test_untouched_repo_fails_grading(task: AgentTask, tmp_path: Path):
    errors = check_untouched(task, tmp_path)
    assert not errors, "\n".join(errors)


@pytest.mark.parametrize("task", TASKS, ids=[t.id for t in TASKS])
def test_solution_overlay_passes_grading(task: AgentTask, tmp_path: Path):
    err = check_solution_passes(task, tmp_path)
    assert err is None, err
