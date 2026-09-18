"""Claude Code headless (``claude -p``) on the operator's own login.

Why the CLI and not the SDK: it uses the already-paid subscription (metered at
API rates against the plan allowance), reports list-price cost and cache
read/write tokens in its JSON result, and is the same surface non-developers
get through Claude Cowork.  Subscription auth is only legitimate for local,
personal use - never ship this path (see career-manager ADR-0021).

The CLI writes its prompt cache with the 1-hour TTL (billed at 2x input, not
1.25x); ``usage.cache_creation`` splits the write by TTL and is recorded so
list-price cost matches the CLI's reported cost to the cent.

Every flag below exists to make the call *minimal and reproducible*: no tools,
no MCP servers, no settings files, no CLAUDE.md discovery, our own system
prompt.  With these, a trivial call costs ~600 input tokens (measured
2026-09-18) instead of the ~26k floor the Agent SDK adapter showed with the
full harness loaded.  ``--bare`` is deliberately NOT used: it disables
keychain/OAuth reads, so it only works with an API key.
"""

from __future__ import annotations

import json
import subprocess
import time
from typing import Any

from model_routing.providers.base import ProviderResult
from model_routing.types import Usage

DEFAULT_SYSTEM = "You are a careful assistant. Answer the request directly and concisely."


class ClaudeCliProvider:
    name = "claude_cli"

    def __init__(self, binary: str = "claude", timeout_s: int = 600, max_budget_usd: float = 1.0):
        self.binary = binary
        self.timeout_s = timeout_s
        self.max_budget_usd = max_budget_usd

    def build_args(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None,
        effort: str | None,
        schema: dict[str, Any] | None,
        extra: dict[str, Any] | None,
    ) -> list[str]:
        extra = extra or {}
        args = [
            self.binary,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--model",
            model,
            "--max-turns",
            str(extra.get("max_turns", 1)),
            "--tools",
            "",
            "--no-session-persistence",
            "--setting-sources",
            "",
            "--strict-mcp-config",
            "--system-prompt",
            system or DEFAULT_SYSTEM,
            "--max-budget-usd",
            str(extra.get("max_budget_usd", self.max_budget_usd)),
        ]
        if effort:
            args += ["--effort", effort]
        if schema:
            args += ["--json-schema", json.dumps(schema, separators=(",", ":"))]
        if extra.get("fallback_model"):
            args += ["--fallback-model", str(extra["fallback_model"])]
        return args

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
        args = self.build_args(
            model, prompt, system=system, effort=effort, schema=schema, extra=extra
        )
        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                args, capture_output=True, text=True, timeout=self.timeout_s, check=False
            )
        except subprocess.TimeoutExpired:
            return ProviderResult("", Usage(), int((time.monotonic() - t0) * 1000), error="timeout")
        wall_ms = int((time.monotonic() - t0) * 1000)
        try:
            data = json.loads(proc.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            err = (proc.stderr or proc.stdout or "no output").strip()[-500:]
            return ProviderResult("", Usage(), wall_ms, error=f"unparseable output: {err}")
        return parse_result(data, wall_ms)


def parse_result(data: dict[str, Any], wall_ms: int) -> ProviderResult:
    """Map the ``--output-format json`` result object to a ProviderResult."""
    u = data.get("usage") or {}
    usage = Usage(
        input_tokens=int(u.get("input_tokens", 0)),
        cache_read=int(u.get("cache_read_input_tokens", 0)),
        cache_write=int(u.get("cache_creation_input_tokens", 0)),
        output_tokens=int(u.get("output_tokens", 0)),
        reasoning=int((u.get("output_tokens_details") or {}).get("thinking_tokens", 0)),
        cache_write_1h=int((u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens", 0)),
    )
    model_usage = data.get("modelUsage") or {}
    resolved = None
    if model_usage:
        # One model per call in this harness; if the CLI ever fell back, the
        # last key is the one that answered.
        key = list(model_usage)[-1]
        resolved = model_usage[key].get("canonicalModel") or key
    error = None
    if data.get("is_error"):
        error = str(data.get("result", "error"))[:500]
    structured = data.get("structured_output")
    if structured is not None and not isinstance(structured, dict):
        structured = {"value": structured}
    return ProviderResult(
        output=str(data.get("result", "")),
        usage=usage,
        duration_ms=int(data.get("duration_ms", wall_ms)),
        resolved_model=resolved,
        cost_usd_reported=float(data["total_cost_usd"]) if "total_cost_usd" in data else None,
        structured=structured,
        error=error,
        raw={
            k: data.get(k)
            for k in (
                "stop_reason",
                "num_turns",
                "duration_api_ms",
                "ttft_ms",
                "session_id",
                "terminal_reason",
                "modelUsage",
            )
        },
    )
