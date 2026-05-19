"""
Repositories package initialization.

This module provides the base repository class and exports all repository
implementations for data access layer abstraction.
"""

from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Protocol,
    TypeVar,
    Union,
    runtime_checkable,
)
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

# Type variables for generic repository pattern
T = TypeVar("T")
ID = TypeVar("ID", bound=Union[int, str, UUID])


@runtime_checkable
class Entity(Protocol):
    """Protocol defining the minimum interface for entities stored in repositories."""

    id: ID
    created_at: datetime
    updated_at: datetime


@dataclass
class RepositoryError(Exception):
    """Base exception for repository operations."""

    message: str
    entity_type: Optional[str] = None
    operation: Optional[str] = None
    original_error: Optional[Exception] = None

    def __post_init__(self) -> None:
        """Initialize the exception with formatted message."""
        if self.entity_type and self.operation:
            self.message = f"[{self.entity_type}] {self.operation}: {self.message}"
        super().__init__(self.message)


@dataclass
class EntityNotFoundError(RepositoryError):
    """Exception raised when an entity is not found."""

    entity_id: Optional[ID] = None

    def __post_init__(self) -> None:
        """Initialize with entity ID information."""
        if self.entity_id:
            self.message = f"Entity with ID '{self.entity_id}' not found. {self.message}"
        super().__post_init__()


@dataclass
class DuplicateEntityError(RepositoryError):
    """Exception raised when attempting to create a duplicate entity."""

    duplicate_key: Optional[str] = None

    def __post_init__(self) -> None:
        """Initialize with duplicate key information."""
        if self.duplicate_key:
            self.message = f"Duplicate entity with key '{self.duplicate_key}'. {self.message}"
        super().__post_init__()


@dataclass
class RepositoryValidationError(RepositoryError):
    """Exception raised when entity validation fails."""

    field_errors: Optional[Dict[str, str]] = None

    def __post_init__(self) -> None:
        """Initialize with field validation errors."""
        if self.field_errors:
            error_details = "; ".join(
                f"{field}: {error}" for field, error in self.field_errors.items()
            )
            self.message = f"Validation failed: {error_details}. {self.message}"
        super().__post_init__()


class BaseRepository(ABC, Generic[T, ID]):
    """
    Abstract base repository providing CRUD operations interface.

    This class defines the contract for all repository implementations,
    ensuring consistent data access patterns across the application.

    Type Parameters:
        T: The entity type this repository manages
        ID: The type of the entity's identifier
    """

    def __init__(self, entity_type: str) -> None:
        """
        Initialize the base repository.

        Args:
            entity_type: Human-readable name of the entity type for error messages
        """
        self._entity_type = entity_type

    @abstractmethod
    async def create(self, entity: T) -> T:
        """
        Create a new entity in the repository.

        Args:
            entity: The entity to create

        Returns:
            The created entity with any generated fields populated

        Raises:
            DuplicateEntityError: If an entity with the same unique key exists
            RepositoryValidationError: If the entity fails validation
            RepositoryError: For other repository-level errors
        """
        ...

    @abstractmethod
    async def get(self, entity_id: ID) -> T:
        """
        Retrieve an entity by its identifier.

        Args:
            entity_id: The unique identifier of the entity

        Returns:
            The requested entity

        Raises:
            EntityNotFoundError: If no entity exists with the given ID
            RepositoryError: For other repository-level errors
        """
        ...

    @abstractmethod
    async def update(self, entity_id: ID, updates: Dict[str, Any]) -> T:
        """
        Update an existing entity with partial updates.

        Args:
            entity_id: The unique identifier of the entity to update
            updates: Dictionary of fields to update with their new values

        Returns:
            The updated entity

        Raises:
            EntityNotFoundError: If no entity exists with the given ID
            RepositoryValidationError: If the updates fail validation
            RepositoryError: For other repository-level errors
        """
        ...

    @abstractmethod
    async def delete(self, entity_id: ID) -> bool:
        """
        Delete an entity by its identifier.

        Args:
            entity_id: The unique identifier of the entity to delete

        Returns:
            True if the entity was deleted, False if it didn't exist

        Raises:
            RepositoryError: For repository-level errors
        """
        ...

    @abstractmethod
    async def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "asc",
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[T]:
        """
        List entities with optional filtering, sorting, and pagination.

        Args:
            filters: Dictionary of field-value pairs to filter by
            sort_by: Field name to sort results by
            sort_order: Sort direction ('asc' or 'desc')
            limit: Maximum number of entities to return
            offset: Number of entities to skip for pagination

        Returns:
            List of entities matching the criteria

        Raises:
            RepositoryValidationError: If filter or sort parameters are invalid
            RepositoryError: For repository-level errors
        """
        ...

    @abstractmethod
    async def count(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Count entities matching the given filters.

        Args:
            filters: Dictionary of field-value pairs to filter by

        Returns:
            The count of matching entities

        Raises:
            RepositoryValidationError: If filter parameters are invalid
            RepositoryError: For repository-level errors
        """
        ...

    @abstractmethod
    async def exists(self, entity_id: ID) -> bool:
        """
        Check if an entity exists by its identifier.

        Args:
            entity_id: The unique identifier to check

        Returns:
            True if the entity exists, False otherwise

        Raises:
            RepositoryError: For repository-level errors
        """
        ...

    def _validate_id(self, entity_id: ID) -> None:
        """
        Validate that the provided ID is not None or empty.

        Args:
            entity_id: The identifier to validate

        Raises:
            RepositoryValidationError: If the ID is invalid
        """
        if entity_id is None:
            raise RepositoryValidationError(
                message="Entity ID cannot be None",
                entity_type=self._entity_type,
                operation="validate_id",
                field_errors={"id": "ID must not be None"},
            )

        if isinstance(entity_id, str) and not entity_id.strip():
            raise RepositoryValidationError(
                message="Entity ID cannot be empty",
                entity_type=self._entity_type,
                operation="validate_id",
                field_errors={"id": "ID must not be empty"},
            )

    def _generate_id(self) -> ID:
        """
        Generate a new unique identifier for an entity.

        Returns:
            A new UUID as the identifier

        Note:
            Override this method in subclasses to use different ID generation strategies
        """
        return uuid4()  # type: ignore

    def _update_timestamps(self, entity: T, is_new: bool = False) -> T:
        """
        Update the created_at and updated_at timestamps on an entity.

        Args:
            entity: The entity to update timestamps on
            is_new: If True, set created_at as well as updated_at

        Returns:
            The entity with updated timestamps

        Note:
            This method assumes the entity has created_at and updated_at attributes.
            Override if your entity uses different timestamp field names.
        """
        now = datetime.utcnow()
        if is_new and hasattr(entity, "created_at"):
            entity.created_at = now  # type: ignore
        if hasattr(entity, "updated_at"):
            entity.updated_at = now  # type: ignore
        return entity


# Export all public interfaces and exceptions
__all__: List[str] = [
    # Type variables
    "T",
    "ID",
    # Protocols
    "Entity",
    # Exceptions
    "RepositoryError",
    "EntityNotFoundError",
    "DuplicateEntityError",
    "RepositoryValidationError",
    # Base classes
    "BaseRepository",
]