# triage-desk

Enterprise agentic IT/Ops support triage. A multi-step LLM agent reads the
queue, retrieves context, drafts grounded responses and takes guarded actions.

## Capabilities

- **MCP server** (`mcp_server/`): exposes `search_kb`, `get_ticket` and
  `propose_action` as MCP tools over stdio.
- **RBAC**: every API route checks the caller's role (`agent`, `lead`, `admin`)
  before acting.
- **Hash-chained audit trail**: every event is chained to the previous one by
  SHA-256; `verify_chain()` detects tampering.
- **Human-approval gates**: actions above risk level 1 wait for a lead's
  approval, enforced server-side before execution.
- **RAG with data governance**: retrieval honours document classification, so
  restricted runbooks never reach an agent without clearance.
- **Eval-gated CI**: every release must pass the eval harness at >= 0.85.
- **Web UI** (`web/`, React + TypeScript): queue, ticket detail and approvals.
- **Runs fully offline**: with no API key the agent uses a deterministic local
  model, so tests and demos need no network.

## Run

```bash
python -m pytest -q
python -m triage.api
```
