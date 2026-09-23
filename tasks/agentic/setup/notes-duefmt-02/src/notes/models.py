"""Core data model: a single note or to-do."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Note:
    """A note or to-do.

    ``due`` is either ``None`` or the due date as an ISO ``YYYY-MM-DD``
    string, so that due dates compare and sort correctly as plain strings.
    """

    id: int
    text: str
    tags: list[str] = field(default_factory=list)
    due: str | None = None
    done: bool = False

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
