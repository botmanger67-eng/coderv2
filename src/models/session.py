"""Session model for managing user sessions."""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import uuid4, UUID

from pydantic import BaseModel, Field, field_validator
from enum import Enum


class SessionStatus(str, Enum):
    """Enumeration of possible session states."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


class Session(BaseModel):
    """Represents a user session with authentication and lifecycle management.
    
    Attributes:
        session_id: Unique identifier for the session.
        user_id: Identifier of the user associated with the session.
        token: Authentication token for the session.
        status: Current status of the session.
        created_at: Timestamp when the session was created.
        expires_at: Timestamp when the session expires.
        last_activity: Timestamp of the last activity in the session.
        ip_address: IP address from which the session was initiated.
        user_agent: User agent string from the client.
        metadata: Additional metadata associated with the session.
    """
    
    session_id: UUID = Field(default_factory=uuid4, description="Unique session identifier")
    user_id: str = Field(..., min_length=1, max_length=255, description="User identifier")
    token: str = Field(..., min_length=32, max_length=512, description="Authentication token")
    status: SessionStatus = Field(default=SessionStatus.ACTIVE, description="Session status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation timestamp")
    expires_at: datetime = Field(..., description="Session expiration timestamp")
    last_activity: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")
    ip_address: Optional[str] = Field(None, max_length=45, description="Client IP address")
    user_agent: Optional[str] = Field(None, max_length=512, description="Client user agent")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional session metadata")
    
    @field_validator('expires_at')
    @classmethod
    def validate_expires_at(cls, value: datetime) -> datetime:
        """Validate that expiration time is in the future.
        
        Args:
            value: The expiration timestamp to validate.
            
        Returns:
            The validated expiration timestamp.
            
        Raises:
            ValueError: If the expiration time is not in the future.
        """
        if value <= datetime.utcnow():
            raise ValueError("Expiration time must be in the future")
        return value
    
    @field_validator('last_activity')
    @classmethod
    def validate_last_activity(cls, value: datetime) -> datetime:
        """Validate that last activity timestamp is not in the future.
        
        Args:
            value: The last activity timestamp to validate.
            
        Returns:
            The validated last activity timestamp.
            
        Raises:
            ValueError: If the timestamp is in the future.
        """
        if value > datetime.utcnow():
            raise ValueError("Last activity timestamp cannot be in the future")
        return value
    
    @field_validator('ip_address')
    @classmethod
    def validate_ip_address(cls, value: Optional[str]) -> Optional[str]:
        """Validate IP address format.
        
        Args:
            value: The IP address to validate.
            
        Returns:
            The validated IP address or None.
            
        Raises:
            ValueError: If the IP address format is invalid.
        """
        if value is not None:
            import ipaddress
            try:
                ipaddress.ip_address(value)
            except ValueError as exc:
                raise ValueError(f"Invalid IP address format: {value}") from exc
        return value
    
    def is_expired(self) -> bool:
        """Check if the session has expired.
        
        Returns:
            True if the session has expired, False otherwise.
        """
        return datetime.utcnow() >= self.expires_at
    
    def is_active(self) -> bool:
        """Check if the session is currently active.
        
        Returns:
            True if the session is active and not expired, False otherwise.
        """
        return self.status == SessionStatus.ACTIVE and not self.is_expired()
    
    def update_activity(self) -> None:
        """Update the last activity timestamp to the current time."""
        self.last_activity = datetime.utcnow()
    
    def revoke(self) -> None:
        """Revoke the session, changing its status to REVOKED."""
        self.status = SessionStatus.REVOKED
    
    def suspend(self) -> None:
        """Suspend the session, changing its status to SUSPENDED."""
        self.status = SessionStatus.SUSPENDED
    
    def extend_expiry(self, duration: timedelta) -> None:
        """Extend the session expiration time.
        
        Args:
            duration: The duration to extend the session by.
            
        Raises:
            ValueError: If the session is not active.
        """
        if not self.is_active():
            raise ValueError("Cannot extend expiry of an inactive session")
        self.expires_at = datetime.utcnow() + duration
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the session to a dictionary representation.
        
        Returns:
            Dictionary containing session data.
        """
        return {
            "session_id": str(self.session_id),
            "user_id": self.user_id,
            "token": self.token,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Create a Session instance from a dictionary.
        
        Args:
            data: Dictionary containing session data.
            
        Returns:
            A new Session instance.
            
        Raises:
            ValueError: If required fields are missing or data is invalid.
        """
        required_fields = ["user_id", "token", "expires_at"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # Parse datetime fields if they are strings
        datetime_fields = ["created_at", "expires_at", "last_activity"]
        for field in datetime_fields:
            if field in data and isinstance(data[field], str):
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except ValueError as exc:
                    raise ValueError(f"Invalid datetime format for {field}: {data[field]}") from exc
        
        # Parse UUID if string
        if "session_id" in data and isinstance(data["session_id"], str):
            try:
                data["session_id"] = UUID(data["session_id"])
            except ValueError as exc:
                raise ValueError(f"Invalid UUID format for session_id: {data['session_id']}") from exc
        
        # Parse status if string
        if "status" in data and isinstance(data["status"], str):
            try:
                data["status"] = SessionStatus(data["status"])
            except ValueError as exc:
                raise ValueError(f"Invalid session status: {data['status']}") from exc
        
        return cls(**data)
    
    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
            SessionStatus: lambda v: v.value
        }
        validate_assignment = True
        arbitrary_types_allowed = False