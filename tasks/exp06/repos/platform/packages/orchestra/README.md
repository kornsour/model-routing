# orchestra

A small, deterministic scheduler for DAGs of batch jobs. The data platform uses
it two ways: to *simulate* a pipeline before rolling it out (how long will the
nightly run take with 4 warehouse slots? what happens if `load_orders` fails
twice?), and as the planning core of the real runner, which replays the same
decisions against real executors.

Everything runs on a simulated clock, so a run is a pure function of its job
specs and resource capacities: same input, same events, same final states.

## Layout

| module | role |
|---|---|
| `orchestra.model` | `JobSpec`, `State`, `JobRun`, `Event`, `RunResult` |
| `orchestra.dag` | building and validating the DAG, topological order |
| `orchestra.pool` | resource pools (warehouse slots, API quotas, ...) |
| `orchestra.retry` | retry back-off |
| `orchestra.scheduler` | the discrete-event run loop |
| `orchestra.events` | rebuilding job states from an event log |
| `orchestra.store` | saving and loading run results as JSON |
| `orchestra.cli` | `orchestra run pipeline.json` |

## Scheduling semantics

See the docstring of `orchestra.scheduler` - it is the reference for how a
run proceeds, and the tests hold it to that.

Run the tests with `python -m pytest -q`.
