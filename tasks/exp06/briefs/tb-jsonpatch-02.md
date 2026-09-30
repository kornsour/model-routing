---
title: Implement JSON Patch / JSON Pointer in toolbelt.jsonpatch
terse: Implement RFC 6902 JSON Patch and RFC 6901 JSON Pointer in toolbelt.jsonpatch.
repo: toolbelt
allowed: ["src/toolbelt/jsonpatch.py", "tests/*.py"]
category: feature
tags: [spec-compliance, rfc, stub]
---
The config service is moving from "replace the whole document" to operator-authored JSON Patches, and it needs `src/toolbelt/jsonpatch.py` implemented. The module has the signatures stubbed out (`PatchError`, `resolve`, `make_pointer`, `apply_patch`, `diff`); please implement them. Documents are the Python values `json.loads` produces (dict, list, str, int, float, bool, None).

Requirements:

**JSON Pointer (RFC 6901).** `resolve(doc, pointer)` returns the referenced value. `""` is the whole document; otherwise the pointer must start with `/`, and each `/`-separated token is unescaped with `~1` -> `/` then `~0` -> `~` (in that order, so `~01` means the literal key `~1`). Any other `~` escape is an error. A token addressing an array must be `0` or a decimal without leading zeros, and in range; `-` never resolves to an existing element. Descending into a scalar, a missing member, or a malformed pointer is an error. `make_pointer(tokens)` is the inverse: it escapes each token (`str()` of ints) and joins them; `make_pointer([]) == ""`.

**JSON Patch (RFC 6902).** `apply_patch(doc, patch)` applies a list of operation objects in order and returns the result. It must not modify `doc` or any value inside `patch` (the result must not share mutable structure with either), and it is atomic: if any operation fails, raise `PatchError` and nothing is changed. `PatchError` subclasses `ValueError`. Each operation sees the result of the ones before it.

- `add`: the target's parent must exist. On an object it sets the member (replacing an existing one). On an array, the index may be `0..len` (inclusive) or `-` (append); the value is inserted there. A path of `""` replaces the whole document.
- `remove`: the target must exist. Removing `""` is an error.
- `replace`: the target must exist (for arrays the index must be `< len`; `-` is an error); `""` replaces the whole document.
- `move`: `from` must exist; `path` must not be a proper child of `from` (error); moving to the same location is a no-op (but `from` must still exist). Otherwise it is remove-then-add, so indices in `path` are interpreted after the removal.
- `copy`: add a deep copy of the value at `from` at `path`.
- `test`: the value at `path` must equal `value` under JSON semantics: numbers are equal when numerically equal (`1 == 1.0`), booleans are *not* numbers (`true != 1`), `null` equals only `null`, strings compare exactly, arrays element-wise in order, objects by the same key set with equal values. A failed test is a `PatchError`.
- An unknown `op`, a missing required member (`op`, `path`, `value` for add/replace/test, `from` for move/copy), a patch that is not a list, or an operation that is not an object are all `PatchError`. Unrecognised extra members are ignored.

**Diff.** `diff(a, b)` returns a patch that turns `a` into `b`, deterministically, following exactly these rules so the review UI can show stable diffs: if `a` and `b` are equal under the `test` semantics above, emit nothing. If both are objects, walk the union of their keys in sorted order: a key only in `a` emits `remove`, a key only in `b` emits `add` (with the value), a key in both recurses. If both are arrays of the same length, recurse index by index. In every other case (different types, arrays of different lengths, different scalars, bool vs number) emit a single `replace` of the current location with the new value. Paths are built with `make_pointer`. Values in the diff must be copies, not references into `b`.

Add tests (the RFC 6902 appendix examples are a good start). Keep `python -m pytest -q` green and keep the change to `src/toolbelt/jsonpatch.py` and the tests.
