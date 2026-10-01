---
title: Capacity planner that survives scheduling anomalies
terse: Add exhaustive capacity search and anomaly detection to orchestra, and a cost-optimal planner plus CLI to ledger, without assuming more capacity is never slower.
repo: platform
parent: platform
allowed: ["packages/orchestra/*", "packages/ledger/*", "docs/*", "README.md"]
category: feature
tags: [long-horizon, multi-package, search, scheduling]
stratum: B
max_turns: 80
harvest_shape: "investigation-backed feature with a counter-intuitive prior finding the implementer must not paper over (harvested #12/#21 style: the measured fact is the point)"
authorship: "Brief drafted from the shape of harvested dispatches by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
Ops sizes the warehouse and API pools for each pipeline by hand, and the nightly SLA was missed twice in September. I want a planner: given a pipeline's job specs, an SLA and a range of capacities per pool, find the capacities to buy. You are in the `platform` monorepo (current directory); `python -m pytest -q` runs every suite.

## Prior findings — read before designing anything

An earlier attempt binary-searched each pool independently ("find the smallest capacity that meets the SLA"), which assumes **adding capacity never makes a run slower**. That assumption is false for orchestra's scheduler. It is greedy list scheduling (see the `orchestra.scheduler` docstring), and list scheduling has Graham's anomalies: with Graham's classic nine-job example, one warehouse pool and priorities in list order, the makespan is 12 with 3 slots, **15 with 4**, and 12 again with 5. The binary search answered "5" for an SLA of 13 when 3 was enough. So: no monotonicity assumptions anywhere. The search spaces are small (a few pools, single-digit capacities), so exhaustive search is fine and is what I want.

## orchestra: `orchestra.planning` (new module)

1. `simulate(specs, capacities) -> RunResult | None` — runs the scheduler, returning `None` when the capacities cannot run some job at all (the scheduler raises `PoolError` for a job needing more of a pool than its capacity). Pools a job needs that are missing from `capacities` are an error, as in the scheduler.
2. `feasible(specs, capacities, sla) -> bool` — true when `simulate` returns a result in which **every** job succeeded and `makespan <= sla`.
3. `search(specs, bounds, sla) -> Plan | None` — `bounds` maps each pool to an inclusive `(lo, hi)` integer range (`1 <= lo <= hi`, else `ValueError`). Try every combination; among feasible ones choose the fewest total units (sum of capacities), breaking ties by lower makespan, then by the capacities compared as a tuple in sorted pool-name order (smaller first). `Plan` is a frozen dataclass: `capacities: dict[str, int]`, `makespan: float`, `units: int`. `None` when nothing is feasible.
4. `anomalies(specs, pool, capacities, lo, hi) -> list[int]` — holding every other pool at `capacities`, the values `c` in `lo .. hi-1` for which capacity `c + 1` gives a strictly **longer** makespan than `c`. Values where either run is impossible are skipped. This is the evidence an operator needs before trusting any rule of thumb, so it is part of the deliverable, not a debugging aid.
5. Document the anomaly (with the 3/4/5 example) in the module docstring, and add the module to the orchestra README.

## ledger: cost-optimal plans

6. `ledger.planner.cheapest(specs, bounds, sla, rates) -> PricedPlan | None`. Capacity is reserved for the whole run, so a plan costs `sum(capacity[pool] * rate[pool]) * makespan`. Among feasible combinations choose the lowest cost, breaking ties exactly as `search` does after cost (makespan, then capacities tuple). `PricedPlan`: `capacities`, `makespan`, `cost`. Note the cheapest plan is often **not** the one with the fewest units: a bigger pool that finishes sooner can cost less.
7. `ledger plan SPECS.json --sla S --bounds pool=lo:hi[,pool=lo:hi...] [--objective units|cost] [--rates R]` prints three lines: `capacities: api=1 warehouse=3` (pools sorted), `makespan: 12.0`, and `cost: $156.0000` (the plan's reserved-capacity cost at the given rates, whichever objective chose it). With nothing feasible it prints `no feasible plan` and exits 1. `--objective` defaults to `cost`.

## Constraints

- Stdlib only. `ledger` must not import `_`-prefixed names from `orchestra`.
- Tests in each package's `tests/`, including Graham's example (durations 3, 2, 2, 2, 4, 4, 4, 4, 9; job 9 depends on job 1; jobs 5-8 depend on job 4; priorities in list order) showing the 3/4/5 anomaly and that `search` is not fooled by it.
- Report back what you built, the search order you implemented, and the anomaly output for Graham's example over capacities 1-6.
