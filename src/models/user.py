"""
User model for the application.

This module defines the User class representing a user entity in the system.
It includes fields for user identification, authentication, and profile management.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from pydantic.networks import IPvAnyAddress


class UserRole(str, Enum):
    """Enumeration of possible user roles in the system."""

    ADMIN = "admin"
    USER = "user"
    MODERATOR = "moderator"
    GUEST = "guest"


class UserStatus(str, Enum):
    """Enumeration of possible user account statuses."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"
    PENDING_VERIFICATION = "pending_verification"


class User(BaseModel):
    """
    Represents a user entity in the system.

    Attributes:
        id: Unique identifier for the user.
        username: Unique username for the user.
        email: User's email address.
        password_hash: Hashed password for authentication.
        role: User's role in the system.
        status: Current status of the user account.
        first_name: User's first name.
        last_name: User's last name.
        phone: User's phone number (optional).
        avatar_url: URL to user's avatar image (optional).
        bio: Short biography or description (optional).
        last_login: Timestamp of last successful login.
        created_at: Timestamp when the user was created.
        updated_at: Timestamp when the user was last updated.
        email_verified: Whether the email has been verified.
        two_factor_enabled: Whether two-factor authentication is enabled.
        failed_login_attempts: Number of consecutive failed login attempts.
        locked_until: Timestamp until which the account is locked.
        permissions: Set of additional permissions granted to the user.
        metadata: Dictionary for storing arbitrary user metadata.
        ip_address: Last known IP address of the user.
        user_agent: Last known user agent string.
    """

    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat(),
        },
        "populate_by_name": True,
        "validate_assignment": True,
        "extra": "forbid",
    }

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="Unique identifier for the user",
        frozen=True,
    )
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="Unique username for the user",
    )
    email: EmailStr = Field(
        ...,
        description="User's email address",
    )
    password_hash: str = Field(
        ...,
        min_length=60,
        max_length=128,
        description="Hashed password for authentication",
    )
    role: UserRole = Field(
        default=UserRole.USER,
        description="User's role in the system",
    )
    status: UserStatus = Field(
        default=UserStatus.PENDING_VERIFICATION,
        description="Current status of the user account",
    )
    first_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="User's first name",
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="User's last name",
    )
    phone: Optional[str] = Field(
        default=None,
        max_length=20,
        pattern=r"^\+?[1-9]\d{1,14}$",
        description="User's phone number in E.164 format",
    )
    avatar_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL to user's avatar image",
    )
    bio: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Short biography or description",
    )
    last_login: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last successful login",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the user was created",
        frozen=True,
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the user was last updated",
    )
    email_verified: bool = Field(
        default=False,
        description="Whether the email has been verified",
    )
    two_factor_enabled: bool = Field(
        default=False,
        description="Whether two-factor authentication is enabled",
    )
    failed_login_attempts: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Number of consecutive failed login attempts",
    )
    locked_until: Optional[datetime] = Field(
        default=None,
        description="Timestamp until which the account is locked",
    )
    permissions: Set[str] = Field(
        default_factory=set,
        description="Set of additional permissions granted to the user",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary for storing arbitrary user metadata",
    )
    ip_address: Optional[IPvAnyAddress] = Field(
        default=None,
        description="Last known IP address of the user",
    )
    user_agent: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Last known user agent string",
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        """
        Validate the username field.

        Args:
            value: The username to validate.

        Returns:
            The validated username.

        Raises:
            ValueError: If the username is invalid.
        """
        if not value.strip():
            raise ValueError("Username cannot be empty or whitespace only")
        if value.lower() in {"admin", "root", "system", "null", "undefined"}:
            raise ValueError(f"Username '{value}' is reserved and cannot be used")
        return value.strip()

    @field_validator("password_hash")
    @classmethod
    def validate_password_hash(cls, value: str) -> str:
        """
        Validate the password hash field.

        Args:
            value: The password hash to validate.

        Returns:
            The validated password hash.

        Raises:
            ValueError: If the password hash is invalid.
        """
        if not value.strip():
            raise ValueError("Password hash cannot be empty or whitespace only")
        if not value.startswith("$2"):
            raise ValueError("Password hash must be a valid bcrypt hash")
        return value.strip()

    @model_validator(mode="after")
    def validate_account_lock(self) -> "User":
        """
        Validate account lock state.

        Returns:
            The validated user instance.

        Raises:
            ValueError: If the account is locked and status is not suspended.
        """
        if self.locked_until is not None and self.status != UserStatus.SUSPENDED:
            raise ValueError(
                "Account must be suspended when locked_until is set"
            )
        return self

    def is_locked(self) -> bool:
        """
        Check if the user account is currently locked.

        Returns:
            True if the account is locked, False otherwise.
        """
        if self.locked_until is None:
            return False
        return datetime.now(timezone.utc) < self.locked_until

    def can_login(self) -> bool:
        """
        Check if the user can attempt to log in.

        Returns:
            True if the user can log in, False otherwise.
        """
        if self.status in {UserStatus.DELETED, UserStatus.SUSPENDED}:
            return False
        if self.is_locked():
            return False
        return True

    def increment_failed_login(self) -> None:
        """
        Increment the failed login attempts counter.

        Locks the account if the maximum number of attempts is reached.
        """
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.locked_until = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + __import__("datetime").timedelta(hours=1)
            self.status = UserStatus.SUSPENDED

    def reset_failed_login(self) -> None:
        """
        Reset the failed login attempts counter and unlock the account.
        """
        self.failed_login_attempts = 0
        self.locked_until = None
        if self.status == UserStatus.SUSPENDED:
            self.status = UserStatus.ACTIVE

    def update_last_login(self) -> None:
        """
        Update the last login timestamp to the current time.
        """
        self.last_login = datetime.now(timezone.utc)
        self.reset_failed_login()

    def has_permission(self, permission: str) -> bool:
        """
        Check if the user has a specific permission.

        Args:
            permission: The permission to check.

        Returns:
            True if the user has the permission, False otherwise.
        """
        if self.role == UserRole.ADMIN:
            return True
        return permission in self.permissions

    def add_permission(self, permission: str) -> None:
        """
        Add a permission to the user.

        Args:
            permission: The permission to add.
        """
        self.permissions.add(permission)

    def remove_permission(self, permission: str) -> None:
        """
        Remove a permission from the user.

        Args:
            permission: The permission to remove.
        """
        self.permissions.discard(permission)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the user to a dictionary.

        Returns:
            A dictionary representation of the user.
        """
        return self.model_dump(exclude={"password_hash"})

    def to_json(self) -> str:
        """
        Convert the user to a JSON string.

        Returns:
            A JSON string representation of the user.
        """
        return self.model_dump_json(exclude={"password_hash"})

    def __str__(self) -> str:
        """
        Return a string representation of the user.

        Returns:
            A string representation of the user.
        """
        return f"User(id={self.id}, username={self.username}, email={self.email})"

    def __repr__(self) -> str:
        """
        Return a detailed string representation of the user.

        Returns:
            A detailed string representation of the user.
        """
        return (
            f"User(id={self.id!r}, username={self.username!r}, "
            f"email={self.email!r}, role={self.role!r}, status={self.status!r})"
        )

    def __eq__(self, other: object) -> bool:
        """
        Check if two users are equal.

        Args:
            other: The other object to compare.

        Returns:
            True if the users are equal, False otherwise.
        """
        if not isinstance(other, User):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        """
        Return a hash value for the user.

        Returns:
            A hash value for the user.
        """
        return hash(self.id)