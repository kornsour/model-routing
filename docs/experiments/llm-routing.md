# LLM model routing: does it actually save money?

## The claim under test

"Route easy requests to a cheap model and hard ones to an expensive model, and
you cut the bill." The counter-claim, heard from people who run these systems:
once you count the routing decision, the retries when the cheap model is
wrong, and the prompt cache you fragment by spreading one workload across
several models, routing costs the same or more than one well-chosen model.

Both claims are usually argued from per-token price lists. This harness
measures them on a fixed workload with a fixed grader, and reports the number
that decides the question: **cost per completed task**.

## Why this matters for non-engineering work

The workload here is deliberately not code: classification, extraction,
rewriting, arithmetic over tables, and policy questions over a shared
employee handbook. That is the shape of work a non-developer does in Claude
Cowork or ChatGPT Work. If a routing policy holds up on this workload, it is
an argument for rolling those tools out more broadly with a cost story that
survives scrutiny.

## Hypotheses

| # | Hypothesis | Where it shows up |
|---|---|---|
| H1 | Per-token prices do not predict cost per completed task. | exp01: rank by `cost/pass`, not `cost/task`. |
| H2 | The frontier model at low effort is on the accuracy/cost Pareto frontier, often beating the mid tier. | exp01/exp02: `all_opus_low` row. |
| H3 | An oracle router (perfect difficulty labels) saves less than the price gap suggests. | exp02: `oracle` vs `all_sonnet`. |
| H4 | Deployable routers (heuristic, classifier) recover only part of the oracle's saving, and the classifier's own call eats a visible share. | exp02: `router overhead` column. |
| H5 | Cascades win only when a real checker exists; self-reported confidence escalates too little or too much. | exp02: `cascade_checker` vs `cascade_confidence`, `escalations` column. |
| H6 | Splitting one context across models fragments the prompt cache; a single model on a shared context reads far more from cache. | exp02/exp03: `cache hit` per router and per candidate. |
| H7 | Harness floors dominate small requests: Codex headless carries ~18k scaffolding tokens, Claude headless ~600. | exp04: `mean prompt tokens`. |

## What gets measured, per call

Every call becomes one line in `calls.jsonl`: provider, model, effort, role
(`candidate` or `router`), uncached input tokens, cache-read tokens,
cache-write tokens, output tokens, thinking tokens, duration, the provider's
reported cost when it gives one (Claude CLI does), and the list-price cost
computed from `src/model_routing/data/pricing.toml` so both vendors are on
the same footing. Every task becomes one line in `outcomes.jsonl` with all
its calls, the grader verdict, and escalation count.

The report (`summary.md`) aggregates per router:

- **pass rate**, overall and by difficulty label
- **cost/task** and **cost/pass** (spend divided by passes: the headline)
- **router overhead**: share of spend on the routing decision
- **escalations**: cascade retries
- **cache hit**: cache-read tokens over all prompt tokens
- **p90 cost**: the tail, where the money usually is
- **★** on routers that are not dominated on (pass rate, cost/task)

## How the CLIs are driven

Both providers run the vendor's own CLI headless on the operator's personal
login, the same mechanism as career-manager's `claude-code/*` and `codex/*`
tiers. Two constraints follow:

1. **Local, personal use only.** Both vendors prohibit shipping a product that
   authenticates through a consumer subscription. This harness never leaves
   the laptop.
2. **Metered against the plan allowance at API rates.** Spend is real even
   when no invoice arrives, which is why every run prints list-price cost and
   accepts `--budget-usd`.

Claude flags (see `providers/claude_cli.py`): `--tools ""`,
`--setting-sources ""`, `--strict-mcp-config`, `--no-session-persistence`,
`--system-prompt`, `--max-turns 1`, `--max-budget-usd`, optional `--effort`
and `--json-schema`. Measured floor on 2026-09-18: 621 input tokens for a
one-line prompt. `--bare` is not used because it disables keychain reads and
therefore the login.

Codex flags (see `providers/codex_cli.py`): `exec --json --ephemeral
--ignore-user-config -s read-only -m <model> -c model_reasoning_effort=...`.
Measured floor: ~18k input tokens, ~10.6k of which were cache reads on the
second call. Codex reports no dollars, so its cost is list price only.

## Running

