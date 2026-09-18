# Routing beyond LLMs: the roadmap

The harness's core types are paradigm-agnostic on purpose. A routing
experiment in any paradigm has the same skeleton:

| Concept | LLM (implemented) | Tabular | Computer vision | Search / retrieval |
|---|---|---|---|---|
| **Task** | prompt + grader | a row (or batch) + label | an image + label/boxes | a query + relevance judgments |
| **Candidate** | provider + model + effort | GBDT vs. small NN vs. large NN; feature set size | tiny/medium/large backbone; input resolution | BM25 vs. dense vs. hybrid; rerank depth |
| **Cost** | tokens × list price (+ harness floor) | inference ms × instance price; feature-fetch cost | GPU ms × price; preprocessing | index bytes, QPS capacity, rerank calls |
| **Cache** | prompt cache, model-scoped | feature store / prediction cache | embedding cache | query result cache, embedding cache |
| **Router** | static / oracle / heuristic / classifier / cascade | confidence-threshold cascade; feature-availability gate | early-exit cascades; resolution gating | query-difficulty classifier; rerank-on-uncertainty |
| **Grader** | deterministic checks | metric on held-out labels | mAP / accuracy | nDCG / recall@k |

What carries over unchanged: `Task`, `Candidate`, `CallRecord` (usage becomes
whatever the resource unit is), `Outcome`, the runner's ordering discipline,
the budget guard, and the report's cost-per-completed-task framing and Pareto
frontier. What each paradigm adds: a provider that knows how to invoke its
models and measure their resource use, a pricing table in the right units,
and graders for its metric.

Suggested order, cheapest-to-instrument first:

1. **Tabular.** Fully local, deterministic, fast. Cascade a GBDT into a larger
   model on low-margin predictions; the "harness floor" analogue is feature
   fetch latency. Good for validating the report layer without spending.
2. **Search.** Cheap lexical retrieval with a dense reranker only on hard
   queries; the cache analogue (query result cache) is strong and easy to
   fragment, which mirrors the LLM prompt-cache story closely.
3. **Computer vision.** Resolution and backbone cascades; costs are GPU time,
   which needs a consistent measurement harness before the numbers mean
   anything.

Each paradigm gets its own `experiments/<paradigm>/` and
`tasks/<paradigm>/` directories, a provider module, and a pricing section.
