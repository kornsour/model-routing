"""INI-style service configuration (``services.ini``).

A thin layer we own instead of ``configparser`` so that the deploy tooling and
the job runner read the files identically.
"""

from __future__ import annotations

import re

_SECTION_RE = re.compile(r"^\[(.+)\]$")
_REF_RE = re.compile(r"\$\{([^}]+)\}")


class ConfigError(ValueError):
    pass


class Config:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, str]] = {}

    def sections(self) -> list[str]:
        return [s for s in self._data if s != "DEFAULT"]

    def _raw(self, section: str, key: str) -> str:
        if key in self._data.get(section, {}):
            return self._data[section][key]
        if key in self._data.get("DEFAULT", {}):
            return self._data["DEFAULT"][key]
        raise ConfigError(f"no key {key!r} in [{section}]")

    def get(self, section: str, key: str) -> str:
        value = self._raw(section, key)
        return _REF_RE.sub(lambda m: self.get(section, m.group(1)), value)

    def getint(self, section: str, key: str) -> int:
        return int(self.get(section, key))

    def getbool(self, section: str, key: str) -> bool:
        return self.get(section, key).lower() in ("1", "yes", "true", "on")


def parse(text: str) -> Config:
    cfg = Config()
    current = None
    for line in text.splitlines():
        line = line.split("#")[0].split(";")[0].strip()
        if not line:
            continue
        m = _SECTION_RE.match(line)
        if m:
            current = m.group(1).strip()
            cfg._data.setdefault(current, {})
            continue
        if current is None:
            raise ConfigError("key outside of a section")
        key, _, value = line.partition("=")
        cfg._data[current][key.strip()] = value.strip()
    return cfg
