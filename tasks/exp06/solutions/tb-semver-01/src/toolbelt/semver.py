"""npm-style version ranges.  The contract is ``docs/semver-ranges.md``."""

from __future__ import annotations

import functools
import re
from collections.abc import Iterable
from dataclasses import dataclass

_NUM = r"0|[1-9]\d*"
_IDENT = r"[0-9A-Za-z-]+"
_FULL_RE = re.compile(
    rf"^(?P<major>{_NUM})\.(?P<minor>{_NUM})\.(?P<patch>{_NUM})"
    rf"(?:-(?P<pre>{_IDENT}(?:\.{_IDENT})*))?"
    rf"(?:\+(?P<build>{_IDENT}(?:\.{_IDENT})*))?$"
)
_XR = r"[xX*]|0|[1-9]\d*"
_PARTIAL_RE = re.compile(
    rf"^v?=?\s*(?P<major>{_XR})(?:\.(?P<minor>{_XR})(?:\.(?P<patch>{_XR})"
    rf"(?:-(?P<pre>{_IDENT}(?:\.{_IDENT})*))?"
    rf"(?:\+(?P<build>{_IDENT}(?:\.{_IDENT})*))?)?)?$"
)


def _is_num(s: str) -> bool:
    return s.isdigit()


@functools.total_ordering
@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()
    build: tuple[str, ...] = ()

    def _key(self) -> tuple:
        return (self.major, self.minor, self.patch)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._key() == other._key() and self.prerelease == other.prerelease

    def __hash__(self) -> int:
        return hash((self._key(), self.prerelease))

    def __lt__(self, other: Version) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return _compare(self, other) < 0

    def __str__(self) -> str:
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            s += "-" + ".".join(self.prerelease)
        return s


def _cmp_ident(a: str, b: str) -> int:
    an, bn = _is_num(a), _is_num(b)
    if an and bn:
        return (int(a) > int(b)) - (int(a) < int(b))
    if an:
        return -1
    if bn:
        return 1
    return (a > b) - (a < b)


def _compare(a: Version, b: Version) -> int:
    if a._key() != b._key():
        return -1 if a._key() < b._key() else 1
    if a.prerelease == b.prerelease:
        return 0
    if not a.prerelease:
        return 1
    if not b.prerelease:
        return -1
    for x, y in zip(a.prerelease, b.prerelease, strict=False):
        c = _cmp_ident(x, y)
        if c:
            return c
    return (len(a.prerelease) > len(b.prerelease)) - (len(a.prerelease) < len(b.prerelease))


def _check_pre(pre: tuple[str, ...]) -> None:
    for ident in pre:
        if _is_num(ident) and len(ident) > 1 and ident[0] == "0":
            raise ValueError(f"numeric prerelease identifier with leading zero: {ident!r}")


def parse_version(text: str) -> Version:
    if not isinstance(text, str):
        raise ValueError(f"not a version: {text!r}")
    s = text.strip()
    if s[:1] == "v":
        s = s[1:]
    elif s[:1] == "=":
        s = s[1:]
        if s[:1] == "v":
            s = s[1:]
    m = _FULL_RE.match(s)
    if not m:
        raise ValueError(f"invalid version: {text!r}")
    pre = tuple(m["pre"].split(".")) if m["pre"] else ()
    _check_pre(pre)
    build = tuple(m["build"].split(".")) if m["build"] else ()
    return Version(int(m["major"]), int(m["minor"]), int(m["patch"]), pre, build)


# --------------------------------------------------------------------------- #
# Ranges
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Comparator:
    op: str  # one of "<", "<=", ">", ">=", "="
    version: Version

    def test(self, v: Version) -> bool:
        c = _compare(v, self.version)
        return {
            "<": c < 0,
            "<=": c <= 0,
            ">": c > 0,
            ">=": c >= 0,
            "=": c == 0,
        }[self.op]

    def __str__(self) -> str:
        return ("" if self.op == "=" else self.op) + str(self.version)


def _is_x(s: str | None) -> bool:
    return s is None or s in ("x", "X", "*")


