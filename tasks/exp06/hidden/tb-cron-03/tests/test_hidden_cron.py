from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from toolbelt.cron import iter_fires, next_fire, parse

NY = ZoneInfo("America/New_York")
MON = datetime(2026, 3, 2, 10, 7)  # a Monday


@pytest.mark.parametrize(
    "expr,after,expected",
    [
        ("*/15 * * * *", MON, datetime(2026, 3, 2, 10, 15)),
        ("*/15 * * * *", datetime(2026, 3, 2, 10, 15), datetime(2026, 3, 2, 10, 30)),
        ("*/15 * * * *", datetime(2026, 3, 2, 10, 14, 59, 999), datetime(2026, 3, 2, 10, 15)),
        ("5-59/20 * * * *", MON, datetime(2026, 3, 2, 10, 25)),
        ("5/20 * * * *", datetime(2026, 3, 2, 10, 46), datetime(2026, 3, 2, 11, 5)),
        ("0 22 * * 1-5", MON, datetime(2026, 3, 2, 22, 0)),
        ("0 9 * * MON-FRI", datetime(2026, 3, 6, 9, 0), datetime(2026, 3, 9, 9, 0)),
        ("0 9 * * mon,wed", MON, datetime(2026, 3, 4, 9, 0)),
        ("0 0 * * 7", MON, datetime(2026, 3, 8, 0, 0)),
        ("0 0 * * SUN", MON, datetime(2026, 3, 8, 0, 0)),
        ("0 0 * * 5-7", MON, datetime(2026, 3, 6, 0, 0)),
        ("0 0 1 JAN-MAR/2 *", MON, datetime(2027, 1, 1, 0, 0)),
        ("0 12 1 jun *", MON, datetime(2026, 6, 1, 12, 0)),
        ("@annually", MON, datetime(2027, 1, 1, 0, 0)),
        ("@yearly", MON, datetime(2027, 1, 1, 0, 0)),
        ("@midnight", MON, datetime(2026, 3, 3, 0, 0)),
        ("@hourly", MON, datetime(2026, 3, 2, 11, 0)),
        ("@weekly", MON, datetime(2026, 3, 8, 0, 0)),
        ("@monthly", MON, datetime(2026, 4, 1, 0, 0)),
        ("  @Daily ", MON, datetime(2026, 3, 3, 0, 0)),
        ("0 0 29 2 *", MON, datetime(2028, 2, 29, 0, 0)),
        ("0 0 31 * *", MON, datetime(2026, 3, 31, 0, 0)),
        ("0 0 31 4,6,9,11,12 *", MON, datetime(2026, 12, 31, 0, 0)),
        ("59 23 31 12 *", datetime(2026, 12, 31, 23, 59), datetime(2027, 12, 31, 23, 59)),
        ("0,30 8-9 * * *", datetime(2026, 3, 2, 9, 30), datetime(2026, 3, 3, 8, 0)),
    ],
)
def test_naive(expr, after, expected):
    assert next_fire(expr, after) == expected


def test_dom_dow_or_when_both_restricted():
    # 13th of the month OR any Friday
    fires = iter_fires("0 0 13 * FRI", datetime(2026, 3, 1), 4)
    assert fires == [
        datetime(2026, 3, 6),
        datetime(2026, 3, 13),
        datetime(2026, 3, 20),
        datetime(2026, 3, 27),
    ]
    assert next_fire("0 0 30 2 1", MON) == datetime(2027, 2, 1)
    assert next_fire("0 0 1,15 * 3", datetime(2026, 3, 2)) == datetime(2026, 3, 4)


def test_star_prefixed_field_means_and():
    # dom=1 AND an even weekday number (Sun, Tue, Thu, Sat): 2026-08-01 is a Saturday.
    assert next_fire("0 0 1 * */2", MON) == datetime(2026, 8, 1)
    # dow restricted, dom "*/1" starts with * -> AND -> just Fridays
    assert next_fire("0 0 */1 * 5", MON) == datetime(2026, 3, 6)
    assert next_fire("0 0 */10 * 5", MON) == datetime(2026, 5, 1)


