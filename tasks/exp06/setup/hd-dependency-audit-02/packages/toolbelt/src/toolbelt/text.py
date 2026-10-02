"""Small text helpers."""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orchestra.model import JobSpec

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(value: str, sep: str = "-") -> str:
    """ASCII slug: accents folded, runs of anything else collapsed to ``sep``."""
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return _SLUG_STRIP.sub(sep, folded.lower()).strip(sep)


def truncate(value: str, width: int, ellipsis: str = "...") -> str:
    """Cut ``value`` to at most ``width`` characters, ending in ``ellipsis`` if cut."""
    if width < len(ellipsis):
        raise ValueError("width shorter than the ellipsis")
    if len(value) <= width:
        return value
    return value[: width - len(ellipsis)] + ellipsis


def job_label(spec: JobSpec) -> str:
    """``name (priority N)`` for log lines."""
    return f"{spec.name} (priority {spec.priority})"


def squash_ws(value: str) -> str:
    """Collapse every run of whitespace to one space and strip the ends."""
    return " ".join(value.split())
