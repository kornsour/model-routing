---
title: Fact-check the orchestra FAQ draft
terse: Check each claim in docs/faq-draft.md against orchestra's actual behaviour and record true/false in ANSWER.json.
repo: orchestra
allowed: ["ANSWER.json"]
category: investigation
tags: [read-only, investigation, documentation]
stratum: D
max_turns: 40
harvest_shape: "read-only claims audit: verify each documented claim against the code, precision over volume (harvested #7/#27: audit portfolio claims)"
authorship: "Brief drafted from the shape of harvested audit dispatches by Claude Opus 5.5; fixture, answer key and reference answer by Claude Opus 5.5 (same family as the models under test)."
---
READ-ONLY. Do not modify any file, including the draft. The only file you may create is `ANSWER.json` at the repo root.

The platform team wrote `docs/faq-draft.md` from memory for the new-starter wiki. Before it goes up, check every claim (F1 to F10) against what orchestra actually does today: the code and its tests are the ground truth (the `orchestra.scheduler` docstring is the documented contract and matches the code). You may run the code. A claim is `true` only if it holds as written; a claim that is partly right is `false`.

Answer in `ANSWER.json`, exactly this shape, one boolean per claim:

```json
{"F1": true, "F2": true, "F3": true, "F4": true, "F5": true,
 "F6": true, "F7": true, "F8": true, "F9": true, "F10": true}
```
