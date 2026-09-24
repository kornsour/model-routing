"""Export parsed log entries to a flat CSV: timestamp,level,message."""

from __future__ import annotations

import csv
from pathlib import Path

from logproc.parser import LogEntry

HEADER = "timestamp,level,message"
_FIELDS = HEADER.split(",")


def export_csv(entries: list[LogEntry], path: str | Path) -> None:
    with Path(path).open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(_FIELDS)
        for entry in entries:
            writer.writerow([entry.timestamp, entry.level, entry.message])


def import_csv(path: str | Path) -> list[LogEntry]:
    with Path(path).open(newline="") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        if header != _FIELDS:
            raise ValueError("missing or unexpected CSV header")
        entries = []
        for row in reader:
            if not row:
                continue
            timestamp, level, message = row
            entries.append(LogEntry(timestamp=timestamp, level=level, message=message))
    return entries
