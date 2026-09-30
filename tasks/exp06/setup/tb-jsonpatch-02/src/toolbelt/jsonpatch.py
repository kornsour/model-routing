"""JSON Patch (RFC 6902) and JSON Pointer (RFC 6901).

Used by the config service to apply operator edits to stored documents.
Not implemented yet - see the ticket.
"""

from __future__ import annotations

from typing import Any


class PatchError(ValueError):
    """A patch could not be applied (bad operation, bad pointer, failed test)."""


def resolve(doc: Any, pointer: str) -> Any:
    raise NotImplementedError


def make_pointer(tokens: list[str | int]) -> str:
    raise NotImplementedError


def apply_patch(doc: Any, patch: list[dict[str, Any]]) -> Any:
    raise NotImplementedError


def diff(a: Any, b: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
