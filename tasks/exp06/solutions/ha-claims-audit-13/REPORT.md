# triage-desk: claims vs code

## Section 1 — VERIFIED
- MCP server: `mcp_server/server.py` registers `search_kb`, `get_ticket`, `propose_action`; JSON-RPC over stdio with `initialize`, `tools/list`, `tools/call` (`tests/test_mcp.py`).
- Hash-chained audit: `src/triage/audit.py` chains SHA-256 digests; `verify_chain()` exists and `tests/test_audit.py::test_tampering_is_detected` proves tamper detection.
- Approval gate: `execute_action` (`src/triage/actions.py`) refuses risk > 1 without `approved_by`, server-side.
- Web UI: `web/src/pages/` has Queue, Ticket and Approvals.
- Offline: `get_model()` falls back to `LocalModel` with no `TRIAGE_API_KEY`; the whole suite passes offline (7 passed).

## Section 2 — GAPS
1. **RBAC enforced at request paths** (README "every API route checks the caller's role"). Only `/actions/{id}/approve` calls `require` (via `approve`); `/tickets/triage`, `/actions`, `/actions/{id}/execute` and `/admin/audit` never check `X-Role` (`src/triage/api.py`). Fix: a `require(role, permission)` per route with a permission table and tests per role.
2. **RAG data governance** (README, `docs/architecture.md`). `Retriever.search` accepts `clearance` and ignores it (`src/triage/rag.py`); the restricted break-glass runbook is retrievable by anyone. Fix: filter chunks by `CLEARANCE[classification] <= CLEARANCE[clearance]`, plus a test.
3. **Eval-gated CI** (README). `evals/run_evals.py` exits 1 below 0.85, but the `evals` job has `continue-on-error: true` (`.github/workflows/ci.yml`), so it never blocks. Fix: drop `continue-on-error` and require the job.

## Section 3 — EXISTING OPEN ISSUES
#9 Dark mode for the web UI; #11 Architecture diagram in docs; #14 Enforce RBAC on every API route (covers gap 1).

```json
{"capabilities": {"mcp_server": "VERIFIED", "rbac_enforced": "GAP", "audit_hash_chain": "VERIFIED", "approval_gate_server_side": "VERIFIED", "rag_data_governance": "GAP", "eval_gates_ci": "GAP", "web_ui": "VERIFIED", "runs_offline": "VERIFIED"}, "open_issues_covering_gaps": [14]}
```
