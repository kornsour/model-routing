---
title: Make toolbelt.durations handle real ISO 8601 durations and calendar math
terse: Fix toolbelt.durations parsing, formatting and date arithmetic for ISO 8601 durations.
repo: toolbelt
allowed: ["src/toolbelt/durations.py", "tests/*.py"]
category: bugfix
tags: [spec-compliance, datetime, dst]
---
Retention policies and job timeouts are configured as ISO 8601 durations and go through `src/toolbelt/durations.py`. It was written quickly and it is now wrong in ways that matter: `P1M` added to 31 January lands on 2 March (it adds 30 days), `P1Y` is 365 days, `PT0.5S` and negative durations are rejected, `P1D` and `PT24H` give the same answer across a DST change (they must not: one is a calendar day, the other exactly 24 hours), and `str()` output doesn't round-trip for several inputs. Please rework the module to the rules below. Keep the names `Duration`, `parse_duration` and `add`; the visible tests show how callers use them.

**Grammar.** `[+|-]P[nY][nM][nW][nD][T[nH][nM][nS]]`, case-sensitive, no surrounding whitespace. Components appear in that order, each at most once, and at least one must be present. If `T` is present, at least one of H/M/S must follow it. A number is one or more digits, optionally with a fractional part introduced by `.` or `,` (at least one digit on each side); only the smallest component that is present may have a fraction. Weeks cannot be combined with any other component. Anything else raises `ValueError`.

**Value.** `Duration` is a frozen dataclass with `years, months, weeks, days, hours, minutes, seconds` as `Decimal` (non-negative; constructing it with ints or strings must also work, e.g. `Duration(days=1)`) and a `negative: bool` flag for the sign. A zero duration is never negative. Equality is structural and hashable: `P1D != PT24H`, but `PT1.50S == PT1.5S`. Unary minus flips the sign. `total_seconds()` returns a `Decimal` (weeks = 604800 s, days = 86400 s, negative when the duration is) and raises `ValueError` if years or months are non-zero, since those have no fixed length.

**Canonical form.** `str()` omits zero components, writes the `T` only when a time component is non-zero, writes numbers without trailing zeros or exponent (`1.5`, `0.000001`, `10`), uses `.` as the separator, prefixes `-` for negative durations and never `+`, and writes a zero duration as `PT0S`.

**Arithmetic.** `add(dt, duration)` works for naive and aware datetimes and applies the sign to every component. In order:
1. Years and months move the calendar (years count as 12 months). If the day doesn't exist in the target month, clamp to its last day (31 January + `P1M` = 28 or 29 February). Fractional years or months raise `ValueError`.
2. The whole part of weeks and days moves the calendar date, keeping the wall-clock time.
3. Everything else (the fractional part of weeks/days at 86400 s per day, plus hours, minutes and seconds) is added as exact elapsed time, to microsecond precision.
For an aware datetime, steps 1 and 2 are wall-clock operations in its time zone; if the wall-clock time they produce falls in a DST gap, move it forward by the gap's length (02:30 on a spring-forward day becomes 03:30). Step 3 is absolute time, so `PT24H` across a spring-forward is 13:00 the next day while `P1D` is 12:00. The result has the same `tzinfo` as the input.

Keep the visible tests green and add your own. Only change `src/toolbelt/durations.py` and the tests.
