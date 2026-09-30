"""JSON Patch (RFC 6902) and JSON Pointer (RFC 6901)."""

from __future__ import annotations

import copy
import re
from typing import Any


class PatchError(ValueError):
    """A patch could not be applied (bad operation, bad pointer, failed test)."""


_INDEX_RE = re.compile(r"^(0|[1-9][0-9]*)$")


def _unescape(token: str) -> str:
    if re.search(r"~(?![01])", token):
        raise PatchError(f"invalid escape in pointer token {token!r}")
    return token.replace("~1", "/").replace("~0", "~")


def _tokens(pointer: str) -> list[str]:
    if not isinstance(pointer, str):
        raise PatchError(f"pointer must be a string: {pointer!r}")
    if pointer == "":
        return []
    if not pointer.startswith("/"):
        raise PatchError(f"pointer must start with '/': {pointer!r}")
    return [_unescape(t) for t in pointer[1:].split("/")]


def _index(container: list, token: str, *, allow_end: bool) -> int:
    if token == "-":
        if allow_end:
            return len(container)
        raise PatchError("'-' is only valid when adding to an array")
    if not _INDEX_RE.match(token):
        raise PatchError(f"invalid array index {token!r}")
    i = int(token)
    limit = len(container) if allow_end else len(container) - 1
    if i > limit:
        raise PatchError(f"array index {i} out of range")
    return i


def _child(node: Any, token: str) -> Any:
    if isinstance(node, dict):
        if token not in node:
            raise PatchError(f"member {token!r} not found")
        return node[token]
    if isinstance(node, list):
        return node[_index(node, token, allow_end=False)]
    raise PatchError(f"cannot descend into a scalar with {token!r}")


def resolve(doc: Any, pointer: str) -> Any:
    node = doc
    for token in _tokens(pointer):
        node = _child(node, token)
    return node


def make_pointer(tokens: list[str | int]) -> str:
    return "".join("/" + str(t).replace("~", "~0").replace("/", "~1") for t in tokens)


def _parent(doc: Any, pointer: str) -> tuple[Any, str]:
    tokens = _tokens(pointer)
    node = doc
    for token in tokens[:-1]:
        node = _child(node, token)
    return node, tokens[-1]


def _json_equal(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_json_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_json_equal(x, y) for x, y in zip(a, b))
    if type(a) is not type(b):
        return False
    return a == b


def _add(doc: Any, pointer: str, value: Any) -> Any:
    if pointer == "":
        return value
    parent, token = _parent(doc, pointer)
    if isinstance(parent, dict):
        parent[token] = value
    elif isinstance(parent, list):
        parent.insert(_index(parent, token, allow_end=True), value)
    else:
        raise PatchError(f"cannot add to a scalar at {pointer!r}")
    return doc


def _remove(doc: Any, pointer: str) -> tuple[Any, Any]:
    if pointer == "":
        raise PatchError("cannot remove the whole document")
    parent, token = _parent(doc, pointer)
    if isinstance(parent, dict):
        if token not in parent:
            raise PatchError(f"member {token!r} not found")
        return doc, parent.pop(token)
    if isinstance(parent, list):
        return doc, parent.pop(_index(parent, token, allow_end=False))
    raise PatchError(f"cannot remove from a scalar at {pointer!r}")


def _replace(doc: Any, pointer: str, value: Any) -> Any:
    if pointer == "":
        return value
    parent, token = _parent(doc, pointer)
    if isinstance(parent, dict):
        if token not in parent:
            raise PatchError(f"member {token!r} not found")
        parent[token] = value
    elif isinstance(parent, list):
        parent[_index(parent, token, allow_end=False)] = value
    else:
        raise PatchError(f"cannot replace inside a scalar at {pointer!r}")
    return doc


_MISSING = object()


def _member(op: dict[str, Any], name: str) -> Any:
    if name not in op:
        raise PatchError(f"operation {op.get('op')!r} is missing {name!r}")
    return op[name]


def apply_patch(doc: Any, patch: list[dict[str, Any]]) -> Any:
    if not isinstance(patch, list):
        raise PatchError("a patch must be a list of operations")
    result = copy.deepcopy(doc)
    for op in patch:
        if not isinstance(op, dict):
            raise PatchError(f"operation must be an object: {op!r}")
        kind = _member(op, "op")
        path = _member(op, "path")
        _tokens(path)
        if kind == "add":
            result = _add(result, path, copy.deepcopy(_member(op, "value")))
        elif kind == "remove":
            result, _ = _remove(result, path)
        elif kind == "replace":
            result = _replace(result, path, copy.deepcopy(_member(op, "value")))
        elif kind == "move":
            src = _member(op, "from")
            _tokens(src)
            if path == src:
                resolve(result, src)
                continue
            if path.startswith(src + "/"):
                raise PatchError("cannot move a value into one of its own children")
            result, value = _remove(result, src)
            result = _add(result, path, value)
        elif kind == "copy":
            src = _member(op, "from")
            value = copy.deepcopy(resolve(result, src))
            result = _add(result, path, value)
        elif kind == "test":
            expected = _member(op, "value")
            if not _json_equal(resolve(result, path), expected):
                raise PatchError(f"test failed at {path!r}")
        else:
            raise PatchError(f"unknown operation {kind!r}")
    return result


def _diff(a: Any, b: Any, tokens: list[str | int], out: list[dict[str, Any]]) -> None:
    if _json_equal(a, b):
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            path = make_pointer([*tokens, key])
            if key not in b:
                out.append({"op": "remove", "path": path})
            elif key not in a:
                out.append({"op": "add", "path": path, "value": copy.deepcopy(b[key])})
            else:
                _diff(a[key], b[key], [*tokens, key], out)
        return
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            _diff(x, y, [*tokens, i], out)
        return
    out.append({"op": "replace", "path": make_pointer(tokens), "value": copy.deepcopy(b)})


def diff(a: Any, b: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    _diff(a, b, [], out)
    return out
