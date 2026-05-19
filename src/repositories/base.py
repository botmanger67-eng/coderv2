from abc import ABC, abstractmethod
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
)
from uuid import UUID

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
ID = TypeVar("ID", bound=Union[int, str, UUID])


class BaseRepository(ABC, Generic[T, ID]):
    """
    Abstract base repository providing a generic interface for CRUD operations
    on domain entities. All concrete repository implementations should inherit
    from this class and implement the abstract methods.

    Type Parameters:
        T: The entity type (must be a Pydantic BaseModel subclass)
        ID: The type of the entity's identifier (int, str, or UUID)
    """

    @abstractmethod
    async def create(self, entity: T) -> T:
        """
        Persist a new entity in the data store.

        Args:
            entity: The entity instance to create

        Returns:
            The created entity with any generated fields populated

        Raises:
            ValueError: If the entity already exists or validation fails
            ConnectionError: If the data store connection fails
        """
        ...

    @abstractmethod
    async def get_by_id(self, entity_id: ID) -> Optional[T]:
        """
        Retrieve an entity by its unique identifier.

        Args:
            entity_id: The unique identifier of the entity

        Returns:
            The entity if found, None otherwise

        Raises:
            ConnectionError: If the data store connection fails
        """
        ...

    @abstractmethod
    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[T]:
        """
        Retrieve a paginated list of entities with optional filtering.

        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            filters: Optional dictionary of field-value pairs to filter by

        Returns:
            A list of entities matching the criteria

        Raises:
            ValueError: If skip or limit are negative
            ConnectionError: If the data store connection fails
        """
        ...

    @abstractmethod
    async def update(self, entity_id: ID, updates: Dict[str, Any]) -> Optional[T]:
        """
        Update an existing entity with partial or full field updates.

        Args:
            entity_id: The unique identifier of the entity to update
            updates: Dictionary of field names and their new values

        Returns:
            The updated entity if found, None otherwise

        Raises:
            ValueError: If the updates dictionary is empty or contains invalid fields
            ConnectionError: If the data store connection fails
        """
        ...

    @abstractmethod
    async def delete(self, entity_id: ID) -> bool:
        """
        Delete an entity by its unique identifier.

        Args:
            entity_id: The unique identifier of the entity to delete

        Returns:
            True if the entity was deleted, False if not found

        Raises:
            ConnectionError: If the data store connection fails
        """
        ...

    @abstractmethod
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count entities matching optional filter criteria.

        Args:
            filters: Optional dictionary of field-value pairs to filter by

        Returns:
            The number of entities matching the criteria

        Raises:
            ConnectionError: If the data store connection fails
        """
        ...

    @abstractmethod
    async def exists(self, entity_id: ID) -> bool:
        """
        Check if an entity exists by its unique identifier.

        Args:
            entity_id: The unique identifier to check

        Returns:
            True if the entity exists, False otherwise

        Raises:
            ConnectionError: If the data store connection fails
        """
        ...

    async def bulk_create(self, entities: List[T]) -> List[T]:
        """
        Persist multiple entities in a single operation.

        Default implementation calls create() for each entity.
        Override in subclasses for optimized batch operations.

        Args:
            entities: List of entity instances to create

        Returns:
            List of created entities with any generated fields populated

        Raises:
            ValueError: If any entity already exists or validation fails
            ConnectionError: If the data store connection fails
        """
        if not entities:
            return []

        created_entities: List[T] = []
        for entity in entities:
            created = await self.create(entity)
            created_entities.append(created)

        return created_entities

    async def bulk_delete(self, entity_ids: List[ID]) -> int:
        """
        Delete multiple entities by their identifiers.

        Default implementation calls delete() for each ID.
        Override in subclasses for optimized batch operations.

        Args:
            entity_ids: List of unique identifiers to delete

        Returns:
            Number of entities successfully deleted

        Raises:
            ConnectionError: If the data store connection fails
        """
        if not entity_ids:
            return 0

        deleted_count = 0
        for entity_id in entity_ids:
            if await self.delete(entity_id):
                deleted_count += 1

        return deleted_count

    async def get_or_create(
        self,
        entity_id: ID,
        defaults: Optional[Dict[str, Any]] = None,
    ) -> T:
        """
        Retrieve an existing entity or create a new one if it doesn't exist.

        Args:
            entity_id: The unique identifier to look up
            defaults: Optional dictionary of default field values for creation

        Returns:
            The existing or newly created entity

        Raises:
            ValueError: If creation fails due to validation errors
            ConnectionError: If the data store connection fails
        """
        existing = await self.get_by_id(entity_id)
        if existing is not None:
            return existing

        if defaults is None:
            defaults = {}

        # Create a new entity instance with the provided ID and defaults
        entity_data = {"id": entity_id, **defaults}
        entity_class: Type[T] = self.__class__.__orig_bases__[0].__args__[0]  # type: ignore
        entity = entity_class(**entity_data)

        return await self.create(entity)

    async def update_or_create(
        self,
        entity_id: ID,
        updates: Dict[str, Any],
    ) -> T:
        """
        Update an existing entity or create a new one if it doesn't exist.

        Args:
            entity_id: The unique identifier to look up
            updates: Dictionary of field values to set

        Returns:
            The updated or newly created entity

        Raises:
            ValueError: If the updates dictionary is empty or validation fails
            ConnectionError: If the data store connection fails
        """
        existing = await self.get_by_id(entity_id)
        if existing is not None:
            updated = await self.update(entity_id, updates)
            if updated is None:
                raise ValueError(f"Failed to update entity with ID {entity_id}")
            return updated

        # Create a new entity with the provided ID and updates
        entity_data = {"id": entity_id, **updates}
        entity_class: Type[T] = self.__class__.__orig_bases__[0].__args__[0]  # type: ignore
        entity = entity_class(**entity_data)

        return await self.create(entity)

    async def find_one(
        self,
        filters: Dict[str, Any],
    ) -> Optional[T]:
        """
        Find a single entity matching the given filter criteria.

        Args:
            filters: Dictionary of field-value pairs to match

        Returns:
            The first matching entity if found, None otherwise

        Raises:
            ValueError: If filters is empty
            ConnectionError: If the data store connection fails
        """
        if not filters:
            raise ValueError("Filters dictionary cannot be empty for find_one operation")

        results = await self.get_all(skip=0, limit=1, filters=filters)
        return results[0] if results else None

    async def find_many(
        self,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 100,
    ) -> List[T]:
        """
        Find multiple entities matching the given filter criteria.

        Args:
            filters: Dictionary of field-value pairs to match
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            A list of matching entities

        Raises:
            ValueError: If filters is empty, or skip/limit are negative
            ConnectionError: If the data store connection fails
        """
        if not filters:
            raise ValueError("Filters dictionary cannot be empty for find_many operation")

        return await self.get_all(skip=skip, limit=limit, filters=filters)

    async def count_by_filters(self, filters: Dict[str, Any]) -> int:
        """
        Count entities matching specific filter criteria.

        Args:
            filters: Dictionary of field-value pairs to match

        Returns:
            The number of matching entities

        Raises:
            ValueError: If filters is empty
            ConnectionError: If the data store connection fails
        """
        if not filters:
            raise ValueError("Filters dictionary cannot be empty for count_by_filters operation")

        return await self.count(filters=filters)