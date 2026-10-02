# Ledger history migrations

The history format evolves through declarative migrations in
`packages/ledger/src/ledger/migrations/`, one JSON file per step, named
`NNNN_slug.json`:

```json
{"id": "m-2b9e", "prev_id": "m-6f1c", "version": 2,
 "description": "records carry their currency",
 "ops": [{"op": "add_field", "field": "currency", "default": "USD"}]}
```

## Chain rules

1. Numbers are contiguous from `0000`; no number appears twice.
2. Migration `NNNN` produces format version `NNNN + 1`. `0000` is the format-1
   baseline: `prev_id` is `null` and it has no ops.
3. Every other migration's `prev_id` is the `id` of migration `NNNN - 1`.
   Renaming a file does not change its `prev_id`; repoint it explicitly.
4. Ids are unique.

When two branches both add `NNNN`, the one that merged first keeps its number.
The other is renumbered to the next free number, its `version` bumped to match,
and its `prev_id` repointed to the new predecessor. Its ops are not edited.

## Ops

Applied in order to one record (a JSON object), each a no-op when its
precondition does not hold:

| op | fields | effect |
|---|---|---|
| `add_field` | `field`, `default` | if `field` is absent, set it to a copy of `default` |
| `rename_field` | `from`, `to` | if `from` is present, move its value to `to`; an existing `to` is an error |
| `map_values` | `field`, `mapping` | if `field` is present and its value is a key of `mapping`, replace it |
| `drop_field` | `field` | remove `field` if present |

A record at version `v` is upgraded by applying, in order, every migration
whose `version` is greater than `v`, then setting `version` to the latest. A
record newer than the latest migration is an error.
