from datetime import datetime

from toolbelt.cron import next_fire


def test_every_fifteen_minutes():
    assert next_fire("*/15 * * * *", datetime(2026, 3, 2, 10, 7)) == datetime(2026, 3, 2, 10, 15)


def test_daily():
    assert next_fire("@daily", datetime(2026, 3, 2, 10, 7)) == datetime(2026, 3, 3, 0, 0)


def test_weekday_names():
    # 2026-03-02 is a Monday
    assert next_fire("30 9 * * FRI", datetime(2026, 3, 2, 10, 7)) == datetime(2026, 3, 6, 9, 30)
