from app.models.domain import (
    Permission,
    PermissionOverrides,
    PermissionProfile,
    User,
    UserRole,
)


PERMISSION_ORDER = [
    Permission.operations_write,
    Permission.supervisor_control,
    Permission.audit_read,
    Permission.setup_manage,
]

ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.agent: {Permission.operations_write},
    UserRole.supervisor: {
        Permission.operations_write,
        Permission.supervisor_control,
        Permission.audit_read,
    },
    UserRole.admin: set(PERMISSION_ORDER),
    UserRole.auditor: {Permission.audit_read},
    UserRole.service_account: {Permission.operations_write},
}

PROFILE_PERMISSIONS: dict[PermissionProfile, set[Permission]] = {
    PermissionProfile.read_only: set(),
    PermissionProfile.operations: {Permission.operations_write},
    PermissionProfile.supervisor: {
        Permission.operations_write,
        Permission.supervisor_control,
        Permission.audit_read,
    },
    PermissionProfile.admin: set(PERMISSION_ORDER),
    PermissionProfile.custom: set(),
}


def normalize_permission_overrides(value: object | None) -> PermissionOverrides:
    if value is None:
        return PermissionOverrides()
    if isinstance(value, PermissionOverrides):
        return value
    return PermissionOverrides.model_validate(value)


def effective_permissions_for(
    role: UserRole | str,
    permission_profile: PermissionProfile | str | None,
    permission_overrides: PermissionOverrides | dict | None,
) -> list[Permission]:
    resolved_role = role if isinstance(role, UserRole) else UserRole(role)
    resolved_profile = (
        permission_profile
        if isinstance(permission_profile, PermissionProfile)
        else PermissionProfile(permission_profile or PermissionProfile.role_default.value)
    )
    overrides = normalize_permission_overrides(permission_overrides)
    if resolved_profile == PermissionProfile.role_default:
        permissions = set(ROLE_PERMISSIONS[resolved_role])
    else:
        permissions = set(PROFILE_PERMISSIONS[resolved_profile])
    permissions.update(overrides.allow)
    permissions.difference_update(overrides.deny)
    return [permission for permission in PERMISSION_ORDER if permission in permissions]


def has_permission(user: User, permission: Permission) -> bool:
    return permission in set(user.effective_permissions)
