"""Path glob matching for the artifact uploader's include/exclude lists.

``fnmatch`` is not good enough here (its ``*`` crosses ``/`` and it has no
``**`` or braces); see the ticket for the rules we need.
"""

from __future__ import annotations

from collections.abc import Iterable


def match(pattern: str, path: str, *, dot: bool = False, ignore_case: bool = False) -> bool:
    raise NotImplementedError


def select(paths: Iterable[str], patterns: list[str], *, dot: bool = False) -> list[str]:
    raise NotImplementedError
