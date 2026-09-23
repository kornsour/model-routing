"""Tag parsing and filtering.

Tags are case-insensitive: ``Errand``, ``errand`` and ``ERRAND`` are the
same tag, and wherever a tag is reported it is shown in lowercase. A note
never carries the same tag twice.
"""

from __future__ import annotations

from collections.abc import Iterable

from notes.models import Note


def normalize_tags(tags: Iterable[str]) -> list[str]:
    """Lowercase, strip, drop empties and repeats, keeping first-seen order."""
    seen: list[str] = []
    for tag in tags:
        clean = tag.strip().lower()
        if clean and clean not in seen:
            seen.append(clean)
    return seen


def parse_tags(text: str) -> list[str]:
    """Split a comma-separated ``--tag`` argument into a clean tag list."""
    return normalize_tags(text.split(","))


def filter_tag(notes: list[Note], tag: str) -> list[Note]:
    """The notes carrying ``tag``, whatever the casing on either side."""
    wanted = tag.strip().lower()
    return [n for n in notes if wanted in normalize_tags(n.tags)]
