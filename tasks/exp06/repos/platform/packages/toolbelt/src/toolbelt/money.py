"""Money helpers for the billing exporter: exact allocation, currency minor
units, conversion and display."""

from __future__ import annotations

import decimal
from decimal import Decimal
from fractions import Fraction

EXPONENTS = {"JPY": 0, "KRW": 0, "USD": 2, "EUR": 2, "GBP": 2, "KWD": 3, "BHD": 3, "CLF": 4}
_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}
_ROUNDING = {
    "half_even": decimal.ROUND_HALF_EVEN,
    "half_up": decimal.ROUND_HALF_UP,
    "down": decimal.ROUND_DOWN,
    "up": decimal.ROUND_UP,
    "ceiling": decimal.ROUND_CEILING,
    "floor": decimal.ROUND_FLOOR,
}


def _exp(currency: str) -> int:
    if currency not in EXPONENTS:
        raise ValueError(f"unknown currency {currency!r}")
    return EXPONENTS[currency]


def _fraction(x: object) -> Fraction:
    if isinstance(x, bool):
        raise TypeError("ratios must be numbers")
    if isinstance(x, float):
        raise TypeError("float ratios are not allowed; use int, Fraction or Decimal")
    if isinstance(x, (int, Fraction, Decimal)):
        return Fraction(x)
    raise TypeError(f"unsupported ratio {x!r}")


def allocate(amount: int, ratios: list) -> list[int]:
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise TypeError("amount must be an int number of minor units")
    fr = [_fraction(r) for r in ratios]
    if not fr:
        raise ValueError("at least one ratio is required")
    if any(r < 0 for r in fr):
        raise ValueError("ratios must be non-negative")
    total = sum(fr)
    if total == 0:
        raise ValueError("ratios must not all be zero")
    if amount < 0:
        return [-x for x in allocate(-amount, ratios)]
    exact = [amount * r / total for r in fr]
    base = [int(e) for e in exact]  # floor, amount >= 0
    left = amount - sum(base)
    order = sorted(range(len(fr)), key=lambda i: (-(exact[i] - base[i]), i))
    for i in order[:left]:
        base[i] += 1
    return base


def split(amount: int, n: int) -> list[int]:
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("n must be a positive int")
    return allocate(amount, [1] * n)


def _rounding(mode: str) -> str:
    if mode not in _ROUNDING:
        raise ValueError(f"unknown rounding mode {mode!r}")
    return _ROUNDING[mode]


def _decimal(amount: object) -> Decimal:
    if isinstance(amount, bool) or isinstance(amount, float):
        raise TypeError("use a str, int or Decimal amount, not float")
    if isinstance(amount, (int, Decimal)):
        return Decimal(amount)
    if isinstance(amount, str):
        try:
            d = Decimal(amount.strip())
        except decimal.InvalidOperation as exc:
            raise ValueError(f"invalid amount {amount!r}") from exc
        if not d.is_finite():
            raise ValueError(f"invalid amount {amount!r}")
        return d
    raise TypeError(f"unsupported amount {amount!r}")


def to_minor(amount: object, currency: str, rounding: str = "half_even") -> int:
    exp = _exp(currency)
    d = _decimal(amount)
    with decimal.localcontext() as ctx:
        ctx.prec = 100
        scaled = d.scaleb(exp)
        return int(scaled.quantize(Decimal(1), rounding=_rounding(rounding)))


def convert(
    minor: int, from_currency: str, to_currency: str, rate: object, rounding: str = "half_even"
) -> int:
    if isinstance(minor, bool) or not isinstance(minor, int):
        raise TypeError("minor must be an int")
    r = _decimal(rate)
    if r <= 0:
        raise ValueError("rate must be positive")
    with decimal.localcontext() as ctx:
        ctx.prec = 100
        major = Decimal(minor).scaleb(-_exp(from_currency)) * r
        return to_minor(major, to_currency, rounding)


def _group(digits: str, sep: str) -> str:
    out = []
    while len(digits) > 3:
        out.append(digits[-3:])
        digits = digits[:-3]
    out.append(digits)
    return sep.join(reversed(out))


def format_money(minor: int, currency: str, locale: str = "en") -> str:
    if isinstance(minor, bool) or not isinstance(minor, int):
        raise TypeError("minor must be an int")
    exp = _exp(currency)
    if locale not in ("en", "de"):
        raise ValueError(f"unsupported locale {locale!r}")
    neg = minor < 0
    digits = str(abs(minor)).rjust(exp + 1, "0")
    whole, frac = (digits[:-exp], digits[-exp:]) if exp else (digits, "")
    if locale == "en":
        number = _group(whole, ",") + ("." + frac if exp else "")
        sym = _SYMBOLS.get(currency)
        body = f"{sym}{number}" if sym else f"{currency} {number}"
    else:
        number = _group(whole, ".") + ("," + frac if exp else "")
        sym = _SYMBOLS.get(currency, currency)
        body = f"{number} {sym}"
    return "-" + body if neg else body
