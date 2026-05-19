"""Project model for the application."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class ProjectStatus(str, Enum):
    """Enumeration of possible project statuses."""

    DRAFT = "draft"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class ProjectPriority(str, Enum):
    """Enumeration of project priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Project(BaseModel):
    """Represents a project entity with all necessary attributes.

    Attributes:
        id: Unique identifier for the project.
        name: Human-readable project name.
        description: Detailed description of the project.
        status: Current status of the project.
        priority: Priority level of the project.
        owner_id: UUID of the project owner.
        team_member_ids: List of UUIDs for team members.
        start_date: Project start date.
        end_date: Project end date (optional).
        budget: Allocated budget for the project.
        tags: List of tags for categorization.
        metadata: Additional key-value pairs for extensibility.
        created_at: Timestamp when the project was created.
        updated_at: Timestamp when the project was last updated.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique project identifier")
    name: str = Field(..., min_length=1, max_length=200, description="Project name")
    description: str = Field(
        default="", max_length=5000, description="Project description"
    )
    status: ProjectStatus = Field(
        default=ProjectStatus.DRAFT, description="Current project status"
    )
    priority: ProjectPriority = Field(
        default=ProjectPriority.MEDIUM, description="Project priority level"
    )
    owner_id: UUID = Field(..., description="UUID of the project owner")
    team_member_ids: List[UUID] = Field(
        default_factory=list, description="List of team member UUIDs"
    )
    start_date: datetime = Field(
        default_factory=datetime.utcnow, description="Project start date"
    )
    end_date: Optional[datetime] = Field(
        default=None, description="Project end date"
    )
    budget: float = Field(
        default=0.0, ge=0.0, description="Allocated project budget"
    )
    tags: List[str] = Field(
        default_factory=list, description="List of project tags"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional project metadata"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Validate project name.

        Args:
            value: The project name to validate.

        Returns:
            The validated project name.

        Raises:
            ValueError: If the name contains invalid characters.
        """
        if not value.strip():
            raise ValueError("Project name cannot be empty or whitespace only")
        if any(char in value for char in ["<", ">", "&", "%"]):
            raise ValueError("Project name contains invalid characters")
        return value.strip()

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: List[str]) -> List[str]:
        """Validate project tags.

        Args:
            value: List of tags to validate.

        Returns:
            The validated list of tags.

        Raises:
            ValueError: If any tag is invalid.
        """
        validated_tags = []
        for tag in value:
            if not tag or not tag.strip():
                raise ValueError("Tag cannot be empty")
            if len(tag) > 50:
                raise ValueError(f"Tag '{tag}' exceeds maximum length of 50 characters")
            validated_tags.append(tag.strip().lower())
        return validated_tags

    @field_validator("budget")
    @classmethod
    def validate_budget(cls, value: float) -> float:
        """Validate project budget.

        Args:
            value: The budget value to validate.

        Returns:
            The validated budget value.

        Raises:
            ValueError: If the budget is negative.
        """
        if value < 0:
            raise ValueError("Budget cannot be negative")
        return round(value, 2)

    @model_validator(mode="after")
    def validate_dates(self) -> "Project":
        """Validate project date consistency.

        Returns:
            The validated project instance.

        Raises:
            ValueError: If end_date is before start_date.
        """
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")
        return self

    @model_validator(mode="after")
    def validate_owner_not_in_team(self) -> "Project":
        """Ensure owner is not duplicated in team members.

        Returns:
            The validated project instance.
        """
        if self.owner_id in self.team_member_ids:
            self.team_member_ids.remove(self.owner_id)
        return self

    def add_team_member(self, member_id: UUID) -> None:
        """Add a team member to the project.

        Args:
            member_id: UUID of the team member to add.

        Raises:
            ValueError: If the member is already part of the team.
        """
        if member_id in self.team_member_ids:
            raise ValueError(f"Team member {member_id} is already part of the project")
        if member_id == self.owner_id:
            raise ValueError("Project owner cannot be added as a team member")
        self.team_member_ids.append(member_id)
        self.updated_at = datetime.utcnow()

    def remove_team_member(self, member_id: UUID) -> None:
        """Remove a team member from the project.

        Args:
            member_id: UUID of the team member to remove.

        Raises:
            ValueError: If the member is not found in the team.
        """
        if member_id not in self.team_member_ids:
            raise ValueError(f"Team member {member_id} not found in project")
        self.team_member_ids.remove(member_id)
        self.updated_at = datetime.utcnow()

    def update_status(self, new_status: ProjectStatus) -> None:
        """Update the project status.

        Args:
            new_status: The new status to set.

        Raises:
            ValueError: If the status transition is invalid.
        """
        valid_transitions = {
            ProjectStatus.DRAFT: [ProjectStatus.ACTIVE, ProjectStatus.CANCELLED],
            ProjectStatus.ACTIVE: [
                ProjectStatus.ON_HOLD,
                ProjectStatus.COMPLETED,
                ProjectStatus.CANCELLED,
            ],
            ProjectStatus.ON_HOLD: [ProjectStatus.ACTIVE, ProjectStatus.CANCELLED],
            ProjectStatus.COMPLETED: [ProjectStatus.ARCHIVED],
            ProjectStatus.CANCELLED: [ProjectStatus.ARCHIVED],
            ProjectStatus.ARCHIVED: [],
        }

        if new_status not in valid_transitions.get(self.status, []):
            raise ValueError(
                f"Cannot transition from {self.status.value} to {new_status.value}"
            )
        self.status = new_status
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary representation.

        Returns:
            Dictionary containing all project attributes.
        """
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "owner_id": str(self.owner_id),
            "team_member_ids": [str(member_id) for member_id in self.team_member_ids],
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "budget": self.budget,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        """Create a Project instance from a dictionary.

        Args:
            data: Dictionary containing project data.

        Returns:
            A new Project instance.

        Raises:
            ValueError: If required fields are missing or data is invalid.
        """
        required_fields = ["name", "owner_id"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        # Convert string UUIDs to UUID objects if necessary
        if isinstance(data.get("owner_id"), str):
            data["owner_id"] = UUID(data["owner_id"])
        if isinstance(data.get("id"), str):
            data["id"] = UUID(data["id"])
        if isinstance(data.get("team_member_ids"), list):
            data["team_member_ids"] = [
                UUID(member_id) if isinstance(member_id, str) else member_id
                for member_id in data["team_member_ids"]
            ]

        # Parse datetime strings
        for date_field in ["start_date", "end_date", "created_at", "updated_at"]:
            if isinstance(data.get(date_field), str):
                try:
                    data[date_field] = datetime.fromisoformat(data[date_field])
                except (ValueError, TypeError):
                    raise ValueError(f"Invalid datetime format for {date_field}")

        return cls(**data)

    def __str__(self) -> str:
        """Return string representation of the project.

        Returns:
            Human-readable string representation.
        """
        return f"Project(id={self.id}, name='{self.name}', status={self.status.value})"

    def __repr__(self) -> str:
        """Return official string representation of the project.

        Returns:
            Detailed string representation for debugging.
        """
        return (
            f"Project(id={self.id!r}, name={self.name!r}, "
            f"status={self.status!r}, priority={self.priority!r}, "
            f"owner_id={self.owner_id!r})"
        )