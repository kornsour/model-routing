"""Task-chip harvester.

Scans local Claude Code session transcripts (JSONL under
``~/.claude/projects/<project-slug>/*.jsonl``, including nested subagent
directories) for two kinds of handoffs:

* a ``spawn_task`` tool call (any tool name ending in ``spawn_task``, e.g.
  ``mcp__ccd_session__spawn_task``) - a "task chip" the assistant flagged for
  a background session, with ``title`` / ``tldr`` / ``prompt`` / optional
  ``cwd``;
* a subagent dispatch (tool name ``Agent`` or ``Task``) - the parent handing
  work to a subagent, with ``description`` / ``prompt`` / optional
  ``model`` / ``subagent_type``. The ``model`` field, when present, is real
  evidence of how the parent already routes subagent work.

The output is personal data (it contains prompts the operator wrote), so it
is only ever written under a git-ignored path; see ``_check_out_path``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_OUT_PATH = Path("tasks/agentic/private/harvested.jsonl")

_SUBAGENT_TOOL_NAMES = {"Agent", "Task"}


def harvest_chips(projects_dir: Path, out_path: Path) -> int:
    """Stream-parse every ``*.jsonl`` under ``projects_dir`` (recursively) and
    write deduplicated task-chip / subagent-dispatch records as JSONL to
    ``out_path``, sorted by timestamp. Returns the number of records written.

    Bad JSON lines and events missing required fields are skipped rather than
    raising. ``out_path``'s parent directories are created as needed.
    """
    projects_dir = Path(projects_dir)
    out_path = Path(out_path)
    _check_out_path(out_path)

    records: dict[str, dict[str, Any]] = {}

    if projects_dir.exists():
        for jsonl_file in sorted(projects_dir.rglob("*.jsonl")):
            if not jsonl_file.is_file():
                continue
            try:
                session_file = str(jsonl_file.relative_to(projects_dir))
            except ValueError:
                session_file = jsonl_file.name
            project = _project_slug(jsonl_file, projects_dir)
            _harvest_file(jsonl_file, project=project, session_file=session_file, records=records)

    ordered = sorted(records.values(), key=lambda rec: rec.get("timestamp") or "")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for rec in ordered:
            fh.write(json.dumps(rec, sort_keys=True))
            fh.write("\n")

    return len(ordered)


def summarize_harvest(path: Path) -> dict[str, Any]:
    """Load a harvested JSONL file and return counts useful as real-world
    evidence about how parents already route subagent work: counts by kind,
    by project, by parent model, the chosen-model distribution for subagent
    dispatches, and prompt-length (word count) quantiles."""
    path = Path(path)
    records: list[dict[str, Any]] = []
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    records.append(event)

    by_kind = Counter(rec.get("kind") or "unknown" for rec in records)
    by_project = Counter(rec.get("project") or "unknown" for rec in records)
    by_parent_model = Counter(rec.get("parent_model") or "unknown" for rec in records)
    chosen_model_distribution = Counter(
        rec.get("chosen_model")
        for rec in records
        if rec.get("kind") == "subagent" and rec.get("chosen_model")
    )

    word_counts = sorted(int(rec.get("prompt_words") or 0) for rec in records)

    return {
        "count": len(records),
        "by_kind": dict(by_kind),
        "by_project": dict(by_project),
        "by_parent_model": dict(by_parent_model),
        "chosen_model_distribution": dict(chosen_model_distribution),
        "prompt_length_words": _quantiles(word_counts),
    }


# --- git-ignore guard -------------------------------------------------------


def _check_out_path(out_path: Path) -> None:
    """Refuse to harvest into ``out_path`` if it lives inside a git repo but
    is not covered by a ``.gitignore`` rule there. Harvested data is personal
    (raw prompts); it must never land somewhere a routine ``git add`` could
    pick it up. Paths outside any git repo are left alone (e.g. a scratch
    directory, or the operator's home directory in a non-repo layout)."""
    repo_root = _repo_root_for(out_path)
    if repo_root is None:
        return

    resolved = out_path.resolve() if out_path.is_absolute() else (Path.cwd() / out_path).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        return  # out_path is outside this repo entirely

    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(resolved)],
            cwd=repo_root,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return  # can't verify; don't block on an environment without git

    if result.returncode != 0:
        raise ValueError(
            f"refusing to write harvested transcript data to {out_path}: it is "
            f"inside the git repo at {repo_root} but not covered by a "
            ".gitignore rule. Use a git-ignored location, e.g. "
            f"{DEFAULT_OUT_PATH}."
        )


