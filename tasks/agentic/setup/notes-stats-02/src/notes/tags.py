"""Tag parsing and filtering.

Tags are case-insensitive: ``Errand``, ``errand`` and ``ERRAND`` are the
same tag, and wherever a tag is reported it is shown in lowercase. A note
never carries the same tag twice.
"""

from __future__ import annotations

from notes.models import Note


def parse_tags(text: str) -> list[str]:
    """Split a comma-separated ``--tag`` argument into a clean tag list."""
    return [t.strip() for t in text.split(",") if t.strip()]


def filter_tag(notes: list[Note], tag: str) -> list[Note]:
    """The notes carrying ``tag``."""
    return [n for n in notes if tag in n.tags]
