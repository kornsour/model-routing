"""Roles and permissions."""

ROLE_PERMISSIONS = {
    "agent": {"ticket:read", "ticket:reply"},
    "lead": {"ticket:read", "ticket:reply", "action:approve"},
    "admin": {"ticket:read", "ticket:reply", "action:approve", "admin:config"},
}


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def require(role: str, permission: str) -> None:
    if not has_permission(role, permission):
        raise PermissionError(f"{role} lacks {permission}")
