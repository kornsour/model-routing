from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from toolbelt.durations import Duration, add, parse_duration

NY = ZoneInfo("America/New_York")


@pytest.mark.parametrize(
    "text,fields",
    [
        ("P1Y", {"years": 1}),
        ("P1Y2M3DT4H5M6S", {"years": 1, "months": 2, "days": 3, "hours": 4, "minutes": 5, "seconds": 6}),
        ("P2W", {"weeks": 2}),
        ("PT0.5S", {"seconds": Decimal("0.5")}),
        ("PT1,25H", {"hours": Decimal("1.25")}),
        ("P1DT2.5H", {"days": 1, "hours": Decimal("2.5")}),
        ("P0D", {}),
        ("PT36H", {"hours": 36}),
        ("P1M", {"months": 1}),
        ("PT1M", {"minutes": 1}),
        ("P1.5Y", {"years": Decimal("1.5")}),
        ("P0.5W", {"weeks": Decimal("0.5")}),
        ("+P3D", {"days": 3}),
    ],
)
def test_parse_fields(text, fields):
    d = parse_duration(text)
    for name in ("years", "months", "weeks", "days", "hours", "minutes", "seconds"):
        assert getattr(d, name) == Decimal(str(fields.get(name, 0))), name
    assert d.negative is False


def test_negative():
    d = parse_duration("-P1DT1H")
    assert d.negative and d.days == 1 and d.hours == 1
    assert str(d) == "-P1DT1H"
    assert str(-d) == "P1DT1H"
    assert parse_duration("-PT0S").negative is False


@pytest.mark.parametrize(
    "text",
    [
        "P",
        "PT",
        "P1DT",
        "1D",
        "P1H",
        "PT1D",
        "P1D2Y",
        "P1Y1Y",
        "P1.5YT2H",
        "PT1.5H30M",
        "P1W2D",
        "P1WT1H",
        "p1d",
        "P1d",
        " P1D",
        "P1D ",
        "P-1D",
        "P1.D",
        "P.5D",
        "--P1D",
        "PT1H1S1M",
        "",
        "P1,5,5D",
    ],
)
def test_parse_invalid(text):
    with pytest.raises(ValueError):
        parse_duration(text)


@pytest.mark.parametrize(
    "text,canon",
    [
        ("P0D", "PT0S"),
        ("PT0H0M0S", "PT0S"),
        ("P1Y0M", "P1Y"),
        ("PT1,50S", "PT1.5S"),
        ("PT0.250S", "PT0.25S"),
        ("P2W", "P2W"),
        ("P1DT0H", "P1D"),
        ("PT36H", "PT36H"),
        ("P0Y0DT0.000001S", "PT0.000001S"),
        ("PT10.0S", "PT10S"),
    ],
)
def test_canonical_str(text, canon):
    assert str(parse_duration(text)) == canon


def test_structural_equality():
    assert parse_duration("P1D") != parse_duration("PT24H")
    assert parse_duration("PT1.50S") == parse_duration("PT1.5S")
    assert Duration(days=1) == parse_duration("P1D")
    assert hash(Duration(days=1)) == hash(parse_duration("P1D"))


def test_total_seconds():
    assert parse_duration("P1W").total_seconds() == 604800
    assert parse_duration("P1DT1.5S").total_seconds() == Decimal("86401.5")
    assert parse_duration("-PT1M").total_seconds() == -60
    with pytest.raises(ValueError):
        parse_duration("P1M").total_seconds()


@pytest.mark.parametrize(
    "start,text,expected",
    [
        (datetime(2026, 1, 31), "P1M", datetime(2026, 2, 28)),
        (datetime(2028, 1, 31), "P1M", datetime(2028, 2, 29)),
        (datetime(2026, 3, 31), "-P1M", datetime(2026, 2, 28)),
        (datetime(2028, 2, 29), "P1Y", datetime(2029, 2, 28)),
        (datetime(2026, 1, 31), "P1M1D", datetime(2026, 3, 1)),
        (datetime(2026, 1, 31), "P2M", datetime(2026, 3, 31)),
        (datetime(2026, 11, 15), "P3M", datetime(2027, 2, 15)),
        (datetime(2026, 2, 15), "-P14M", datetime(2024, 12, 15)),
        (datetime(2026, 3, 1, 12), "PT36H", datetime(2026, 3, 3, 0)),
        (datetime(2026, 3, 1), "P1.5D", datetime(2026, 3, 2, 12)),
        (datetime(2026, 3, 1), "P0.5W", datetime(2026, 3, 4, 12)),
        (datetime(2026, 3, 1), "PT0.000001S", datetime(2026, 3, 1, 0, 0, 0, 1)),
        (datetime(2026, 3, 31, 10), "-P1M1DT1H", datetime(2026, 2, 27, 9)),
        (datetime(2026, 5, 31), "P1Y3M", datetime(2027, 8, 31)),
    ],
)
def test_add_naive(start, text, expected):
    assert add(start, parse_duration(text)) == expected


def test_add_rejects_fractional_calendar():
    with pytest.raises(ValueError):
        add(datetime(2026, 1, 1), parse_duration("P1.5Y"))
    with pytest.raises(ValueError):
        add(datetime(2026, 1, 1), parse_duration("P0.5M"))


def test_add_across_dst_calendar_vs_exact():
    start = datetime(2026, 3, 7, 12, 0, tzinfo=NY)  # EST, day before spring forward
    day = add(start, parse_duration("P1D"))
    exact = add(start, parse_duration("PT24H"))
    assert day.replace(tzinfo=None) == datetime(2026, 3, 8, 12, 0)
    assert exact.replace(tzinfo=None) == datetime(2026, 3, 8, 13, 0)
    assert day.tzinfo is NY and exact.tzinfo is NY
    assert exact.astimezone(timezone.utc) - start.astimezone(timezone.utc) == timedelta(hours=24)
    back = add(datetime(2026, 11, 1, 0, 30, tzinfo=NY), parse_duration("PT2H"))
    assert back.replace(tzinfo=None) == datetime(2026, 11, 1, 1, 30)
    assert back.utcoffset() == timedelta(hours=-5)


def test_add_lands_in_gap():
    start = datetime(2026, 3, 7, 2, 30, tzinfo=NY)
    got = add(start, parse_duration("P1D"))
    assert got.replace(tzinfo=None) == datetime(2026, 3, 8, 3, 30)
    assert got.utcoffset() == timedelta(hours=-4)


def test_add_fixed_offset_and_negative_exact():
    tz = timezone(timedelta(hours=2))
    assert add(datetime(2026, 1, 1, 1, tzinfo=tz), parse_duration("-PT2H")) == datetime(
        2025, 12, 31, 23, tzinfo=tz
    )
    assert add(datetime(2026, 3, 8, 12, tzinfo=NY), parse_duration("-PT24H")).replace(
        tzinfo=None
    ) == datetime(2026, 3, 7, 11, 0)
