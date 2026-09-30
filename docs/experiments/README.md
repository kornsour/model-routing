# Experiments

One folder per experiment, named `expNN-<slug>`. Each holds the design doc and,
where they exist, the pre-registration, findings, and paper. The `experiments/`
directory at the repo root holds the run configs (TOML); `tasks/` holds the
task sets, which are shared across experiments.

| Experiment | Question | Docs | Config | Harness code | Tasks |
| --- | --- | --- | --- | --- | --- |
| exp01-04 | Does routing between models lower cost per completed task on single-turn knowledge work? (baselines, routers, cache order, cross-vendor) | [`exp01-04-llm-routing/`](./exp01-04-llm-routing/design.md) | `experiments/exp01-04-llm-routing/exp0[1-4]_*.toml` | `single_turn/` (`runner.py`, `routers/`, `graders.py`, `report.py`) | `tasks/llm/` |
| exp05 | Does dispatch-time routing lower cost per completed task on agentic coding chips? | [`exp05-dispatch/`](./exp05-dispatch/design.md) | `experiments/exp05-dispatch/exp05_*.toml` | `dispatch/` | `tasks/agentic/` |
| exp06 | Route on evidence: hypothesis paper for a gate plus escalation ladder | [`exp06-route-on-evidence/`](./exp06-route-on-evidence/paper.md) | none yet | `dispatch/` (planned) | `tasks/agentic/` |
| exp07 | Does a third-party decision model (Jev) help as a routing gate? | [`exp07-jev-gate/`](./exp07-jev-gate/preregistration.md) | none yet | none yet | none yet |

Shared by all experiments: `providers/`, `pricing.py`, `store.py`, `types.py`.
The lab UI ([`../platform.md`](../platform.md)) is infrastructure, not an experiment.

## Conventions

- Findings go in `<experiment>/findings/<date>-<slug>.md`. `results/` is git-ignored.
- exp05 is pre-registered: the analysis plan is `exp05-dispatch/preregistration.md`, and
  `make dispatch-preregister` freezes the design and task-set hash into the config.
