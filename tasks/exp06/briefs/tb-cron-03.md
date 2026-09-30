---
title: Fix toolbelt.cron so schedules fire when cron says they should
terse: Fix toolbelt.cron's next-fire computation (day matching, steps, names, DST).
repo: toolbelt
allowed: ["src/toolbelt/cron.py", "tests/*.py"]
category: bugfix
tags: [spec-compliance, datetime, dst, performance]
---
The job runner computes every schedule with `toolbelt.cron.next_fire`, and we have a pile of tickets that all trace back to `src/toolbelt/cron.py`: a "13th of the month or any Friday" report that only runs on Friday the 13th, `@annually` and `@midnight` being rejected (they are in the docs we give teams), `0 0 * * 7` never firing, `5/20` raising, a job that fired twice in a row because `next_fire` can return the time it was given, the scheduler pinning a CPU for minutes on a schedule that only fires on 29 February, and the New York jobs misbehaving around the DST changes. Rather than patch these one at a time, please make the module implement the semantics below (these are Vixie cron's, which is what the teams writing schedules expect).

**Expressions.** Five whitespace-separated fields: minute (0-59), hour (0-23), day of month (1-31), month (1-12), day of week (0-7, where both 0 and 7 are Sunday). Leading/trailing whitespace is ignored. Each field is a comma-separated list of elements; an element is `*`, a value, or a range `a-b` (inclusive, `a <= b`, no wrap-around), optionally followed by `/n` (a step, `n >= 1`). `*/n` steps over the whole field, `a-b/n` steps from `a` to `b`, and `a/n` means `a` through the field's maximum stepping by `n`. Months accept `JAN`-`DEC` and days of week accept `SUN`-`SAT` (case-insensitive), anywhere a number is accepted, including in ranges; `SUN` is 0, so `MON-SUN` is a reversed range and invalid. Macros (case-insensitive): `@yearly` and `@annually` = `0 0 1 1 *`, `@monthly` = `0 0 1 * *`, `@weekly` = `0 0 * * 0`, `@daily` and `@midnight` = `0 0 * * *`, `@hourly` = `0 * * * *`. Anything else (other macros such as `@reboot`, a wrong field count, out-of-range values, unknown names, a step of 0, empty list elements, a reversed range) makes `parse` raise `ValueError`.

**Which days match.** A field is *unrestricted* if its text starts with `*` (so `*/2` counts as unrestricted). If either the day-of-month or the day-of-week field is unrestricted, a day must match both fields; if both are restricted, a day matches if it matches either one. The month must always match.

**Next fire.** `next_fire(expr, after)` accepts an expression string or a parsed expression and returns the first fire time *strictly after* `after`, with seconds and microseconds zero. For a naive `after`, work in naive wall-clock time. For an aware `after`, fire times are wall-clock times in `after`'s time zone, returned as aware datetimes with that same `tzinfo`: a wall-clock time that does not exist because of a DST gap is skipped (no fire for that minute that day), a wall-clock time that occurs twice fires only at its first occurrence, and "strictly after" is judged in absolute time. If the expression cannot fire within 5 years of `after` (for example `0 0 30 2 *`), raise `ValueError`. `next_fire` is on the scheduler's hot path, so it must not step minute by minute: a far-away or impossible schedule should be answered in well under a second.

Also add `iter_fires(expr, after, count)`, returning the next `count` fire times in order (each strictly after the previous one), and make `parse` return the parsed expression object so callers can reuse it.

Keep the existing tests passing (their expectations are correct) and add tests for the cases above. Only change `src/toolbelt/cron.py` and the tests.
