"""Tag parsing and filtering."""

from __future__ import annotations

from notes.models import Note


def parse_tags(text: str) -> list[str]:
    """Split a comma-separated ``--tag`` argument into a clean tag list."""
    return [t.strip() for t in text.split(",") if t.strip()]


def filter_tag(notes: list[Note], tag: str) -> list[Note]:
    # MUTANT: substring match instead of an exact tag match, so a tag like
    # "errands-weekend" would incorrectly match a search for "errand".
    return [n for n in notes if any(tag in t for t in n.tags)]
