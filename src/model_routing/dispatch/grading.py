"""Deterministic grading of a finished sandbox.

A task passes when: the hidden tests (copied in only now, after the agent is
done) pass, the visible tests still pass, no file outside
``grader["allowed_paths"]`` changed, and - for "add a missing test" tasks -
the agent's new test actually catches the known-buggy mutant. No LLM judge.
"""

from __future__ import annotations

import fnmatch
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from model_routing.dispatch.sandbox import FAKE_SOLUTION_DIRNAME, Sandbox
from model_routing.dispatch.types import AgentTask, GradeResult

_IGNORED_DIR_NAMES = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", FAKE_SOLUTION_DIRNAME}

DEFAULT_TIMEOUT_S = 120


def _default_visible_cmd() -> list[str]:
    return [sys.executable, "-m", "pytest", "-q"]


def _run(cmd: list[str], cwd: Path, timeout_s: int) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        out = str(exc.stdout or "") + str(exc.stderr or "")
        return False, f"timed out after {timeout_s}s\n{_tail(out)}"
    ok = proc.returncode == 0
    output = proc.stdout + proc.stderr
    return ok, _tail(output)


def _tail(output: str, lines: int = 25) -> str:
    parts = output.strip().splitlines()
    return "\n".join(parts[-lines:])


def _is_ignored(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    return any(p in _IGNORED_DIR_NAMES for p in parts)


def _changed_files(sandbox_path: Path) -> list[str]:
    """Files changed vs. the sandbox's initial commit, tracked or not."""
    tracked = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=sandbox_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=sandbox_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    untracked = [line[3:] for line in status if line.startswith("??")]
    changed = sorted({*tracked, *untracked})
    return [f for f in changed if f and not _is_ignored(f)]


def _check_scope(changed: list[str], allowed_paths: list[str]) -> bool:
    return all(any(fnmatch.fnmatch(f, pattern) for pattern in allowed_paths) for f in changed)


def _copy_overlay(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))


def _relative_py_files(overlay: Path) -> list[str]:
    return [str(p.relative_to(overlay)) for p in overlay.rglob("*.py")]


def _run_hidden_tests(task: AgentTask, sandbox_path: Path, timeout_s: int) -> tuple[bool, str]:
    hidden_dir = Path(task.grader["hidden_tests"])
    _copy_overlay(hidden_dir, sandbox_path)
    targets = _relative_py_files(hidden_dir)
    if not targets:
        return False, "hidden_tests overlay has no test files"
    cmd = [*_default_visible_cmd(), *targets]
    return _run(cmd, sandbox_path, timeout_s)


def _mutation_test_targets(changed: list[str]) -> list[str]:
    return [
        f
        for f in changed
        if fnmatch.fnmatch(f, "tests/*.py") or fnmatch.fnmatch(f, "tests/**/*.py")
    ]


def _run_mutation_check(
    task: AgentTask, sandbox_path: Path, changed: list[str], timeout_s: int
) -> tuple[bool, str]:
    targets = _mutation_test_targets(changed)
    if not targets:
        return False, "no new/changed test file under tests/ to run the mutant against"

    mutant_dir = Path(task.grader["mutation_overlay"])
    with tempfile.TemporaryDirectory(prefix=f"{task.id}-mutant-") as tmp:
        mutant_copy = Path(tmp) / "sandbox"
        shutil.copytree(
            sandbox_path, mutant_copy, ignore=shutil.ignore_patterns(*_IGNORED_DIR_NAMES)
        )
        _copy_overlay(mutant_dir, mutant_copy)
        cmd = [*_default_visible_cmd(), *targets]
        mutant_ok, mutant_detail = _run(cmd, mutant_copy, timeout_s)

    if mutant_ok:
        # The new test(s) passed even against the known-buggy mutant: they
        # don't actually exercise the bug, so this doesn't count as coverage.
        return False, f"new test did not catch the known-buggy mutant\n{mutant_detail}"
    return True, "new test correctly failed against the mutant"


def grade_sandbox(task: AgentTask, sandbox: Sandbox) -> GradeResult:
    timeout_s = int(task.grader.get("timeout_s", DEFAULT_TIMEOUT_S))
    sandbox_path = sandbox.path

    changed = _changed_files(sandbox_path)
    allowed_paths = task.grader.get("allowed_paths", [])
    scope_ok = _check_scope(changed, allowed_paths)

    visible_cmd = task.grader.get("visible_cmd", _default_visible_cmd())
    visible_ok, visible_detail = _run(visible_cmd, sandbox_path, timeout_s)

    checks: dict[str, bool] = {"scope": scope_ok, "visible_tests": visible_ok}
    details: list[str] = []
    if not scope_ok:
        out_of_scope = [f for f in changed if not any(fnmatch.fnmatch(f, p) for p in allowed_paths)]
        details.append(f"out-of-scope files changed: {out_of_scope}")
    if not visible_ok:
        details.append(f"visible tests failed:\n{visible_detail}")

    if task.grader.get("hidden_tests"):
        hidden_ok, hidden_detail = _run_hidden_tests(task, sandbox_path, timeout_s)
        checks["hidden_tests"] = hidden_ok
        if not hidden_ok:
            details.append(f"hidden tests failed:\n{hidden_detail}")

    if task.grader.get("mutation_overlay"):
        mutation_ok, mutation_detail = _run_mutation_check(task, sandbox_path, changed, timeout_s)
        checks["mutation"] = mutation_ok
        if not mutation_ok:
            details.append(f"mutation check failed:\n{mutation_detail}")

    passed = all(checks.values())
    return GradeResult(
        passed=passed,
        checks=checks,
        detail="; ".join(details) if details else "all checks passed",
        files_changed=changed,
    )
