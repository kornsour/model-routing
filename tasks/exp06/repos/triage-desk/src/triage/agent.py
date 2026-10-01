"""Plan -> retrieve -> draft -> act."""

from triage.audit import AuditLog
from triage.llm import get_model
from triage.rag import Retriever


def triage_ticket(ticket: dict, audit: AuditLog, clearance: str = "public") -> dict:
    context = Retriever().search(ticket["subject"] + " " + ticket["body"], clearance=clearance)
    draft = get_model().complete(ticket["subject"] + "\n" + "\n".join(c.text for c in context))
    audit.append({"type": "drafted", "ticket": ticket["id"], "sources": [c.doc for c in context]})
    return {"ticket": ticket["id"], "draft": draft, "sources": [c.doc for c in context]}
