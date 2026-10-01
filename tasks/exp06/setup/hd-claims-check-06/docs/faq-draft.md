# orchestra FAQ (DRAFT - not yet reviewed)

Written from memory by the platform team for the new-starter wiki. Each
answer below is a claim about how orchestra behaves today.

- **F1.** A job with `max_attempts: 3` runs at most three attempts, however its outcomes are set.
- **F2.** Retry delays double with each failed attempt and never exceed the job's `max_backoff`.
- **F3.** When two runnable jobs have the same priority, the one requesting more resources starts first, so big jobs are not starved.
- **F4.** If the highest-priority runnable job cannot get its resources, nothing else starts in that step either, so priorities are strict.
- **F5.** When a job fails for good, every job downstream of it (not just its direct dependents) is marked `upstream_failed` in that same step.
- **F6.** A run's makespan includes the time at which jobs were marked `upstream_failed`.
- **F7.** `orchestra.store` refuses to load a saved run whose format version is not the current one.
- **F8.** Rebuilding job states from the event log (`orchestra.events.replay`) restores the `retry_at` of a job that is waiting to retry.
- **F9.** You can set a resource pool's capacity to 0 to switch it off; jobs that need it are then skipped.
- **F10.** `JobSpec.from_dict` ignores fields it does not know, so old spec files with extra keys still load.
