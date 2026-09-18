"""Deterministic graders.  No LLM-as-judge by default: judges cost money and
add noise, and every seed task here has a checkable answer.

A grader spec is a dict with a ``type`` key.  Supported types:

* ``exact``        - normalized (case/whitespace/punctuation-insensitive) equality
* ``contains_all`` - every string in ``values`` appears (case-insensitive)
* ``contains_any`` - at least one of ``values`` appears
* ``not_contains`` - none of ``values`` appear (combine via ``all_of``)
* ``regex``        - ``pattern`` matches (re.search, IGNORECASE|DOTALL)
* ``number``       - the answer number is within ``tol`` of ``value``.  Verbose
                     answers restate inputs, so candidates are taken from the
                     last non-empty line first, then bold text, then the last
                     number anywhere; the first non-empty group is graded
* ``json_fields``  - output parses as JSON (or a ``structured`` dict is given)
                     and each key in ``expect`` equals the expected value
* ``max_words``    - at most ``value`` words (use inside ``all_of``)
* ``all_of``       - every grader in ``graders`` passes
"""

from __future__ import annotations

import json
import re
import string
from typing import Any

_NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def normalize(text: str) -> str:
    return " ".join(text.lower().translate(_PUNCT_TABLE).split())


def _extract_json(text: str) -> Any:
    """Parse JSON from a response, tolerating code fences and surrounding prose."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"[\[{].*[\]}]", text, flags=re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def grade(
    spec: dict[str, Any], output: str, structured: dict[str, Any] | None = None
) -> tuple[bool, str]:
    """Return (passed, detail).  Never raises on malformed model output."""
    kind = spec.get("type")
    if kind == "exact":
        want = normalize(str(spec["value"]))
        got = normalize(output)
        return got == want, f"exact: want={want!r} got={got[:80]!r}"
    if kind == "contains_all":
        low = output.lower()
        missing = [v for v in spec["values"] if str(v).lower() not in low]
        return not missing, f"contains_all: missing={missing}"
    if kind == "contains_any":
        low = output.lower()
        hit = [v for v in spec["values"] if str(v).lower() in low]
        return bool(hit), f"contains_any: hit={hit}"
    if kind == "not_contains":
        low = output.lower()
        found = [v for v in spec["values"] if str(v).lower() in low]
        return not found, f"not_contains: found={found}"
    if kind == "regex":
        ok = re.search(spec["pattern"], output, flags=re.I | re.S) is not None
        return ok, f"regex: {spec['pattern']!r} matched={ok}"
    if kind == "number":
        cands = _answer_numbers(output)
        if not cands:
            return False, "number: no number found"
        tol = float(spec.get("tol", 0))
        want = float(spec["value"])
        ok = any(abs(c - want) <= tol for c in cands)
        return ok, f"number: want={want} got={cands} tol={tol}"
    if kind == "json_fields":
        data = structured if structured is not None else _extract_json(output)
        if not isinstance(data, dict):
            return False, "json_fields: output is not a JSON object"
        bad = {
            k: data.get(k)
            for k, v in spec["expect"].items()
            if _norm_val(data.get(k)) != _norm_val(v)
        }
        return not bad, f"json_fields: mismatches={bad}"
    if kind == "max_words":
        n = len(output.split())
        return n <= int(spec["value"]), f"max_words: {n} <= {spec['value']}"
    if kind == "all_of":
        details = []
        for sub in spec["graders"]:
            ok, d = grade(sub, output, structured)
            details.append(d)
            if not ok:
                return False, "all_of failed: " + d
        return True, "all_of: " + "; ".join(details)
    return False, f"unknown grader type {kind!r}"


def _answer_numbers(output: str) -> list[float]:
    """Numbers most likely to be the answer, from the most answer-like region."""
    lines = [ln for ln in output.strip().splitlines() if ln.strip()]
    groups = []
    if lines:
        groups.append(_NUM_RE.findall(lines[-1]))
    groups.append([n for b in re.findall(r"\*\*(.+?)\*\*", output) for n in _NUM_RE.findall(b)])
    all_nums = _NUM_RE.findall(output)
    groups.append(all_nums[-1:])
    for g in groups:
        vals = [float(x.replace(",", "")) for x in g]
        if vals:
            return vals
    return []


def _norm_val(v: Any) -> Any:
    if isinstance(v, str):
        return normalize(v)
    if isinstance(v, list):
        return [_norm_val(x) for x in v]
    if isinstance(v, bool):
        return v
    if isinstance(v, int | float):
        return float(v)
    return v
