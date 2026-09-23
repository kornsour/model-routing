"""Create and tear down a throwaway sandbox copy of a task's fixture repo.

Each sandbox is a fresh directory: a copy of ``task.repo`` (plus any
``grader["setup_overlay"]``), initialized as its own git repo with one
commit, so grading can use ``git diff``/``git status`` to see exactly what
an agent session changed. When ``simulate=True`` (used by the fake provider
for free, no-network runs), the task's solution overlay is also copied in
under ``.fake_solution/`` - never part of a real run, and always excluded
from scope checks (see ``grading.py``).
"""

from __future__ import annotations

import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from model_routing.dispatch.types import AgentTask

FAKE_SOLUTION_DIRNAME = ".fake_solution"

_IGNORED_COPY_NAMES = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", FAKE_SOLUTION_DIRNAME}


def _copytree_overlay(src: Path, dst: Path) -> None:
    """Copy ``src`` onto ``dst``, overwriting files that already exist."""
    shutil.copytree(
        src,
        dst,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(*_IGNORED_COPY_NAMES),
    )


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


@dataclass
class Sandbox:
    task: AgentTask
    path: Path
    keep: bool = False

    @classmethod
    def create(cls, task: AgentTask, root: Path, *, simulate: bool = False) -> Sandbox:
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        workdir = root / f"{task.id}-{uuid.uuid4().hex[:8]}"
        workdir.mkdir(parents=True)

        _copytree_overlay(task.repo, workdir)

        setup_overlay = task.grader.get("setup_overlay")
        if setup_overlay:
            _copytree_overlay(Path(setup_overlay), workdir)

        _git(["init", "-q"], cwd=workdir)
        _git(
            ["-c", "user.name=sandbox", "-c", "user.email=sandbox@local", "add", "-A"], cwd=workdir
        )
        _git(
            [
                "-c",
                "user.name=sandbox",
                "-c",
                "user.email=sandbox@local",
                "commit",
                "-q",
                "-m",
                "initial fixture state",
                "--allow-empty",
            ],
            cwd=workdir,
        )

        if simulate:
            solution_overlay = task.grader.get("solution_overlay")
            if solution_overlay:
                fake_dir = workdir / FAKE_SOLUTION_DIRNAME
                _copytree_overlay(Path(solution_overlay), fake_dir)

        return cls(task=task, path=workdir, keep=False)

    def cleanup(self) -> None:
        if self.keep:
            return
        shutil.rmtree(self.path, ignore_errors=True)
