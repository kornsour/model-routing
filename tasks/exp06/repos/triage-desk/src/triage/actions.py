"""Guarded actions. Anything above risk 1 needs an approval first."""

from dataclasses import dataclass

from triage.audit import AuditLog


@dataclass
class Action:
    id: str
    kind: str
    risk: int
    approved_by: str | None = None


class ApprovalRequired(Exception):
    pass


def approve(action: Action, approver_role: str, approver: str) -> None:
    from triage.rbac import require

    require(approver_role, "action:approve")
    action.approved_by = approver


def execute_action(action: Action, audit: AuditLog) -> str:
    if action.risk > 1 and not action.approved_by:
        audit.append({"type": "action_blocked", "action": action.id})
        raise ApprovalRequired(action.id)
    audit.append({"type": "action_executed", "action": action.id, "approved_by": action.approved_by})
    return f"executed {action.kind}"
