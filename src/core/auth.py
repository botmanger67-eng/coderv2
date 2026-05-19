"""
Authorization utilities for the application.

This module provides decorators and helper functions for role-based access control,
permission checking, and user authentication verification.
"""

from __future__ import annotations

import functools
import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, TypeVar, Union, cast

from flask import abort, current_app, g, request, session
from werkzeug.exceptions import Forbidden, Unauthorized

logger = logging.getLogger(__name__)

# Type variables for generic decorator support
F = TypeVar("F", bound=Callable[..., Any])
T = TypeVar("T")


class Permission(Enum):
    """Enumeration of all possible permissions in the system."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    VIEW_REPORTS = "view_reports"
    EXPORT_DATA = "export_data"
    IMPORT_DATA = "import_data"
    CONFIGURE_SYSTEM = "configure_system"
    AUDIT_LOGS = "audit_logs"


class Role(Enum):
    """Enumeration of predefined roles with associated permissions."""

    VIEWER = "viewer"
    EDITOR = "editor"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

    def get_permissions(self) -> Set[Permission]:
        """Get the set of permissions associated with this role.

        Returns:
            Set of Permission enums granted to this role.
        """
        role_permissions: Dict[Role, Set[Permission]] = {
            Role.VIEWER: {Permission.READ, Permission.VIEW_REPORTS},
            Role.EDITOR: {
                Permission.READ,
                Permission.WRITE,
                Permission.VIEW_REPORTS,
                Permission.EXPORT_DATA,
            },
            Role.MODERATOR: {
                Permission.READ,
                Permission.WRITE,
                Permission.DELETE,
                Permission.VIEW_REPORTS,
                Permission.EXPORT_DATA,
                Permission.MANAGE_USERS,
            },
            Role.ADMIN: {
                Permission.READ,
                Permission.WRITE,
                Permission.DELETE,
                Permission.ADMIN,
                Permission.MANAGE_USERS,
                Permission.MANAGE_ROLES,
                Permission.VIEW_REPORTS,
                Permission.EXPORT_DATA,
                Permission.IMPORT_DATA,
                Permission.CONFIGURE_SYSTEM,
                Permission.AUDIT_LOGS,
            },
            Role.SUPER_ADMIN: {
                permission for permission in Permission
            },
        }
        return role_permissions.get(self, set())


class AuthorizationError(Exception):
    """Custom exception for authorization failures."""

    def __init__(
        self,
        message: str = "Authorization failed",
        required_permissions: Optional[Sequence[Permission]] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Initialize the authorization error.

        Args:
            message: Human-readable error description.
            required_permissions: Permissions that were required but not granted.
            user_id: Identifier of the user who failed authorization.
        """
        self.message = message
        self.required_permissions = required_permissions or []
        self.user_id = user_id
        super().__init__(self.message)


def get_current_user_id() -> Optional[str]:
    """Retrieve the current user's identifier from the session.

    Returns:
        User ID string if authenticated, None otherwise.
    """
    return session.get("user_id")


def get_current_user_roles() -> List[Role]:
    """Retrieve the current user's roles from the session.

    Returns:
        List of Role enums assigned to the current user.
    """
    role_names: List[str] = session.get("roles", [])
    roles: List[Role] = []
    for role_name in role_names:
        try:
            roles.append(Role(role_name))
        except ValueError:
            logger.warning("Unknown role '%s' found in session", role_name)
    return roles


def get_current_user_permissions() -> Set[Permission]:
    """Compute the union of all permissions from the user's roles.

    Returns:
        Set of all Permission enums the current user possesses.
    """
    roles = get_current_user_roles()
    permissions: Set[Permission] = set()
    for role in roles:
        permissions.update(role.get_permissions())
    return permissions


def has_permission(permission: Permission) -> bool:
    """Check if the current user has a specific permission.

    Args:
        permission: The Permission to check.

    Returns:
        True if the user has the permission, False otherwise.
    """
    return permission in get_current_user_permissions()


