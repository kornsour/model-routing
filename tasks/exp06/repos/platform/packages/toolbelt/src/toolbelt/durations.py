"""ISO 8601 durations (``P1DT2H``) for retention policies and job timeouts."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

_NUM = r"(\d+(?:[.,]\d+)?)"
_RE = re.compile(
    rf"^(?P<sign>[+-])?P(?:{_NUM}Y)?(?:{_NUM}M)?(?:{_NUM}W)?(?:{_NUM}D)?"
    rf"(?P<t>T(?:{_NUM}H)?(?:{_NUM}M)?(?:{_NUM}S)?)?$"
)
_FIELDS = ("years", "months", "weeks", "days", "hours", "minutes", "seconds")
_UNITS = ("Y", "M", "W", "D", "H", "M", "S")


@dataclass(frozen=True)
class Duration:
    years: Decimal = Decimal(0)
    months: Decimal = Decimal(0)
    weeks: Decimal = Decimal(0)
    days: Decimal = Decimal(0)
    hours: Decimal = Decimal(0)
    minutes: Decimal = Decimal(0)
    seconds: Decimal = Decimal(0)
    negative: bool = False

    def __post_init__(self) -> None:
        for name in _FIELDS:
            value = Decimal(str(getattr(self, name)))
            if value < 0:
                raise ValueError("components must be non-negative; use negative=True")
            object.__setattr__(self, name, value)
        if self.is_zero():
            object.__setattr__(self, "negative", False)

    def is_zero(self) -> bool:
        return all(getattr(self, n) == 0 for n in _FIELDS)

    def __neg__(self) -> Duration:
        return Duration(**{n: getattr(self, n) for n in _FIELDS}, negative=not self.negative)

    def __str__(self) -> str:
        if self.is_zero():
            return "PT0S"
        out = "-P" if self.negative else "P"
        for name, unit in zip(_FIELDS[:4], _UNITS[:4]):
            v = getattr(self, name)
            if v:
                out += _fmt(v) + unit
        time = ""
        for name, unit in zip(_FIELDS[4:], _UNITS[4:]):
            v = getattr(self, name)
            if v:
                time += _fmt(v) + unit
        if time:
            out += "T" + time
        return out

    def total_seconds(self) -> Decimal:
        if self.years or self.months:
            raise ValueError("a duration with years or months has no fixed length")
        total = (
            self.weeks * 604800
            + self.days * 86400
            + self.hours * 3600
            + self.minutes * 60
            + self.seconds
        )
        return -total if self.negative else total


def _fmt(v: Decimal) -> str:
    if v == v.to_integral_value():
        return str(int(v))
    s = format(v.normalize(), "f")
    return s


def parse_duration(text: str) -> Duration:
    if not isinstance(text, str):
        raise ValueError(f"invalid duration: {text!r}")
    m = _RE.match(text)
    if not m:
        raise ValueError(f"invalid duration: {text!r}")
    raw = [m.group(i) for i in (2, 3, 4, 5, 7, 8, 9)]
    if all(r is None for r in raw):
        raise ValueError(f"duration has no components: {text!r}")
    if m.group("t") is not None and all(r is None for r in raw[4:]):
        raise ValueError(f"'T' must be followed by a time component: {text!r}")
    given = [i for i, r in enumerate(raw) if r is not None]
    for i in given[:-1]:
        if "." in raw[i] or "," in raw[i]:  # type: ignore[operator]
            raise ValueError(f"only the smallest component may have a fraction: {text!r}")
    if raw[2] is not None and len(given) > 1:
        raise ValueError(f"weeks cannot be combined with other components: {text!r}")
    values = {
        name: Decimal(r.replace(",", ".")) if r is not None else Decimal(0)
        for name, r in zip(_FIELDS, raw)
    }
    return Duration(**values, negative=m.group("sign") == "-")


def _add_months(dt: datetime, months: int) -> datetime:
    total = dt.year * 12 + (dt.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    if not 1 <= year <= 9999:
        raise OverflowError("date out of range")
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _td(seconds: Decimal) -> timedelta:
    return timedelta(microseconds=int((seconds * 1_000_000).to_integral_value()))


def add(dt: datetime, dur: Duration) -> datetime:
    """Calendar components on the wall clock, then exact elapsed time."""
    if dur.years != int(dur.years) or dur.months != int(dur.months):
        raise ValueError("cannot add fractional years or months")
    sign = -1 if dur.negative else 1
    months = sign * int(dur.years * 12 + dur.months)
    out = _add_months(dt, months) if months else dt
    whole_days = dur.weeks * 7 + dur.days
    int_days = int(whole_days)
    frac_days = whole_days - int_days
    if int_days:
        out = out + timedelta(days=sign * int_days)
    exact = frac_days * 86400 + dur.hours * 3600 + dur.minutes * 60 + dur.seconds
    aware = out.tzinfo is not None and out.utcoffset() is not None
    if aware:
        tz = out.tzinfo
        # Normalise the wall-clock result (resolves times inside a DST gap).
        out = out.astimezone(UTC).astimezone(tz)
        if exact:
            out = (out.astimezone(UTC) + sign * _td(exact)).astimezone(tz)
        return out
    if exact:
        out = out + sign * _td(exact)
    return out
