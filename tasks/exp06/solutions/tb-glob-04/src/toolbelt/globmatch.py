"""Path glob matching for the artifact uploader's include/exclude lists."""

from __future__ import annotations

import functools
from collections.abc import Iterable


def _find_close(p: str, start: int) -> int:
    """Index of the ``}`` closing the ``{`` at ``start``, or -1."""
    depth = 0
    i = start
    while i < len(p):
        c = p[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _split_alts(body: str) -> list[str]:
    alts: list[str] = []
    depth = 0
    cur = ""
    i = 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            cur += body[i : i + 2]
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if c == "," and depth == 0:
            alts.append(cur)
            cur = ""
        else:
            cur += c
        i += 1
    alts.append(cur)
    return alts


@functools.lru_cache(maxsize=1024)
def expand_braces(pattern: str) -> tuple[str, ...]:
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\":
            i += 2
            continue
        if c == "[":
            end = _class_end(pattern, i)
            if end != -1:
                i = end + 1
                continue
        if c == "{":
            close = _find_close(pattern, i)
            if close == -1:
                i += 1
                continue
            body = pattern[i + 1 : close]
            alts = _split_alts(body)
            if len(alts) < 2:
                i += 1
                continue
            head, tail = pattern[:i], pattern[close + 1 :]
            out: list[str] = []
            for alt in alts:
                for exp in expand_braces(head + alt + tail):
                    if exp not in out:
                        out.append(exp)
            return tuple(out)
        i += 1
    return (pattern,)


def _class_end(p: str, start: int) -> int:
    """Index of the ``]`` closing the class at ``start``, or -1 if unterminated."""
    i = start + 1
    if i < len(p) and p[i] in "!^":
        i += 1
    if i < len(p) and p[i] == "]":
        i += 1
    while i < len(p):
        if p[i] == "\\":
            i += 2
            continue
        if p[i] == "]":
            return i
        i += 1
    return -1


def _split_segments(pattern: str) -> list[str]:
    segs: list[str] = []
    cur = ""
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\" and i + 1 < len(pattern):
            cur += pattern[i : i + 2]
            i += 2
            continue
        if c == "[":
            end = _class_end(pattern, i)
            if end != -1 and "/" not in pattern[i:end]:
                cur += pattern[i : end + 1]
                i = end + 1
                continue
        if c == "/":
            segs.append(cur)
            cur = ""
        else:
            cur += c
        i += 1
    segs.append(cur)
    return segs


Token = tuple


@functools.lru_cache(maxsize=4096)
def _compile_segment(seg: str) -> tuple[tuple[Token, ...], bool]:
    """Tokens for one path segment, and whether it starts with a wildcard."""
    toks: list[Token] = []
    i = 0
    first_wild = False
    while i < len(seg):
        c = seg[i]
        if c == "\\":
            if i + 1 < len(seg):
                toks.append(("lit", seg[i + 1]))
                i += 2
            else:
                toks.append(("lit", "\\"))
                i += 1
            continue
        if c == "*":
            if i == 0:
                first_wild = True
            while i < len(seg) and seg[i] == "*":
                i += 1
            toks.append(("star",))
            continue
        if c == "?":
            if i == 0:
                first_wild = True
            toks.append(("any",))
            i += 1
            continue
        if c == "[":
            end = _class_end(seg, i)
            if end == -1:
                toks.append(("lit", "["))
                i += 1
                continue
            if i == 0:
                first_wild = True
            j = i + 1
            negate = False
            if seg[j] in "!^":
                negate = True
                j += 1
            chars: list[str] = []
            k = j
            while k < end:
                ch = seg[k]
                if ch == "\\" and k + 1 < end:
                    chars.append(seg[k + 1])
                    k += 2
                    continue
                chars.append(ch)
                k += 1
            ranges: list[tuple[str, str]] = []
            n = 0
            while n < len(chars):
                if n + 2 < len(chars) and chars[n + 1] == "-":
                    ranges.append((chars[n], chars[n + 2]))
                    n += 3
                else:
                    ranges.append((chars[n], chars[n]))
                    n += 1
            toks.append(("cls", negate, tuple(ranges)))
            i = end + 1
            continue
        toks.append(("lit", c))
        i += 1
    return tuple(toks), first_wild


def _tok_ok(tok: Token, ch: str, ignore_case: bool) -> bool:
    kind = tok[0]
    if kind == "any":
        return ch != "/"
    if kind == "lit":
        return ch == tok[1] or (ignore_case and ch.lower() == tok[1].lower())
    _, negate, ranges = tok
    if ch == "/":
        return False
    cands = {ch, ch.lower(), ch.upper()} if ignore_case else {ch}
    hit = any(lo <= c <= hi for c in cands for lo, hi in ranges)
    return hit != negate


def _segment_match(seg: str, text: str, dot: bool, ignore_case: bool) -> bool:
    toks, first_wild = _compile_segment(seg)
    if first_wild and not dot and text.startswith("."):
        return False
    # Greedy wildcard matching with backtracking to the last star: O(len*len).
    ti = pi = 0
    star_pi, star_ti = -1, 0
    while ti < len(text):
        if pi < len(toks) and toks[pi][0] != "star" and _tok_ok(toks[pi], text[ti], ignore_case):
            ti += 1
            pi += 1
        elif pi < len(toks) and toks[pi][0] == "star":
            star_pi, star_ti = pi, ti
            pi += 1
        elif star_pi != -1:
            pi = star_pi + 1
            star_ti += 1
            ti = star_ti
        else:
            return False
    while pi < len(toks) and toks[pi][0] == "star":
        pi += 1
    return pi == len(toks)


def _match_segments(
    psegs: tuple[str, ...], parts: tuple[str, ...], dot: bool, ignore_case: bool
) -> bool:
    @functools.lru_cache(maxsize=None)
    def go(pi: int, si: int) -> bool:
        if pi == len(psegs):
            return si == len(parts)
        seg = psegs[pi]
        if seg == "**":
            if pi == len(psegs) - 1:
                rest = parts[si:]
                return len(rest) > 0 and (dot or not any(p.startswith(".") for p in rest))
            if go(pi + 1, si):
                return True
            if si < len(parts) and (dot or not parts[si].startswith(".")):
                return go(pi, si + 1)
            return False
        if si == len(parts):
            return False
        if not _segment_match(seg, parts[si], dot, ignore_case):
            return False
        return go(pi + 1, si + 1)

    return go(0, 0)


def match(pattern: str, path: str, *, dot: bool = False, ignore_case: bool = False) -> bool:
    if path == "":
        return False
    parts = tuple(path.split("/"))
    for alt in expand_braces(pattern):
        segs = tuple(_split_segments(alt))
        if _match_segments(segs, parts, dot, ignore_case):
            return True
    return False


def select(paths: Iterable[str], patterns: list[str], *, dot: bool = False) -> list[str]:
    compiled: list[tuple[bool, str]] = []
    for pat in patterns:
        if pat.startswith("!"):
            compiled.append((False, pat[1:]))
        elif pat.startswith("\\!"):
            compiled.append((True, pat[1:]))
        else:
            compiled.append((True, pat))
    out: list[str] = []
    for path in paths:
        keep = False
        for include, pat in compiled:
            if match(pat, path, dot=dot):
                keep = include
        if keep:
            out.append(path)
    return out
