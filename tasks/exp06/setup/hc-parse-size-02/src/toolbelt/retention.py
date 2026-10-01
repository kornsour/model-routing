"""Retention policy for the artifact store (``config/retention.ini``-style dict).

``load(raw)`` turns the raw config mapping into a ``Policy``. Today only
``max_age_days`` is supported.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    max_age_days: int


def load(raw: Mapping[str, str]) -> Policy:
    return Policy(max_age_days=int(raw["max_age_days"]))
