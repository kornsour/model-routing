"""Layered ledger configuration.

Layers, lowest to highest precedence: built-in defaults, a system file, a
project file (``ledger.ini`` in the working directory unless another is
given), ``LEDGER__<SECTION>__<KEY>`` environment variables, and
``--set section.key=value`` overrides. Files use ``toolbelt.iniconf``
syntax; layers are merged raw, so ``${section:key}`` references resolve
against the merged result. ``provenance`` names the layer that supplied a
key's raw value.

Keys whose names contain ``password``, ``secret`` or ``token``, or end with
``key``, are secret: ``dump`` shows them as ``********``, and shows any value
whose interpolation reaches a secret (directly or through other keys) raw,
with its references intact. Loading fails loudly if any value cannot be
interpolated.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from toolbelt.iniconf import Config, ConfigError, merge, parse

DEFAULTS = {"paths": {"history": "history.jsonl", "inflight": "inflight.json", "rates": "rates.json"}}
ENV_PREFIX = "LEDGER__"
REDACTED = "********"
_REF = re.compile(r"\$(\$|\{([^}]*)\})")


def is_secret(key: str) -> bool:
    k = key.lower()
    return "password" in k or "secret" in k or "token" in k or k.endswith("key")


def _refs(value: str, section: str) -> list[tuple[str, str]]:
    out = []
    for m in _REF.finditer(value):
        if m.group(1) == "$":
            continue
        ref = m.group(2).strip()
        if ":" in ref:
            ref_section, _, ref_key = ref.partition(":")
            out.append((ref_section.strip(), ref_key.strip().lower()))
        else:
            out.append((section, ref.lower()))
    return out


class LedgerConfig:
    def __init__(self, layers: list[tuple[str, Config]]) -> None:
        self.layers = layers
        self.merged = merge(*(cfg for _, cfg in layers))
        for section in self.merged.sections():
            for key in self.merged.keys(section):
                self.merged.get(section, key)

    def get(self, section: str, key: str) -> str:
        return self.merged.get(section, key)

    def has(self, section: str, key: str) -> bool:
        return self.merged.has_section(section) and self.merged.raw(section, key) is not None

    def provenance(self, section: str, key: str) -> str:
        found = self.merged.raw(section, key)
        if found is None:
            raise ConfigError(f"no key {key!r} in [{section}]")
        value, owner = found
        for label, cfg in reversed(self.layers):
            try:
                hit = cfg.raw(owner, key)
            except ConfigError:
                continue
            if hit == (value, owner):
                return label
        raise ConfigError(f"cannot place [{section}] {key}")

    def _reaches_secret(self, section: str, key: str, seen: set[tuple[str, str]]) -> bool:
        if is_secret(key):
            return True
        found = self.merged.raw(section, key)
        if found is None or (section, key) in seen:
            return False
        seen.add((section, key))
        return any(self._reaches_secret(s, k, seen) for s, k in _refs(found[0], section))

    def display(self, section: str, key: str) -> str:
        if is_secret(key):
            return REDACTED
        if self._reaches_secret(section, key, set()):
            return self.merged.raw(section, key)[0]
        return self.get(section, key)

    def dump(self) -> str:
        blocks = []
        for section in sorted(self.merged.sections()):
            lines = [f"[{section}]"]
            for key in sorted(self.merged.keys(section)):
                lines.append(f"{key} = {self.display(section, key)}  # {self.provenance(section, key)}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks) + "\n"


def _from_mapping(values: Mapping[str, Mapping[str, str]]) -> Config:
    cfg = Config()
    for section, keys in values.items():
        for key, value in keys.items():
            cfg.set(section, key, value)
    return cfg


def load_config(
    system: str | Path | None = None,
    project: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    overrides: Iterable[str] = (),
) -> LedgerConfig:
    layers: list[tuple[str, Config]] = [("default", _from_mapping(DEFAULTS))]
    if system is not None:
        layers.append((f"system:{system}", parse(Path(system).read_text(), require_parents=False)))
    if project is None and Path("ledger.ini").exists():
        project = "ledger.ini"
    if project is not None:
        layers.append((f"project:{project}", parse(Path(project).read_text(), require_parents=False)))
    env = os.environ if env is None else env
    for name in sorted(env):
        if not name.startswith(ENV_PREFIX):
            continue
        parts = name[len(ENV_PREFIX):].split("__")
        if len(parts) != 2 or not all(parts):
            continue
        cfg = Config()
        cfg.set(parts[0].lower(), parts[1].lower(), env[name])
        layers.append((f"env:{name}", cfg))
    for item in overrides:
        target, eq, value = item.partition("=")
        section, dot, key = target.partition(".")
        if not eq or not dot or not section.strip() or not key.strip():
            raise ValueError(f"--set expects section.key=value, got {item!r}")
        cfg = Config()
        cfg.set(section.strip(), key.strip(), value)
        layers.append((f"cli:{section.strip()}.{key.strip().lower()}", cfg))
    return LedgerConfig(layers)
