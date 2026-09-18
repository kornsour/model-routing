"""Deterministic stand-in provider for tests and ``--dry-run`` cost estimates.

Token counts are estimated at ~4 characters per token plus a configurable
per-call harness floor, so a dry run's cost estimate is in the right ballpark
without spending anything.  Answers come from an optional ``answers`` map
(task prompt -> output); otherwise the output is a placeholder that fails
graders, which is the honest default for a cost-only estimate.
"""

from __future__ import annotations

import hashlib
from typing import Any

from model_routing.providers.base import ProviderResult
from model_routing.types import Usage


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class FakeProvider:
    name = "fake"

    def __init__(
        self,
        floor_tokens: int = 600,
        output_tokens: int = 150,
        answers: dict[str, str] | None = None,
        cache_after_first: bool = True,
    ):
        self.floor_tokens = floor_tokens
        self.output_tokens = output_tokens
        self.answers = answers or {}
        self.cache_after_first = cache_after_first
        self._seen_prefixes: set[str] = set()
        self.calls: list[dict[str, Any]] = []

    def call(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None = None,
        effort: str | None = None,
        schema: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ProviderResult:
        self.calls.append({"model": model, "prompt": prompt, "system": system, "effort": effort})
        sys_tokens = estimate_tokens(system or "")
        prompt_tokens = estimate_tokens(prompt)
        # Cache is model-scoped: the same system prefix on a different model is a miss.
        key = hashlib.sha1(f"{model}\x00{system or ''}".encode()).hexdigest()
        if self.cache_after_first and key in self._seen_prefixes and sys_tokens >= 1024:
            usage = Usage(
                input_tokens=self.floor_tokens + prompt_tokens,
                cache_read=sys_tokens,
                output_tokens=self.output_tokens,
            )
        else:
            self._seen_prefixes.add(key)
            usage = Usage(
                input_tokens=self.floor_tokens + prompt_tokens,
                cache_write=sys_tokens if sys_tokens >= 1024 else 0,
                output_tokens=self.output_tokens,
            )
            if sys_tokens < 1024:
                usage.input_tokens += sys_tokens
        output = self.answers.get(prompt, f"[fake:{model}] no answer configured")
        structured = None
        if schema and output.startswith("{"):
            import json

            try:
                structured = json.loads(output)
            except json.JSONDecodeError:
                structured = None
        return ProviderResult(
            output=output, usage=usage, duration_ms=1, resolved_model=model, structured=structured
        )
