from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from model_routing.dispatch.harvest import harvest_chips, summarize_harvest

FIXTURES = Path(__file__).parent / "fixtures" / "harvest" / "projects"

DUP_PROMPT = (
    "Fix the flaky test in tests/test_foo.py: it intermittently fails because "
    "of a race with the background worker. Add a bounded retry or a proper "
    "wait condition, and keep the test fast."
)


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_harvest_finds_nested_dirs_and_both_kinds(tmp_path: Path) -> None:
    out_path = tmp_path / "harvested.jsonl"

    count = harvest_chips(FIXTURES, out_path)

    records = _read_jsonl(out_path)
    assert count == len(records)
    kinds = {r["kind"] for r in records}
    assert kinds == {"chip", "subagent"}

    # session inside the nested "subagents" subdirectory was discovered.
    assert any(r["session_file"].startswith("-Users-op-repo-a" + "/subagents/") for r in records)


def test_harvest_dedupes_by_prompt_hash(tmp_path: Path) -> None:
    out_path = tmp_path / "harvested.jsonl"

    harvest_chips(FIXTURES, out_path)

    records = _read_jsonl(out_path)
    matching = [r for r in records if r["prompt"] == DUP_PROMPT]
    assert len(matching) == 1
    # first occurrence (by sorted file path) is kept: repo-a, not repo-b.
    assert matching[0]["project"] == "-Users-op-repo-a"


def test_harvest_skips_malformed_lines_and_missing_prompt(tmp_path: Path) -> None:
    out_path = tmp_path / "harvested.jsonl"

    harvest_chips(FIXTURES, out_path)

    records = _read_jsonl(out_path)
    # The malformed JSON line and the spawn_task with no "prompt" field must
    # not produce records (and must not crash the harvest).
    assert not any(r.get("title") == "Missing prompt chip" for r in records)


def test_harvest_captures_parent_and_chosen_model(tmp_path: Path) -> None:
    out_path = tmp_path / "harvested.jsonl"

    harvest_chips(FIXTURES, out_path)

    records = _read_jsonl(out_path)
    subagent_records = [r for r in records if r["kind"] == "subagent"]
    assert subagent_records

    research = next(r for r in subagent_records if "Investigate how auth tokens" in r["prompt"])
    assert research["parent_model"] == "claude-opus-5"
    assert research["chosen_model"] == "claude-haiku-5"
    assert research["subagent_type"] == "general-purpose"
    assert research["title"] == "Research auth token refresh"

    summarize = next(r for r in subagent_records if "Summarize the auth token" in r["prompt"])
    assert summarize["parent_model"] == "claude-haiku-5"
    assert summarize["chosen_model"] is None


def test_harvest_handles_missing_fields_gracefully(tmp_path: Path) -> None:
    out_path = tmp_path / "harvested.jsonl"

    harvest_chips(FIXTURES, out_path)

    records = _read_jsonl(out_path)
    changelog = next(r for r in records if "changelog" in r["prompt"])
    # this event's message has no "model" key and the tool input has no title/tldr.
    assert changelog["parent_model"] is None
    assert changelog["title"] is None
    assert changelog["tldr"] is None


def test_harvest_is_sorted_by_timestamp_and_ignores_unrelated_tools(tmp_path: Path) -> None:
    out_path = tmp_path / "harvested.jsonl"

    harvest_chips(FIXTURES, out_path)

    records = _read_jsonl(out_path)
    timestamps = [r["timestamp"] for r in records]
    assert timestamps == sorted(timestamps)
    assert not any("does not end in spawn_task" in r["prompt"] for r in records)


def test_harvest_on_missing_projects_dir_writes_empty_file(tmp_path: Path) -> None:
    out_path = tmp_path / "harvested.jsonl"

    count = harvest_chips(tmp_path / "does-not-exist", out_path)

    assert count == 0
    assert out_path.exists()
    assert out_path.read_text() == ""


def test_summarize_harvest_shape(tmp_path: Path) -> None:
    out_path = tmp_path / "harvested.jsonl"
    harvest_chips(FIXTURES, out_path)

    summary = summarize_harvest(out_path)

    assert summary["count"] > 0
    assert set(summary["by_kind"]) <= {"chip", "subagent"}
    assert "-Users-op-repo-a" in summary["by_project"]
    assert "-Users-op-repo-b" in summary["by_project"]
    assert "claude-haiku-5" in summary["chosen_model_distribution"]
    quantiles = summary["prompt_length_words"]
    assert quantiles["min"] <= quantiles["p50"] <= quantiles["max"]


def test_summarize_harvest_on_missing_file(tmp_path: Path) -> None:
    summary = summarize_harvest(tmp_path / "nope.jsonl")
    assert summary["count"] == 0
    assert summary["prompt_length_words"] == {}


# --- git-ignore guard --------------------------------------------------------


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)


def test_refuses_out_path_inside_repo_but_not_ignored(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / ".gitignore").write_text("private/\n")

    out_path = repo / "tasks" / "agentic" / "harvested.jsonl"  # NOT under private/

    with pytest.raises(ValueError, match="git-ignored"):
        harvest_chips(FIXTURES, out_path)

    assert not out_path.exists()


def test_allows_out_path_under_gitignored_dir(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "tasks" / "agentic").mkdir(parents=True)
    (repo / "tasks" / "agentic" / ".gitignore").write_text("private/\n")

    out_path = repo / "tasks" / "agentic" / "private" / "harvested.jsonl"

    count = harvest_chips(FIXTURES, out_path)

    assert out_path.exists()
    assert count > 0


def test_allows_out_path_outside_any_repo(tmp_path: Path) -> None:
    # tmp_path itself is not inside a git repository, so no guard applies.
    out_path = tmp_path / "outside" / "harvested.jsonl"

    count = harvest_chips(FIXTURES, out_path)

    assert out_path.exists()
    assert count > 0
