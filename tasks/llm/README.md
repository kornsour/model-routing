# LLM task sets

Each task set is a JSONL file; one task per line:

```json
{"id": "hb-mileage-01", "difficulty": "hard", "category": "policy",
 "context": "handbook.md", "prompt": "...", "grader": {"type": "number", "value": 405.4, "tol": 0.01}}
```

Fields: `id` (unique), `prompt`, `grader` (see `model_routing/graders.py`),
`difficulty` (`easy|medium|hard`, a human label the oracle router uses),
`category`, optional `context` (a file under `context/`, prepended as system
context), optional `schema` (JSON Schema for structured output), `tags`.

`context/handbook.md` is a fictional employee handbook, ~2,900 words / ~4,000+
tokens, deliberately longer than Haiku 4.5's 4,096-token minimum cacheable
prefix so that prompt caching is observable on every candidate model.
Tasks tagged `context` ask questions about it; a run of many such tasks on
one model is the caching-favorable case, and routing them across models is
the cache-fragmenting case.

Difficulty labels are the author's judgment and are only used by the `oracle`
router and the per-difficulty breakdown. If the oracle does not beat the
baselines, the labels (or the tasks) are wrong, which is itself a finding.
