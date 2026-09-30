---
title: Implement exact money helpers for the billing exporter
terse: Implement toolbelt.money (allocate, split, to_minor, convert, format_money).
repo: toolbelt
allowed: ["src/toolbelt/money.py", "tests/*.py"]
category: feature
tags: [spec-compliance, numerics, stub]
---
The billing exporter currently splits invoices with float arithmetic and occasionally loses or invents a cent, which finance catches at month end. We're replacing it with exact helpers in `src/toolbelt/money.py` (currently stubs). All amounts are integers in *minor units* (cents, yen, fils) unless stated otherwise. Floats must never be used for money: passing a float amount, ratio or rate raises `TypeError`.

**Currencies.** Minor-unit exponents: JPY 0, KRW 0, USD 2, EUR 2, GBP 2, KWD 3, BHD 3, CLF 4. Any other code is a `ValueError`.

**`allocate(amount, ratios) -> list[int]`.** Splits an integer `amount` across `ratios` (ints, `Fraction`s or `Decimal`s, non-negative, at least one non-zero, at least one given; otherwise `ValueError`) with the largest-remainder method, so the shares always sum to `amount` exactly, even for amounts far beyond float precision. For a non-negative amount: each share is first the floor of its exact proportional value; the units left over are then handed out one each to the shares with the largest fractional remainders, ties going to the earlier share. A zero ratio always gets 0. A negative amount is allocated as the negation of allocating its absolute value (so `allocate(-100, [1, 1, 1]) == [-34, -33, -33]`). A non-int amount (including `bool`) is a `TypeError`.

**`split(amount, n)`** is `allocate(amount, [1] * n)`; `n` must be a positive `int`, otherwise `ValueError`.

**`to_minor(amount, currency, rounding="half_even") -> int`.** Converts a major-unit amount (`str`, `int` or `Decimal`; strings may have surrounding whitespace and exponent notation; anything unparseable, NaN or infinite is a `ValueError`) to minor units, rounding to a whole minor unit with one of: `half_even` (banker's), `half_up` (ties away from zero), `down` (toward zero), `up` (away from zero), `ceiling`, `floor`. Unknown modes are a `ValueError`. It must be exact for amounts with dozens of digits.

**`convert(minor, from_currency, to_currency, rate, rounding="half_even") -> int`.** Converts minor units of one currency into minor units of another at `rate` (target major units per source major unit; `str`, `int` or `Decimal`; must be > 0), with the conversion done exactly and rounded once at the end with `rounding`.

**`format_money(minor, currency, locale="en") -> str`.** Always shows exactly the currency's number of decimals.
- `en`: symbol first for USD `$`, EUR `€`, GBP `£`, JPY `¥`; for other currencies, the code and a space (`KWD 1.234`). Thousands separator `,`, decimal point `.`. Negative amounts have a leading `-` before the symbol or code: `-$1,234.56`.
- `de`: number first, thousands separator `.`, decimal comma `,`, then a no-break space (U+00A0) and the symbol, or the code if there is no symbol: `1.234,56 €`, `1,234 KWD`. Negative amounts have a leading `-`: `-1.234,56 €`.
- Other locales are a `ValueError`; a non-int `minor` is a `TypeError`.

Add tests; keep `python -m pytest -q` green; only change `src/toolbelt/money.py` and the tests.
