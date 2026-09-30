"""npm-style version ranges used by the deploy tooling.

See docs/semver-ranges.md for what the ranges mean.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

_VERSION_RE = re.compile(
    r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$"
)


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int
    # Sort key for the prerelease: releases sort after prereleases.
    _pre_key: tuple = field(default=(1,), repr=False)
    prerelease: tuple[str, ...] = ()
    build: tuple[str, ...] = ()

    def __str__(self) -> str:
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            s += "-" + ".".join(self.prerelease)
        return s


def parse_version(text: str) -> Version:
    m = _VERSION_RE.match(text.strip())
    if not m:
        raise ValueError(f"invalid version: {text!r}")
    pre = tuple(m.group(4).split(".")) if m.group(4) else ()
    build = tuple(m.group(5).split(".")) if m.group(5) else ()
    pre_key = (0, pre) if pre else (1,)
    return Version(int(m.group(1)), int(m.group(2)), int(m.group(3)), pre_key, pre, build)


def _fill(text: str) -> tuple[Version, int]:
    """Fill a partial version with zeros; also return how many parts were given."""
    parts = text.lstrip("v").split(".")
    given = 0
    nums = []
    for p in parts[:3]:
        if p in ("x", "X", "*"):
            break
        nums.append(p)
        given += 1
    while len(nums) < 3:
        nums.append("0")
    return parse_version(".".join(nums)), given


def _bump(v: Version, given: int) -> Version:
    if given <= 1:
        return Version(v.major + 1, 0, 0)
    if given == 2:
        return Version(v.major, v.minor + 1, 0)
    return Version(v.major, v.minor, v.patch + 1)


def _desugar(token: str) -> list[tuple[str, Version]]:
    if token in ("", "*", "x", "X"):
        return [(">=", Version(0, 0, 0))]
    if token.startswith("^"):
        v, given = _fill(token[1:])
        return [(">=", v), ("<", Version(v.major + 1, 0, 0))]
    if token.startswith("~"):
        v, given = _fill(token[1:])
        return [(">=", v), ("<", _bump(v, min(given, 2)))]
    m = re.match(r"^(<=|>=|<|>|=)?(.*)$", token)
    assert m
    op, rest = m.group(1) or "=", m.group(2)
    v, given = _fill(rest)
    if given == 3:
        return [(op, v)]
    if op == "=":
        return [(">=", v), ("<", _bump(v, given))]
    return [(op, v)]


def _test(op: str, v: Version, bound: Version) -> bool:
    return {
        "<": v < bound,
        "<=": v <= bound,
        ">": v > bound,
        ">=": v >= bound,
        "=": v == bound,
    }[op]


def _parse_set(text: str) -> list[tuple[str, Version]]:
    text = text.strip()
    if " - " in text:
        lo, hi = text.split(" - ")
        return [(">=", _fill(lo)[0]), ("<=", _fill(hi)[0])]
    comps: list[tuple[str, Version]] = []
    for token in text.split():
        comps.extend(_desugar(token))
    return comps or [(">=", Version(0, 0, 0))]


def normalize(range_text: str) -> str:
    sets = [_parse_set(s) for s in range_text.split("||")]
    return "||".join(
        " ".join(("" if op == "=" else op) + str(v) for op, v in comps) for comps in sets
    )


def satisfies(version: str | Version, range_text: str) -> bool:
    try:
        v = version if isinstance(version, Version) else parse_version(version)
    except ValueError:
        return False
    for part in range_text.split("||"):
        if all(_test(op, v, bound) for op, bound in _parse_set(part)):
            return True
    return False


def max_satisfying(versions: Iterable[str], range_text: str) -> str | None:
    ok = [s for s in versions if satisfies(s, range_text)]
    return max(ok, key=parse_version) if ok else None
