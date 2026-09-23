"""Query an entries CSV (as written by ``logproc process``) without rebuilding the report.

The on-call dashboard opens one :class:`EntryIndex` per entries CSV and fires
many small queries at it while a page renders - a count per level, the rows
for the level the operator clicked, the time window around an incident. The
index is a read-only view: it never writes the CSV, and it may be created
before the CSV exists (the writer that produces it can still be running).

The CSV on disk only changes when a writer flushes, so an index is expected
to serve its queries from one snapshot of the file and to pick up new rows
only when the caller asks for it with :meth:`EntryIndex.refresh`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from logproc.csvexport import import_csv
from logproc.parser import LogEntry
from logproc.timestamps import parse_timestamp


class EntryIndex:
    """Read-only query helper over one entries CSV."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _entries(self) -> list[LogEntry]:
        if not self.path.exists():
            return []
        return import_csv(self.path)

    def count(self, level: str | None = None) -> int:
        """Number of entries, or of entries at ``level`` when given."""
        entries = self._entries()
        if level is None:
            return len(entries)
        return sum(1 for e in entries if e.level == level)

    def levels(self) -> list[str]:
        """Sorted distinct levels present in the CSV."""
        return sorted({e.level for e in self._entries()})

    def entries_for(self, level: str) -> list[LogEntry]:
        """Entries at ``level``, in file order."""
        return [e for e in self._entries() if e.level == level]

    def between(self, start: datetime, end: datetime) -> list[LogEntry]:
        """Entries whose timestamp satisfies ``start <= t < end``, in file order."""
        return [e for e in self._entries() if start <= parse_timestamp(e.timestamp) < end]

    def refresh(self) -> None:
        """Forget the current snapshot so the next query sees rows flushed since."""
        return None
