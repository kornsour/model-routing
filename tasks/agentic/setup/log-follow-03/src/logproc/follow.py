"""Incremental ("follow") processing of a live, rotating log file.

The on-call box runs ``logproc follow app.log --state app.state --out entries.csv``
from cron every minute. Each run picks up where the previous one stopped: the
state file remembers how far into the log the last run got, so that across
runs every log line ends up in the entries CSV exactly once, in log order.

Two facts about the environment this runs in:

* The service appends to the log while we read it, so the last line of the
  file may be only partly written when a run starts (no trailing newline
  yet). The rest of that line arrives later.
* ``logrotate`` periodically moves ``app.log`` aside (to ``app.log.1``) and
  the service starts writing a fresh ``app.log``. Lines already processed
  from the old file must not be processed again, and the fresh file must be
  read from its first line.

The state file is JSON and is only ever read and written by this module. A
missing state file means "nothing processed yet".
"""

from __future__ import annotations

import json
from pathlib import Path

from logproc.parser import parse_line
from logproc.pipeline import EntryWriter


def load_state(state_path: str | Path) -> dict:
    path = Path(state_path)
    if not path.exists():
        return {"offset": 0}
    return json.loads(path.read_text())


def save_state(state_path: str | Path, state: dict) -> None:
    Path(state_path).write_text(json.dumps(state))


def read_new_lines(log_path: str | Path, offset: int) -> tuple[list[str], int]:
    """Return the lines appended to ``log_path`` since byte ``offset``, and the new offset."""
    with open(log_path, "rb") as fh:
        fh.seek(offset)
        data = fh.read()
    return data.decode("utf-8").splitlines(), offset + len(data)


def follow_once(log_path: str | Path, state_path: str | Path, writer: EntryWriter) -> int:
    """Process whatever was appended to ``log_path`` since the last run.

    Parsed entries go to ``writer``; returns the number of entries written.
    """
    state = load_state(state_path)
    lines, new_offset = read_new_lines(log_path, state["offset"])
    count = 0
    for line in lines:
        entry = parse_line(line)
        if entry is not None:
            writer.write(entry)
            count += 1
    save_state(state_path, {"offset": new_offset})
    return count
