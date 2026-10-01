# Runner log lines

The job runner writes one line per finished attempt. The log shipper parses
these lines and the on-call alerts match on them, so their shape is a
contract.

```
<timestamp> job=<name> attempt=<n> status=<ok|fail> took=<duration>
```

## Samples from the legacy (Go) runner, August 2026

```
2026-08-30T02:14:07Z job=load_orders attempt=1 status=ok took=2h 3m
2026-08-30T02:16:09Z job=refresh_cache attempt=1 status=ok took=45s
2026-08-30T02:17:09Z job=ping attempt=1 status=ok took=1m 0s
2026-08-30T03:58:12Z job=noop attempt=1 status=ok took=0s
2026-08-31T04:00:00Z job=backfill attempt=2 status=fail took=1d 0h
2026-08-31T04:02:00Z job=compact attempt=1 status=ok took=3h 59m
```

The shipper's pattern for the duration is `took=(\d+[dhms])( \d+[dhms])?`.
The Go runner computed it from whole seconds (it never rounded up: a 3h 59m
59s compaction logged as `3h 59m`).
