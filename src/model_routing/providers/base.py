"""Provider protocol: turn (candidate, prompt, context) into a CallRecord."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from model_routing.types import Usage


@dataclass
class ProviderResult:
    """What a provider hands back before the runner prices and records it."""

    output: str
    usage: Usage
    duration_ms: int
    resolved_model: str | None = None
    cost_usd_reported: float | None = None
    structured: dict[str, Any] | None = None
    error: str | None = None
    raw: dict[str, Any] | None = None


class Provider(Protocol):
    name: str

    def call(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None = None,
        effort: str | None = None,
        schema: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ProviderResult: ...
