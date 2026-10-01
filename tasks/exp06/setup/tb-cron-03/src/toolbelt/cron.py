"""Five-field cron expressions for the job runner.

Supports the classic ``minute hour day-of-month month day-of-week`` form.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_DAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]

_MACROS = {
    "@yearly": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@hourly": "0 * * * *",
}

_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]


def _field(text: str, lo: int, hi: int, names: list[str] | None) -> set[int]:
    out: set[int] = set()
    for part in text.split(","):
        step = 1
        if "/" in part:
            part, step_s = part.split("/")
            step = int(step_s)
        if part == "*":
            start, end = lo, hi
        elif "-" in part:
            a, b = part.split("-")
            start, end = int(a), int(b)
        elif names and part.upper() in names:
            start = end = names.index(part.upper()) + (1 if names is _MONTHS else 0)
        else:
            start = end = int(part)
        for v in range(lo, end + 1, step):
            if v >= start:
                out.add(v)
    return out


@dataclass
class CronExpr:
    minutes: set[int]
    hours: set[int]
    days: set[int]
    months: set[int]
    weekdays: set[int]

    def matches(self, dt: datetime) -> bool:
        return (
            dt.minute in self.minutes
            and dt.hour in self.hours
            and dt.day in self.days
            and dt.month in self.months
            and (dt.isoweekday() % 7) in self.weekdays
        )


def parse(expr: str) -> CronExpr:
    expr = _MACROS.get(expr.strip(), expr)
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields, got {len(fields)}")
    names = [None, None, None, _MONTHS, _DAYS]
    sets = [_field(t, lo, hi, n) for t, (lo, hi), n in zip(fields, _RANGES, names)]
    return CronExpr(*sets)


def next_fire(expr: str | CronExpr, after: datetime) -> datetime:
    """Next time the expression fires at or after ``after``."""
    cron = parse(expr) if isinstance(expr, str) else expr
    dt = after.replace(second=0, microsecond=0)
    for _ in range(366 * 24 * 60):
        if cron.matches(dt):
            return dt
        dt += timedelta(minutes=1)
    raise ValueError("no fire time within a year")
