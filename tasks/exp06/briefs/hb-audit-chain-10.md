---
title: Tamper-evident run history with compaction
terse: Hash-chain every ledger history record, verify the chain (detecting edits, deletions, reordering and insertions), and compact old months into a verifiable checkpoint.
repo: platform
parent: platform
allowed: ["packages/ledger/*", "docs/*", "README.md"]
category: feature
tags: [long-horizon, integrity, data-format, cli]
stratum: B
max_turns: 80
harvest_shape: "a claimed property (hash-chained, verified, tamper-detected) that must be genuinely implemented and proven by tests, not just modelled (harvested #27: audit the hash-chained audit-trail claim)"
authorship: "Brief drafted from the shape of harvested dispatch #27 by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
Finance will start using `history.jsonl` as the record behind chargebacks, and audit asked the obvious question: how would we know if someone edited it? Today we wouldn't. Make the history tamper-evident, and give us a way to keep it small without losing that property. You are in the `platform` monorepo (current directory); `python -m pytest -q` runs every suite.

## Design (agreed with audit — implement exactly this)

**Chain.** Every record appended from now on carries two extra fields, `prev_hash` and `hash`:

- `body` is the record's JSON object without `prev_hash` and `hash`; `canonical(body)` is `json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
- `hash = sha256((prev_hash + canonical(body)).encode("utf-8")).hexdigest()`.
- `prev_hash` is the previous chained line's `hash` (for a checkpoint line, see below), or `GENESIS = "0" * 64` for the first chained line.

History files already in production contain unchained lines (no hash fields). Those lines are the **pre-chain prefix**: allowed only before the first chained line, never after it. Records are still appended, never rewritten; `ledger.store.append` does the chaining itself, so every existing caller gets it for free.

**Verification.** `ledger.audit.verify(path) -> Verification`, a frozen dataclass `ok: bool`, `checked: int` (chained record lines verified), `pre_chain: int`, `checkpoints: int`, `bad_line: int | None` (1-based), `reason: str` (empty when ok). It walks the file once and stops at the first problem. It must detect at least: an edited record (hash mismatch), a deleted record (the next `prev_hash` no longer matches), two records swapped, an unchained line after the chain started, and an edited checkpoint. An empty or missing file verifies ok with all counts 0.

**Checkpoints.** `ledger.audit.compact(path, out_path, before_month) -> str` writes a new file (never in place; `out_path` must not exist, else `FileExistsError`) in which every **chained** record whose `started_at` month (UTC, `YYYY-MM`) is earlier than `before_month` and that precedes the first record of `before_month` or later in file order is replaced by **one** checkpoint line, followed by all remaining lines **byte-for-byte unchanged**. Pre-chain lines are kept as they are, before the checkpoint. The checkpoint is:

```json
{"kind": "checkpoint", "covers": 41, "through_hash": "<hash of the last compacted record>",
 "summary": {"nightly": {"runs": 30, "total_usd": 412.5}, ...},
 "prev_hash": "<hash of the line before the first compacted record, or GENESIS>", "hash": "..."}
```

`summary` holds runs and the summed `total_usd` (rounded to 6 decimal places) per pipeline over the compacted records. Compacting an already-compacted file must work: when the compacted range starts with an existing checkpoint, fold it into the new one (its `covers` and per-pipeline `summary` are added in, and its `prev_hash` becomes the new checkpoint's `prev_hash`). The checkpoint's `hash` is computed like any other line's. The line after a checkpoint has `prev_hash == through_hash` — exactly as before compaction — so verification continues from `through_hash`. `compact` returns the checkpoint's hash (audit publishes it). With nothing to compact it writes an identical copy and returns `""`.

**Store.** `ledger.store.load` ignores checkpoint lines (and the hash fields of record lines); everything else about loading is unchanged.

## CLI

- `ledger verify [--history F]` prints `ok: N records verified (P pre-chain, C checkpoints)` and exits 0, or `FAILED at line L: <reason>` and exits 1.
- `ledger compact --before YYYY-MM --out NEW [--history F]` prints `checkpoint <hash>` (or `nothing to compact`).

## Constraints

- Stdlib only (`hashlib`, `json`). Put the chain logic in a new `ledger.audit` module and have `store.append` call it; do not duplicate the hash computation.
- Update the `ledger.store` docstring (it documents the line format) and the ledger README.
- Tests in `packages/ledger/tests/` must cover each kind of tampering above, a pre-chain prefix, and compaction followed by verification. Report back what you built and the exact rule you used to decide which records a compaction covers.
