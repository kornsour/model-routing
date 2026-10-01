"""INI-style service configuration (``services.ini``)."""

from __future__ import annotations

import re
from typing import Any

_SECTION_RE = re.compile(r"^\[\s*([^\]:]+?)\s*(?::\s*([^\]]+?)\s*)?\]$")
_KEY_RE = re.compile(r"^([^=:\s][^=:]*?)\s*[=:]\s*(.*)$")
_MISSING: Any = object()
_TRUE = {"1", "yes", "true", "on"}
_FALSE = {"0", "no", "false", "off"}
_ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "t": "\t"}


class ConfigError(ValueError):
    def __init__(self, message: str, lineno: int | None = None) -> None:
        super().__init__(f"line {lineno}: {message}" if lineno else message)
        self.lineno = lineno


def _strip_comment(value: str) -> str:
    for i, ch in enumerate(value):
        if ch in "#;" and i > 0 and value[i - 1].isspace():
            return value[:i].rstrip()
    return value.rstrip()


def _unquote(value: str, lineno: int) -> str:
    out = []
    i = 1
    while i < len(value):
        ch = value[i]
        if ch == "\\":
            if i + 1 >= len(value) or value[i + 1] not in _ESCAPES:
                raise ConfigError("invalid escape in quoted value", lineno)
            out.append(_ESCAPES[value[i + 1]])
            i += 2
            continue
        if ch == '"':
            rest = value[i + 1 :].strip()
            if rest and rest[0] not in "#;":
                raise ConfigError("text after closing quote", lineno)
            return "".join(out)
        out.append(ch)
        i += 1
    raise ConfigError("unterminated quoted value", lineno)


class Config:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, str]] = {}
        self._parents: dict[str, str] = {}
        self._quoted: set[tuple[str, str]] = set()

    # ------------------------------------------------------------------ lookup
    def sections(self) -> list[str]:
        return [s for s in self._data if s != "DEFAULT"]

    def has_section(self, section: str) -> bool:
        return section in self._data and section != "DEFAULT"

    def _chain(self, section: str) -> list[str]:
        if section not in self._data:
            raise ConfigError(f"no section [{section}]")
        chain = [section]
        while chain[-1] in self._parents:
            chain.append(self._parents[chain[-1]])
        if section != "DEFAULT" and "DEFAULT" in self._data:
            chain.append("DEFAULT")
        return chain

    def _raw(self, section: str, key: str) -> tuple[str, str] | None:
        key = key.lower()
        for s in self._chain(section):
            if key in self._data[s]:
                return self._data[s][key], s
        return None

    def keys(self, section: str) -> list[str]:
        out: list[str] = []
        for s in self._chain(section):
            for k in self._data[s]:
                if k not in out:
                    out.append(k)
        return out

    def _interpolate(self, section: str, key: str, stack: tuple[tuple[str, str], ...]) -> str:
        ident = (section, key.lower())
        if ident in stack:
            path = " -> ".join(f"{s}:{k}" for s, k in (*stack, ident))
            raise ConfigError(f"interpolation cycle: {path}")
        found = self._raw(section, key)
        if found is None:
            raise ConfigError(f"no key {key!r} in [{section}]")
        value, _owner = found
        out: list[str] = []
        i = 0
        while i < len(value):
            ch = value[i]
            if ch != "$":
                out.append(ch)
                i += 1
                continue
            nxt = value[i + 1 : i + 2]
            if nxt == "$":
                out.append("$")
                i += 2
                continue
            if nxt != "{":
                raise ConfigError(f"bad '$' in [{section}] {key}")
            end = value.find("}", i + 2)
            if end == -1:
                raise ConfigError(f"unterminated reference in [{section}] {key}")
            ref = value[i + 2 : end].strip()
            if ":" in ref:
                ref_section, _, ref_key = ref.partition(":")
                ref_section, ref_key = ref_section.strip(), ref_key.strip()
            else:
                ref_section, ref_key = section, ref
            if not ref_key or not ref_section:
                raise ConfigError(f"empty reference in [{section}] {key}")
            out.append(self._interpolate(ref_section, ref_key, (*stack, ident)))
            i = end + 1
        return "".join(out)

    # ----------------------------------------------------------------- getters
    def get(self, section: str, key: str, default: Any = _MISSING) -> str:
        if default is not _MISSING and (
            section not in self._data or self._raw(section, key) is None
        ):
            return default
        return self._interpolate(section, key, ())

    def getint(self, section: str, key: str, default: Any = _MISSING) -> int:
        v = self.get(section, key, default)
        return v if v is default else int(v)

    def getfloat(self, section: str, key: str, default: Any = _MISSING) -> float:
        v = self.get(section, key, default)
        return v if v is default else float(v)

    def getbool(self, section: str, key: str, default: Any = _MISSING) -> bool:
        v = self.get(section, key, default)
        if v is default:
            return v
        low = v.strip().lower()
        if low in _TRUE:
            return True
        if low in _FALSE:
            return False
        raise ValueError(f"not a boolean: {v!r}")

    def getlist(self, section: str, key: str, default: Any = _MISSING) -> list[str]:
        v = self.get(section, key, default)
        if v is default:
            return v
        parts = v.split("\n") if "\n" in v else v.split(",")
        return [p.strip() for p in parts if p.strip()]


def parse(text: str) -> Config:
    cfg = Config()
    current: str | None = None
    last_key: str | None = None
    last_indent = 0
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        indent = len(raw_line) - len(raw_line.lstrip())
        if not stripped:
            last_key = None
            continue
        if stripped[0] in "#;":
            continue
        if last_key is not None and indent > last_indent and current is not None:
            if (current, last_key) in cfg._quoted:
                raise ConfigError("continuation of a quoted value", lineno)
            cont = _strip_comment(stripped)
            cfg._data[current][last_key] += "\n" + cont
            continue
        m = _SECTION_RE.match(stripped)
        if stripped.startswith("["):
            if not m:
                raise ConfigError(f"bad section header {stripped!r}", lineno)
            name = m.group(1)
            if name in cfg._data:
                raise ConfigError(f"duplicate section [{name}]", lineno)
            cfg._data[name] = {}
            if m.group(2):
                if name == "DEFAULT":
                    raise ConfigError("DEFAULT cannot inherit", lineno)
                cfg._parents[name] = m.group(2)
            current = name
            last_key = None
            continue
        km = _KEY_RE.match(stripped)
        if not km:
            raise ConfigError(f"expected 'key = value', got {stripped!r}", lineno)
        if current is None:
            raise ConfigError("key outside of a section", lineno)
        key = km.group(1).strip().lower()
        if key in cfg._data[current]:
            raise ConfigError(f"duplicate key {key!r} in [{current}]", lineno)
        value = km.group(2)
        if value.startswith('"'):
            cfg._data[current][key] = _unquote(value, lineno)
            cfg._quoted.add((current, key))
        else:
            cfg._data[current][key] = _strip_comment(value)
        last_key = key
        last_indent = indent
    for child, parent in cfg._parents.items():
        if parent not in cfg._data or parent == "DEFAULT":
            raise ConfigError(f"[{child}] inherits from unknown section [{parent}]")
        seen = {child}
        cur = parent
        while cur in cfg._parents:
            if cur in seen:
                raise ConfigError(f"inheritance cycle involving [{child}]")
            seen.add(cur)
            cur = cfg._parents[cur]
        if cur in seen:
            raise ConfigError(f"inheritance cycle involving [{child}]")
    return cfg
