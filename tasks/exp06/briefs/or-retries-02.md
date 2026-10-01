---
title: Fix orchestra's retry behaviour and add timeouts, jitter and retry_on
terse: Fix orchestra retry bugs and add per-job timeout, jitter and retry_on.
repo: orchestra
allowed: ["src/orchestra/*.py", "tests/*.py", "README.md"]
category: bugfix
tags: [multi-module, scheduling, interacting-bugs]
---
The nightly simulation stopped matching what the real runner does whenever a job retries. Three things from the on-call notes:

- `load_orders` has `max_attempts = 3` and fails transiently, but the simulation only ever gives it two attempts, and the time between attempts is twice what the pipeline owner configured.
- While `load_orders` was waiting to retry, nothing else could use the warehouse slot it had been using, so the whole nightly run was predicted to take an hour longer than it really does. Conversely, when it was ready to retry it restarted immediately even though every slot was busy.
- Nobody can model a job that hangs: we need timeouts.

`src/orchestra/scheduler.py`'s module docstring is the reference for how a run proceeds; please make the code match it again and extend it (docstring included) with the features below. `retry.py` holds the back-off, `model.py` the `JobSpec`. Everything that isn't mentioned here must keep behaving exactly as the docstring describes.

Intended semantics (the docstring already states the first three; the code has drifted):

1. `max_attempts` is the total number of attempts including the first.
2. The delay after failed attempt *n* (1-based) is `backoff * 2 ** (n - 1)`, capped at `max_backoff`.
3. A job holds its resources only while an attempt is running. A job waiting to retry holds nothing, and once its `retry_at` has come it competes for resources in dispatch like any other candidate (priority, then name).

New `JobSpec` fields (all must round-trip through `to_dict`/`from_dict`):

- `timeout: float | None = None`. If set, it must be > 0. An attempt whose `duration` exceeds the timeout ends at `start + timeout` as a *timed-out* attempt, whatever its outcome would have been; an attempt whose duration equals the timeout is not timed out. A timed-out attempt is a failure for everything downstream (it releases resources, can be retried, and a final one makes the job `FAILED` with reason `attempt N timed out`; a final ordinary failure keeps `attempt N failed`).
- `jitter: float = 0.0`, between 0 and 1 inclusive. After the cap is applied, the delay is multiplied by `1 + jitter * f`, where `f` is a deterministic fraction for the job and the failed attempt number: take the SHA-256 hex digest of the UTF-8 string `"<job name>:<failed attempt>"`, read its first 8 hex digits as an integer, and divide by `2**32`. Expose that as `orchestra.retry.jitter_fraction(name, attempt)`. Runs must stay reproducible.
- `retry_on: tuple[str, ...] = ("fail", "timeout")`: which kinds of failed attempt may be retried. Only `"fail"` and `"timeout"` are allowed. A failed attempt whose kind isn't listed makes the job `FAILED` straight away, even if attempts remain.

Invalid values are a `ValueError` when the `JobSpec` is constructed. The `retry` event's detail is still the retry time, and `replay` and `store` must keep round-tripping results exactly. Add tests for all of this, including the retry-while-resources-are-busy cases, and keep `python -m pytest -q` green.
