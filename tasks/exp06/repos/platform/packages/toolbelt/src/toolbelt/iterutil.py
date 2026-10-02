"""Iteration helpers."""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Iterator
from typing import TypeVar

T = TypeVar("T")
H = TypeVar("H", bound=Hashable)


def chunked(items: Iterable[T], size: int) -> Iterator[list[T]]:
    if size < 1:
        raise ValueError("size must be >= 1")
    buf: list[T] = []
    for item in items:
        buf.append(item)
        if len(buf) == size:
            yield buf
            buf = []
    if buf:
        yield buf


def unique(items: Iterable[H]) -> list[H]:
    """Stable de-duplication."""
    seen: set[H] = set()
    out: list[H] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
