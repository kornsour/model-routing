"""Cross-references between notes.

A note's text may refer to another note as ``#<id>`` ("blocked on #12").
:func:`expand_links` rewrites each reference as ``[#<id> <text of that
note>]``, or ``[#<id> ?]`` when there is no such note, and
:func:`linked_notes` returns the referenced notes themselves, in order of
first mention, skipping ids that don't exist.
"""

from __future__ import annotations

import re

from notes.models import Note
from notes.store import Store

LINK_RE = re.compile(r"#(\d+)")


def linked_ids(text: str) -> list[int]:
    """Ids referenced in ``text``, in order of first mention, without repeats."""
    seen: list[int] = []
    for match in LINK_RE.finditer(text):
        note_id = int(match.group(1))
        if note_id not in seen:
            seen.append(note_id)
    return seen


def _lookup(store: Store, note_id: int) -> Note | None:
    # The store itself keeps lookups fresh (it re-reads only when the file changed).
    return store.get(note_id)


def expand_links(store: Store, text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        note_id = int(match.group(1))
        target = _lookup(store, note_id)
        return f"[#{note_id} {target.text if target is not None else '?'}]"

    return LINK_RE.sub(replace, text)


def linked_notes(store: Store, note: Note) -> list[Note]:
    found: list[Note] = []
    for note_id in linked_ids(note.text):
        target = _lookup(store, note_id)
        if target is not None:
            found.append(target)
    return found
