"""Retention policy for the artifact store (``config/retention.ini``-style dict).

``load(raw)`` turns the raw config mapping into a ``Policy``: ``max_age_days``
(required) and ``max_size`` (optional; see ``toolbelt.numbers.parse_size``:
``500MB`` is 500 x 1000^2 bytes, ``2GiB`` is 2 x 1024^3).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from toolbelt.numbers import parse_size


@dataclass(frozen=True)
class Policy:
    max_age_days: int
    max_size_bytes: int | None = None


def load(raw: Mapping[str, str]) -> Policy:
    size = raw.get("max_size")
    return Policy(
        max_age_days=int(raw["max_age_days"]),
        max_size_bytes=None if size is None else parse_size(size),
    )
