---
title: Audit triage-desk claims
terse: Check the triage-desk repo's documented capabilities against its code and report what is verified, what is a gap, and which open issues cover the gaps.
repo: triage-desk
parent: harvested
allowed: ["REPORT.md"]
category: investigation
tags: [harvested, read-only, audit, python]
stratum: A
max_turns: 40
agent_bash: ["git:*", "grep:*", "rg:*", "find:*", "wc:*", "head:*", "make:*"]
harvest_id: 8216cd3ff9145a4b
draw_position: 27
adaptations: "Personal account, repo and site renamed; absolute path replaced by the working directory; offline note added (gh issue list result given inline, report also written to REPORT.md ending in a json block for grading). Fixture repo written for the task (stdlib only, runs offline)."
authorship: "Brief: harvested text (parent model wrote it). Fixture, hidden tests and reference solution: Claude Opus 5.5 (same family as the models under test); no cross-family re-derivation."
---
> **Offline note (added when this handoff was converted to a fixture task).** The repo is the current working directory; there is no network and no `gh`. `python -m pytest -q` runs the suite offline. `gh issue list -R ellisport/triage-desk --state open --limit 100` returns: #9 "Dark mode for the web UI", #11 "Architecture diagram in docs", #14 "Enforce RBAC on every API route". Besides returning your report as your final message, write it to `REPORT.md` at the repo root (the one file you may create; it is what gets read) and end it with a fenced `json` block of exactly this shape: `{"capabilities": {"mcp_server": V, "rbac_enforced": V, "audit_hash_chain": V, "approval_gate_server_side": V, "rag_data_governance": V, "eval_gates_ci": V, "web_ui": V, "runs_offline": V}, "open_issues_covering_gaps": [issue numbers]}` with each V `"VERIFIED"` or `"GAP"`.

You are auditing a PUBLIC portfolio repo to see whether the code actually delivers what its own documentation and the owner's portfolio site claim about it. READ-ONLY: do not modify any file, do not create branches, do not create GitHub issues. Report findings back as your final text.

Repo: `ellisport/triage-desk`, local checkout at the current working directory (level with origin/main).

THE CLAIMS TO VERIFY

1. The portfolio site (the owner's personal site) describes it verbatim as:
"An enterprise agentic system that triages an IT/Ops queue end to end: retrieves context, drafts grounded responses, and takes guarded actions behind human-approval gates, with RBAC, a hash-chained audit trail, and every release gated by an evaluation harness."
Tech listed: Python, FastAPI, React, TypeScript, MCP.

2. The GitHub repo description: "Enterprise agentic IT/Ops support triage: a multi-step LLM agent with an MCP server, RBAC + human-approval gates, hash-chained audit, RAG with data governance, and an eval-gated CI pipeline. Python/FastAPI + React/TS; runs fully offline."

3. Everything the repo's own README.md and docs/ assert about capabilities, architecture, and status.

WHAT TO DO

- Read README.md and everything under docs/ first; enumerate every concrete capability claim it makes.
- Then verify each claim against the actual code: src/, mcp_server/, web/, evals/, tests/, knowledge_base/, Makefile, pyproject.toml, and CI config under .github/workflows/.
- Specifically check: is there a real MCP server (tools registered, transport wired)? Is RBAC actually enforced at request paths, or just a data model? Is the audit chain really hash-chained AND verified (is there a verify function + a test that detects tampering)? Is the approval gate enforced server-side before an action executes? Does RAG exist with the "data governance" the docs claim? Does the eval harness actually gate CI (a workflow that fails the build on a threshold), or does it merely exist as a script? Does the React/TS web UI exist and cover the flows described? Does "runs fully offline" hold (is there a local/mock model path that works with no API key)?
- Run the test suite if it's cheap and self-contained (`uv run pytest` or per the Makefile) to see what actually passes. Do NOT install heavy dependencies or make network calls to paid APIs. If running is impractical, say so rather than guessing.
- Check existing open issues with `gh issue list -R ellisport/triage-desk --state open --limit 100` so we don't duplicate.

REPORT FORMAT (your final message is the deliverable — be concrete and evidence-backed)

Section 1 — VERIFIED: claims the code genuinely supports, one line each with the file path that proves it.
Section 2 — GAPS: claims that are absent, partial, stubbed, untested, or weaker than stated. For each gap give: (a) the exact claim and where it's made, (b) what actually exists, with file paths and line numbers, (c) what concrete work would close the gap, sized as a single GitHub issue. Be specific enough that an engineer could start work from your description alone.
Section 3 — EXISTING OPEN ISSUES: numbers + titles, and flag any that already cover a gap you found.

Precision matters far more than volume. Do not report a gap you have not actually confirmed by reading the code — a false gap costs more than a missed one here. If a claim is fully met, say so plainly.
