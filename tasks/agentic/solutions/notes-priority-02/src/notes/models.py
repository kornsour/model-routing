"""Core data model: a single note or to-do."""

from __future__ import annotations

from dataclasses import dataclass, field

PRIORITIES = ("low", "normal", "high")
DEFAULT_PRIORITY = "normal"


@dataclass
class Note:
    id: int
    text: str
    tags: list[str] = field(default_factory=list)
    due: str | None = None
    done: bool = False
    priority: str = DEFAULT_PRIORITY

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "tags": self.tags,
            "due": self.due,
            "done": self.done,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> Note:
        return cls(
            id=raw["id"],
            text=raw["text"],
            tags=list(raw.get("tags", [])),
            due=raw.get("due"),
            done=raw.get("done", False),
            priority=raw.get("priority", DEFAULT_PRIORITY),
        )
