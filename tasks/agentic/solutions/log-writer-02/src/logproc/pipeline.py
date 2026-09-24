"""Reads log files, writes parsed entries to CSV, and builds a summary report.

``EntryWriter`` buffers rows in memory and only writes them to disk on
:meth:`EntryWriter.close`, so a run can batch many small log files into one
CSV write. Whatever is already in the CSV when a writer flushes - rows from
an earlier run, or rows another writer flushed to the same file a moment
before - is kept; a flush only ever adds the writer's own rows after them.
``build_report`` reads the CSV back from disk (it needs to work even when
the writer belongs to an earlier process), so callers must close the writer
before building a report that should include everything just written.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from logproc.aggregate import count_by_level
from logproc.csvexport import HEADER, import_csv
from logproc.parser import LogEntry, parse_line


def _parse_timestamp(text: str) -> datetime:
    """Parse a log entry timestamp for sorting.

    Accepts the same ISO/space-separated formats as
    ``logproc.timestamps.parse_timestamp``. Kept separate so the pipeline has
    no dependency on the timestamps module.
    """
    text = text.strip()
    normalized = text.replace("T", " ", 1) if "T" in text else text
    return datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S")


class EntryWriter:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._pending: list[LogEntry] = []

    def write(self, entry: LogEntry) -> None:
        self._pending.append(entry)

    def close(self) -> None:
        """Flush pending entries to ``self.path`` as CSV.

        Safe to call more than once: the on-call script closes its writer in
        a ``finally`` block after the CLI code path may already have closed it.
        """
        if not self._pending:
            return
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


def process_logs(log_paths: Iterable[str | Path], out_path: str | Path) -> EntryWriter:
    """Parse every log in ``log_paths`` (in order) into one ``out_path``.

    This is what the on-call script calls with a night's worth of rotated
    files. Like :func:`process_log`, returns the writer for the caller to
    close.
    """
    writer = EntryWriter(out_path)
    for log_path in log_paths:
        for entry in read_entries(log_path):
            writer.write(entry)
    return writer


def build_report(out_path: str | Path) -> dict:
    """Summarize the CSV at ``out_path``: counts by level, sorted by time."""
    entries = import_csv(out_path) if Path(out_path).exists() else []
    entries_sorted = sorted(entries, key=lambda e: _parse_timestamp(e.timestamp))
    return {
        "count": len(entries_sorted),
        "by_level": count_by_level(entries_sorted),
    }
