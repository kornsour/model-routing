"""Apply unified diffs to text (used by the config-drift fixer)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


class PatchError(ValueError):
    """The patch is malformed or does not apply."""


@dataclass
class PatchResult:
    text: str
    offsets: list[int] = field(default_factory=list)


@dataclass
class _Line:
    kind: str  # " ", "-", "+"
    text: str
    eol: bool = True


@dataclass
class _Hunk:
    old_start: int
    old_len: int
    new_start: int
    new_len: int
    lines: list[_Line]


_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _parse(patch: str) -> list[_Hunk]:
    raw = patch.split("\n")
    if raw and raw[-1] == "":
        raw.pop()
    hunks: list[_Hunk] = []
    i = 0
    while i < len(raw) and not raw[i].startswith("@@"):
        i += 1
    while i < len(raw):
        m = _HEADER_RE.match(raw[i])
        if not m:
            raise PatchError(f"malformed hunk header: {raw[i]!r}")
        old_start = int(m.group(1))
        old_len = int(m.group(2)) if m.group(2) is not None else 1
        new_start = int(m.group(3))
        new_len = int(m.group(4)) if m.group(4) is not None else 1
        i += 1
        lines: list[_Line] = []
        old_seen = new_seen = 0
        while i < len(raw) and (old_seen < old_len or new_seen < new_len):
            line = raw[i]
            if line.startswith("\\"):
                if not lines:
                    raise PatchError("'\\ No newline' marker before any line")
                lines[-1].eol = False
                i += 1
                continue
            kind = line[:1] if line else " "
            if kind not in " -+":
                raise PatchError(f"malformed hunk line: {line!r}")
            lines.append(_Line(kind, line[1:]))
            if kind != "+":
                old_seen += 1
            if kind != "-":
                new_seen += 1
            i += 1
        if old_seen != old_len or new_seen != new_len:
            raise PatchError("hunk line counts do not match its header")
        while i < len(raw) and raw[i].startswith("\\"):
            if not lines:
                raise PatchError("'\\ No newline' marker before any line")
            lines[-1].eol = False
            i += 1
        if hunks and old_start < hunks[-1].old_start + hunks[-1].old_len:
            raise PatchError("hunks overlap or are out of order")
        hunks.append(_Hunk(old_start, old_len, new_start, new_len, lines))
        while i < len(raw) and not raw[i].startswith("@@"):
            if raw[i].startswith(("diff ", "---", "+++", "index ")):
                raise PatchError("patch touches more than one file")
            i += 1
    if not hunks:
        raise PatchError("no hunks in patch")
    return hunks


def _reverse(h: _Hunk) -> _Hunk:
    flip = {" ": " ", "-": "+", "+": "-"}
    return _Hunk(
        h.new_start,
        h.new_len,
        h.old_start,
        h.old_len,
        [_Line(flip[ln.kind], ln.text, ln.eol) for ln in h.lines],
    )


def _split(text: str) -> list[tuple[str, bool]]:
    if text == "":
        return []
    parts = text.split("\n")
    out = [(p, True) for p in parts[:-1]]
    if parts[-1] != "":
        out.append((parts[-1], False))
    return out


def apply_patch(text: str, patch: str, *, reverse: bool = False) -> PatchResult:
    hunks = _parse(patch)
    if reverse:
        hunks = [_reverse(h) for h in hunks]
    lines = _split(text)
    out: list[tuple[str, bool]] = []
    cursor = 0  # next unconsumed line of the original
    offsets: list[int] = []
    delta = 0  # cumulative applied offset
    for n, h in enumerate(hunks, start=1):
        old = [(ln.text, ln.eol) for ln in h.lines if ln.kind != "+"]
        new = [(ln.text, ln.eol) for ln in h.lines if ln.kind != "-"]
        if h.old_len == 0:
            expected = h.old_start  # insert after line old_start
        else:
            expected = h.old_start - 1
        expected += delta
        if not old:
            pos = expected
            if pos < cursor or pos > len(lines):
                raise PatchError(f"hunk {n} does not apply")
        else:
            limit = len(lines) - len(old)
            best: int | None = None
            for cand in range(cursor, limit + 1):
                if _block_matches(lines, cand, old):
                    if best is None or abs(cand - expected) < abs(best - expected):
                        best = cand
            if best is None:
                raise PatchError(f"hunk {n} does not apply")
            pos = best
        offsets.append(pos - (expected - delta))
        delta = pos - (expected - delta)
        out.extend(lines[cursor:pos])
        out.extend(new)
        cursor = pos + len(old)
    out.extend(lines[cursor:])
    for _, eol in out[:-1]:
        if not eol:
            raise PatchError("a line without a newline is not the last line")
    return PatchResult("".join(t + ("\n" if eol else "") for t, eol in out), offsets)


def _block_matches(lines: list[tuple[str, bool]], at: int, block: list[tuple[str, bool]]) -> bool:
    for k, (t, eol) in enumerate(block):
        lt, leol = lines[at + k]
        if lt != t or leol != eol:
            return False
    return True
