"""Core data model: a single note or to-do."""

from __future__ import annotations

from dataclasses import dataclass, field

REPEATS = ("daily", "weekly", "monthly", "yearly")


@dataclass
class Note:
    """A note or to-do.

    ``due`` is an ISO ``YYYY-MM-DD`` string or ``None``.

    ``repeat`` is ``None`` for a one-off note, or one of :data:`REPEATS` for a
    repeating to-do. Completing a repeating to-do that has a due date marks it
    done and adds its next occurrence to the store as a new, open to-do with the
    same text, tags and repeat, due one day / week / month / year later.
    Monthly and yearly to-dos stay on the day of the month they were first due:
    in a month too short for that day, the occurrence falls on the month's last
    day instead, and later occurrences go back to the original day.
    """

    id: int
    text: str
    tags: list[str] = field(default_factory=list)
    due: str | None = None
    done: bool = False
    repeat: str | None = None
    # Day of the month a monthly/yearly to-do was first due; ``None`` in files
    # written before it was recorded, meaning "the day of ``due``".
    repeat_day: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "tags": self.tags,
            "due": self.due,
            "done": self.done,
            "repeat": self.repeat,
            "repeat_day": self.repeat_day,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> Note:
        return cls(
            id=raw["id"],
            text=raw["text"],
            tags=list(raw.get("tags", [])),
            due=raw.get("due"),
            done=raw.get("done", False),
            repeat=raw.get("repeat"),
            repeat_day=raw.get("repeat_day"),
        )
