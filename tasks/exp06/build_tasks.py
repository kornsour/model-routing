"""Assemble the exp06 task files from briefs/*.md (front matter + brief body).

    uv run python tasks/exp06/build_tasks.py

Briefs without a ``stratum`` key are the first Stage 0 batch and go to
``tasks.jsonl`` (frozen; rebuilding it must not change a byte). Briefs with a
``stratum`` (A harvested, B long-horizon, C ambiguous, D read-only) are the
Stage 0 extension (``docs/experiments/exp06-route-on-evidence/extension-plan.md``)
and go to ``tasks_ext.jsonl``. Front-matter values that parse as JSON are taken
as JSON; anything else in brackets is a bare comma list (the first batch's
``tags`` style).
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
    "platform": (
        "We have been working in the `platform` monorepo: `orchestra` (the job-DAG scheduler), "
        "`toolbelt` (shared stdlib helpers) and `ledger` (the cost and run-history service that "
        "consumes both) live side by side under `packages/`, each with its own `src/` and "
        "`tests/`. One `python -m pytest -q` at the root runs all three suites; nothing needs "
        "installing."
    ),
    "harvested": (
        "This session is an operator's working session across the Copperline organisation's "
        "repositories and the operator's personal ones. The operator hands self-contained jobs "
        "to subagents with a written brief and integrates the results. This sandbox is offline: "
        "there is no network, no `gh`, no package installs and no remote unless the brief's "
        "offline note says otherwise."
    ),
}

_FIRST_BATCH_KEYS = ("title", "terse", "repo", "allowed", "category", "tags")


def _value(raw: str):
    raw = raw.strip()
    if raw[:1] in "[{":
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            items = raw.strip("[]").split(",")
            return [i.strip().strip('"') for i in items if i.strip()]
    return raw


def parse(path: Path) -> dict:
    text = path.read_text()
    assert text.startswith("---\n"), path
    head, body = text[4:].split("\n---\n", 1)
    meta: dict = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = _value(value)
    task_id = path.stem
    row = {
        "id": task_id,
        "title": meta["title"],
        "brief": body.strip(),
        "brief_terse": meta["terse"],
        "parent_context": PARENT_CONTEXT[meta.get("parent", meta["repo"])],
        "repo": meta["repo"],
        "grader": {"allowed_paths": meta["allowed"]},
        "difficulty": "hard",
        "category": meta["category"],
        "max_turns": int(meta.get("max_turns", 40)),
        "tags": meta.get("tags", []),
    }
    if "stratum" not in meta:
        return row
    for key in ("visible_cmd", "timeout_s", "history_script"):
        if key in meta:
            row["grader"][key] = meta[key]
    if "agent_bash" in meta:
        row["agent_bash"] = meta["agent_bash"]
    row["stratum"] = meta["stratum"]
    row["provenance"] = {
        k: meta[k]
        for k in ("harvest_id", "draw_position", "harvest_shape", "adaptations", "authorship")
        if k in meta
    }
    return row


def main() -> None:
    rows = [parse(p) for p in sorted((HERE / "briefs").glob("*.md"))]
    first = [r for r in rows if "stratum" not in r]
    ext = sorted((r for r in rows if "stratum" in r), key=lambda r: (r["stratum"], r["id"]))
    for name, batch in (("tasks.jsonl", first), ("tasks_ext.jsonl", ext)):
        with (HERE / name).open("w") as f:
            for row in batch:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"wrote {len(batch)} tasks to {name}")


if __name__ == "__main__":
    main()
