"""ISO 8601 durations (``P1DT2H``) for retention policies and job timeouts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

_RE = re.compile(
    r"^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$"
)


@dataclass(frozen=True)
class Duration:
    years: int = 0
    months: int = 0
    weeks: int = 0
    days: int = 0
    hours: int = 0
    minutes: int = 0
    seconds: int = 0

    def __str__(self) -> str:
        out = "P"
        for value, unit in ((self.years, "Y"), (self.months, "M"), (self.weeks, "W"), (self.days, "D")):
            if value:
                out += f"{value}{unit}"
        time = ""
        for value, unit in ((self.hours, "H"), (self.minutes, "M"), (self.seconds, "S")):
            if value:
                time += f"{value}{unit}"
        if time:
            out += "T" + time
        return out


def parse_duration(text: str) -> Duration:
    m = _RE.match(text.strip())
    if not m or text.strip() in ("P", "PT"):
        raise ValueError(f"invalid duration: {text!r}")
    return Duration(*(int(g) if g else 0 for g in m.groups()))


def add(dt: datetime, dur: Duration) -> datetime:
    days = dur.years * 365 + dur.months * 30 + dur.weeks * 7 + dur.days
    return dt + timedelta(
        days=days, hours=dur.hours, minutes=dur.minutes, seconds=dur.seconds
    )
