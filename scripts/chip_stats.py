#!/usr/bin/env python3
"""Aggregate statistics: harvested real handoffs vs the synthetic task set.

    uv run python scripts/chip_stats.py [HARVESTED_JSONL] [--tasks TASKS_JSONL]

Reads the git-ignored output of ``make harvest-chips`` (default
``tasks/agentic/private/harvested.jsonl``) and the synthetic task set's
``brief`` field (default ``tasks/agentic/tasks.jsonl``) and prints the same
aggregate statistics for both, side by side, as a Markdown table.

PRIVACY: the harvested file holds raw private prompt text. This script prints
aggregates only - counts, shares and length quantiles - never prompt text,
titles, paths, project names or session ids. Keep it that way.

The heuristics (tests / file names / scope sentence / category / stated
model) are keyword regexes; they are coarse by design and are unit-tested on
synthetic strings in ``tests/test_chip_stats.py``. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

DEFAULT_HARVEST = Path("tasks/agentic/private/harvested.jsonl")
DEFAULT_TASKS = Path("tasks/agentic/tasks.jsonl")

CATEGORIES = (
    "bugfix",
    "feature",
    "refactor",
    "tests",
    "docs",
    "config",
    "migration",
    "perf",
    "investigation",
    "other",
)

_TEST_RE = re.compile(
    r"\btests?\b|\btesting\b|\bpytest\b|\bunittest\b|\btest_\w+|\bspecs?\b|\bvitest\b|\bjest\b",
    re.IGNORECASE,
)

_EXT = (
    "py|pyi|ts|tsx|js|jsx|mjs|cjs|md|mdx|toml|json|jsonl|ya?ml|sh|zsh|go|rs|java|kt|swift|"
    "rb|php|c|h|cc|cpp|hpp|cs|html|css|scss|sql|txt|cfg|ini|lock|csv|ipynb|tf|env|xml|plist"
)
# A path-like token ending in a known extension (``src/a.py``, ``README.md``),
# or a slash-containing path (``src/foo/``, ``tests/*.py``).
_FILE_RE = re.compile(
    rf"(?<![\w@/.-])((?:[\w.*-]+/)*[\w*-][\w.*-]*\.(?:{_EXT}))(?![\w/-])"
    r"|(?<![\w@/.:-])((?:[\w.*-]+/){1,}[\w.*-]*)(?![\w:])",
    re.IGNORECASE,
)

_SCOPE_RE = re.compile(
    r"\bscope\b|\bout of scope\b"
    r"|\bonly (?:change|touch|modify|edit)\b"
    r"|\b(?:do not|don't|dont|never|must not|should not) "
    r"(?:change|touch|modify|edit|commit|push|delete|add|run|refactor|cd|spend)\b"
    r"|\bleave\b[^.\n]{0,80}\buntouched\b"
    r"|\bwithout (?:changing|touching|modifying)\b"
    r"|\bconstraints?\s*:"
    r"|\bkeep (?:it|the change|changes|the diff) (?:minimal|small|focused)\b"
    r"|\bread[- ]only\b",
    re.IGNORECASE,
)

_MODEL_RE = re.compile(r"\b(?:opus|sonnet|haiku|gpt-?\d|o\d-mini|gemini|codex)\b", re.IGNORECASE)

# Keyword -> category. Scored: each distinct matching pattern is one point;
# ties break in CATEGORIES order.
_CATEGORY_PATTERNS: dict[str, tuple[str, ...]] = {
    "bugfix": (
        r"\bfix(?:es|ed|ing)?\b",
        r"\bbugs?\b",
        r"\bbroken\b",
        r"\bcrash(?:es|ing)?\b",
        r"\bregression\b",
        r"\bincorrect(?:ly)?\b",
        r"\bwrong\b",
        r"\bfails?\b|\bfailing\b",
        r"\berrors?\b",
        r"\bflaky\b",
    ),
    "feature": (
        r"\bimplement\w*\b",
        r"\badd (?:a |an |support|the )",
        r"\bnew (?:feature|command|flag|option|endpoint|page|field)\b",
        r"\bsupport for\b",
        r"\bbuild (?:a|an|the)\b",
        r"\bcreate (?:a|an|the)\b",
        r"\bintroduce\b",
        r"\bneeds? (?:a|an|to)\b|\bmust (?:accept|support)\b",
        r"\bretr(?:y|ies)\b|\bgains?\b",
    ),
    "refactor": (
        r"\brefactor\w*\b",
        r"\bclean ?up\b",
        r"\bdedup\w*\b|\bduplicat\w*\b",
        r"\bextract\b",
        r"\bsimplif\w*\b",
        r"\bconsolidat\w*\b",
        r"\brestructur\w*\b",
        r"\bdead code\b",
    ),
    "tests": (
        r"\b(?:add|write|missing|more) (?:a |unit |regression )?tests?\b",
        r"\btest coverage\b|\bcoverage\b",
        r"\bregression test\b",
        r"\bunit tests?\b",
    ),
    "docs": (
        r"\breadme\b",
        r"\bdocumentation\b",
        r"\bdocstrings?\b",
        r"\bchangelog\b",
        r"\bdocs?\b",
        r"\bcomments?\b",
    ),
    "config": (
        r"\bconfig\w*\b",
        r"\bci\b|\bworkflows?\b|\bgithub actions\b",
        r"\bmakefile\b|\bpyproject\b|\bpackage\.json\b",
        r"\benv(?:ironment)? var\w*\b",
        r"\bdependenc\w*\b|\blockfile\b",
        r"\bsettings\b",
        r"\blint\w*\b",
    ),
    "migration": (
        r"\bmigrat\w*\b",
        r"\bupgrad\w*\b",
        r"\bdeprecat\w*\b",
        r"\bport(?:ing)? (?:\w+ )?to\b",
        r"\bswitch (?:\w+ )?(?:from|to)\b",
        r"\bevery call site\b|\ball call sites\b|\bcall sites\b",
        r"\brename\w*\b.{0,60}\b(?:across|everywhere|throughout)\b",
        r"\breplace\b.{0,60}\bwith\b.{0,60}\b(?:across|everywhere|throughout)\b",
    ),
    "perf": (
        r"\bperf(?:ormance)?\b",
        r"\bslow(?:er|ness)?\b",
        r"\bfaster\b|\bspeed ?up\b",
        r"\blatency\b",
        r"\boptimi[sz]\w*\b",
        r"\bO\(n",
        r"\bmemory\b",
        r"\bcach(?:e|ing)\b",
    ),
    "investigation": (
        r"\binvestigat\w*\b",
        r"\bresearch\b",
        r"\bfind out\b|\bfigure out\b",
        r"\bexplore\b",
        r"\blook into\b",
        r"\baudit\b",
        r"\banaly[sz]\w*\b",
        r"\breport back\b|\breport (?:your|the) findings\b",
        r"\bwhy (?:does|do|is|are)\b",
        r"\bsurvey\b|\bsearch (?:for|the)\b",
        r"\bdo not (?:edit|modify|change) (?:any )?files\b",
    ),
}
_CATEGORY_RES = {
    cat: tuple(re.compile(p, re.IGNORECASE) for p in pats)
    for cat, pats in _CATEGORY_PATTERNS.items()
}


# --- heuristics ---------------------------------------------------------------


def mentions_tests(text: str) -> bool:
    return bool(_TEST_RE.search(text))


def file_mentions(text: str) -> set[str]:
    """Distinct path-like tokens (``src/a.py``, ``README.md``, ``tests/*.py``)."""
    found: set[str] = set()
    for m in _FILE_RE.finditer(text):
        tok = (m.group(1) or m.group(2) or "").strip("`'\".,;:()")
        if not tok or tok.startswith(("http", "www.")) or tok.count("/") > 12:
            continue
        # A bare "a/b" pair of words (e.g. "and/or", "input/output") is not a path.
        if m.group(2) and tok.count("/") == 1 and not tok.endswith("/"):
            continue
        found.add(tok.rstrip("/"))
    return found


def has_scope_constraint(text: str) -> bool:
    return bool(_SCOPE_RE.search(text))


def mentions_model(text: str) -> bool:
    return bool(_MODEL_RE.search(text))


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def categorize(text: str) -> str:
    """Coarse category by keyword score. Scope/constraint sentences are dropped
    first (a "leave the README and docstrings untouched" line says nothing
    about the task's kind), and the opening two sentences - where a brief
    states its goal - count double."""
    sentences = [s for s in _SENTENCE_RE.split(text) if s.strip()]
    kept = [s for s in sentences if not has_scope_constraint(s)]
    head, tail = " ".join(kept[:2]), " ".join(kept[2:])
    scores = {
        # "...and add tests" trails most fix/feature briefs, so a tests-only
        # task has to say so in its goal sentences.
        cat: sum(
            2 * bool(rx.search(head)) + (cat != "tests" and bool(rx.search(tail))) for rx in regexes
        )
        for cat, regexes in _CATEGORY_RES.items()
    }
    best = max(scores.values())
    if best == 0:
        return "other"
    for cat in CATEGORIES:
        if scores.get(cat) == best:
            return cat
    return "other"  # pragma: no cover


# --- aggregation --------------------------------------------------------------


def percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    k = (len(sorted_values) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


def quantiles(values: Iterable[float]) -> dict[str, float]:
    vals = sorted(values)
    if not vals:
        return {}
    return {
        "min": float(vals[0]),
        "median": percentile(vals, 0.5),
        "p90": percentile(vals, 0.9),
        "max": float(vals[-1]),
    }


def stats(texts: list[str], stated_model: list[bool] | None = None) -> dict[str, Any]:
    """Aggregate statistics over a list of brief/prompt texts. ``stated_model``
    (parallel to ``texts``) marks items spawned with an explicit model field;
    when absent, only the text-mention share is reported."""
    n = len(texts)
    chars = [len(t) for t in texts]
    files = [file_mentions(t) for t in texts]
    cats = Counter(categorize(t) for t in texts)

    def share(flags: Iterable[bool]) -> float:
        flags = list(flags)
        return (sum(flags) / len(flags)) if flags else 0.0

    return {
        "n": n,
        "chars": quantiles(chars),
        "tokens": quantiles(c / 4 for c in chars),
        "mentions_tests": share(mentions_tests(t) for t in texts),
        "names_files": share(len(f) >= 1 for f in files),
        "multi_file": share(len(f) >= 2 for f in files),
        "scope_constraint": share(has_scope_constraint(t) for t in texts),
        "model_field": share(stated_model) if stated_model is not None else None,
        "model_in_text": share(mentions_model(t) for t in texts),
        "categories": {c: (cats.get(c, 0) / n if n else 0.0) for c in CATEGORIES},
    }


def parent_session(session_file: str) -> str:
    """Root session of a harvested record: ``<project>/<session>.jsonl`` and
    ``<project>/<session>/subagents/...`` both map to ``<project>/<session>``."""
    parts = Path(session_file).parts
    if len(parts) < 2:
        return session_file
    root = parts[1]
    return f"{parts[0]}/{root.removesuffix('.jsonl')}"


def spawns_per_session(records: list[dict[str, Any]]) -> dict[str, Any]:
    per = Counter(parent_session(str(r.get("session_file") or "")) for r in records)
    counts = list(per.values())
    buckets = Counter(
        "1" if c == 1 else "2-3" if c <= 3 else "4-10" if c <= 10 else "11+" for c in counts
    )
    return {"sessions": len(counts), "quantiles": quantiles(counts), "buckets": dict(buckets)}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


# --- rendering ------------------------------------------------------------------


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def _q(q: dict[str, float]) -> str:
    if not q:
        return "n/a"
    return f"{q['min']:.0f} / {q['median']:.0f} / {q['p90']:.0f} / {q['max']:.0f}"


def render(columns: dict[str, dict[str, Any]]) -> str:
    names = list(columns)
    rows: list[tuple[str, list[str]]] = [
        ("items (n)", [str(columns[c]["n"]) for c in names]),
        ("chars min / median / p90 / max", [_q(columns[c]["chars"]) for c in names]),
        ("~tokens (chars/4) min / median / p90 / max", [_q(columns[c]["tokens"]) for c in names]),
        ("mentions tests", [_pct(columns[c]["mentions_tests"]) for c in names]),
        ("names >=1 file path", [_pct(columns[c]["names_files"]) for c in names]),
        ("multi-file (>=2 paths)", [_pct(columns[c]["multi_file"]) for c in names]),
        (
            "explicit scope/constraint sentence",
            [_pct(columns[c]["scope_constraint"]) for c in names],
        ),
        ("spawned with explicit model field", [_pct(columns[c]["model_field"]) for c in names]),
        ("names a model in the text", [_pct(columns[c]["model_in_text"]) for c in names]),
    ]
    for cat in CATEGORIES:
        rows.append((f"category: {cat}", [_pct(columns[c]["categories"][cat]) for c in names]))
    lines = ["| metric | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    lines += [f"| {label} | " + " | ".join(vals) + " |" for label, vals in rows]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("harvested", nargs="?", type=Path, default=DEFAULT_HARVEST)
    ap.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    args = ap.parse_args(argv)

    tasks = load_jsonl(args.tasks)
    harvested = load_jsonl(args.harvested)

    columns: dict[str, dict[str, Any]] = {}
    columns["synthetic briefs"] = stats([str(t.get("brief") or "") for t in tasks])
    for label, subset in (
        ("harvested: all", harvested),
        ("harvested: spawn_task chips", [r for r in harvested if r.get("kind") == "chip"]),
        ("harvested: subagent dispatches", [r for r in harvested if r.get("kind") == "subagent"]),
    ):
        columns[label] = stats(
            [str(r.get("prompt") or "") for r in subset],
            [bool(r.get("chosen_model")) for r in subset],
        )

    print(render(columns))

    if tasks:
        labelled = [
            (str(t.get("category") or ""), categorize(str(t.get("brief") or ""))) for t in tasks
        ]
        agree = sum(1 for lab, got in labelled if lab == got)
        print(
            f"\nCategory heuristic vs the synthetic set's own labels: "
            f"{agree}/{len(labelled)} agree ({100 * agree / len(labelled):.0f}%)."
        )
        print(
            "Synthetic labelled categories: "
            + ", ".join(f"{k} {v}" for k, v in Counter(lab for lab, _ in labelled).most_common())
        )

    if harvested:
        sess = spawns_per_session(harvested)
        chips = [r for r in harvested if r.get("kind") == "chip"]
        print(
            f"\nHandoffs per parent session (all kinds): {sess['sessions']} sessions; "
            f"min/median/p90/max {_q(sess['quantiles'])}; buckets {sess['buckets']}"
        )
        if chips:
            cs = spawns_per_session(chips)
            print(
                f"spawn_task chips per parent session: {cs['sessions']} sessions; "
                f"min/median/p90/max {_q(cs['quantiles'])}; buckets {cs['buckets']}"
            )
        models = Counter(str(r.get("chosen_model")) for r in harvested if r.get("chosen_model"))
        print(
            "Explicit model field values (subagent dispatches): "
            + (", ".join(f"{k} {v}" for k, v in models.most_common()) or "none")
        )
        types = Counter(
            str(r.get("subagent_type") or "unset") for r in harvested if r.get("kind") == "subagent"
        )
        print(
            "Subagent type (subagent dispatches): "
            + ", ".join(f"{k} {v}" for k, v in types.most_common())
        )
    else:
        print(f"\nNo harvested records at {args.harvested} (run `make harvest-chips`).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
