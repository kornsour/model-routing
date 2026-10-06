# exp07 analysis

52 tasks in the run; 45 easy (primary set).

## Hypotheses

|  | estimate [95% CI] | bound | verdict |
| --- | --- | --- | --- |
| E1 cost: cpt evidence / standard (easy) | 0.61 [0.55, 0.69] | upper < 1.0 | supported |
| E1 completion: evidence - standard, pts (easy) | 0.0 [-3.7, 3.0] | lower > -10 | supported |
| **E1** |  | both | **supported** |
| E2: cpt evidence / static Sonnet (easy) | 1.16 [1.08, 1.27] | upper < 1.25 | inconclusive (p 0.057, Holm 0.057) |
| E3: evidence-labelled share, evidence - standard (easy) | n/a n/a | lower > 0 | descriptive (few events) (p n/a, Holm n/a; 0 evidence-arm requests) |

## Arms

| arm | easy: pass [CI] | easy: cpt [CI] | all: cpt | requests/cell mean, median, p90, max | cells with no request | advisor share of cost | handoff | ESCALATE | evidence-labelled share (easy) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ladder_evidence | 95% [88%, 100%] | $0.299 [0.259, 0.340] | $0.318 | 0.00, 0, 0.0, 0 | 100% | 0% | 3% | 2% | n/a |
| ladder_noforce | 95% [89%, 99%] | $0.487 [0.398, 0.576] | $0.518 | 0.56, 0, 2.0, 7 | 61% | 30% | 4% | 3% | 43% |
| static_sonnet | 94% [87%, 99%] | $0.257 [0.220, 0.295] | $0.278 | 0.00, 0, 0.0, 0 | 100% | 0% | 0% | 0% | n/a |

## Medium and hard tasks (descriptive)

| task | label | calibrated Sonnet pass rate | ladder_evidence | ladder_noforce | static_sonnet |
| --- | --- | --- | --- | --- | --- |
| ha-claims-audit-04 | hard | 33% | PPP | PPP | PPP |
| ha-runner-class-01 | medium | 67% | PPP | PPP | PPP |
| hb-config-layers-09 | hard | 33% | Pff | PPP | fPP |
| hb-incidents-11 | hard | 0% | fff | fff | fff |
| hb-money-ledger-01 | hard | 33% | PPP | fff | PPf |
| hc-run-json-04 | hard | 0% | PPP | PPP | PPf |
| tb-cron-03 | medium | 67% | PPP | PPP | PPf |

Advisor input tokens per counted request (median per cell; a real read is
at least ~31k, so much lower values mean the requests are over-counted):

- ladder_evidence: n/a
- ladder_noforce: 44,806
- static_sonnet: n/a

## Advisor requests

Logged by the hook: 0; seen in the session streams: 88.

