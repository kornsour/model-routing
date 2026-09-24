"""Masks secrets in log messages. The README's "Redaction" section is the reference."""

from __future__ import annotations

import re

MASK = "***"

_KEY_VALUE = re.compile(r"\b(password|passwd|secret|token|api_key|apikey)=(\w+)")


def redact(message: str) -> str:
    """Return ``message`` with every secret replaced by ``***``."""
    return _KEY_VALUE.sub(lambda m: f"{m.group(1)}={MASK}", message)
