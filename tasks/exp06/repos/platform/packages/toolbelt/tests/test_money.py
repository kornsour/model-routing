from decimal import Decimal
from fractions import Fraction

import pytest

from toolbelt.money import allocate, convert, format_money, split, to_minor


@pytest.mark.parametrize(
    "amount,ratios,expected",
    [
        (100, [1, 1, 1], [34, 33, 33]),
        (5, [3, 7], [2, 3]),
        (1, [1, 1], [1, 0]),
        (2, [1, 1, 1], [1, 1, 0]),
        (-100, [1, 1, 1], [-34, -33, -33]),
        (-5, [3, 7], [-2, -3]),
        (0, [1, 2], [0, 0]),
        (10, [0, 1, 0], [0, 10, 0]),
        (7, [0, 1, 1], [0, 4, 3]),
        (100, [Fraction(1, 3), Fraction(2, 3)], [33, 67]),
        (1000, [Decimal("0.7"), Decimal("0.2"), Decimal("0.1")], [700, 200, 100]),
        (101, [Decimal("0.7"), Decimal("0.2"), Decimal("0.1")], [71, 20, 10]),
        (3, [1, 2, 1, 2], [1, 1, 0, 1]),
        (10, [2, 2, 3, 3], [2, 2, 3, 3]),
        (11, [1, 1, 1, 1, 1, 1], [2, 2, 2, 2, 2, 1]),
    ],
)
def test_allocate(amount, ratios, expected):
    got = allocate(amount, ratios)
    assert got == expected
    assert sum(got) == amount


def test_allocate_is_exact_for_huge_amounts():
    amount = 10**30 + 1
    got = allocate(amount, [1, 1, 1])
    assert got == [333333333333333333333333333334, 333333333333333333333333333334, 333333333333333333333333333333]
    assert sum(got) == amount
    got2 = allocate(10**25, [1, 3])
    assert got2 == [25 * 10**23, 75 * 10**23]


def test_ties_go_to_the_earlier_share():
    assert allocate(4, [1, 1, 1]) == [2, 1, 1]
    assert allocate(-4, [1, 1, 1]) == [-2, -1, -1]
    assert allocate(2, [1, 2, 1]) == [1, 1, 0]


def test_allocate_errors():
    with pytest.raises(ValueError):
        allocate(10, [])
    with pytest.raises(ValueError):
        allocate(10, [0, 0])
    with pytest.raises(ValueError):
        allocate(10, [1, -1])
    with pytest.raises(TypeError):
        allocate(10, [0.5, 0.5])
    with pytest.raises(TypeError):
        allocate(10.0, [1])
    with pytest.raises(TypeError):
        allocate(True, [1])


def test_split():
    assert split(100, 3) == [34, 33, 33]
    assert split(-7, 2) == [-4, -3]
    assert split(0, 4) == [0, 0, 0, 0]
    for bad in (0, -1, 2.0):
        with pytest.raises(ValueError):
            split(10, bad)


@pytest.mark.parametrize(
    "amount,currency,rounding,expected",
    [
        ("12.345", "USD", "half_even", 1234),
        ("12.355", "USD", "half_even", 1236),
        ("12.345", "USD", "half_up", 1235),
        ("-12.345", "USD", "half_up", -1235),
        ("12.349", "USD", "down", 1234),
        ("-12.349", "USD", "down", -1234),
        ("12.341", "USD", "up", 1235),
        ("-12.341", "USD", "up", -1235),
        ("-12.341", "USD", "ceiling", -1234),
        ("-12.341", "USD", "floor", -1235),
        ("1234.5", "JPY", "half_even", 1234),
        ("1235.5", "JPY", "half_even", 1236),
        ("1.2345", "KWD", "half_even", 1234),
        ("0.00005", "CLF", "half_up", 1),
        (" 7 ", "EUR", "half_even", 700),
        (Decimal("0.005"), "USD", "half_even", 0),
        (3, "GBP", "half_even", 300),
        ("1e3", "USD", "half_even", 100000),
    ],
)
def test_to_minor(amount, currency, rounding, expected):
    assert to_minor(amount, currency, rounding) == expected


def test_to_minor_errors():
    with pytest.raises(ValueError):
        to_minor("1.00", "XYZ")
    with pytest.raises(ValueError):
        to_minor("abc", "USD")
    with pytest.raises(ValueError):
        to_minor("NaN", "USD")
    with pytest.raises(ValueError):
        to_minor("1", "USD", rounding="banker")
    with pytest.raises(TypeError):
        to_minor(1.5, "USD")
    assert to_minor("123456789012345678901234567890.125", "USD") == 12345678901234567890123456789012


def test_convert():
    assert convert(10000, "USD", "JPY", "151.235") == 15124
    assert convert(10000, "USD", "JPY", "151.245", rounding="half_up") == 15125
    assert convert(10000, "USD", "JPY", Decimal("151.245")) == 15124
    assert convert(1234, "KWD", "USD", "3.25") == 401
    assert convert(-999, "EUR", "USD", "1.085") == -1084
    assert convert(1, "JPY", "CLF", "0.0000265") == 0
    assert convert(100, "JPY", "CLF", "0.0000265", rounding="up") == 27
    with pytest.raises(ValueError):
        convert(100, "USD", "EUR", "0")
    with pytest.raises(ValueError):
        convert(100, "USD", "EUR", "-1")
    with pytest.raises(TypeError):
        convert(100, "USD", "EUR", 1.1)


@pytest.mark.parametrize(
    "minor,currency,locale,expected",
    [
        (123456, "USD", "en", "$1,234.56"),
        (-123456, "USD", "en", "-$1,234.56"),
        (5, "USD", "en", "$0.05"),
        (0, "EUR", "en", "€0.00"),
        (123456789, "EUR", "en", "€1,234,567.89"),
        (1235, "JPY", "en", "¥1,235"),
        (-1, "JPY", "en", "-¥1"),
        (1234, "KWD", "en", "KWD 1.234"),
        (100000, "GBP", "en", "£1,000.00"),
        (12, "CLF", "en", "CLF 0.0012"),
        (123456, "EUR", "de", "1.234,56 €"),
        (-123456, "EUR", "de", "-1.234,56 €"),
        (1234, "KWD", "de", "1,234 KWD"),
        (1234567, "JPY", "de", "1.234.567 ¥"),
        (99, "USD", "de", "0,99 $"),
    ],
)
def test_format(minor, currency, locale, expected):
    assert format_money(minor, currency, locale) == expected


def test_format_errors():
    with pytest.raises(ValueError):
        format_money(1, "XYZ")
    with pytest.raises(ValueError):
        format_money(1, "USD", "fr")
    with pytest.raises(TypeError):
        format_money(1.0, "USD")
