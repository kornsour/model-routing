"""Heuristics in scripts/chip_stats.py, on synthetic strings only (never on
harvested transcript data, which is private)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "chip_stats.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("chip_stats", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["chip_stats"] = mod
    spec.loader.exec_module(mod)
    return mod


cs = _load()


def test_mentions_tests() -> None:
    assert cs.mentions_tests("Keep `python -m pytest -q` green.")
    assert cs.mentions_tests("Add a regression test for the parser.")
    assert cs.mentions_tests("see test_parser.py")
    assert not cs.mentions_tests("Update the badge in the README.")
    assert not cs.mentions_tests("The latest release is broken.")  # "latest" is not "test"


def test_file_mentions() -> None:
    text = "Edit `src/pkg/cli.py` and README.md; add tests under tests/*.py. Use and/or logic."
    assert cs.file_mentions(text) == {"src/pkg/cli.py", "README.md", "tests/*.py"}
    assert cs.file_mentions("Look in the src/pkg/ directory.") == {"src/pkg"}
    assert cs.file_mentions("See https://example.com/a/b.html for details.") == set()
    assert cs.file_mentions("No paths here, input/output only, version 1.2.") == set()


def test_scope_constraint() -> None:
    assert cs.has_scope_constraint("Scope: change only `src/a.py`.")
    assert cs.has_scope_constraint("Do not modify any other files.")
    assert cs.has_scope_constraint("Leave every other file untouched.")
    assert cs.has_scope_constraint("Constraints: stdlib only.")
    assert cs.has_scope_constraint("This is a read-only investigation.")
    assert not cs.has_scope_constraint("Fix the crash when the input is empty.")


def test_mentions_model() -> None:
    assert cs.mentions_model("Run this on Sonnet.")
    assert cs.mentions_model("compare against gpt-5")
    assert not cs.mentions_model("Model the invoice as a dataclass.")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Fix the crash in the parser when the input is empty.", "bugfix"),
        ("Implement a new command that exports notes. Add a flag for the format.", "feature"),
        ("Refactor the two duplicated helpers into one and simplify the call sites.", "refactor"),
        ("Add unit tests for the rounding helper. Improve test coverage.", "tests"),
        ("Update the README and the docstrings to describe the new behaviour.", "docs"),
        ("Update the CI workflow and pyproject lint settings.", "config"),
        ("Migrate every call site from the deprecated API.", "migration"),
        ("The report is slow; optimize the hot loop for performance.", "perf"),
        ("Investigate why the sync drops records and report back your findings.", "investigation"),
        ("Hello there.", "other"),
    ],
)
def test_categorize(text: str, expected: str) -> None:
    assert cs.categorize(text) == expected


def test_categorize_ignores_scope_sentence_and_trailing_tests() -> None:
    text = (
        "Fix the wrong total when an invoice has no items. Keep the fix small. "
        "Add tests for it. "
        "Scope: change only src/a.py; leave the README, docstrings and comments untouched."
    )
    assert cs.categorize(text) == "bugfix"


def test_quantiles_and_sessions() -> None:
    q = cs.quantiles([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert q["min"] == 1 and q["max"] == 10 and q["median"] == 5.5
    assert q["p90"] == pytest.approx(9.1)
    assert cs.quantiles([]) == {}

    assert cs.parent_session("proj/abc.jsonl") == "proj/abc"
    assert cs.parent_session("proj/abc/subagents/agent-1.jsonl") == "proj/abc"
    recs = [
        {"session_file": "p/s1.jsonl"},
        {"session_file": "p/s1/subagents/agent-a.jsonl"},
        {"session_file": "p/s2.jsonl"},
    ]
    out = cs.spawns_per_session(recs)
    assert out["sessions"] == 2
    assert out["buckets"] == {"2-3": 1, "1": 1}


def test_stats_and_main_print_aggregates_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = "SECRET-PROMPT-TEXT fix src/x.py and src/y.py, do not touch tests"
    harvested = tmp_path / "h.jsonl"
    harvested.write_text(
        json.dumps(
            {
                "kind": "chip",
                "prompt": secret,
                "session_file": "secret-project/s1.jsonl",
                "title": "SECRET-TITLE",
            }
        )
        + "\n"
        + json.dumps(
            {
                "kind": "subagent",
                "prompt": "Investigate the slow path.",
                "chosen_model": "sonnet",
                "session_file": "secret-project/s1/subagents/agent-a.jsonl",
            }
        )
        + "\n"
    )
    tasks = tmp_path / "t.jsonl"
    tasks.write_text(json.dumps({"brief": "Fix the bug in src/a.py.", "category": "bugfix"}) + "\n")

    s = cs.stats([secret], [False])
    assert s["n"] == 1 and s["multi_file"] == 1.0 and s["scope_constraint"] == 1.0

    assert cs.main([str(harvested), "--tasks", str(tasks)]) == 0
    out = capsys.readouterr().out
    assert "SECRET" not in out and "secret-project" not in out
    assert "| items (n) | 1 | 2 | 1 | 1 |" in out
