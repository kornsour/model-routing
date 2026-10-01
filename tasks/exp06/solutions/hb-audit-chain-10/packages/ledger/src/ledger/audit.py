"""Tamper-evident history: a hash chain over ``history.jsonl`` lines.

Every chained line carries ``prev_hash`` and ``hash``, where
``hash = sha256(prev_hash + canonical(body))`` and ``body`` is the line's
object without those two fields. The first chained line follows ``GENESIS``.
Unchained lines written before chaining existed form a *pre-chain prefix*,
allowed only before the first chained line.

``compact`` replaces the oldest chained records with one checkpoint line
(``kind: checkpoint``) that records how many records it covers, a per-pipeline
summary and ``through_hash``, the hash of the last record it replaced. The
line after it keeps its original ``prev_hash`` (== ``through_hash``), so
``verify`` continues the chain from there.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

GENESIS = "0" * 64
_HASH_FIELDS = ("prev_hash", "hash")


def canonical(body: dict[str, Any]) -> str:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def line_hash(prev_hash: str, doc: dict[str, Any]) -> str:
    body = {k: v for k, v in doc.items() if k not in _HASH_FIELDS}
    return hashlib.sha256((prev_hash + canonical(body)).encode("utf-8")).hexdigest()


def chain(doc: dict[str, Any], prev_hash: str) -> dict[str, Any]:
    """``doc`` with ``prev_hash`` and ``hash`` set."""
    out = {k: v for k, v in doc.items() if k not in _HASH_FIELDS}
    out["prev_hash"] = prev_hash
    out["hash"] = line_hash(prev_hash, out)
    return out


def _is_chained(doc: dict[str, Any]) -> bool:
    return "hash" in doc and "prev_hash" in doc


def last_hash(path: str | Path) -> str:
    """The hash the next appended line must follow."""
    p = Path(path)
    if not p.exists():
        return GENESIS
    for line in reversed(p.read_text().splitlines()):
        if line.strip():
            doc = json.loads(line)
            return doc["hash"] if _is_chained(doc) else GENESIS
    return GENESIS


@dataclass(frozen=True)
class Verification:
    ok: bool
    checked: int
    pre_chain: int
    checkpoints: int
    bad_line: int | None = None
    reason: str = ""


def verify(path: str | Path) -> Verification:
    p = Path(path)
    if not p.exists():
        return Verification(True, 0, 0, 0)
    checked = pre_chain = checkpoints = 0
    prev: str | None = None

    def fail(lineno: int, reason: str) -> Verification:
        return Verification(False, checked, pre_chain, checkpoints, lineno, reason)

    for lineno, line in enumerate(p.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            doc = json.loads(line)
        except json.JSONDecodeError:
            return fail(lineno, "not valid JSON")
        if not _is_chained(doc):
            if prev is not None:
                return fail(lineno, "unchained record after the chain started")
            pre_chain += 1
            continue
        expected_prev = GENESIS if prev is None else prev
        if doc["prev_hash"] != expected_prev:
            return fail(lineno, "prev_hash does not match the previous line (record deleted, inserted or reordered)")
        if doc["hash"] != line_hash(doc["prev_hash"], doc):
            return fail(lineno, "hash mismatch (line edited)")
        if doc.get("kind") == "checkpoint":
            checkpoints += 1
            prev = doc["through_hash"]
        else:
            checked += 1
            prev = doc["hash"]
    return Verification(True, checked, pre_chain, checkpoints)


def _month(doc: dict[str, Any]) -> str:
    return datetime.fromisoformat(doc["started_at"]).astimezone(UTC).strftime("%Y-%m")


def compact(path: str | Path, out_path: str | Path, before_month: str) -> str:
    out = Path(out_path)
    if out.exists():
        raise FileExistsError(out)
    raw_lines = [line for line in Path(path).read_text().splitlines() if line.strip()]
    docs = [json.loads(line) for line in raw_lines]
    start = 0
    while start < len(docs) and not _is_chained(docs[start]):
        start += 1
    end = start
    while end < len(docs) and (docs[end].get("kind") == "checkpoint" or _month(docs[end]) < before_month):
        if docs[end].get("kind") == "checkpoint" and end != start:
            break
        end += 1
    covered = docs[start:end]
    if not covered or all(d.get("kind") == "checkpoint" for d in covered):
        out.write_text("".join(line + "\n" for line in raw_lines))
        return ""
    covers = 0
    summary: dict[str, dict[str, float]] = {}
    prev_hash = covered[0]["prev_hash"]
    for doc in covered:
        if doc.get("kind") == "checkpoint":
            covers += doc["covers"]
            for pipeline, s in doc["summary"].items():
                row = summary.setdefault(pipeline, {"runs": 0, "total_usd": 0.0})
                row["runs"] += s["runs"]
                row["total_usd"] += s["total_usd"]
            continue
        covers += 1
        row = summary.setdefault(doc["pipeline"], {"runs": 0, "total_usd": 0.0})
        row["runs"] += 1
        row["total_usd"] += doc["total_usd"]
    for row in summary.values():
        row["total_usd"] = round(row["total_usd"], 6)
    checkpoint = chain(
        {
            "kind": "checkpoint",
            "covers": covers,
            "through_hash": covered[-1]["through_hash"] if covered[-1].get("kind") == "checkpoint" else covered[-1]["hash"],
            "summary": dict(sorted(summary.items())),
        },
        prev_hash,
    )
    new_lines = raw_lines[:start] + [json.dumps(checkpoint, sort_keys=True)] + raw_lines[end:]
    out.write_text("".join(line + "\n" for line in new_lines))
    return checkpoint["hash"]
