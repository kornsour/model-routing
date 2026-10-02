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


_IEC = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")


def format_size(n: int) -> str:
    """Human-readable byte count for dashboards: ``format_size(1536) == '1.5 KiB'``.

    Units follow IEC: binary multiples always carry the ``i`` (KiB = 1024 bytes,
    MiB = 1024 KiB, ...). An SI suffix without the ``i`` (KB, MB, GB) means
    powers of 1000, never 1024; we never print those, but storage vendors and
    humans write them, so anything that *reads* sizes must honour the
    difference.
    """
    if n < 0:
        raise ValueError("size must be non-negative")
    value = float(n)
    for unit in _IEC:
        if value < 1024 or unit == _IEC[-1]:
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")
