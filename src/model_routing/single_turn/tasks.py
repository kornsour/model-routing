"""Load task sets (JSONL) and their shared context documents."""

from __future__ import annotations

import json
from pathlib import Path

from model_routing.types import Task


def load_tasks(
    path: str | Path,
    limit: int | None = None,
    sample: int | None = None,
    tags: tuple[str, ...] | list[str] | None = None,
) -> list[Task]:
    """Load tasks in file order.

    ``tags`` keeps only tasks carrying every listed tag.  ``sample`` keeps N
    tasks evenly spaced through the (filtered) file, so a small run still
    touches every difficulty and both context/no-context groups; ``limit``
    keeps the first N.  ``sample`` is applied before ``limit``.
    """
    path = Path(path)
    tasks: list[Task] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            raw = json.loads(line)
            tasks.append(
                Task(
                    id=raw["id"],
                    prompt=raw["prompt"],
                    grader=raw["grader"],
                    difficulty=raw.get("difficulty", "unknown"),
                    category=raw.get("category", "general"),
                    context=raw.get("context"),
                    schema=raw.get("schema"),
                    tags=tuple(raw.get("tags", ())),
                )
            )
    ids = [t.id for t in tasks]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate task ids in {path}: {sorted(dupes)}")
    if tags:
        tasks = [t for t in tasks if all(tag in t.tags for tag in tags)]
    if sample and sample < len(tasks):
        step = len(tasks) / sample
        tasks = [tasks[int(i * step)] for i in range(sample)]
    return tasks[:limit] if limit else tasks


class ContextStore:
    """Resolves ``Task.context`` names to document text, relative to the task file."""

    def __init__(self, base: str | Path):
        self.base = Path(base)
        self._cache: dict[str, str] = {}

    def get(self, name: str | None) -> str | None:
        if name is None:
            return None
        if name not in self._cache:
            self._cache[name] = (self.base / "context" / name).read_text()
        return self._cache[name]
