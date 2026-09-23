"""Export parsed log entries to a flat CSV: timestamp,level,message."""

from __future__ import annotations

from pathlib import Path

from logproc.parser import LogEntry

HEADER = "timestamp,level,message"


def export_csv(entries: list[LogEntry], path: str | Path) -> None:
    lines = [HEADER]
    for entry in entries:
        fields = [entry.timestamp, entry.level, entry.message]
        lines.append(",".join(fields))
    Path(path).write_text("\n".join(lines) + "\n")


def import_csv(path: str | Path) -> list[LogEntry]:
    text = Path(path).read_text()
    rows = [line for line in text.splitlines() if line.strip()]
    if not rows or rows[0] != HEADER:
        raise ValueError("missing or unexpected CSV header")

    entries = []
    for row in rows[1:]:
        timestamp, level, message = row.split(",")
        entries.append(LogEntry(timestamp=timestamp, level=level, message=message))
    return entries
