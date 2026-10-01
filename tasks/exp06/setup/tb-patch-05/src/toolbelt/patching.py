"""Apply unified diffs to text (used by the config-drift fixer).

Not implemented yet; see the ticket.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class PatchError(ValueError):
    """The patch is malformed or does not apply."""


@dataclass
class PatchResult:
    text: str
    offsets: list[int] = field(default_factory=list)


def apply_patch(text: str, patch: str, *, reverse: bool = False) -> PatchResult:
    raise NotImplementedError
