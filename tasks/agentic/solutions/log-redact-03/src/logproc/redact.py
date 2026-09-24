"""Masks secrets in log messages. The README's "Redaction" section is the reference."""

from __future__ import annotations

import re

MASK = "***"

_SECRET_KEY = (
    r"(?:password|passwd|secret|token|api_key|apikey"
    r"|[A-Za-z0-9_-]*_(?:password|secret|token))"
)
_KEY_VALUE = re.compile(rf"(?<![A-Za-z0-9_-])({_SECRET_KEY}=)[^\s&;]+", re.IGNORECASE)
_AUTHORIZATION = re.compile(r"(Authorization:\s*(?:Bearer|Basic)\s+)\S+", re.IGNORECASE)


def redact(message: str) -> str:
    """Return ``message`` with every secret replaced by ``***``."""
    message = _AUTHORIZATION.sub(lambda m: m.group(1) + MASK, message)
    return _KEY_VALUE.sub(lambda m: m.group(1) + MASK, message)
