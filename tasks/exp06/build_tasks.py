"""Assemble tasks.jsonl from briefs/*.md (front matter + brief body).

    uv run python tasks/exp06/build_tasks.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

PARENT_CONTEXT = {
    "toolbelt": (
        "We have been working in `toolbelt`, the stdlib-only helper package shared by the deploy "
        "tooling, the job runner and the billing exporter. Each module under `src/toolbelt/` is "
        "self-contained and has its own tests under `tests/`; the suite runs with "
        "`python -m pytest -q` and needs no install step. Today's work is clearing the backlog of "
        "tickets against individual modules."
    ),
    "orchestra": (
        "We have been working in `orchestra`, the deterministic job-DAG scheduler the data "
        "platform uses to simulate pipelines and as the planning core of the real runner. The run "
        "loop in `src/orchestra/scheduler.py` is documented in its module docstring, which is the "
        "reference for scheduling behaviour; tests run with `python -m pytest -q`."
    ),
}


def parse(path: Path) -> dict:
    text = path.read_text()
    assert text.startswith("---\n"), path
    head, body = text[4:].split("\n---\n", 1)
    meta: dict = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith("["):
            items = value.strip("[]").split(",")
            meta[key.strip()] = [i.strip().strip('"') for i in items if i.strip()]
        else:
            meta[key.strip()] = value
    task_id = path.stem
    return {
        "id": task_id,
        "title": meta["title"],
        "brief": body.strip(),
        "brief_terse": meta["terse"],
        "parent_context": PARENT_CONTEXT[meta["repo"]],
        "repo": meta["repo"],
        "grader": {"allowed_paths": meta["allowed"]},
        "difficulty": "hard",
        "category": meta["category"],
        "max_turns": 40,
        "tags": meta.get("tags", []),
    }


def main() -> None:
    rows = [parse(p) for p in sorted((HERE / "briefs").glob("*.md"))]
    with (HERE / "tasks.jsonl").open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} tasks")


if __name__ == "__main__":
    main()