@dataclass
class _Partial:
    major: str | None
    minor: str | None
    patch: str | None
    pre: tuple[str, ...]


def _parse_partial(text: str) -> _Partial:
    m = _PARTIAL_RE.match(text)
    if not m:
        raise ValueError(f"invalid version in range: {text!r}")
    pre = tuple(m["pre"].split(".")) if m["pre"] else ()
    _check_pre(pre)
    major, minor, patch = m["major"], m["minor"], m["patch"]
    # Anything after an X is an X as well.
    if _is_x(major):
        minor = patch = None
        pre = ()
    elif _is_x(minor):
        patch = None
        pre = ()
    elif _is_x(patch):
        pre = ()
    return _Partial(
        None if _is_x(major) else major,
        None if _is_x(minor) else minor,
        None if _is_x(patch) else patch,
        pre,
    )


def _v(major: int, minor: int, patch: int, pre: tuple[str, ...] = ()) -> Version:
    return Version(major, minor, patch, pre)


_ZERO_PRE = ("0",)
_ANY = [_Comparator(">=", _v(0, 0, 0))]
_NONE = [_Comparator("<", _v(0, 0, 0, _ZERO_PRE))]


def _xrange(op: str, p: _Partial) -> list[_Comparator]:
    if p.major is None:
        if op in ("<", ">"):
            return list(_NONE)
        return list(_ANY)
    ma = int(p.major)
    if p.minor is None:
        lo, hi = _v(ma, 0, 0), _v(ma + 1, 0, 0, _ZERO_PRE)
    elif p.patch is None:
        mi = int(p.minor)
        lo, hi = _v(ma, mi, 0), _v(ma, mi + 1, 0, _ZERO_PRE)
    else:
        v = _v(ma, int(p.minor), int(p.patch), p.pre)
        return [_Comparator(op or "=", v)]
    if op in ("", "="):
        return [_Comparator(">=", lo), _Comparator("<", hi)]
    if op == ">":
        return [_Comparator(">=", Version(hi.major, hi.minor, hi.patch))]
    if op == ">=":
        return [_Comparator(">=", lo)]
    if op == "<":
        return [_Comparator("<", Version(lo.major, lo.minor, lo.patch, _ZERO_PRE))]
    if op == "<=":
        return [_Comparator("<", hi)]
    raise ValueError(f"unknown operator {op!r}")


def _tilde(p: _Partial) -> list[_Comparator]:
    if p.major is None:
        return list(_ANY)
    ma = int(p.major)
    if p.minor is None:
        return [_Comparator(">=", _v(ma, 0, 0)), _Comparator("<", _v(ma + 1, 0, 0, _ZERO_PRE))]
    mi = int(p.minor)
    pa = 0 if p.patch is None else int(p.patch)
    return [
        _Comparator(">=", _v(ma, mi, pa, p.pre)),
        _Comparator("<", _v(ma, mi + 1, 0, _ZERO_PRE)),
    ]


def _caret(p: _Partial) -> list[_Comparator]:
    if p.major is None:
        return list(_ANY)
    ma = int(p.major)
    if p.minor is None:
        return [_Comparator(">=", _v(ma, 0, 0)), _Comparator("<", _v(ma + 1, 0, 0, _ZERO_PRE))]
    mi = int(p.minor)
    if p.patch is None:
        lo = _v(ma, mi, 0)
        if ma > 0:
            hi = _v(ma + 1, 0, 0, _ZERO_PRE)
        else:
            hi = _v(0, mi + 1, 0, _ZERO_PRE)
        return [_Comparator(">=", lo), _Comparator("<", hi)]
    pa = int(p.patch)
    lo = _v(ma, mi, pa, p.pre)
    if ma > 0:
        hi = _v(ma + 1, 0, 0, _ZERO_PRE)
    elif mi > 0:
        hi = _v(0, mi + 1, 0, _ZERO_PRE)
    else:
        hi = _v(0, 0, pa + 1, _ZERO_PRE)
    return [_Comparator(">=", lo), _Comparator("<", hi)]