| task | trial | arm | role | turn | label | source |
| --- | --- | --- | --- | --- | --- | --- |
| or-cancel-05 | 0 | ladder_noforce | worker | 12 | no_evidence | stream |
| or-retries-02 | 0 | ladder_noforce | worker | 8 | no_evidence | stream |
| or-retries-02 | 0 | ladder_noforce | worker | 20 | evidence_present | stream |
| or-starve-06 | 0 | ladder_noforce | worker | 22 | evidence_present | stream |
| or-store-03 | 0 | ladder_noforce | worker | 12 | no_evidence | stream |
| tb-cron-03 | 0 | ladder_noforce | worker | 13 | evidence_present | stream |
| tb-cron-03 | 0 | ladder_noforce | worker | 17 | evidence_present | stream |
| tb-duration-06 | 0 | ladder_noforce | worker | 4 | no_evidence | stream |
| tb-duration-06 | 0 | ladder_noforce | worker | 12 | evidence_present | stream |
| tb-glob-04 | 0 | ladder_noforce | worker | 13 | evidence_present | stream |
| tb-glob-04 | 0 | ladder_noforce | worker | 14 | evidence_present | stream |
| tb-jsonpatch-02 | 0 | ladder_noforce | worker | 10 | no_evidence | stream |
| tb-patch-05 | 0 | ladder_noforce | worker | 14 | no_evidence | stream |
| tb-semver-01 | 0 | ladder_noforce | worker | 18 | no_evidence | stream |
| tb-semver-01 | 0 | ladder_noforce | worker | 19 | no_evidence | stream |
| ha-claims-audit-13 | 0 | ladder_noforce | worker | 13 | no_evidence | stream |
| ha-ruleset-sweep-10 | 0 | ladder_noforce | worker | 37 | no_evidence | stream |
| hb-audit-chain-10 | 0 | ladder_noforce | worker | 6 | no_evidence | stream |
| hb-audit-chain-10 | 0 | ladder_noforce | worker | 23 | evidence_present | stream |
| hb-audit-chain-10 | 0 | ladder_noforce | worker | 25 | evidence_present | stream |
| hb-backoff-05 | 0 | ladder_noforce | worker | 37 | evidence_present | stream |
| hb-budget-policy-03 | 0 | ladder_noforce | worker | 22 | no_evidence | stream |
| hb-capacity-planner-08 | 0 | ladder_noforce | worker | 17 | no_evidence | stream |
| hb-capacity-planner-08 | 0 | ladder_noforce | worker | 21 | no_evidence | stream |
| hb-capacity-planner-08 | 0 | ladder_noforce | worker | 37 | evidence_present | stream |
| hb-config-layers-09 | 0 | ladder_noforce | worker | 9 | no_evidence | stream |
| hb-config-layers-09 | 0 | ladder_noforce | worker | 12 | no_evidence | stream |
| hb-config-layers-09 | 0 | ladder_noforce | worker | 35 | no_evidence | stream |
| hb-dashboard-export-12 | 0 | ladder_noforce | worker | 38 | no_evidence | stream |
| hb-heartbeat-02 | 0 | ladder_noforce | worker | 21 | no_evidence | stream |
| hb-ingest-04 | 0 | ladder_noforce | worker | 35 | evidence_present | stream |
| hb-money-ledger-01 | 0 | ladder_noforce | worker | 22 | evidence_present | stream |
| hb-store-migrations-07 | 0 | ladder_noforce | worker | 30 | no_evidence | stream |
| hc-humanize-01 | 0 | ladder_noforce | worker | 6 | no_evidence | stream |
| hc-parse-size-02 | 0 | ladder_noforce | worker | 14 | no_evidence | stream |
| or-cancel-05 | 1 | ladder_noforce | worker | 13 | no_evidence | stream |
| or-retries-02 | 1 | ladder_noforce | worker | 25 | evidence_present | stream |
| or-retries-02 | 1 | ladder_noforce | worker | 26 | evidence_present | stream |
| or-store-03 | 1 | ladder_noforce | worker | 14 | no_evidence | stream |
| tb-jsonpatch-02 | 1 | ladder_noforce | worker | 9 | no_evidence | stream |
| tb-patch-05 | 1 | ladder_noforce | worker | 19 | evidence_present | stream |
| ha-ruleset-sweep-10 | 1 | ladder_noforce | worker | 34 | no_evidence | stream |
| hb-audit-chain-10 | 1 | ladder_noforce | worker | 34 | evidence_present | stream |
| hb-backoff-05 | 1 | ladder_noforce | worker | 23 | no_evidence | stream |
| hb-budget-policy-03 | 1 | ladder_noforce | worker | 32 | no_evidence | stream |
| hb-budget-policy-03 | 1 | ladder_noforce | worker | 33 | no_evidence | stream |
| hb-config-layers-09 | 1 | ladder_noforce | worker | 30 | no_evidence | stream |
| hb-ingest-04 | 1 | ladder_noforce | worker | 39 | evidence_present | stream |
| hb-money-ledger-01 | 1 | ladder_noforce | worker | 11 | no_evidence | stream |
| hb-money-ledger-01 | 1 | ladder_noforce | worker | 38 | evidence_present | stream |
| hb-store-migrations-07 | 1 | ladder_noforce | worker | 35 | no_evidence | stream |
| hb-store-migrations-07 | 1 | ladder_noforce | worker | 36 | no_evidence | stream |
| hc-budget-warning-06 | 1 | ladder_noforce | worker | 23 | evidence_present | stream |
| hc-budget-warning-06 | 1 | ladder_noforce | worker | 24 | evidence_present | stream |
| hc-dedupe-events-03 | 1 | ladder_noforce | worker | 6 | no_evidence | stream |
| hc-humanize-01 | 1 | ladder_noforce | worker | 6 | no_evidence | stream |
| hc-parse-size-02 | 1 | ladder_noforce | worker | 14 | no_evidence | stream |
| or-perf-04 | 2 | ladder_noforce | worker | 25 | evidence_present | stream |
| or-retries-02 | 2 | ladder_noforce | worker | 27 | no_evidence | stream |
| or-starve-06 | 2 | ladder_noforce | worker | 18 | evidence_present | stream |
| or-starve-06 | 2 | ladder_noforce | worker | 19 | evidence_present | stream |
| or-store-03 | 2 | ladder_noforce | worker | 12 | no_evidence | stream |
| tb-glob-04 | 2 | ladder_noforce | worker | 13 | evidence_present | stream |
| tb-glob-04 | 2 | ladder_noforce | worker | 19 | evidence_present | stream |
| tb-money-08 | 2 | ladder_noforce | worker | 16 | evidence_present | stream |
| tb-patch-05 | 2 | ladder_noforce | worker | 20 | evidence_present | stream |
| tb-semver-01 | 2 | ladder_noforce | worker | 15 | no_evidence | stream |
| tb-semver-01 | 2 | ladder_noforce | worker | 16 | no_evidence | stream |
| hb-backoff-05 | 2 | ladder_noforce | worker | 9 | no_evidence | stream |
| hb-budget-policy-03 | 2 | ladder_noforce | worker | 27 | no_evidence | stream |
| hb-budget-policy-03 | 2 | ladder_noforce | worker | 33 | evidence_present | stream |
| hb-budget-policy-03 | 2 | ladder_noforce | worker | 37 | evidence_present | stream |
| hb-budget-policy-03 | 2 | ladder_noforce | worker | 39 | evidence_present | stream |
| hb-budget-policy-03 | 2 | ladder_noforce | worker | 42 | evidence_present | stream |
| hb-budget-policy-03 | 2 | ladder_noforce | worker | 44 | evidence_present | stream |
| hb-budget-policy-03 | 2 | ladder_noforce | worker | 45 | evidence_present | stream |
| hb-capacity-planner-08 | 2 | ladder_noforce | worker | 52 | evidence_present | stream |
| hb-config-layers-09 | 2 | ladder_noforce | worker | 8 | no_evidence | stream |
| hb-config-layers-09 | 2 | ladder_noforce | worker | 33 | evidence_present | stream |
| hb-dashboard-export-12 | 2 | ladder_noforce | worker | 34 | no_evidence | stream |
| hb-ingest-04 | 2 | ladder_noforce | worker | 52 | evidence_present | stream |
| hb-money-ledger-01 | 2 | ladder_noforce | worker | 49 | evidence_present | stream |
| hb-report-06 | 2 | ladder_noforce | worker | 31 | no_evidence | stream |
| hb-report-06 | 2 | ladder_noforce | worker | 32 | no_evidence | stream |
| hb-store-migrations-07 | 2 | ladder_noforce | worker | 37 | no_evidence | stream |
| hc-budget-warning-06 | 2 | ladder_noforce | worker | 22 | no_evidence | stream |
| hc-humanize-01 | 2 | ladder_noforce | worker | 6 | no_evidence | stream |
| hc-run-json-04 | 2 | ladder_noforce | worker | 14 | no_evidence | stream |
