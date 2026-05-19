"""
Authorized User Model

This module defines the AuthorizedUser model representing users who have been
granted access to the system. It includes fields for user identification,
authentication, authorization levels, and account management.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from pydantic.networks import IPvAnyAddress


class UserRole(str, Enum):
    """Enumeration of possible user roles within the system."""
    ADMIN = "admin"
    MANAGER = "manager"
    OPERATOR = "operator"
    VIEWER = "viewer"
    AUDITOR = "auditor"


class UserStatus(str, Enum):
    """Enumeration of possible user account statuses."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    LOCKED = "locked"
    PENDING_VERIFICATION = "pending_verification"
    EXPIRED = "expired"


class AuthorizedUser(BaseModel):
    """
    Represents an authorized user in the system with full access control capabilities.
    
    This model encapsulates all user-related data including authentication details,
    authorization levels, account status, and audit information. It enforces
    validation rules for data integrity and security.
    
    Attributes:
        user_id: Unique identifier for the user
        username: Unique username for login
        email: User's email address
        password_hash: Hashed password (never stored in plaintext)
        role: User's role determining permissions
        status: Current account status
        is_mfa_enabled: Whether multi-factor authentication is enabled
        mfa_secret: Encrypted MFA secret key
        allowed_ips: List of IP addresses allowed to access the system
        permissions: Set of specific permissions granted to the user
        department: User's department or team
        created_at: Timestamp when the user was created
        updated_at: Timestamp when the user was last updated
        last_login: Timestamp of the last successful login
        last_password_change: Timestamp of the last password change
        failed_login_attempts: Count of consecutive failed login attempts
        account_expiry: Optional timestamp when the account expires
        session_timeout_minutes: Session timeout duration in minutes
        metadata: Additional user metadata as key-value pairs
    """
    
    user_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the user"
    )
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r'^[a-zA-Z0-9_\-\.]+$',
        description="Unique username for login"
    )
    email: EmailStr = Field(
        ...,
        description="User's email address"
    )
    password_hash: str = Field(
        ...,
        min_length=60,
        max_length=128,
        description="Hashed password using bcrypt or similar algorithm"
    )
    role: UserRole = Field(
        default=UserRole.VIEWER,
        description="User's role determining permissions"
    )
    status: UserStatus = Field(
        default=UserStatus.PENDING_VERIFICATION,
        description="Current account status"
    )
    is_mfa_enabled: bool = Field(
        default=False,
        description="Whether multi-factor authentication is enabled"
    )
    mfa_secret: Optional[str] = Field(
        default=None,
        min_length=16,
        max_length=64,
        description="Encrypted MFA secret key"
    )
    allowed_ips: List[IPvAnyAddress] = Field(
        default_factory=list,
        description="List of IP addresses allowed to access the system"
    )
    permissions: Set[str] = Field(
        default_factory=set,
        description="Set of specific permissions granted to the user"
    )
    department: Optional[str] = Field(
        default=None,
        max_length=100,
        description="User's department or team"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the user was created"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the user was last updated"
    )
    last_login: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the last successful login"
    )
    last_password_change: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the last password change"
    )
    failed_login_attempts: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Count of consecutive failed login attempts"
    )
    account_expiry: Optional[datetime] = Field(
        default=None,
        description="Optional timestamp when the account expires"
    )
    session_timeout_minutes: int = Field(
        default=30,
        ge=5,
        le=1440,
        description="Session timeout duration in minutes"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional user metadata as key-value pairs"
    )

    @field_validator('username')
    @classmethod
    def validate_username(cls, value: str) -> str:
        """
        Validate that the username meets security requirements.
        
        Args:
            value: The username to validate
            
        Returns:
            The validated username
            
        Raises:
            ValueError: If the username contains invalid characters or patterns
        """
        if not value:
            raise ValueError("Username cannot be empty")
        
        # Check for reserved usernames
        reserved_usernames: Set[str] = {
            'admin', 'root', 'system', 'superuser', 'administrator',
            'anonymous', 'guest', 'test', 'null', 'undefined'
        }
        
        if value.lower() in reserved_usernames:
            raise ValueError(f"Username '{value}' is reserved and cannot be used")
        
        # Check for consecutive special characters
        if '..' in value or '--' in value or '__' in value:
            raise ValueError("Username cannot contain consecutive special characters")
        
        # Check for leading/trailing special characters
        if value.startswith(('.', '-', '_')) or value.endswith(('.', '-', '_')):
            raise ValueError("Username cannot start or end with special characters")
        
        return value.lower()

    @field_validator('password_hash')
    @classmethod
    def validate_password_hash(cls, value: str) -> str:
        """
        Validate that the password hash has the correct format.
        
        Args:
            value: The password hash to validate
            
        Returns:
            The validated password hash
            
        Raises:
            ValueError: If the hash format is invalid
        """
        if not value:
            raise ValueError("Password hash cannot be empty")
        
        # Basic validation for bcrypt hash format
        if not value.startswith('$2b$') and not value.startswith('$2a$') and not value.startswith('$2y$'):
            raise ValueError("Invalid password hash format. Must be a bcrypt hash")
        
        return value

    @field_validator('mfa_secret')
    @classmethod
    def validate_mfa_secret(cls, value: Optional[str]) -> Optional[str]:
        """
        Validate the MFA secret if provided.
        
        Args:
            value: The MFA secret to validate
            
        Returns:
            The validated MFA secret or None
            
        Raises:
            ValueError: If the MFA secret format is invalid
        """
        if value is not None:
            if not value.strip():
                raise ValueError("MFA secret cannot be empty if provided")
            
            # Validate base32 encoding for TOTP secrets
            import base64
            try:
                # Attempt to decode as base32 (common for TOTP)
                base64.b32decode(value.upper())
            except Exception as exc:
                raise ValueError(f"Invalid MFA secret format: {exc}") from exc
        
        return value

    @model_validator(mode='after')
    def validate_model(self) -> 'AuthorizedUser':
        """
        Perform cross-field validation after all fields are validated.
        
        Returns:
            The validated model instance
            
        Raises:
            ValueError: If cross-field validation fails
        """
        # Validate that MFA is enabled if MFA secret is provided
        if self.mfa_secret is not None and not self.is_mfa_enabled:
            raise ValueError("MFA must be enabled if MFA secret is provided")
        
        # Validate that account expiry is in the future if set
        if self.account_expiry is not None:
            if self.account_expiry <= datetime.now(timezone.utc):
                raise ValueError("Account expiry must be in the future")
        
        # Validate that last_login is not in the future
        if self.last_login is not None:
            if self.last_login > datetime.now(timezone.utc):
                raise ValueError("Last login timestamp cannot be in the future")
        
        # Validate that last_password_change is not in the future
        if self.last_password_change is not None:
            if self.last_password_change > datetime.now(timezone.utc):
                raise ValueError("Last password change timestamp cannot be in the future")
        
        # Validate timestamps consistency
        if self.created_at > self.updated_at:
            raise ValueError("Created timestamp cannot be after updated timestamp")
        
        if self.last_login is not None and self.created_at > self.last_login:
            raise ValueError("Created timestamp cannot be after last login timestamp")
        
        if self.last_password_change is not None and self.created_at > self.last_password_change:
            raise ValueError("Created timestamp cannot be after last password change timestamp")
        
        return self

    def is_active(self) -> bool:
        """
        Check if the user account is active and not expired.
        
        Returns:
            True if the account is active and not expired, False otherwise
        """
        if self.status != UserStatus.ACTIVE:
            return False
        
        if self.account_expiry is not None and datetime.now(timezone.utc) >= self.account_expiry:
            return False
        
        return True

    def has_permission(self, permission: str) -> bool:
        """
        Check if the user has a specific permission.
        
        Args:
            permission: The permission to check
            
        Returns:
            True if the user has the permission, False otherwise
        """
        return permission in self.permissions

    def has_role(self, role: UserRole) -> bool:
        """
        Check if the user has a specific role.
        
        Args:
            role: The role to check
            
        Returns:
            True if the user has the role, False otherwise
        """
        return self.role == role

    def is_ip_allowed(self, ip_address: str) -> bool:
        """
        Check if an IP address is allowed to access the system.
        
        Args:
            ip_address: The IP address to check
            
        Returns:
            True if the IP is allowed or no restrictions are set, False otherwise
        """
        if not self.allowed_ips:
            return True
        
        try:
            from ipaddress import ip_address as ip_addr
            request_ip = ip_addr(ip_address)
            return any(request_ip == allowed_ip for allowed_ip in self.allowed_ips)
        except ValueError:
            return False

    def increment_failed_login(self) -> None:
        """
        Increment the failed login attempts counter.
        
        Raises:
            ValueError: If the counter would exceed the maximum allowed value
        """
        if self.failed_login_attempts >= 100:
            raise ValueError("Maximum failed login attempts exceeded")
        
        self.failed_login_attempts += 1
        self.updated_at = datetime.now(timezone.utc)

    def reset_failed_login(self) -> None:
        """Reset the failed login attempts counter to zero."""
        self.failed_login_attempts = 0
        self.updated_at = datetime.now(timezone.utc)

    def update_last_login(self) -> None:
        """Update the last login timestamp to the current time."""
        self.last_login = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def update_password(self, new_password_hash: str) -> None:
        """
        Update the user's password hash and record the change timestamp.
        
        Args:
            new_password_hash: The new hashed password
            
        Raises:
            ValueError: If the new password hash is invalid
        """
        if not new_password_hash:
            raise ValueError("New password hash cannot be empty")
        
        self.password_hash = new_password_hash
        self.last_password_change = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the user model to a dictionary, excluding sensitive fields.
        
        Returns:
            Dictionary representation of the user without sensitive data
        """
        return {
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'role': self.role.value,
            'status': self.status.value,
            'is_mfa_enabled': self.is_mfa_enabled,
            'allowed_ips': [str(ip) for ip in self.allowed_ips],
            'permissions': list(self.permissions),
            'department': self.department,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'last_password_change': self.last_password_change.isoformat() if self.last_password_change else None,
            'failed_login_attempts': self.failed_login_attempts,
            'account_expiry': self.account_expiry.isoformat() if self.account_expiry else None,
            'session_timeout_minutes': self.session_timeout_minutes,
            'metadata': self.metadata
        }

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Set: lambda v: list(v),
            IPvAnyAddress: lambda v: str(v)
        }
        validate_assignment = True
        extra = 'forbid'
        frozen = False