def _hyphen(a: _Partial, b: _Partial) -> list[_Comparator]:
    out: list[_Comparator] = []
    if a.major is None:
        out.append(_Comparator(">=", _v(0, 0, 0)))
    else:
        out.append(
            _Comparator(
                ">=",
                _v(
                    int(a.major),
                    int(a.minor or 0),
                    int(a.patch or 0),
                    a.pre if a.patch is not None else (),
                ),
            )
        )
    if b.major is None:
        pass
    elif b.minor is None:
        out.append(_Comparator("<", _v(int(b.major) + 1, 0, 0, _ZERO_PRE)))
    elif b.patch is None:
        out.append(_Comparator("<", _v(int(b.major), int(b.minor) + 1, 0, _ZERO_PRE)))
    else:
        out.append(_Comparator("<=", _v(int(b.major), int(b.minor), int(b.patch), b.pre)))
    return out


_HYPHEN_RE = re.compile(r"^\s*(\S+)\s+-\s+(\S+)\s*$")
_TOKEN_RE = re.compile(r"(~>|~|\^|<=|>=|<|>|=)?\s*([^\s<>=~^]+)")


def _parse_set(text: str) -> list[_Comparator]:
    text = text.strip()
    if text == "":
        return list(_ANY)
    hm = _HYPHEN_RE.match(text)
    if hm:
        return _hyphen(_parse_partial(hm.group(1)), _parse_partial(hm.group(2)))
    comps: list[_Comparator] = []
    pos = 0
    while pos < len(text):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            break
        m = _TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            raise ValueError(f"invalid range: {text!r}")
        op = m.group(1) or ""
        p = _parse_partial(m.group(2))
        if op in ("~", "~>"):
            comps.extend(_tilde(p))
        elif op == "^":
            comps.extend(_caret(p))
        else:
            comps.extend(_xrange(op, p))
        pos = m.end()
        if pos < len(text) and not text[pos].isspace():
            raise ValueError(f"invalid range: {text!r}")
    return comps


def _parse_range(range_text: str) -> list[list[_Comparator]]:
    if not isinstance(range_text, str):
        raise ValueError(f"not a range: {range_text!r}")
    return [_parse_set(part) for part in range_text.split("||")]


def normalize(range_text: str) -> str:
    return "||".join(" ".join(str(c) for c in s) for s in _parse_range(range_text))


def _set_ok(comps: list[_Comparator], v: Version, include_prerelease: bool) -> bool:
    if not all(c.test(v) for c in comps):
        return False
    if v.prerelease and not include_prerelease:
        return any(
            c.version.prerelease and c.version._key() == v._key() for c in comps
        )
    return True


def _coerce(version: str | Version) -> Version | None:
    if isinstance(version, Version):
        return version
    try:
        return parse_version(version)
    except ValueError:
        return None


def satisfies(
    version: str | Version, range_text: str, *, include_prerelease: bool = False
) -> bool:
    sets = _parse_range(range_text)
    v = _coerce(version)
    if v is None:
        return False
    return any(_set_ok(s, v, include_prerelease) for s in sets)


def _pick(
    versions: Iterable[str | Version], range_text: str, include_prerelease: bool, best: int
) -> str | Version | None:
    sets = _parse_range(range_text)
    chosen: tuple[Version, str | Version] | None = None
    for raw in versions:
        v = _coerce(raw)
        if v is None:
            continue
        if not any(_set_ok(s, v, include_prerelease) for s in sets):
            continue
        if chosen is None or _compare(v, chosen[0]) * best > 0:
            chosen = (v, raw)
    return None if chosen is None else chosen[1]


def max_satisfying(
    versions: Iterable[str | Version], range_text: str, *, include_prerelease: bool = False
) -> str | Version | None:
    return _pick(versions, range_text, include_prerelease, 1)


def min_satisfying(
    versions: Iterable[str | Version], range_text: str, *, include_prerelease: bool = False
) -> str | Version | None:
    return _pick(versions, range_text, include_prerelease, -1)
