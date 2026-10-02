from triage.agent import triage_ticket
from triage.audit import AuditLog


def test_agent_runs_without_a_key(monkeypatch):
    monkeypatch.delenv("TRIAGE_API_KEY", raising=False)
    out = triage_ticket({"id": "T1", "subject": "VPN drops", "body": "hourly"}, AuditLog())
    assert out["draft"].startswith("[local]") and "vpn" in out["sources"]