@pytest.mark.parametrize(
    "expr",
    [
        "* * * *",
        "* * * * * *",
        "60 * * * *",
        "* 24 * * *",
        "* * 0 * *",
        "* * 32 * *",
        "* * * 13 *",
        "* * * * 8",
        "*/0 * * * *",
        "5-1 * * * *",
        "* * * FOO *",
        "* * * * FUNDAY",
        "@reboot",
        "@every 5m",
        "1,,2 * * * *",
        "a * * * *",
        "-1 * * * *",
        "* * * * MON-SUN",
    ],
)
def test_invalid(expr):
    with pytest.raises(ValueError):
        parse(expr)


def test_never_fires():
    with pytest.raises(ValueError):
        next_fire("0 0 30 2 *", MON)
    with pytest.raises(ValueError):
        next_fire("0 0 31 4 *", MON)


def test_iter_fires():
    assert iter_fires("0 */6 * * *", datetime(2026, 3, 2, 23, 0), 3) == [
        datetime(2026, 3, 3, 0, 0),
        datetime(2026, 3, 3, 6, 0),
        datetime(2026, 3, 3, 12, 0),
    ]
    cron = parse("15 10 * * *")
    assert iter_fires(cron, MON, 2) == [datetime(2026, 3, 2, 10, 15), datetime(2026, 3, 3, 10, 15)]


def test_results_have_zero_seconds():
    got = next_fire("* * * * *", datetime(2026, 3, 2, 10, 7, 30, 123))
    assert got == datetime(2026, 3, 2, 10, 8)
    assert got.second == 0 and got.microsecond == 0


def test_dst_spring_forward_gap_is_skipped():
    # 2026-03-08 02:00 -> 03:00 in New York; 02:30 does not exist that day.
    after = datetime(2026, 3, 8, 0, 0, tzinfo=NY)
    got = next_fire("30 2 * * *", after)
    assert got == datetime(2026, 3, 9, 2, 30, tzinfo=NY)
    assert got.tzinfo is NY
    got2 = next_fire("*/20 * * * *", datetime(2026, 3, 8, 1, 50, tzinfo=NY))
    assert got2.replace(tzinfo=None) == datetime(2026, 3, 8, 3, 0)
    assert got2.utcoffset() == timedelta(hours=-4)


def test_dst_fall_back_fires_once():
    # 2026-11-01 01:00-02:00 happens twice in New York.
    after = datetime(2026, 11, 1, 0, 50, tzinfo=NY)
    got = next_fire("30 1 * * *", after)
    assert got.replace(tzinfo=None) == datetime(2026, 11, 1, 1, 30)
    assert got.utcoffset() == timedelta(hours=-4)
    again = next_fire("30 1 * * *", got)
    assert again.replace(tzinfo=None) == datetime(2026, 11, 2, 1, 30)


def test_dst_after_in_second_occurrence():
    after = datetime(2026, 11, 1, 1, 15, tzinfo=NY, fold=1)  # 06:15 UTC
    got = next_fire("30 1 * * *", after)
    assert got.replace(tzinfo=None) == datetime(2026, 11, 2, 1, 30)
    hourly = next_fire("0 * * * *", after)
    assert hourly.replace(tzinfo=None) == datetime(2026, 11, 1, 2, 0)
    assert hourly.utcoffset() == timedelta(hours=-5)


def test_fixed_offset_aware():
    from datetime import timezone

    tz = timezone(timedelta(hours=5, minutes=30))
    got = next_fire("0 9 * * *", datetime(2026, 3, 2, 9, 0, tzinfo=tz))
    assert got == datetime(2026, 3, 3, 9, 0, tzinfo=tz)


def test_performance_far_fire():
    # Must not step minute by minute through five years.
    import time

    t0 = time.perf_counter()
    next_fire("0 0 29 2 1", datetime(2026, 3, 2))
    with pytest.raises(ValueError):
        next_fire("59 23 31 2 *", MON)
    assert time.perf_counter() - t0 < 2.0
