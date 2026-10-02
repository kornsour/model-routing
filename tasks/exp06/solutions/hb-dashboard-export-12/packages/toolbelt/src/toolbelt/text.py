"""Small text helpers."""

from __future__ import annotations

import re
import unicodedata

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


def squash_ws(value: str) -> str:
    """Collapse every run of whitespace to one space and strip the ends."""
    return " ".join(value.split())


def unique_slugs(names: list[str], sep: str = "-") -> dict[str, str]:
    """Slug every name, de-duplicating collisions with ``-2``, ``-3``, ... in
    sorted name order. An empty slug becomes ``item``. A suffixed slug never
    takes another name's plain slug."""
    ordered = sorted(set(names))
    plain = {n: slugify(n, sep) or "item" for n in ordered}
    reserved = set(plain.values())
    taken: set[str] = set()
    out: dict[str, str] = {}
    for name in ordered:
        slug = plain[name]
        if slug in taken:
            k = 2
            while f"{slug}{sep}{k}" in taken or f"{slug}{sep}{k}" in reserved:
                k += 1
            slug = f"{slug}{sep}{k}"
        taken.add(slug)
        out[name] = slug
    return out
