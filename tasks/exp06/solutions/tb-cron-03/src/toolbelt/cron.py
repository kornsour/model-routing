"""Five-field cron expressions: parsing and next-fire computation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1
)}
_DAYS = {d: i for i, d in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"])}

_MACROS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

SEARCH_YEARS = 5


@dataclass(frozen=True)
class _Field:
    lo: int
    hi: int
    names: dict[str, int] | None = None


_FIELDS = [
    _Field(0, 59),
    _Field(0, 23),
    _Field(1, 31),
    _Field(1, 12, _MONTHS),
    _Field(0, 7, _DAYS),
]


def _value(text: str, f: _Field) -> int:
    if f.names and text.upper() in f.names:
        return f.names[text.upper()]
    if not text.isdigit():
        raise ValueError(f"invalid value {text!r}")
    v = int(text)
    if not f.lo <= v <= f.hi:
        raise ValueError(f"value {v} out of range {f.lo}-{f.hi}")
    return v


def _parse_field(text: str, f: _Field) -> set[int]:
    out: set[int] = set()
    if text == "":
        raise ValueError("empty field")
    for part in text.split(","):
        step = 1
        if "/" in part:
            base, _, step_text = part.partition("/")
            if not step_text.isdigit() or int(step_text) == 0:
                raise ValueError(f"invalid step in {part!r}")
            step = int(step_text)
        else:
            base = part
            step_text = ""
        if base == "*":
            lo, hi = f.lo, f.hi
        elif "-" in base:
            a, _, b = base.partition("-")
            lo, hi = _value(a, f), _value(b, f)
            if lo > hi:
                raise ValueError(f"reversed range {base!r}")
        else:
            lo = _value(base, f)
            hi = f.hi if step_text else lo
        out.update(range(lo, hi + 1, step))
    return out


@dataclass(frozen=True)
class CronExpr:
    minutes: frozenset[int]
    hours: frozenset[int]
    days: frozenset[int]
    months: frozenset[int]
    weekdays: frozenset[int]  # 0 = Sunday .. 6 = Saturday
    dom_star: bool
    dow_star: bool

    def day_matches(self, d: date) -> bool:
        if d.month not in self.months:
            return False
        dom_ok = d.day in self.days
        dow_ok = (d.isoweekday() % 7) in self.weekdays
        if self.dom_star or self.dow_star:
            return dom_ok and dow_ok
        return dom_ok or dow_ok


def parse(expr: str) -> CronExpr:
    text = expr.strip()
    if text.startswith("@"):
        key = text.lower()
        if key not in _MACROS:
            raise ValueError(f"unsupported macro {text!r}")
        text = _MACROS[key]
    fields = text.split()
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields, got {len(fields)}")
    sets = [_parse_field(t, f) for t, f in zip(fields, _FIELDS)]
    weekdays = {0 if d == 7 else d for d in sets[4]}
    return CronExpr(
        frozenset(sets[0]),
        frozenset(sets[1]),
        frozenset(sets[2]),
        frozenset(sets[3]),
        frozenset(weekdays),
        fields[2].startswith("*"),
        fields[4].startswith("*"),
    )


def _exists(wall: datetime) -> bool:
    """True if the aware wall-clock time exists (is not in a DST gap)."""
    back = wall.astimezone(UTC).astimezone(wall.tzinfo)
    return back.replace(tzinfo=None) == wall.replace(tzinfo=None)


def next_fire(expr: str | CronExpr, after: datetime) -> datetime:
    """The first fire time strictly after ``after``."""
    cron = parse(expr) if isinstance(expr, str) else expr
    tz = after.tzinfo
    aware = tz is not None and after.utcoffset() is not None
    after_abs = after.astimezone(UTC) if aware else None
    minutes = sorted(cron.minutes)
    hours = sorted(cron.hours)
    start = after.date()
    for offset in range(SEARCH_YEARS * 366 + 2):
        day = start + timedelta(days=offset)
        if not cron.day_matches(day):
            continue
        for h in hours:
            for m in minutes:
                naive = datetime.combine(day, time(h, m))
                if not aware:
                    if naive > after:
                        return naive
                    continue
                cand = naive.replace(tzinfo=tz, fold=0)
                if not _exists(cand):
                    continue
                assert after_abs is not None
                if cand.astimezone(UTC) > after_abs:
                    return cand
    raise ValueError(f"{expr!r} never fires within {SEARCH_YEARS} years")


def iter_fires(expr: str | CronExpr, after: datetime, count: int) -> list[datetime]:
    cron = parse(expr) if isinstance(expr, str) else expr
    out: list[datetime] = []
    cur = after
    for _ in range(count):
        cur = next_fire(cron, cur)
        out.append(cur)
    return out
