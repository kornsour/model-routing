"""Reads a log file, writes parsed entries to CSV, and builds a summary report.

``EntryWriter`` buffers rows in memory and only writes them to disk on
:meth:`EntryWriter.close`, so a run can batch many small log files into one
CSV write. ``build_report`` reads the CSV back from disk (it needs to work
even when the writer belongs to an earlier process), so callers must close
the writer before building a report that should include everything just
written.
"""

from __future__ import annotations

from pathlib import Path

from logproc.aggregate import count_by_level
from logproc.csvexport import HEADER, import_csv
from logproc.parser import LogEntry, parse_line
from logproc.timestamps import parse_timestamp
from logproc.window import filter_window

_parse_timestamp = parse_timestamp


class EntryWriter:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._pending: list[LogEntry] = []

    def write(self, entry: LogEntry) -> None:
        self._pending.append(entry)

    def close(self) -> None:
        """Flush pending entries to ``self.path`` as CSV."""
        existing = import_csv(self.path) if self.path.exists() else []
        lines = [HEADER]
        for entry in existing + self._pending:
            lines.append(f"{entry.timestamp},{entry.level},{entry.message}")
        self.path.write_text("\n".join(lines) + "\n")
        self._pending = []


def read_entries(log_path: str | Path) -> list[LogEntry]:
    entries = []
    for line in Path(log_path).read_text().splitlines():
        entry = parse_line(line)
        if entry is not None:
            entries.append(entry)
    return entries


def process_log(log_path: str | Path, out_path: str | Path) -> EntryWriter:
    """Parse ``log_path`` and write every entry to ``out_path``.

    Returns the writer so the caller can inspect it, but the caller is
    responsible for closing it before anything downstream reads ``out_path``.
    """
    writer = EntryWriter(out_path)
    for entry in read_entries(log_path):
        writer.write(entry)
    return writer


def build_report(out_path: str | Path, since: str | None = None, until: str | None = None) -> dict:
    """Summarize the CSV at ``out_path``: counts by level, ordered by instant.

    ``since`` / ``until`` restrict the report to a window (see
    ``logproc.window``). ``first`` / ``last`` are the earliest and latest
    entries' timestamps as written in the log, or ``None`` when empty.
    """
    entries = import_csv(out_path) if Path(out_path).exists() else []
    entries = filter_window(entries, since, until)
    entries_sorted = sorted(entries, key=lambda e: _parse_timestamp(e.timestamp))
    return {
        "count": len(entries_sorted),
        "by_level": count_by_level(entries_sorted),
        "first": entries_sorted[0].timestamp if entries_sorted else None,
        "last": entries_sorted[-1].timestamp if entries_sorted else None,
    }
