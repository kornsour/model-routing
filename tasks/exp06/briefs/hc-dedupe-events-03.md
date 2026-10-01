---
title: Dashboard replay breaks on resent events
terse: Make orchestra's event replay tolerate the duplicate events the runner sends after a reconnect.
repo: orchestra
allowed: ["src/orchestra/*", "tests/*.py", "README.md", "docs/*"]
category: bugfix
tags: [ambiguous, events, idempotency]
stratum: C
max_turns: 40
missing_requirement: "What counts as a duplicate and which copy wins is not stated; docs/runner-protocol.md defines the identity (job, kind, attempt) and says the first copy received is authoritative."
answer_key: {"question": "How do I recognise a duplicate, and which copy should win?", "answer": "Per docs/runner-protocol.md: an event's identity is (job, kind, attempt); keep the first copy received and drop every later copy wherever it appears, even if its time or detail differ."}
harvest_shape: "production symptom with a log excerpt and a one-line ask (harvested #18 style)"
authorship: "Brief drafted from the shape of harvested chips by Claude Opus 5.5; fixture, hidden tests and reference solution by Claude Opus 5.5 (same family as the models under test)."
---
Since the runner moved behind the new message bus, the pipeline dashboard occasionally shows nonsense after a network blip: last night `load_orders` showed "attempt 2, running" for an hour after it had succeeded, and a job that failed once was shown as waiting for a retry that had already happened. The runner resends events after a reconnect, and the dashboard rebuilds job states from the event log with `orchestra.events.replay`, which assumes each event appears once.

Please make the replay robust to resent events: add `orchestra.events.dedupe(events) -> list[Event]` and have `replay` use it, so the rebuilt states match what the run actually did. Add tests and keep `python -m pytest -q` green.
