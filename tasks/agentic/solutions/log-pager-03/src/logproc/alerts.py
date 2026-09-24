"""Page on-call about errors in a log - once per problem, not once per line.

``page_errors(entries, sender, window_seconds=600)`` walks ``entries`` in the
order given and calls ``sender(page)`` for each page on-call must receive.
This is the contract agreed with on-call:

* Only ``ERROR`` and ``CRITICAL`` entries page; every other level is ignored.
* Entries with the same *signature* are the same problem. The signature is
  the level plus the message with every run of consecutive digits replaced by
  a single ``#`` - so ``timeout after 3012 ms on shard 7`` and
  ``timeout after 45 ms on shard 12`` are one problem.
* A problem pages at most once per window. The entry that pages opens a
  window of ``window_seconds``, measured on the entries' own timestamps (the
  pager also runs over old logs in backfill, where the wall clock means
  nothing). Entries with that signature inside the window are suppressed.
  The first one at or after the window's end pages again and opens the next
  window.
* A page is a dict ``{"timestamp", "level", "message", "suppressed",
  "digest"}`` describing the entry that paged. ``suppressed`` is how many
  entries of that signature were suppressed since the signature's previous
  page (0 on its first page); ``digest`` is ``False``.
* After the last entry, every signature with suppressed entries that no page
  has reported yet gets one final page, in the order the signatures first
  paged, with ``digest`` set to ``True``, that count in ``suppressed``, and
  the timestamp, level and message of the last suppressed entry.

Returns the number of pages sent. Nothing else ever calls ``sender``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta

from logproc.parser import LogEntry
from logproc.timestamps import parse_timestamp

PAGE_LEVELS = {"ERROR", "CRITICAL"}

Sender = Callable[[dict], None]


def signature(entry: LogEntry) -> str:
    return f"{entry.level} {re.sub(r'[0-9]+', '#', entry.message)}"


def _page(entry: LogEntry, suppressed: int, digest: bool = False) -> dict:
    return {
        "timestamp": entry.timestamp,
        "level": entry.level,
        "message": entry.message,
        "suppressed": suppressed,
        "digest": digest,
    }


def page_errors(entries: Iterable[LogEntry], sender: Sender, window_seconds: int = 600) -> int:
    window = timedelta(seconds=window_seconds)
    window_start: dict[str, datetime] = {}
    suppressed: dict[str, int] = {}
    last_suppressed: dict[str, LogEntry] = {}
    sent = 0
    for entry in entries:
        if entry.level not in PAGE_LEVELS:
            continue
        key = signature(entry)
        ts = parse_timestamp(entry.timestamp)
        start = window_start.get(key)
        if start is not None and ts - start < window:
            suppressed[key] = suppressed.get(key, 0) + 1
            last_suppressed[key] = entry
            continue
        sender(_page(entry, suppressed.pop(key, 0)))
        window_start[key] = ts
        sent += 1
    for key in window_start:
        count = suppressed.get(key, 0)
        if count:
            sender(_page(last_suppressed[key], count, digest=True))
            sent += 1
    return sent
