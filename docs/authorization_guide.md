# Authorization Guide

## Overview

This document provides a comprehensive guide to the authorization system used in this enterprise application. It covers role-based access control (RBAC), permission management, token-based authentication, and best practices for implementing secure authorization flows.

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
3. [Permission Management](#permission-management)
4. [Token-Based Authorization](#token-based-authorization)
5. [Authorization Middleware](#authorization-middleware)
6. [API Endpoint Protection](#api-endpoint-protection)
7. [Error Handling](#error-handling)
8. [Testing Authorization](#testing-authorization)
9. [Security Best Practices](#security-best-practices)

## Core Concepts

### Authorization vs Authentication

- **Authentication**: Verifying the identity of a user (who you are)
- **Authorization**: Determining what resources a user can access (what you can do)

### Key Terminology

| Term | Definition |
|------|------------|
| **User** | An entity that can authenticate and access resources |
| **Role** | A named collection of permissions (e.g., Admin, Editor, Viewer) |
| **Permission** | A specific action that can be performed on a resource (e.g., `read:documents`, `write:documents`) |
| **Resource** | An object or service that requires authorization (e.g., API endpoint, file, database record) |
| **Token** | A signed credential containing user identity and claims |

## Role-Based Access Control (RBAC)

### Role Hierarchy

```python
from enum import Enum
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field


class Role(Enum):
    """Enumeration of available roles with hierarchical ordering."""
    
    VIEWER = 1
    EDITOR = 2
    ADMIN = 3
    SUPER_ADMIN = 4
    
    def __ge__(self, other: 'Role') -> bool:
        """Compare roles based on hierarchy level."""
        if not isinstance(other, Role):
            return NotImplemented
        return self.value >= other.value
    
    def __lt__(self, other: 'Role') -> bool:
        """Compare roles based on hierarchy level."""
        if not isinstance(other, Role):
            return NotImplemented
        return self.value < other.value


@dataclass
class RoleDefinition:
    """Defines a role with its associated permissions."""
    
    name: str
    level: int
    permissions: Set[str] = field(default_factory=set)
    parent_role: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate role definition after initialization."""
        if self.level < 0:
            raise ValueError(f"Role level must be non-negative, got {self.level}")
        if not self.name:
            raise ValueError("Role name cannot be empty")


class RoleManager:
    """Manages role definitions and hierarchy."""
    
    def __init__(self) -> None:
        """Initialize the role manager with default roles."""
        self._roles: Dict[str, RoleDefinition] = {}
        self._initialize_default_roles()
    
    def _initialize_default_roles(self) -> None:
        """Set up default role hierarchy with base permissions."""
        viewer_permissions: Set[str] = {"read:documents", "read:users"}
        editor_permissions: Set[str] = viewer_permissions | {"write:documents", "update:documents"}
        admin_permissions: Set[str] = editor_permissions | {"delete:documents", "manage:users"}
        super_admin_permissions: Set[str] = admin_permissions | {"manage:roles", "manage:system"}
        
        self._roles = {
            "viewer": RoleDefinition("viewer", 1, viewer_permissions),
            "editor": RoleDefinition("editor", 2, editor_permissions, "viewer"),
            "admin": RoleDefinition("admin", 3, admin_permissions, "editor"),
            "super_admin": RoleDefinition("super_admin", 4, super_admin_permissions, "admin"),
        }
    
    def get_role(self, role_name: str) -> RoleDefinition:
        """Retrieve a role definition by name.
        
        Args:
            role_name: The name of the role to retrieve.
        
        Returns:
            The RoleDefinition object.
        
        Raises:
            ValueError: If the role does not exist.
        """
        role = self._roles.get(role_name.lower())
        if role is None:
            raise ValueError(f"Role '{role_name}' not found")
        return role
    
    def get_all_permissions(self, role_name: str) -> Set[str]:
        """Get all permissions for a role, including inherited permissions.
        
        Args:
            role_name: The name of the role.
        
        Returns:
            A set of all permission strings.
        """
        role = self.get_role(role_name)
        permissions: Set[str] = set(role.permissions)
        
        if role.parent_role:
            parent_permissions = self.get_all_permissions(role.parent_role)
            permissions.update(parent_permissions)
        
        return permissions
    
    def has_permission(self, role_name: str, permission: str) -> bool:
        """Check if a role has a specific permission.
        
        Args:
            role_name: The name of the role.
            permission: The permission string to check.
        
        Returns:
            True if the role has the permission, False otherwise.
        """
        try:
            permissions = self.get_all_permissions(role_name)
            return permission in permissions
        except ValueError:
            return False
    
    def add_role(self, name: str, level: int, permissions: Set[str], 
                 parent_role: Optional[str] = None) -> None:
        """Add a new custom role.
        
        Args:
            name: The name of the new role.
            level: The hierarchy level (higher = more privileges).
            permissions: Set of permission strings.
            parent_role: Optional parent role name for inheritance.
        
        Raises:
            ValueError: If the role already exists or parent role is invalid.
        """
        if name.lower() in self._roles:
            raise ValueError(f"Role '{name}' already exists")
        
        if parent_role and parent_role.lower() not in self._roles:
            raise ValueError(f"Parent role '{parent_role}' not found")
        
        self._roles[name.lower()] = RoleDefinition(
            name=name.lower(),
            level=level,
            permissions=permissions,
            parent_role=parent_role.lower() if parent_role else None
        )
```

## Permission Management

### Permission String Format

Permissions follow the format: `action:resource`

- **Actions**: `create`, `read`, `update`, `delete`, `manage`, `execute`
- **Resources**: `documents`, `users`, `roles`, `system`, `reports`

### Permission Checker

```python
from typing import Any, Dict, List, Optional, Set, Union


class PermissionChecker:
    """Validates user permissions against required permissions."""
    
    def __init__(self, role_manager: RoleManager) -> None:
        """Initialize the permission checker.
        
        Args:
            role_manager: An instance of RoleManager.
        """
        self._role_manager = role_manager
    
    def check_permission(self, user_role: str, required_permission: str) -> bool:
        """Check if a user role has a specific permission.
        
        Args:
            user_role: The role of the user.
            required_permission: The permission required for the action.
        
        Returns:
            True if authorized, False otherwise.
        """
        if not user_role or not required_permission:
            return False
        
        return self._role_manager.has_permission(user_role, required_permission)
    
    def check_any_permission(self, user_role: str, 
                             required_permissions: List[str]) -> bool:
        """Check if a user role has any of the specified permissions.
        
        Args:
            user_role: The role of the user.
            required_permissions: List of permissions to check.
        
        Returns:
            True if the user has at least one of the permissions.
        """
        for permission in required_permissions:
            if self.check_permission(user_role, permission):
                return True
        return False
    
    def check_all_permissions(self, user_role: str, 
                              required_permissions: List[str]) -> bool:
        """Check if a user role has all specified permissions.
        
        Args:
            user_role: The role of the user.
            required_permissions: List of permissions to check.
        
        Returns:
            True if the user has all permissions.
        """
        for permission in required_permissions:
            if not self.check_permission(user_role, permission):
                return False
        return True
    
    def get_user_permissions(self, user_role: str) -> Set[str]:
        """Get all permissions for a user role.
        
        Args:
            user_role: The role of the user.
        
        Returns:
            Set of permission strings.
        """
        try:
            return self._role_manager.get_all_permissions(user_role)
        except ValueError:
            return set()
```

## Token-Based Authorization

### JWT Token Handler

```python
import hashlib
import hmac
import json
import time
from base64 import urlsafe_b64encode, urlsafe_b64decode
from typing import Any, Dict, Optional, Tuple


class JWTTokenHandler:
    """Handles JWT token creation, validation, and decoding."""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256", 
                 token_expiry: int = 3600) -> None:
        """Initialize the JWT token handler.
        
        Args:
            secret_key: The secret key for signing tokens.
            algorithm: The signing algorithm (default: HS256).
            token_expiry: Token expiration time in seconds (default: 3600).
        
        Raises:
            ValueError: If secret_key is empty or algorithm is unsupported.
        """
        if not secret_key:
            raise ValueError("Secret key cannot be empty")
        
        supported_algorithms = {"HS256", "HS384", "HS512"}
        if algorithm not in supported_algorithms:
            raise ValueError(f"Unsupported algorithm '{algorithm}'. "
                           f"Supported: {supported_algorithms}")
        
        self._secret_key: str = secret_key
        self._algorithm: str = algorithm
        self._token_expiry: int = token_expiry
    
    def _base64url_encode(self, data: bytes) -> str:
        """Encode bytes to base64url string without padding.
        
        Args:
            data: Bytes to encode.
        
        Returns:
            Base64url encoded string.
        """
        return urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')
    
    def _base64url_decode(self, data: str) -> bytes:
        """Decode base64url string to bytes, adding padding if needed.
        
        Args:
            data: Base64url encoded string.
        
        Returns:
            Decoded bytes.
        """
        padding = 4 - len(data) % 4
        if padding != 4:
            data += '=' * padding
        return urlsafe_b64decode(data)
    
    def _create_signature(self, header_b64: str, payload_b64: str) -> str:
        """Create HMAC signature for token.
        
        Args:
            header_b64: Base64url encoded header.
            payload_b64: Base64url encoded payload.
        
        Returns:
            Base64url encoded signature.
        """
        message = f"{header_b64}.{payload_b64}".encode('utf-8')
        
        hash_funcs = {
            "HS256": hashlib.sha256,
            "HS384": hashlib.sha384,
            "HS512": hashlib.sha512,
        }
        
        hash_func = hash_funcs.get(self._algorithm, hashlib.sha256)
        signature = hmac.new(
            self._secret_key.encode('utf-8'),
            message,
            hash_func
        ).digest()
        
        return self._base64url_encode(signature)
    
    def create_token(self, user_id: str, role: str, 
                     additional_claims: Optional[Dict[str, Any]] = None) -> str:
        """Create a new JWT token.
        
        Args:
            user_id: The user identifier.
            role: The user's role.
            additional_claims: Optional additional claims to include.
        
        Returns:
            A signed JWT token string.
        
        Raises:
            ValueError: If user_id or role is empty.
        """
        if not user_id:
            raise ValueError("User ID cannot be empty")
        if not role:
            raise ValueError("Role cannot be empty")
        
        header: Dict[str, str] = {
            "alg": self._algorithm,
            "typ": "JWT"
        }
        
        current_time: int = int(time.time())
        payload: Dict[str, Any] = {
            "sub": user_id,
            "role": role,
            "iat": current_time,
            "exp": current_time + self._token_expiry
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        header_b64: str = self._base64url_encode(json.dumps(header).encode('utf-8'))
        payload_b64: str = self._base64url_encode(json.dumps(payload).encode('utf-8'))
        signature_b64: str = self._create_signature(header_b64, payload_b64)
        
        return f"{header_b64}.{payload_b64}.{signature_b64}"
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate and decode a JWT token.
        
        Args:
            token: The JWT token string.
        
        Returns:
            The decoded payload if valid.
        
        Raises:
            ValueError: If the token is invalid, expired, or tampered.
        """
        parts: List[str] = token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid token format: expected 3 parts")
        
        header_b64, payload_b64, signature_b64 = parts
        
        # Verify signature
        expected_signature: str = self._create_signature(header_b64, payload_b64)
        if not hmac.compare_digest(signature_b64, expected_signature):
            raise ValueError("Invalid token signature")
        
        # Decode payload
        try:
            payload_bytes: bytes = self._base64url_decode(payload_b64)
            payload: Dict[str, Any] = json.loads(payload_bytes.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"Failed to decode token payload: {e}")
        
        # Check expiration
        current_time: int = int(time.time())
        exp: int = payload.get("exp", 0)
        if current_time > exp:
            raise ValueError("Token has expired")
        
        # Validate required claims
        if "sub" not in payload:
            raise ValueError("Token missing 'sub' claim")
        if "role" not in payload:
            raise ValueError("Token missing 'role' claim")
        
        return payload
    
    def refresh_token(self, token: str) -> str:
        """Refresh an existing valid token.
        
        Args:
            token: The existing valid token.
        
        Returns:
            A new token with updated expiration.
        
        Raises:
            ValueError: If the token is invalid.
        """
        payload = self.validate_token(token)
        
        # Remove old expiration and issued-at time
        payload.pop("exp", None)
        payload.pop("iat", None)
        
        return self.create_token(
            user_id=payload["sub"],
            role=payload["role"],
            additional_claims={k: v for k, v in payload.items() 
                             if k not in ("sub", "role")}
        )
```

## Authorization Middleware

### FastAPI Middleware Example

```python
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Any, Callable, Dict, List, Optional, Set, Union
import functools


class AuthorizationMiddleware:
    """Middleware for handling authorization in FastAPI applications."""
    
    def __init__(self, token_handler: JWTTokenHandler, 
                 permission_checker: PermissionChecker) -> None:
        """Initialize the authorization middleware.
        
        Args:
            token_handler: Instance of JWTTokenHandler.
            permission_checker: Instance of PermissionChecker.
        """
        self._token_handler: JWTTokenHandler = token_handler
        self._permission_checker: PermissionChecker = permission_checker
        self._security_scheme: HTTPBearer = HTTPBearer(auto_error=False)
    
    async def get_current_user(
        self, 
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(self._security_scheme)
    ) -> Dict[str, Any]:
        """Extract and validate the current user from the token.
        
        Args:
            credentials: The HTTP authorization credentials.
        
        Returns:
            Dictionary containing user information.
        
        Raises:
            HTTPException: If authentication fails.
        """
        if credentials is None:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        try:
            payload: Dict[str, Any] = self._token_handler.validate_token(
                credentials.credentials
            )
            return {
                "user_id": payload["sub"],
                "role": payload["role"],
                "claims": {k: v for k, v in payload.items() 
                          if k not in ("sub", "role", "iat", "exp")}
            }
        except ValueError as e:
            raise HTTPException(
                status_code=401,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    def require_permission(self, permission: str) -> Callable:
        """Decorator to require a specific permission for an endpoint.
        
        Args:
            permission: The required permission string.
        
        Returns:
            A decorator function.
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                user: Dict[str, Any] = kwargs.get("current_user", {})
                user_role: str = user.get("role", "")
                
                if not self._permission_checker.check_permission(user_role, permission):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Permission denied: requires '{permission}'"
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    def require_any_permission(self, permissions: List[str]) -> Callable:
        """Decorator to require any of the specified permissions.
        
        Args:
            permissions: List of permission strings.
        
        Returns:
            A decorator function.
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                user: Dict[str, Any] = kwargs.get("current_user", {})
                user_role: str = user.get("role", "")
                
                if not self._permission_checker.check_any_permission(user_role, permissions):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Permission denied: requires one of {permissions}"
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    def require_role(self, minimum_role: str) -> Callable:
        """Decorator to require a minimum role level.
        
        Args:
            minimum_role: The minimum role required.
        
        Returns:
            A decorator function.
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                user: Dict[str, Any] = kwargs.get("current_user", {})
                user_role: str = user.get("role", "")
                
                try:
                    role_manager = RoleManager()
                    user_role_def = role_manager.get_role(user_role)
                    min_role_def = role_manager.get_role(minimum_role)
                    
                    if user_role_def.level < min_role_def.level:
                        raise HTTPException(
                            status_code=403,
                            detail=f"Role '{user_role}' insufficient. "
                                   f"Requires at least '{minimum_role}'"
                        )
                except ValueError as e:
                    raise HTTPException(
                        status_code=403,
                        detail=str(e)
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator
```

## API Endpoint Protection

### Protected Endpoint Examples

```python
from fastapi import FastAPI, Depends, HTTPException
from typing import Any, Dict, List, Optional

# Initialize components
app = FastAPI(title="Enterprise API", version="1.0.0")
role_manager = RoleManager()
permission_checker = PermissionChecker(role_manager)
token_handler = JWTTokenHandler(
    secret_key="your-secret-key-here",
    algorithm="HS256",
    token_expiry=3600
)
auth_middleware = AuthorizationMiddleware(token_handler, permission_checker)


@app.post("/api/v1/auth/login")
async def login(username: str, password: str) -> Dict[str, Any]:
    """Authenticate user and return JWT token.
    
    Args:
        username: The username.
        password: The password.
    
    Returns:
        Dictionary with access token and user info.
    
    Raises:
        HTTPException: If authentication fails.
    """
    # In production, validate against user database
    if username == "admin" and password == "secure_password":
        token = token_handler.create_token(
            user_id="user_123",
            role="admin",
            additional_claims={"username": username}
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": "user_123",
            "role": "admin"
        }
    
    raise HTTPException(
        status_code=401,
        detail="Invalid credentials"
    )


@app.get("/api/v1/documents")
async def list_documents(
    current_user: Dict[str, Any] = Depends(auth_middleware.get_current_user)
) -> Dict[str, Any]:
    """List all documents (requires read permission).
    
    Args:
        current_user: The authenticated user.
    
    Returns:
        Dictionary with document list.
    """
    # Permission check
    if not permission_checker.check_permission(current_user["role"], "read:documents"):
        raise HTTPException(
            status_code=403,
            detail="Permission denied: requires 'read:documents'"
        )
    
    # In production, fetch from database
    return {
        "documents": [
            {"id": "doc_1", "title": "Document 1"},
            {"id": "doc_2", "title": "Document 2"}
        ],
        "user": current_user["user_id"]
    }


@app.post("/api/v1/documents")
@auth_middleware.require_permission("write:documents")
async def create_document(
    title: str,
    content: str,
    current_user: Dict[str, Any] = Depends(auth_middleware.get_current_user)
) -> Dict[str, Any]:
    """Create a new document (requires write permission).
    
    Args:
        title: Document title.
        content: Document content.
        current_user: The authenticated user.
    
    Returns:
        Dictionary with created document info.
    """
    # In production, save to database
    return {
        "id": "doc_new",
        "title": title,
        "created_by": current_user["user_id"],
        "status": "created"
    }


@app.delete("/api/v1/documents/{document_id}")
@auth_middleware.require_role("admin")
async def delete_document(
    document_id: str,
    current_user: Dict[str, Any] = Depends(auth_middleware.get_current_user)
) -> Dict[str, Any]:
    """Delete a document (requires admin role).
    
    Args:
        document_id: The document ID to delete.
        current_user: The authenticated user.
    
    Returns:
        Dictionary with deletion status.
    """
    # In production, delete from database
    return {
        "document_id": document_id,
        "deleted_by": current_user["user_id"],
        "status": "deleted"
    }


@app.get("/api/v1/admin/users")
@auth_middleware.require_permission("manage:users")
async def list_users(
    current_user: Dict[str, Any] = Depends(auth_middleware.get_current_user)
) -> Dict[str, Any]:
    """List all users (requires manage:users permission).
    
    Args:
        current_user: The authenticated user.
    
    Returns:
        Dictionary with user list.
    """
    # In production, fetch from database
    return {
        "users": [
            {"id": "user_1", "role": "viewer"},
            {"id": "user_2", "role": "editor"}
        ],
        "requested_by": current_user["user_id"]
    }
```

## Error Handling

### Authorization Error Classes

```python
from typing import Any, Dict, Optional


class AuthorizationError(Exception):
    """Base exception for authorization errors."""
    
    def __init__(self, message: str, status_code: int = 403, 
                 details: Optional[Dict[str, Any]] = None) -> None:
        """Initialize authorization error.
        
        Args:
            message: Human-readable error message.
            status_code: HTTP status code (default: 403).
            details: Additional error details.
        """
        self.message: str = message
        self.status_code: int = status_code
        self.details: Dict[str, Any] = details or {}
        super().__init__(self.message)


class PermissionDeniedError(AuthorizationError):
    """Raised when user lacks required permission."""
    
    def __init__(self, permission: str, 
                 details: Optional[Dict[str, Any]] = None) -> None:
        """Initialize permission denied error.
        
        Args:
            permission: The permission that was denied.
            details: Additional error details.
        """
        super().__init__(
            message=f"Permission denied: '{permission}' is required",
            status_code=403,
            details={"required_permission": permission, **(details or {})}
        )


class InsufficientRoleError(AuthorizationError):
    """Raised when user role is insufficient."""
    
    def __init__(self, required_role: str, user_role: str,
                 details: Optional[Dict[str, Any]] = None) -> None:
        """Initialize insufficient role error.
        
        Args:
            required_role: The minimum role required.
            user_role: The user's current role.
            details: Additional error details.
        """
        super().__init__(
            message=f"Insufficient role: requires at least '{required_role}', "
                   f"user has '{user_role}'",
            status_code=403,
            details={
                "required_role": required_role,
                "user_role": user_role,
                **(details or {})
            }
        )


class TokenExpiredError(AuthorizationError):
    """Raised when the authentication token has expired."""
    
    def __init__(self, details: Optional[Dict[str, Any]] = None) -> None:
        """Initialize token expired error.
        
        Args:
            details: Additional error details.
        """
        super().__init__(
            message="Authentication token has expired",
            status_code=401,
            details=details or {}
        )


class InvalidTokenError(AuthorizationError):
    """Raised when the authentication token is invalid."""
    
    def __init__(self, reason: str, 
                 details: Optional[Dict[str, Any]] = None) -> None:
        """Initialize invalid token error.
        
        Args:
            reason: The reason the token is invalid.
            details: Additional error details.
        """
        super().__init__(
            message=f"Invalid authentication token: {reason}",
            status_code=401,
            details={"reason": reason, **(details or {})}
        )


def handle_authorization_error(error: AuthorizationError) -> Dict[str, Any]:
    """Convert authorization error to API response format.
    
    Args:
        error: The authorization error to handle.
    
    Returns:
        Dictionary with error details for API response.
    """
    return {
        "error": {
            "code": error.status_code,
            "message": error.message,
            "details": error.details
        }
    }
```

## Testing Authorization

### Unit Tests

```python
import pytest
from typing import Any, Dict, List, Optional, Set
from unittest.mock import Mock, patch


class TestRoleManager:
    """Test suite for RoleManager."""
    
    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.role_manager = RoleManager()
    
    def test_get_role_exists(self) -> None:
        """Test retrieving an existing role."""
        role = self.role_manager.get_role("admin")
        assert role.name == "admin"
        assert role.level == 3
    
    def test_get_role_not_found(self) -> None:
        """Test retrieving a non-existent role raises error."""
        with pytest.raises(ValueError, match="Role 'nonexistent' not found"):
            self.role_manager.get_role("nonexistent")
    
    def test_get_all_permissions_with_inheritance(self) -> None:
        """Test permission inheritance from parent roles."""
        permissions = self.role_manager.get_all_permissions("editor")
        assert "read:documents" in permissions  # Inherited from viewer
        assert "write:documents" in permissions  # Own permission
    
    def test_has_permission_true(self) -> None:
        """Test permission check returns True for valid permission."""
        assert self.role_manager.has_permission("admin", "delete:documents")
    
    def test_has_permission_false(self) -> None:
        """Test permission check returns False for invalid permission."""
        assert not self.role_manager.has_permission("viewer", "delete:documents")
    
    def test_add_custom_role(self) -> None:
        """Test adding a custom role."""
        self.role_manager.add_role(
            name="custom_role",
            level=5,
            permissions={"execute:reports"},
            parent_role="viewer"
        )
        role = self.role_manager.get_role("custom_role")
        assert role.name == "custom_role"
        assert "execute:reports" in role.permissions
    
    def test_add_duplicate_role_raises_error(self) -> None:
        """Test adding a duplicate role raises error."""
        with pytest.raises(ValueError, match="Role 'admin' already exists"):
            self.role_manager.add_role("admin", 3, set())


class TestPermissionChecker:
    """Test suite for PermissionChecker."""
    
    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.role_manager = RoleManager()
        self.permission_checker = PermissionChecker(self.role_manager)
    
    def test_check_permission_authorized(self) -> None:
        """Test authorized permission check."""
        assert self.permission_checker.check_permission("admin", "delete:documents")
    
    def test_check_permission_unauthorized(self) -> None:
        """Test unauthorized permission check."""
        assert not self.permission_checker.check_permission("viewer", "delete:documents")
    
    def test_check_any_permission_success(self) -> None:
        """Test any permission check succeeds."""
        result = self.permission_checker.check_any_permission(
            "editor", 
            ["read:documents", "delete:documents"]
        )
        assert result
    
    def test_check_any_permission_failure(self) -> None:
        """Test any permission check fails."""
        result = self.permission_checker.check_any_permission(
            "viewer",
            ["delete:documents", "manage:users"]
        )
        assert not result
    
    def test_check_all_permissions_success(self) -> None:
        """Test all permissions check succeeds."""
        result = self.permission_checker.check_all_permissions(
            "admin",
            ["read:documents", "write:documents", "delete:documents"]
        )
        assert result
    
    def test_check_all_permissions_failure(self) -> None:
        """Test all permissions check fails."""
        result = self.permission_checker.check_all_permissions(
            "editor",
            ["read:documents", "delete:documents"]
        )
        assert not result


class TestJWTTokenHandler:
    """Test suite for JWTTokenHandler."""
    
    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.secret_key: str = "test-secret-key-for-testing"
        self.token_handler = JWTTokenHandler(
            secret_key=self.secret_key,
            algorithm="HS256",
            token_expiry=3600
        )
    
    def test_create_token_success(self) -> None:
        """Test successful token creation."""
        token = self.token_handler.create_token(
            user_id="user_123",
            role="admin"
        )
        assert token.count('.') == 2
        assert len(token) > 0
    
    def test_validate_token_valid(self) -> None:
        """Test validating a valid token."""
        token = self.token_handler.create_token(
            user_id="user_123",
            role="admin"
        )
        payload = self.token_handler.validate_token(token)
        assert payload["sub"] == "user_123"
        assert payload["role"] == "admin"
        assert "exp" in payload
        assert "iat" in payload
    
    def test_validate_token_expired(self) -> None:
        """Test validating an expired token."""
        expired_handler = JWTTokenHandler(
            secret_key=self.secret_key,
            token_expiry=-1  # Token already expired
        )
        token = expired_handler.create_token("user_123", "admin")
        
        with pytest.raises(ValueError, match="Token has expired"):
            self.token_handler.validate_token(token)
    
    def test_validate_token_invalid_signature(self) -> None:
        """Test validating a token with invalid signature."""
        token = self.token_handler.create_token("user_123", "admin")
        parts = token.split('.')
        tampered_token = f"{parts[0]}.{parts[1]}.invalidsignature"
        
        with pytest.raises(ValueError, match="Invalid token signature"):
            self.token_handler.validate_token(tampered_token)
    
    def test_refresh_token(self) -> None:
        """Test refreshing a valid token."""
        token = self.token_handler.create_token("user_123", "admin")
        new_token = self.token_handler.refresh_token(token)
        
        # New token should be different
        assert new_token != token
        
        # New token should be valid
        payload = self.token_handler.validate_token(new_token)
        assert payload["sub"] == "user_123"
        assert payload["role"] == "admin"


class TestAuthorizationMiddleware:
    """Test suite for AuthorizationMiddleware."""
    
    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.role_manager = RoleManager()
        self.permission_checker = PermissionChecker(self.role_manager)
        self.token_handler = JWTTokenHandler(
            secret_key="test-secret-key",
            algorithm="HS256",
            token_expiry=3600
        )
        self.auth_middleware = AuthorizationMiddleware(
            self.token_handler,
            self.permission_checker
        )
    
    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self) -> None:
        """Test extracting user from valid token."""
        token = self.token_handler.create_token("user_123", "admin")
        
        # Mock credentials
        mock_credentials = Mock()
        mock_credentials.credentials = token
        
        user = await self.auth_middleware.get_current_user(mock_credentials)
        assert user["user_id"] == "user_123"
        assert user["role"] == "admin"
    
    @pytest.mark.asyncio
    async def test_get_current_user_no_credentials(self) -> None:
        """Test extracting user without credentials."""
        with pytest.raises(Exception) as exc_info:
            await self.auth_middleware.get_current_user(None)
        assert exc_info.typename == 'HTTPException'
        assert exc_info.value.status_code == 401
```

## Security Best Practices

### 1. Token Security

- **Use strong secrets**: Generate secrets with at least 256 bits of entropy
- **Set appropriate expiration**: Short-lived tokens (15-60 minutes) with refresh tokens
- **Use HTTPS**: Always transmit tokens over encrypted connections
- **Store tokens securely**: Use HTTP-only cookies or secure storage mechanisms
- **Implement token rotation**: Issue new tokens periodically

### 2. Role Management

- **Principle of least privilege**: Grant minimum permissions necessary
- **Regular audits**: Review role assignments and permissions quarterly
- **Separation of duties**: Critical actions require multiple approvals
- **Role hierarchy**: Use inheritance to simplify permission management

### 3. Permission Validation

- **Server-side validation**: Never trust client-side permission checks
- **Fail securely**: Default to denying access
- **Log authorization failures**: Monitor for potential attacks
- **Rate limiting**: Prevent brute force attempts on authorization

### 4. Implementation Checklist

```python
from typing import List


class SecurityChecklist:
    """Security checklist for authorization implementation."""
    
    @staticmethod
    def validate_implementation() -> List[str]:
        """Run security checks on authorization implementation.
        
        Returns:
            List of security issues found.
        """
        issues: List[str] = []
        
        # Check 1: Token configuration
        # Verify token expiration is set
        # Verify algorithm is secure (HS256 or better)
        # Verify secret key strength
        
        # Check 2: Permission checks
        # Verify all endpoints have permission checks
        # Verify default deny behavior
        # Verify no hardcoded permissions
        
        # Check 3: Error handling
        # Verify no sensitive info in error messages
        # Verify consistent error responses
        # Verify logging of authorization failures
        
        # Check 4: Role management
        # Verify role hierarchy is correct
        # Verify no orphaned permissions
        # Verify role assignments are audited
        
        return issues
```

### 5. Production Configuration

```python
from typing import Any, Dict, Optional


class AuthorizationConfig:
    """Production configuration for authorization system."""
    
    def __init__(self, environment: str = "production") -> None:
        """Initialize authorization configuration.
        
        Args:
            environment: The deployment environment.
        
        Raises:
            ValueError: If environment is invalid.
        """
        valid_environments = {"development", "staging", "production"}
        if environment not in valid_environments:
            raise ValueError(f"Invalid environment '{environment}'. "
                           f"Must be one of {valid_environments}")
        
        self.environment: str = environment
        self.config: Dict[str, Any] = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration based on environment.
        
        Returns:
            Configuration dictionary.
        """
        base_config: Dict[str, Any] = {
            "token_expiry": 3600,  # 1 hour
            "refresh_token_expiry": 86400,  # 24 hours
            "max_login_attempts": 5,
            "lockout_duration": 900,  # 15 minutes
            "require_https": True,
            "log_auth_failures": True,
            "audit_enabled": True,
        }
        
        if self.environment == "development":
            base_config.update({
                "token_expiry": 86400,  # 24 hours for development
                "require_https": False,
                "log_auth_failures": True,
            })
        elif self.environment == "staging":
            base_config.update({
                "token_expiry": 7200,  # 2 hours
                "require_https": True,
                "audit_enabled": True,
            })
        
        return base_config
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.
        
        Args:
            key: Configuration key.
            default: Default value if key not found.
        
        Returns:
            Configuration value.
        """
        return self.config.get(key, default)
```

## Conclusion

This authorization guide provides a complete framework for implementing secure, role-based access control in enterprise applications. Key takeaways:

1. **Use RBAC** with hierarchical roles for scalable permission management
2. **Implement JWT tokens** with proper signing and expiration
3. **Apply middleware** for centralized authorization checks
4. **Handle errors** gracefully with meaningful messages
5. **Test thoroughly** including edge cases and security scenarios
6. **Follow best practices** for production deployments

For additional information, refer to:
- [Authentication Guide](./authentication_guide.md)
- [Security Best Practices](./security_best_practices.md)
- [API Documentation](./api_documentation.md)