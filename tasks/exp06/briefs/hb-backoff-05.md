---
title: One backoff policy for the platform
terse: Move retry backoff into toolbelt.backoff, migrate orchestra to it behind a deprecated shim, and add a ledger retry-cost estimator built on it.
repo: platform
parent: platform
allowed: ["packages/toolbelt/*", "packages/orchestra/*", "packages/ledger/*", "docs/*", "README.md"]
category: refactor
tags: [long-horizon, multi-package, deprecation, math]
stratum: B
max_turns: 80
harvest_shape: "extract shared logic into the common package, migrate callers, keep a compatibility path (harvested #31/#43 style: build on existing modules, match their shape, document caveats)"
authorship: "Brief drafted from the shape of harvested implementation dispatches by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
Retry backoff lives in `orchestra.retry` today, and two more copies are about to be written: the runner's HTTP client wants the same policy, and finance wants ledger to estimate what a retry policy costs before a pipeline ships. One policy, in `toolbelt`, used by everyone — that is this change. You are in the `platform` monorepo (current directory); `python -m pytest -q` runs every suite.

## Prior findings

- `orchestra.retry.backoff_delay(spec, failed_attempt)` is `min(spec.backoff * 2 ** (failed_attempt - 1), spec.max_backoff)`. The factor 2 is hard-coded; two pipelines want 3.
- The scheduler is the only caller of `backoff_delay` inside the monorepo, but the runner and two notebooks import it, so it cannot simply disappear.
- Nobody wants jitter in the simulator (it would break determinism), but the HTTP client does, and its jitter must be reproducible in tests.

## Part 1 — `toolbelt.backoff`

1. `Backoff(base, factor=2.0, cap=math.inf, jitter="none", seed=None)`, a frozen dataclass. `base >= 0`, `factor >= 1`, `cap >= 0`, else `ValueError`. `jitter` is `"none"`, `"full"` or `"equal"` (anything else is a `ValueError`), and `seed` is required (an `int`) whenever jitter is not `"none"`.
2. `delay(failed_attempt) -> float`: `failed_attempt` is a 1-based `int` (`< 1`, a `bool` or a non-int is a `ValueError`/`TypeError` respectively). The un-jittered delay is `d = min(base * factor ** (failed_attempt - 1), cap)`. With `"full"` jitter the result is uniform in `[0, d]`; with `"equal"` it is `d / 2` plus uniform in `[0, d / 2]`. Jitter draws come from `random.Random(f"{seed}:{failed_attempt}")`, so the same seed and attempt always give the same delay, independently of call order.
3. `schedule(n) -> list[float]`: the delays after failed attempts `1..n`; `total(n) -> float`: their sum.
4. Document it in the module docstring and add it to the toolbelt README (create a module table there if there is none).

## Part 2 — orchestra uses it

5. `JobSpec` gains `backoff_factor: float = 2.0`, validated like `Backoff.factor`, included in `to_dict`, and optional in `from_dict` (old spec files without it must still load with factor 2).
6. The scheduler computes the retry delay as `Backoff(spec.backoff, spec.backoff_factor, spec.max_backoff).delay(failed_attempt)`, with no jitter. Update the scheduler docstring's reference to the delay.
7. `orchestra.retry.backoff_delay` stays importable as a deprecated shim with identical results; every call emits a `DeprecationWarning` naming `toolbelt.backoff`. `should_retry` stays as it is. A simulation run must not emit any `DeprecationWarning`.
8. Note the deprecation in the orchestra README's module table.

## Part 3 — ledger estimates retry cost

9. New module `ledger.estimate` with `estimate(spec, rates, p_fail) -> Estimate`, a frozen dataclass with `cost: float` (USD) and `seconds: float`. Assume each attempt fails independently with probability `p_fail` (`0 <= p_fail <= 1`, else `ValueError`) and the job retries up to `max_attempts`. Attempt `k` (1-based) happens with probability `p_fail ** (k - 1)`. Then:
   - `cost = sum over k of P(k) * duration * per_second_rate`, where the per-second rate is `sum(units * rate)` over the spec's resources (as in `ledger.pricing`);
   - `seconds = sum over k of P(k) * duration + sum over k = 1 .. max_attempts - 1 of P(k + 1) * delay(k)` — a backoff wait only happens if the next attempt does — with `delay` from the job's `Backoff` (no jitter).
10. `ledger estimate SPECS.json --p-fail P [--rates R]` prints one line per job in spec order, `f"{name:<24} ${cost:.4f} {seconds:.1f}s"`, then a `total` line in the same format with the summed cost and summed seconds.

## Constraints

- Stdlib only; no package imports another's `_`-prefixed names.
- Existing tests keep passing unchanged except where they assert the old hard-coded factor; add tests for each part in the owning package's `tests/`.
- Report back: the files changed per package, how the shim warns, and the closed-form you used for `seconds`.
