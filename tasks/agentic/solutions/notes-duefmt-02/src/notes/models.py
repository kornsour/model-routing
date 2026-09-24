"""Core data model: a single note or to-do."""

from __future__ import annotations

from dataclasses import dataclass, field

from notes.dates import normalize_due


@dataclass
class Note:
    """A note or to-do.

    ``due`` is either ``None`` or the due date as an ISO ``YYYY-MM-DD``
    string, so that due dates compare and sort correctly as plain strings.
    Whatever form a due date arrives in (typed on the command line, read
    from an older store file, or imported from CSV), it is canonicalized
    here so every consumer sees the ISO form.
    """

    id: int
    text: str
    tags: list[str] = field(default_factory=list)
    due: str | None = None
    done: bool = False

    def __post_init__(self) -> None:
        if self.due is not None:
            self.due = normalize_due(self.due)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "tags": self.tags,
            "due": self.due,
            "done": self.done,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> Note:
        return cls(
            id=raw["id"],
            text=raw["text"],
            tags=list(raw.get("tags", [])),
            due=raw.get("due"),
            done=raw.get("done", False),
        )
