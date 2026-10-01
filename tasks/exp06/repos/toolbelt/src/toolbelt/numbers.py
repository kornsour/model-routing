"""Numeric helpers."""

from __future__ import annotations


def clamp(value: float, lo: float, hi: float) -> float:
    if lo > hi:
        raise ValueError("lo > hi")
    return max(lo, min(hi, value))


def safe_div(num: float, den: float, default: float = 0.0) -> float:
    return default if den == 0 else num / den


def pct(part: float, whole: float, digits: int = 1) -> str:
    """``pct(1, 3) == '33.3%'``; a zero whole is reported as ``'n/a'``."""
    if whole == 0:
        return "n/a"
    return f"{part / whole * 100:.{digits}f}%"
