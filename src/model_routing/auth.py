"""Auth mode for the CLI providers: local subscription login or an API key.

``subscription`` (default) runs the CLI on the operator's own login and scrubs
API-key variables from the child environment, so an exported key can never
silently switch a run to API billing.  ``api_key`` reads the key from a named
environment variable (never from the config file) and hands it to the CLI under
the variable that CLI expects.  Config::

    [auth]
    mode = "subscription"          # default for every provider

    [auth.codex_cli]               # optional per-provider override
    mode = "api_key"
    api_key_env = "OPENAI_API_KEY" # env var holding the key (has a default)
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

MODES = ("subscription", "api_key")

# provider -> (env var the CLI reads, default env var holding the operator's key)
_CLI_KEY_VAR = {"claude_cli": "ANTHROPIC_API_KEY", "codex_cli": "CODEX_API_KEY"}
_DEFAULT_SOURCE = {"claude_cli": "ANTHROPIC_API_KEY", "codex_cli": "OPENAI_API_KEY"}
_SCRUBBED = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY", "CODEX_API_KEY")


@dataclass(frozen=True)
class AuthConfig:
    mode: str = "subscription"
    api_key_env: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"auth mode {self.mode!r} not in {MODES}")

    def child_env(
        self, provider: str, base: Mapping[str, str] | None = None
    ) -> dict[str, str] | None:
        """Environment for the CLI subprocess, or None for providers with no auth."""
        if provider not in _CLI_KEY_VAR:
            return None
        env = dict(os.environ if base is None else base)
        for var in _SCRUBBED:
            env.pop(var, None)
        if self.mode == "api_key":
            source = self.api_key_env or _DEFAULT_SOURCE[provider]
            key = (os.environ if base is None else base).get(source)
            if not key:
                raise ValueError(f"auth mode api_key for {provider}: ${source} is not set")
            env[_CLI_KEY_VAR[provider]] = key
        return env


def parse_auth(section: Mapping[str, Any]) -> dict[str, AuthConfig]:
    """``[auth]`` table -> {provider: AuthConfig}; ``"*"`` holds the default."""
    default = AuthConfig(str(section.get("mode", "subscription")), section.get("api_key_env"))
    out = {"*": default}
    for name, spec in section.items():
        if isinstance(spec, dict):
            out[name] = AuthConfig(
                str(spec.get("mode", default.mode)),
                spec.get("api_key_env", default.api_key_env),
            )
    return out