```bash
make setup
make smoke                                  # one Haiku call; prints usage + cost
make smoke PROVIDER=codex_cli               # one gpt-5.6-luna call
make estimate EXP=experiments/llm/exp01_baselines.toml
make run EXP=experiments/llm/exp01_baselines.toml LIMIT=5 BUDGET=0.50
make run EXP=experiments/llm/exp02_routing.toml BUDGET=5
make run EXP=experiments/llm/exp02_routing.toml BUDGET=5 COOLDOWN=300   # cold cache per router
make run EXP=experiments/llm/exp02_routing.toml SAMPLE=8 ROUTERS=oracle,cascade_checker BUDGET=1
make report RUN=results/exp02_routing/<stamp>
```

Run experiments back to back and sequentially. Prompt caches expire after
five minutes of inactivity, so a long pause mid-run makes the cache column
pessimistic for whichever router was running.

## Things the first validation run taught (2026-09-18)

A 6-task sample of exp02 across all seven routers cost $0.32 and surfaced
three harness facts worth knowing before reading any result:

- **Claude Code writes its prompt cache with the 1-hour TTL**, billed at 2x
  input rather than the 5-minute TTL's 1.25x. The CLI's reported cost was
  about 1.5x the naive list-price figure until the harness priced 1-hour
  writes correctly. The report's "1h-TTL writes" column shows the share. This
  is directly relevant to the "caching costs more than it saves" argument: a
  workload of mostly-unique prompts on Claude Code pays 2x on every write and
  reads back little.
- **Routers share caches.** Caches are model-scoped, not router-scoped. In
  `by_router` order a router that uses Haiku right after another router that
  used Haiku starts warm. Use `--cooldown-s 300` when the cache column is the
  thing being measured; expect the run to take 5 minutes longer per router.
- **A Haiku classifier call can cost as much as the task.** Haiku 4.5 has no
  effort control through the CLI, and it spent 500-900 thinking tokens per
  routing decision, which made router overhead 40% of spend for the
  classifier router. A router has to be much cheaper than the work it routes.

Two grader weaknesses were also fixed: the confidence cascade's appended
`CONFIDENCE:` line is stripped before grading, and the `number` grader reads
the final answer (last line, then bold, then last number) rather than the
first number in a verbose response.

## Reading the results honestly

- Single runs on ~38 tasks are noisy. A one-task difference in pass rate is
  1 in 38. Use `--trials 3` before believing a small gap, and read the
  per-difficulty table: routers earn or lose their money on the hard tail.
- Repeated trials are clustered by task in the platform's uncertainty
  intervals. Three trials of one prompt are still one distinct task for
  workload coverage; they measure response variability, not three independent
  examples.
- If `oracle` does not beat `all_sonnet` on cost/pass, either the difficulty
  labels are wrong or the task set has no cheap tail worth routing. Both are
  findings; fix the labels before blaming routing.
- The Claude CLI's `reported cost` column should agree with the list-price
  column to the cent. If it drifts, `pricing.toml` is stale.
- `cache hit` depends on order. `by_router` is the fair deployed comparison;
  `by_task` (exp03) is the interleaved, pessimistic one.

## Dashboard

`make dashboard` indexes every `results/<experiment>/<stamp>/` directory into
`results/index.sqlite` (standard-library SQLite; the JSONL files stay the
source of truth and the index is rebuilt from them) and writes
`results/dashboard.html`, a single self-contained page: run history, an
evidence table that scores each hypothesis from that run's numbers, the
Pareto scatter, cost per task split by token type, the router table, and a
task × router matrix that drills down to every model answer and grader
verdict. `make run` refreshes it automatically. Fake and estimate runs are
hidden by default.

The verdicts in `src/model_routing/findings.py` are deliberately mechanical
(thresholds are in the code) so they can be argued with; the overview counts
verdicts across runs because one run is one trial. The SQLite file is also
there for ad-hoc questions:

```bash
sqlite3 results/index.sqlite "select router, avg(passed), sum(cost_usd) from outcomes group by router"
```

## Promoting findings

`results/` is git-ignored. When a run says something, copy its `summary.md`
into `docs/experiments/findings/<date>-<experiment>.md` with two or three
sentences of interpretation and the run's `meta.json` provider versions.

## Auth: subscription or API key

Experiment configs take an optional `[auth]` section (see `src/model_routing/auth.py`).
`mode = "subscription"` (default) runs `claude -p` / `codex exec` on the local login and
removes `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` etc. from the child environment.
`mode = "api_key"` reads the key from `api_key_env` (default `ANTHROPIC_API_KEY` for Claude,
`OPENAI_API_KEY` for Codex) and passes it to the CLI; keys never live in the config file.
Override per provider with `[auth.claude_cli]` / `[auth.codex_cli]`.