def _repo_root_for(path: Path) -> Path | None:
    base = path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()
    start = base if base.exists() and base.is_dir() else base.parent
    for candidate in [start, *start.parents]:
        if candidate.exists():
            start = candidate
            break
    else:
        start = Path.cwd()

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    root = result.stdout.strip()
    if not root:
        return None
    return Path(root).resolve()


# --- transcript parsing ------------------------------------------------------


def _project_slug(jsonl_file: Path, projects_dir: Path) -> str:
    try:
        rel = jsonl_file.relative_to(projects_dir)
    except ValueError:
        return ""
    return rel.parts[0] if rel.parts else ""


def _harvest_file(
    jsonl_file: Path,
    *,
    project: str,
    session_file: str,
    records: dict[str, dict[str, Any]],
) -> None:
    try:
        fh = jsonl_file.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            for rec in _extract_handoffs(event, project=project, session_file=session_file):
                records.setdefault(rec["id"], rec)


def _extract_handoffs(
    event: dict[str, Any], *, project: str, session_file: str
) -> list[dict[str, Any]]:
    message = event.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        return []

    content = message.get("content")
    if not isinstance(content, list):
        return []

    parent_model = message.get("model") if isinstance(message.get("model"), str) else None
    timestamp = event.get("timestamp") if isinstance(event.get("timestamp"), str) else None
    event_cwd = event.get("cwd") if isinstance(event.get("cwd"), str) else None

    out: list[dict[str, Any]] = []
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        name = block.get("name")
        if not isinstance(name, str):
            continue
        tool_input = block.get("input")
        if not isinstance(tool_input, dict):
            continue

        rec: dict[str, Any] | None = None
        if name.endswith("spawn_task"):
            rec = _build_record(
                tool_input,
                kind="chip",
                parent_model=parent_model,
                project=project,
                cwd=event_cwd,
                timestamp=timestamp,
                session_file=session_file,
                title_key="title",
            )
        elif name in _SUBAGENT_TOOL_NAMES:
            rec = _build_record(
                tool_input,
                kind="subagent",
                parent_model=parent_model,
                project=project,
                cwd=event_cwd,
                timestamp=timestamp,
                session_file=session_file,
                title_key="description",
            )
        if rec is not None:
            out.append(rec)
    return out


def _build_record(
    tool_input: dict[str, Any],
    *,
    kind: str,
    parent_model: str | None,
    project: str,
    cwd: str | None,
    timestamp: str | None,
    session_file: str,
    title_key: str,
) -> dict[str, Any] | None:
    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return None

    title = tool_input.get(title_key)
    if not isinstance(title, str):
        title = None

    tldr = tool_input.get("tldr")
    if not isinstance(tldr, str):
        tldr = None

    input_cwd = tool_input.get("cwd")
    resolved_cwd = input_cwd if isinstance(input_cwd, str) else cwd

    chosen_model = tool_input.get("model")
    if not isinstance(chosen_model, str):
        chosen_model = None

    subagent_type = tool_input.get("subagent_type")
    if not isinstance(subagent_type, str):
        subagent_type = None

    return {
        "id": _prompt_hash(prompt),
        "kind": kind,
        "title": title,
        "tldr": tldr,
        "prompt": prompt,
        "parent_model": parent_model,
        "chosen_model": chosen_model,
        "subagent_type": subagent_type,
        "project": project,
        "cwd": resolved_cwd,
        "timestamp": timestamp,
        "session_file": session_file,
        "prompt_words": len(prompt.split()),
    }


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def _quantiles(sorted_values: list[int]) -> dict[str, float]:
    if not sorted_values:
        return {}
    return {
        "min": float(sorted_values[0]),
        "p25": _percentile(sorted_values, 0.25),
        "p50": _percentile(sorted_values, 0.50),
        "p75": _percentile(sorted_values, 0.75),
        "p95": _percentile(sorted_values, 0.95),
        "max": float(sorted_values[-1]),
    }


def _percentile(sorted_values: list[int], pct: float) -> float:
    n = len(sorted_values)
    if n == 1:
        return float(sorted_values[0])
    k = (n - 1) * pct
    lo = int(k)
    hi = min(lo + 1, n - 1)
    if lo == hi:
        return float(sorted_values[lo])
    frac = k - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac
