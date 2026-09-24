"""Summary statistics over a list of notes (the ``notes stats`` command)."""

from __future__ import annotations

from notes.models import Note
from notes.tags import normalize_tags


def summary(notes: list[Note]) -> dict[str, int]:
    """Totals: every note, the completed ones, and the ones still open."""
    done = sum(1 for n in notes if n.done)
    return {"total": len(notes), "done": done, "open": len(notes) - done}


def tag_counts(notes: list[Note]) -> dict[str, int]:
    """How many notes carry each tag, most common first, ties by tag name."""
    counts: dict[str, int] = {}
    for note in notes:
        for tag in normalize_tags(note.tags):
            counts[tag] = counts.get(tag, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
