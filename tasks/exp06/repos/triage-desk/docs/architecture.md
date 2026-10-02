# Architecture

`triage.agent` runs a plan -> retrieve -> draft -> act loop. Retrieval goes
through `triage.rag.Retriever`, which filters chunks by the caller's
clearance against each document's `classification`. Actions go through
`triage.actions.execute_action`, which refuses anything unapproved above risk 1.
Every step appends to `triage.audit.AuditLog`.
