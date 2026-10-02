import pytest

from triage.actions import Action, ApprovalRequired, approve, execute_action
from triage.audit import AuditLog


def test_risky_action_needs_approval():
    with pytest.raises(ApprovalRequired):
        execute_action(Action("a1", "reset_password", 2), AuditLog())


def test_approved_action_runs():
    action = Action("a2", "reset_password", 2)
    approve(action, "lead", "dana")
    assert execute_action(action, AuditLog()).startswith("executed")


def test_agents_cannot_approve():
    with pytest.raises(PermissionError):
        approve(Action("a3", "x", 2), "agent", "eve")
