"""Task-set tooling added for the exp06 Stage 0 extension: history scripts,
solution delete manifests and per-task Bash allowlist extensions."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from model_routing.dispatch.agents import ClaudeAgentProvider
from model_routing.dispatch.sandbox import DELETE_MANIFEST, Sandbox, apply_solution_overlay
from model_routing.dispatch.tasks import load_agent_tasks


def _task_dir(tmp_path: Path, *, history: str | None = None, extra: dict | None = None) -> Path:
    root = tmp_path / "tasks"
    (root / "repos" / "r").mkdir(parents=True)
    (root / "repos" / "r" / "a.txt").write_text("a\n")
    (root / "solutions" / "t1").mkdir(parents=True)
    if history is not None:
        (root / "history").mkdir()
        (root / "history" / "t1.sh").write_text(history)
    row = {
        "id": "t1",
        "title": "t",
        "brief": "b",
        "brief_terse": "b",
        "parent_context": "p",
        "repo": "r",
        "grader": {"allowed_paths": ["*"]},
        "difficulty": "hard",
        **(extra or {}),
    }
    (root / "tasks.jsonl").write_text(json.dumps(row) + "\n")
    return root / "tasks.jsonl"


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def test_history_script_runs_after_the_first_commit(tmp_path):
    script = (
        "set -euo pipefail\n"
        "git switch -q -c feature\n"
        "echo b > b.txt && git add b.txt\n"
        "git -c user.name=t -c user.email=t@t commit -q -m 'feature work'\n"
        "git switch -q -\n"
    )
    [task] = load_agent_tasks(_task_dir(tmp_path, history=script))
    assert Path(task.grader["history_script"]).is_absolute()
    sandbox = Sandbox.create(task, tmp_path / "sb")
    try:
        assert _git(sandbox.path, "log", "-1", "--format=%s", "feature") == "feature work"
        assert _git(sandbox.path, "status", "--porcelain") == ""
        assert not (sandbox.path / "b.txt").exists()
    finally:
        sandbox.cleanup()


def test_tasks_without_history_script_are_unchanged(tmp_path):
    [task] = load_agent_tasks(_task_dir(tmp_path))
    assert "history_script" not in task.grader
    assert task.agent_bash == ()


def test_delete_manifest_removes_files(tmp_path):
    overlay, work = tmp_path / "overlay", tmp_path / "work"
    (overlay / "docs").mkdir(parents=True)
    (overlay / "docs" / "new.md").write_text("moved\n")
    (overlay / DELETE_MANIFEST).write_text("old.md\n")
    work.mkdir()
    (work / "old.md").write_text("moved\n")
    apply_solution_overlay(overlay, work)
    assert not (work / "old.md").exists()
    assert (work / "docs" / "new.md").read_text() == "moved\n"
    assert not (work / DELETE_MANIFEST).exists()


def test_agent_bash_extends_the_allowlist(tmp_path):
    [task] = load_agent_tasks(_task_dir(tmp_path, extra={"agent_bash": ["git:*", "go:*"]}))
    assert task.agent_bash == ("git:*", "go:*")
    args = ClaudeAgentProvider().build_args(
        "claude-sonnet-5-5",
        "do it",
        system=None,
        effort=None,
        max_turns=5,
        resume_session=None,
        fork=False,
        tools=True,
        max_budget_usd=1.0,
        extra_bash=task.agent_bash,
    )
    assert "Bash(git:*)" in args and "Bash(go:*)" in args
    plain = ClaudeAgentProvider().build_args(
        "claude-sonnet-5-5",
        "do it",
        system=None,
        effort=None,
        max_turns=5,
        resume_session=None,
        fork=False,
        tools=True,
        max_budget_usd=1.0,
    )
    assert "Bash(git:*)" not in plain
