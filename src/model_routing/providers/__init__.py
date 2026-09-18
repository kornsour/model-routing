"""Provider registry."""

from __future__ import annotations

from typing import Any

from model_routing.providers.base import Provider, ProviderResult
from model_routing.providers.claude_cli import ClaudeCliProvider
from model_routing.providers.codex_cli import CodexCliProvider
from model_routing.providers.fake import FakeProvider

__all__ = [
    "ClaudeCliProvider",
    "CodexCliProvider",
    "FakeProvider",
    "Provider",
    "ProviderResult",
    "make_provider",
]


def make_provider(name: str, **kwargs: Any) -> Provider:
    if name == "claude_cli":
        return ClaudeCliProvider(**kwargs)
    if name == "codex_cli":
        return CodexCliProvider(**kwargs)
    if name == "fake":
        return FakeProvider(**kwargs)
    raise ValueError(f"unknown provider {name!r} (known: claude_cli, codex_cli, fake)")
