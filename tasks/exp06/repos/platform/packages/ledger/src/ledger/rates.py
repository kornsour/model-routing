"""The rate card: what one unit of a resource pool costs per second, in USD.

Rates are kept as decimal strings in ``rates.json`` and parsed to floats here.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

DEFAULT_RATES: dict[str, float] = {
    "warehouse": 0.0004,
    "api": 0.00002,
    "cpu": 0.00001,
}


def load_rates(path: str | Path | None = None) -> dict[str, float]:
    """Read a rate card. A missing file means the default card."""
    if path is None or not Path(path).exists():
        return dict(DEFAULT_RATES)
    raw = json.loads(Path(path).read_text())
    return {pool: float(rate) for pool, rate in raw.items()}


def rate_for(rates: Mapping[str, float], pool: str) -> float:
    if pool not in rates:
        raise KeyError(f"no rate for resource pool {pool!r}")
    return rates[pool]
