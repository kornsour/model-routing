"""``logproc.toml`` discovery and the rules for where ``process`` writes its CSV.

See the README's "Config" section for the precedence between the ``--out``
flag, the ``LOGPROC_OUT`` environment variable, the nearest ``logproc.toml``
and the built-in default.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_NAME = "logproc.toml"
DEFAULT_OUT = "entries.csv"
OUT_ENV = "LOGPROC_OUT"


@dataclass
class Config:
    """The settings read from one ``logproc.toml`` (empty when none was found)."""

    out: str | None = None
    path: Path | None = None
    raw: dict = field(default_factory=dict)


def find_config(start: str | Path | None = None) -> Path | None:
    """The nearest ``logproc.toml`` at or above ``start`` (default: the working directory)."""
    here = Path(start) if start is not None else Path.cwd()
    for directory in (here, *here.parents):
        candidate = directory / CONFIG_NAME
        if candidate.is_file():
            return candidate
    return None


def load_config(start: str | Path | None = None) -> Config:
    """Parse the nearest ``logproc.toml`` (see :func:`find_config`).

    A relative ``[output] path`` is resolved against the toml's own directory.
    """
    path = find_config(start)
    if path is None:
        return Config()
    with path.open("rb") as f:
        raw = tomllib.load(f)
    out = raw.get("output", {}).get("path")
    if out is not None:
        out = str(path.parent / out)
    return Config(out=out, path=path, raw=raw)


def resolve_out(cli_out: str | None, config: Config | None = None) -> str:
    """The entries CSV path for this run, applying the README's precedence rules."""
    if cli_out:
        return cli_out
    env_out = os.environ.get(OUT_ENV)
    if env_out:
        return env_out
    if config is not None and config.out:
        return config.out
    return DEFAULT_OUT
