"""The rate card: what one unit of a resource pool costs per second, in USD.

Rates are exact ``Decimal``s. In ``rates.json`` a rate may be a JSON string
(``"0.0004"``) or a JSON number; numbers are parsed straight to ``Decimal``,
never through ``float``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path

DEFAULT_RATES: dict[str, Decimal] = {
    "warehouse": Decimal("0.0004"),
    "api": Decimal("0.00002"),
    "cpu": Decimal("0.00001"),
}


def _rate(pool: str, raw: object) -> Decimal:
    if isinstance(raw, bool) or not isinstance(raw, (str, int, Decimal)):
        raise ValueError(f"rate for {pool!r} must be a number, got {raw!r}")
    try:
        rate = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"rate for {pool!r} is not a number: {raw!r}") from exc
    if not rate.is_finite() or rate < 0:
        raise ValueError(f"rate for {pool!r} must be a finite, non-negative number: {raw!r}")
    return rate


def load_rates(path: str | Path | None = None) -> dict[str, Decimal]:
    """Read a rate card. A missing file means the default card."""
    if path is None or not Path(path).exists():
        return dict(DEFAULT_RATES)
    raw = json.loads(Path(path).read_text(), parse_float=Decimal)
    return {pool: _rate(pool, value) for pool, value in raw.items()}


def rate_for(rates: Mapping[str, Decimal], pool: str) -> Decimal:
    if pool not in rates:
        raise KeyError(f"no rate for resource pool {pool!r}")
    return rates[pool]
