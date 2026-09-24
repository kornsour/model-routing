"""Export parsed log entries to a flat CSV: timestamp,level,message,source.

Files written before the ``source`` column existed have a three-column
header; they still import, with an empty source on every row.
"""

from __future__ import annotations

import csv
from pathlib import Path

from logproc.parser import LogEntry

HEADER = "timestamp,level,message,source"
_FIELDS = HEADER.split(",")
_LEGACY_FIELDS = _FIELDS[:3]


def export_csv(entries: list[LogEntry], path: str | Path) -> None:
    with Path(path).open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(_FIELDS)
        for entry in entries:
            writer.writerow([entry.timestamp, entry.level, entry.message, entry.source])


def import_csv(path: str | Path) -> list[LogEntry]:
    with Path(path).open(newline="") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        if header not in (_FIELDS, _LEGACY_FIELDS):
            raise ValueError("missing or unexpected CSV header")
        entries = []
        for row in reader:
            if not row:
                continue
            timestamp, level, message = row[:3]
            source = row[3] if len(row) > 3 else ""
            entries.append(
                LogEntry(timestamp=timestamp, level=level, message=message, source=source)
            )
    return entries