def has_any_permission(*permissions: Permission) -> bool:
    """Check if the current user has at least one of the given permissions.

    Args:
        *permissions: Variable number of Permission enums to check.

    Returns:
        True if the user has any of the specified permissions.
    """
    user_permissions = get_current_user_permissions()
    return any(p in user_permissions for p in permissions)


def has_all_permissions(*permissions: Permission) -> bool:
    """Check if the current user has all of the given permissions.

    Args:
        *permissions: Variable number of Permission enums to check.

    Returns:
        True if the user has all specified permissions.
    """
    user_permissions = get_current_user_permissions()
    return all(p in user_permissions for p in permissions)


def require_authentication() -> None:
    """Ensure the current user is authenticated.

    Raises:
        Unauthorized: If no user is authenticated.
    """
    if get_current_user_id() is None:
        logger.warning("Unauthenticated access attempt")
        raise Unauthorized("Authentication required")


def require_permission(permission: Permission) -> None:
    """Ensure the current user has a specific permission.

    Args:
        permission: The required Permission.

    Raises:
        Forbidden: If the user lacks the required permission.
    """
    require_authentication()
    if not has_permission(permission):
        logger.warning(
            "User %s lacks permission '%s'",
            get_current_user_id(),
            permission.value,
        )
        raise Forbidden(f"Permission '{permission.value}' required")


def require_any_permission(*permissions: Permission) -> None:
    """Ensure the current user has at least one of the given permissions.

    Args:
        *permissions: Variable number of Permission enums.

    Raises:
        Forbidden: If the user has none of the specified permissions.
    """
    require_authentication()
    if not has_any_permission(*permissions):
        logger.warning(
            "User %s lacks any of the required permissions: %s",
            get_current_user_id(),
            [p.value for p in permissions],
        )
        raise Forbidden(
            f"At least one of the following permissions required: "
            f"{', '.join(p.value for p in permissions)}"
        )


def require_all_permissions(*permissions: Permission) -> None:
    """Ensure the current user has all of the given permissions.

    Args:
        *permissions: Variable number of Permission enums.

    Raises:
        Forbidden: If the user lacks any of the specified permissions.
    """
    require_authentication()
    if not has_all_permissions(*permissions):
        logger.warning(
            "User %s lacks all required permissions: %s",
            get_current_user_id(),
            [p.value for p in permissions],
        )
        raise Forbidden(
            f"All of the following permissions required: "
            f"{', '.join(p.value for p in permissions)}"
        )


def require_role(role: Role) -> None:
    """Ensure the current user has a specific role.

    Args:
        role: The required Role.

    Raises:
        Forbidden: If the user does not have the required role.
    """
    require_authentication()
    if role not in get_current_user_roles():
        logger.warning(
            "User %s lacks role '%s'",
            get_current_user_id(),
            role.value,
        )
        raise Forbidden(f"Role '{role.value}' required")


def require_any_role(*roles: Role) -> None:
    """Ensure the current user has at least one of the given roles.

    Args:
        *roles: Variable number of Role enums.

    Raises:
        Forbidden: If the user has none of the specified roles.
    """
    require_authentication()
    user_roles = get_current_user_roles()
    if not any(r in user_roles for r in roles):
        logger.warning(
            "User %s lacks any of the required roles: %s",
            get_current_user_id(),
            [r.value for r in roles],
        )
        raise Forbidden(
            f"At least one of the following roles required: "
            f"{', '.join(r.value for r in roles)}"
        )


