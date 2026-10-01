# Stored run format

The dashboard archive holds runs written by every orchestra release since 0.5,
so `orchestra.store` must read all of them. This page records the formats.

## Version 1 (orchestra 0.5)

```json
{
  "version": 1,
  "total_time": 6.0,
  "jobs": {
    "extract": {"status": "SUCCEEDED", "tries": 1, "start": 0.0, "end": 1.0},
    "load": {"status": "FAILED", "tries": 2, "start": 1.0, "end": 4.0},
    "report": {"status": "UPSTREAM_FAILED", "tries": 0, "start": null, "end": 4.0}
  },
  "log": [
    [0.0, "extract", "started", 1],
    [1.0, "extract", "succeeded", 1],
    [1.0, "load", "started", 1],
    [2.0, "load", "retrying", 1, 3.0],
    [3.0, "load", "started", 2],
    [4.0, "load", "failed", 2],
    [4.0, "report", "skipped_upstream", 0]
  ]
}
```

- `status` is one of `PENDING`, `RUNNING`, `WAITING` (waiting to retry),
  `SUCCEEDED`, `FAILED`, `UPSTREAM_FAILED`.
- `jobs` is an object, so v1 carries no job order: order jobs by name.
- `log` entries are `[time, job, kind, attempt]`; `retrying` entries carry a
  fifth element, the retry time. Kinds map to today's event kinds as
  `started` -> `start`, `succeeded` -> `success`, `failed` -> `fail`,
  `retrying` -> `retry`, `skipped_upstream` -> `upstream_failed`.
- v1 did not record reasons or retry times on jobs. When migrating, a
  `FAILED` job's reason (and its `fail` event's detail) is
  `attempt <tries> failed`; an `UPSTREAM_FAILED` job's reason and event detail
  are empty; a `retry` event's detail is the retry time written as Python's
  `repr()` of the float, as version 2 does. A `WAITING` job's `retry_at` is
  the retry time of its last `retrying` log entry; every other job's
  `retry_at` is null.

## Version 2 (orchestra 0.6 - 0.7)

What `store.dumps` writes today: `version`, `makespan`, `runs` (a list of
`JobRun.to_dict()` in run order) and `events` (a list of `Event.to_dict()`).

## Version 3 (orchestra 0.8)

Version 3 is what we write from now on. Archived runs are large, so events
are stored column-wise, and a checksum catches truncated or hand-edited
files.

```json
{
  "version": 3,
  "makespan": 6.0,
  "job_order": ["extract", "load", "report"],
  "runs": {"extract": {...JobRun fields without "name"...}, "...": {}},
  "events": {
    "time": [0.0, 1.0],
    "job": [0, 0],
    "kind": ["start", "success"],
    "attempt": [1, 1],
    "detail": ["", ""]
  },
  "checksum": "<hex>"
}
```

- `job_order` lists the jobs in run order; `runs` is keyed by job name and
  each value holds every `JobRun` field except `name`.
- `events.job` holds indices into `job_order`, not names. All five event
  columns have the same length.
- `checksum` is the SHA-256 hex digest of the canonical JSON of the document
  *without* the `checksum` key: `json.dumps(doc, sort_keys=True,
  separators=(",", ":"))`, UTF-8 encoded.
- `dumps` writes version 3 with `sort_keys=True` and an indent of 2.

## Reading

`loads` accepts versions 1, 2 and 3 and returns a `RunResult`. Older
versions are migrated one step at a time (v1 -> v2 -> v3) by
`migrate(doc)`, which returns a version 3 document (with a valid checksum)
and does not modify its argument. Anything else - an unknown or missing
version, a v3 checksum that doesn't match, event columns of different
lengths, an event job index out of range, a job in `runs` missing from
`job_order` or the other way round, an unknown status or event kind in v1 -
raises `ValueError`.
