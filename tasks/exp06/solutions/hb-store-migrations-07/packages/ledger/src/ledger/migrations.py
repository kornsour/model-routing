"""Declarative history migrations (see ``docs/ledger-migrations.md``).

Each ``migrations/NNNN_slug.json`` file is one step of the history format.
``check`` enforces the chain rules, ``apply_ops`` runs one step's ops on a
record, and ``upgrade`` brings a record from its version to the latest.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
OPS = {"add_field", "rename_field", "map_values", "drop_field"}
_NAME = re.compile(r"^(\d{4})_.+\.json$")


@dataclass(frozen=True)
class Migration:
    number: int
    name: str
    id: str
    prev_id: str | None
    version: int
    description: str
    ops: tuple[dict[str, Any], ...]


def load_migrations(directory: str | Path | None = None) -> list[Migration]:
    d = Path(directory) if directory is not None else MIGRATIONS_DIR
    out = []
    for path in d.glob("*.json"):
        m = _NAME.match(path.name)
        if not m:
            raise ValueError(f"{path.name}: migration files are named NNNN_slug.json")
        doc = json.loads(path.read_text())
        out.append(
            Migration(
                number=int(m.group(1)),
                name=path.name,
                id=doc["id"],
                prev_id=doc.get("prev_id"),
                version=doc["version"],
                description=doc.get("description", ""),
                ops=tuple(doc.get("ops", [])),
            )
        )
    return sorted(out, key=lambda m: (m.number, m.name))


def check(migrations: list[Migration]) -> list[str]:
    problems: list[str] = []
    seen_numbers: dict[int, str] = {}
    seen_ids: dict[str, str] = {}
    for m in migrations:
        if m.number in seen_numbers:
            problems.append(f"{m.name}: number {m.number:04d} already used by {seen_numbers[m.number]}")
        seen_numbers.setdefault(m.number, m.name)
        if m.id in seen_ids:
            problems.append(f"{m.name}: id {m.id!r} already used by {seen_ids[m.id]}")
        seen_ids.setdefault(m.id, m.name)
        if m.version != m.number + 1:
            problems.append(f"{m.name}: version {m.version} should be {m.number + 1}")
        for op in m.ops:
            if op.get("op") not in OPS:
                problems.append(f"{m.name}: unknown op {op.get('op')!r}")
    expected = list(range(len(seen_numbers)))
    if sorted(seen_numbers) != expected:
        missing = sorted(set(range(max(seen_numbers, default=-1) + 1)) - set(seen_numbers))
        problems.append(f"migration numbers are not contiguous from 0000 (missing {', '.join(f'{n:04d}' for n in missing)})")
    by_number = {m.number: m for m in migrations}
    for m in migrations:
        if m.number == 0:
            if m.prev_id is not None:
                problems.append(f"{m.name}: the 0000 baseline must have prev_id null")
            if m.ops:
                problems.append(f"{m.name}: the 0000 baseline must have no ops")
            continue
        prev = by_number.get(m.number - 1)
        if prev is None or m.prev_id != prev.id:
            want = prev.id if prev else "(no predecessor)"
            problems.append(f"{m.name}: prev_id {m.prev_id!r} should be {want!r}")
    return problems


def apply_ops(doc: dict[str, Any], ops: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    for op in ops:
        kind = op["op"]
        if kind == "add_field":
            if op["field"] not in out:
                out[op["field"]] = copy.deepcopy(op["default"])
        elif kind == "rename_field":
            if op["from"] in out:
                if op["to"] in out:
                    raise ValueError(f"cannot rename {op['from']!r}: {op['to']!r} already exists")
                out[op["to"]] = out.pop(op["from"])
        elif kind == "map_values":
            field = op["field"]
            if field in out and isinstance(out[field], str | int | float | bool) and out[field] in op["mapping"]:
                out[field] = op["mapping"][out[field]]
        elif kind == "drop_field":
            out.pop(op["field"], None)
        else:
            raise ValueError(f"unknown op {kind!r}")
    return out


def latest_version(migrations: list[Migration]) -> int:
    return max((m.version for m in migrations), default=1)


def upgrade(doc: dict[str, Any], migrations: list[Migration]) -> dict[str, Any]:
    latest = latest_version(migrations)
    version = doc.get("version")
    if not isinstance(version, int) or version < 1:
        raise ValueError(f"record has no valid version: {version!r}")
    if version > latest:
        raise ValueError(f"record version {version} is newer than the latest migration ({latest})")
    out = copy.deepcopy(doc)
    for m in migrations:
        if m.version > version:
            out = apply_ops(out, m.ops)
    out["version"] = latest
    return out
