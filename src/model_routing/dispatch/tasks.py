"""Agentic task loader.

Loads ``tasks/agentic/tasks.jsonl`` (one :class:`AgentTask` per line) and
resolves every path a task references relative to the JSONL's directory:

* ``repo``                      -> ``repos/<repo>``                (required)
* ``grader["hidden_tests"]``    -> ``hidden/<id>``                 (auto, if present)
* ``grader["setup_overlay"]``   -> ``setup/<id>``                  (auto, if present)
* ``grader["mutation_overlay"]``-> ``mutants/<id>``                (auto, if present)
* ``grader["solution_overlay"]``-> ``solutions/<id>``              (required)

A task's own ``grader`` dict may set any of the ``hidden_tests`` /
``setup_overlay`` / ``mutation_overlay`` keys explicitly (e.g. to point two
tasks at the same overlay); the loader only fills in the convention-based
default when the key is absent and the directory exists. ``solution_overlay``
is always the convention path and must exist for every task - it is what
proves the task is solvable (see ``scripts/validate_agentic_tasks.py``) and
what the fake provider applies during simulated runs.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from model_routing.dispatch.types import AgentTask

_DIFFICULTIES = ("easy", "medium", "hard")

_REQUIRED_STR_FIELDS = ("id", "title", "brief", "brief_terse", "parent_context", "repo")


def _resolve_overlay(
    jsonl_dir: Path, subdir: str, task_id: str, explicit: str | None
) -> str | None:
    """Resolve an overlay directory for ``task_id`` under ``jsonl_dir/subdir``.

    If ``explicit`` is given (a name under ``subdir``, or an already-resolved
    path) it wins. Otherwise, falls back to the ``<subdir>/<task_id>``
    convention if that directory exists. Returns ``None`` if neither applies.
    """
    if explicit:
        candidate = Path(explicit)
        if not candidate.is_absolute():
            candidate = jsonl_dir / subdir / explicit
        if not candidate.is_dir():
            raise ValueError(f"{task_id}: grader overlay not found: {candidate}")
        return str(candidate)
    default = jsonl_dir / subdir / task_id
    return str(default) if default.is_dir() else None


def _validate_raw(raw: dict, path: Path) -> None:
    for field_name in _REQUIRED_STR_FIELDS:
        value = raw.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{path}: task {raw.get('id', '?')!r} missing field {field_name!r}")
    grader = raw.get("grader")
    if not isinstance(grader, dict):
        raise ValueError(f"{path}: task {raw['id']!r} grader must be an object")
    allowed_paths = grader.get("allowed_paths")
    if not isinstance(allowed_paths, list) or not allowed_paths:
        raise ValueError(
            f"{path}: task {raw['id']!r} grader.allowed_paths must be a non-empty list"
        )
    difficulty = raw.get("difficulty", "unknown")
    if difficulty not in _DIFFICULTIES:
        raise ValueError(
            f"{path}: task {raw['id']!r} difficulty must be one of "
            f"{_DIFFICULTIES}, got {difficulty!r}"
        )


def _load_raw(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open() as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            _validate_raw(raw, path)
            rows.append(raw)
    ids = [r["id"] for r in rows]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"{path}: duplicate task ids: {sorted(dupes)}")
    return rows


def _build_task(raw: dict, jsonl_dir: Path) -> AgentTask:
    task_id = raw["id"]
    repo = jsonl_dir / "repos" / raw["repo"]
    if not repo.is_dir():
        raise ValueError(f"{task_id}: repo directory not found: {repo}")

    grader = dict(raw["grader"])
    hidden = _resolve_overlay(jsonl_dir, "hidden", task_id, grader.get("hidden_tests"))
    if hidden:
        grader["hidden_tests"] = hidden
    setup = _resolve_overlay(jsonl_dir, "setup", task_id, grader.get("setup_overlay"))
    if setup:
        grader["setup_overlay"] = setup
    mutation = _resolve_overlay(jsonl_dir, "mutants", task_id, grader.get("mutation_overlay"))
    if mutation:
        grader["mutation_overlay"] = mutation
    solution = jsonl_dir / "solutions" / task_id
    if not solution.is_dir():
        raise ValueError(f"{task_id}: solution overlay not found: {solution}")
    grader["solution_overlay"] = str(solution)

    return AgentTask(
        id=task_id,
        title=raw["title"],
        brief=raw["brief"],
        brief_terse=raw["brief_terse"],
        parent_context=raw["parent_context"],
        repo=repo,
        grader=grader,
        difficulty=raw.get("difficulty", "unknown"),
        category=raw.get("category", "general"),
        max_turns=int(raw.get("max_turns", 30)),
        tags=tuple(raw.get("tags", ())),
    )


def _stratified_sample(tasks: list[AgentTask], sample: int, seed: int) -> list[AgentTask]:
    """Deterministically sample ``sample`` tasks, preserving difficulty mix.

    Groups by ``difficulty``, gives each group a share of ``sample``
    proportional to its size (largest remainder method for rounding), then
    draws that many from the group with a ``random.Random(seed)`` instance
    seeded once per group so the same ``seed`` always yields the same subset.
    Order in the result follows the original file order.
    """
    if sample >= len(tasks):
        return list(tasks)

    by_difficulty: dict[str, list[AgentTask]] = {}
    for t in tasks:
        by_difficulty.setdefault(t.difficulty, []).append(t)

    shares: dict[str, float] = {
        d: len(group) / len(tasks) * sample for d, group in by_difficulty.items()
    }
    counts = {d: int(share) for d, share in shares.items()}
    remainder = sample - sum(counts.values())
    # Largest-remainder method, tie-broken by difficulty name for determinism.
    order = sorted(shares, key=lambda d: (-(shares[d] - counts[d]), d))
    for d in order[:remainder]:
        counts[d] += 1

    chosen_ids: set[str] = set()
    for d, group in by_difficulty.items():
        n = min(counts.get(d, 0), len(group))
        rng = random.Random(f"{seed}:{d}")
        picks = sorted(group, key=lambda t: t.id)
        rng.shuffle(picks)
        chosen_ids.update(t.id for t in picks[:n])

    return [t for t in tasks if t.id in chosen_ids]


def load_agent_tasks(
    path: str | Path, *, sample: int | None = None, seed: int = 0
) -> list[AgentTask]:
    """Load ``tasks/agentic/tasks.jsonl``.

    Resolves ``repo`` and the hidden/setup/mutation/solution overlay paths
    relative to the JSONL's directory (see module docstring). ``sample``
    draws a deterministic, difficulty-stratified subset of that many tasks
    for a given ``seed``; without it, every task is returned in file order.
    """
    path = Path(path)
    jsonl_dir = path.parent
    raws = _load_raw(path)
    tasks = [_build_task(raw, jsonl_dir) for raw in raws]
    if sample is not None:
        tasks = _stratified_sample(tasks, sample, seed)
    return tasks