def login_required(view_func: F) -> F:
    """Decorator that requires authentication for a view.

    Args:
        view_func: The view function to protect.

    Returns:
        Wrapped function that checks authentication before execution.
    """

    @functools.wraps(view_func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            require_authentication()
        except Unauthorized:
            abort(401)
        return view_func(*args, **kwargs)

    return cast(F, wrapper)


def permission_required(permission: Permission) -> Callable[[F], F]:
    """Decorator factory that requires a specific permission.

    Args:
        permission: The Permission required to access the view.

    Returns:
        A decorator that enforces the permission check.
    """

    def decorator(view_func: F) -> F:
        @functools.wraps(view_func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                require_permission(permission)
            except (Unauthorized, Forbidden):
                abort(403)
            return view_func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


def any_permission_required(*permissions: Permission) -> Callable[[F], F]:
    """Decorator factory that requires at least one of the given permissions.

    Args:
        *permissions: Variable number of Permission enums.

    Returns:
        A decorator that enforces the permission check.
    """

    def decorator(view_func: F) -> F:
        @functools.wraps(view_func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                require_any_permission(*permissions)
            except (Unauthorized, Forbidden):
                abort(403)
            return view_func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


def all_permissions_required(*permissions: Permission) -> Callable[[F], F]:
    """Decorator factory that requires all of the given permissions.

    Args:
        *permissions: Variable number of Permission enums.

    Returns:
        A decorator that enforces the permission check.
    """

    def decorator(view_func: F) -> F:
        @functools.wraps(view_func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                require_all_permissions(*permissions)
            except (Unauthorized, Forbidden):
                abort(403)
            return view_func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


def role_required(role: Role) -> Callable[[F], F]:
    """Decorator factory that requires a specific role.

    Args:
        role: The Role required to access the view.

    Returns:
        A decorator that enforces the role check.
    """

    def decorator(view_func: F) -> F:
        @functools.wraps(view_func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                require_role(role)
            except (Unauthorized, Forbidden):
                abort(403)
            return view_func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


def any_role_required(*roles: Role) -> Callable[[F], F]:
    """Decorator factory that requires at least one of the given roles.

    Args:
        *roles: Variable number of Role enums.

    Returns:
        A decorator that enforces the role check.
    """

    def decorator(view_func: F) -> F:
        @functools.wraps(view_func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                require_any_role(*roles)
            except (Unauthorized, Forbidden):
                abort(403)
            return view_func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


def authorize(
    user_id: str,
    required_permissions: Optional[Sequence[Permission]] = None,
    required_roles: Optional[Sequence[Role]] = None,
) -> bool:
    """Programmatic authorization check for a given user.

    Args:
        user_id: The identifier of the user to check.
        required_permissions: Optional list of required permissions.
        required_roles: Optional list of required roles.

    Returns:
        True if the user is authorized, False otherwise.

    Raises:
        AuthorizationError: If the user is not found or lacks required permissions/roles.
    """
    # In a real application, this would query a database or user service.
    # For demonstration, we assume the user exists and has roles from the session.
    if user_id != get_current_user_id():
        logger.error("User ID mismatch during authorization check")
        raise AuthorizationError("User not found", user_id=user_id)

    if required_permissions:
        if not has_all_permissions(*required_permissions):
            raise AuthorizationError(
                "Insufficient permissions",
                required_permissions=required_permissions,
                user_id=user_id,
            )

    if required_roles:
        user_roles = get_current_user_roles()
        if not any(r in user_roles for r in required_roles):
            raise AuthorizationError(
                "Insufficient roles",
                user_id=user_id,
            )

    return True


def get_user_permissions(user_id: str) -> Set[Permission]:
    """Retrieve all permissions for a given user.

    Args:
        user_id: The identifier of the user.

    Returns:
        Set of Permission enums the user possesses.

    Raises:
        AuthorizationError: If the user is not found.
    """
    if user_id != get_current_user_id():
        raise AuthorizationError("User not found", user_id=user_id)
    return get_current_user_permissions()


def get_user_roles(user_id: str) -> List[Role]:
    """Retrieve all roles for a given user.

    Args:
        user_id: The identifier of the user.

    Returns:
        List of Role enums assigned to the user.

    Raises:
        AuthorizationError: If the user is not found.
    """
    if user_id != get_current_user_id():
        raise AuthorizationError("User not found", user_id=user_id)
    return get_current_user_roles()