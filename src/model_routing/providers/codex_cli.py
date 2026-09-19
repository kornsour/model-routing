"""OpenAI Codex headless (``codex exec --json``) on the operator's ChatGPT login.

Codex has no system-prompt flag, so shared context is prepended to the prompt
inside a delimited block.  ``--ignore-user-config`` keeps the run independent
of ``~/.codex/config.toml`` (which on this machine points Codex at a local
Ollama proxy); auth still comes from ``CODEX_HOME``.

Measured 2026-09-18: a trivial call carries ~18-19k input tokens of harness
scaffolding (skills, instructions), of which ~10.6k came back as
``cached_input_tokens`` on the second call.  That floor is part of what the
experiments measure, so it is recorded, not hidden.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from model_routing.providers.base import ProviderResult
from model_routing.types import Usage


class CodexCliProvider:
    name = "codex_cli"

    def __init__(
        self, binary: str = "codex", timeout_s: int = 600, env: dict[str, str] | None = None
    ):
        self.env = env
        self.binary = binary
        self.timeout_s = timeout_s

    def build_args(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None,
        effort: str | None,
        schema_path: Path | None,
        extra: dict[str, Any] | None,
    ) -> list[str]:
        extra = extra or {}
        full_prompt = prompt if not system else f"<context>\n{system}\n</context>\n\n{prompt}"
        args = [
            self.binary,
            "exec",
            "--json",
            "--ephemeral",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "-s",
            "read-only",
            "-m",
            model,
        ]
        if effort:
            args += ["-c", f'model_reasoning_effort="{effort}"']
        for k, v in extra.get("config", {}).items():
            args += ["-c", f"{k}={v}"]
        if schema_path:
            args += ["--output-schema", str(schema_path)]
        args.append(full_prompt)
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
        schema_path = None
        tmp = None
        if schema:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
                json.dump(schema, tmp)
            schema_path = Path(tmp.name)
        args = self.build_args(
            model, prompt, system=system, effort=effort, schema_path=schema_path, extra=extra
        )
        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
                stdin=subprocess.DEVNULL,
                env=self.env,
            )
        except subprocess.TimeoutExpired:
            return ProviderResult("", Usage(), int((time.monotonic() - t0) * 1000), error="timeout")
        finally:
            if tmp:
                Path(tmp.name).unlink(missing_ok=True)
        wall_ms = int((time.monotonic() - t0) * 1000)
        result = parse_jsonl(proc.stdout, wall_ms)
        if result.error is None and proc.returncode != 0:
            result.error = f"exit {proc.returncode}: {(proc.stderr or '').strip()[-300:]}"
        if result.error is None and not result.output:
            result.error = "no agent_message in output"
        if schema and result.error is None:
            try:
                parsed = json.loads(result.output)
                result.structured = parsed if isinstance(parsed, dict) else {"value": parsed}
            except json.JSONDecodeError:
                pass
        return result


def parse_jsonl(stdout: str, wall_ms: int) -> ProviderResult:
    """Fold Codex's JSONL event stream into one result."""
    output = ""
    usage = Usage()
    error = None
    thread_id = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = ev.get("type")
        if kind == "thread.started":
            thread_id = ev.get("thread_id")
        elif kind == "item.completed":
            item = ev.get("item") or {}
            if item.get("type") == "agent_message":
                output = str(item.get("text", ""))
            elif item.get("type") == "error":
                # Codex emits advisory errors (e.g. skills budget) that do not
                # fail the turn; keep the last one for the raw record only.
                pass
        elif kind == "turn.completed":
            u = ev.get("usage") or {}
            # Codex's input_tokens INCLUDES the cached portion; normalize so
            # Usage.input_tokens is the uncached remainder like Anthropic's.
            cached = int(u.get("cached_input_tokens", 0))
            usage = Usage(
                input_tokens=max(int(u.get("input_tokens", 0)) - cached, 0),
                cache_read=cached,
                cache_write=int(u.get("cache_write_input_tokens", 0)),
                output_tokens=int(u.get("output_tokens", 0)),
                reasoning=int(u.get("reasoning_output_tokens", 0)),
            )
        elif kind == "turn.failed" or kind == "error":
            error = str(ev.get("error") or ev.get("message") or ev)[:500]
    return ProviderResult(
        output=output,
        usage=usage,
        duration_ms=wall_ms,
        error=error,
        raw={"thread_id": thread_id},
    )
