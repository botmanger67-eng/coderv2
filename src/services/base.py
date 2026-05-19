from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from src.models.base import Base
from src.schemas.base import BaseCreateSchema, BaseUpdateSchema
from src.core.exceptions import (
    NotFoundError,
    ValidationError,
    DatabaseError,
    ServiceError,
)
from src.core.logging import get_logger

logger = get_logger(__name__)

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseCreateSchema)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseUpdateSchema)


class BaseService(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Base service class providing CRUD operations for all models.
    
    This service implements the repository pattern with generic type hints
    to ensure type safety across all service implementations.
    
    Attributes:
        model: The SQLAlchemy model class
        db_session: The async database session
    """

    def __init__(self, model: Type[ModelType], db_session: AsyncSession) -> None:
        """
        Initialize the base service.
        
        Args:
            model: SQLAlchemy model class
            db_session: Async database session
            
        Raises:
            ServiceError: If initialization fails
        """
        try:
            self.model = model
            self.db_session = db_session
            logger.debug(f"Initialized {self.__class__.__name__} for model {model.__name__}")
        except Exception as e:
            logger.error(f"Failed to initialize {self.__class__.__name__}: {str(e)}")
            raise ServiceError(f"Service initialization failed: {str(e)}")

    async def create(self, schema: CreateSchemaType) -> ModelType:
        """
        Create a new record in the database.
        
        Args:
            schema: Pydantic schema with creation data
            
        Returns:
            Created model instance
            
        Raises:
            ValidationError: If schema validation fails
            DatabaseError: If database operation fails
        """
        try:
            validated_data = schema.model_dump(exclude_unset=True)
            instance = self.model(**validated_data)
            self.db_session.add(instance)
            await self.db_session.commit()
            await self.db_session.refresh(instance)
            logger.info(f"Created {self.model.__name__} with ID: {instance.id}")
            return instance
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to create {self.model.__name__}: {str(e)}")
            raise DatabaseError(f"Failed to create {self.model.__name__}: {str(e)}")

    async def get(self, id: Union[UUID, int, str]) -> Optional[ModelType]:
        """
        Retrieve a record by its ID.
        
        Args:
            id: Primary key value (UUID, int, or string)
            
        Returns:
            Model instance if found, None otherwise
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = select(self.model).where(self.model.id == id)
            result = await self.db_session.execute(query)
            instance = result.scalar_one_or_none()
            if instance:
                logger.debug(f"Retrieved {self.model.__name__} with ID: {id}")
            else:
                logger.debug(f"{self.model.__name__} with ID: {id} not found")
            return instance
        except Exception as e:
            logger.error(f"Failed to retrieve {self.model.__name__} with ID {id}: {str(e)}")
            raise DatabaseError(f"Failed to retrieve {self.model.__name__}: {str(e)}")

    async def get_or_raise(self, id: Union[UUID, int, str]) -> ModelType:
        """
        Retrieve a record by its ID or raise an exception.
        
        Args:
            id: Primary key value (UUID, int, or string)
            
        Returns:
            Model instance
            
        Raises:
            NotFoundError: If record not found
            DatabaseError: If database operation fails
        """
        instance = await self.get(id)
        if not instance:
            logger.warning(f"{self.model.__name__} with ID {id} not found")
            raise NotFoundError(f"{self.model.__name__} with ID {id} not found")
        return instance

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False,
    ) -> List[ModelType]:
        """
        Retrieve multiple records with pagination and filtering.
        
        Args:
            skip: Number of records to skip (offset)
            limit: Maximum number of records to return
            filters: Dictionary of field-value pairs for filtering
            order_by: Field name to order by
            order_desc: Whether to order in descending order
            
        Returns:
            List of model instances
            
        Raises:
            ValidationError: If filter validation fails
            DatabaseError: If database operation fails
        """
        try:
            query = select(self.model)
            
            # Apply filters
            if filters:
                for field, value in filters.items():
                    if hasattr(self.model, field):
                        query = query.where(getattr(self.model, field) == value)
                    else:
                        raise ValidationError(f"Invalid filter field: {field}")
            
            # Apply ordering
            if order_by:
                if hasattr(self.model, order_by):
                    order_column = getattr(self.model, order_by)
                    query = query.order_by(order_column.desc() if order_desc else order_column)
                else:
                    raise ValidationError(f"Invalid order_by field: {order_by}")
            
            # Apply pagination
            query = query.offset(skip).limit(limit)
            
            result = await self.db_session.execute(query)
            instances = list(result.scalars().all())
            logger.debug(f"Retrieved {len(instances)} {self.model.__name__} instances")
            return instances
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve {self.model.__name__} instances: {str(e)}")
            raise DatabaseError(f"Failed to retrieve {self.model.__name__} instances: {str(e)}")

    async def update(
        self,
        id: Union[UUID, int, str],
        schema: UpdateSchemaType,
    ) -> ModelType:
        """
        Update a record by its ID.
        
        Args:
            id: Primary key value (UUID, int, or string)
            schema: Pydantic schema with update data
            
        Returns:
            Updated model instance
            
        Raises:
            NotFoundError: If record not found
            ValidationError: If schema validation fails
            DatabaseError: If database operation fails
        """
        try:
            instance = await self.get_or_raise(id)
            update_data = schema.model_dump(exclude_unset=True)
            
            if not update_data:
                logger.warning(f"No update data provided for {self.model.__name__} with ID {id}")
                return instance
            
            for field, value in update_data.items():
                setattr(instance, field, value)
            
            await self.db_session.commit()
            await self.db_session.refresh(instance)
            logger.info(f"Updated {self.model.__name__} with ID: {id}")
            return instance
        except NotFoundError:
            raise
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to update {self.model.__name__} with ID {id}: {str(e)}")
            raise DatabaseError(f"Failed to update {self.model.__name__}: {str(e)}")

    async def delete(self, id: Union[UUID, int, str]) -> bool:
        """
        Delete a record by its ID.
        
        Args:
            id: Primary key value (UUID, int, or string)
            
        Returns:
            True if deletion was successful
            
        Raises:
            NotFoundError: If record not found
            DatabaseError: If database operation fails
        """
        try:
            instance = await self.get_or_raise(id)
            await self.db_session.delete(instance)
            await self.db_session.commit()
            logger.info(f"Deleted {self.model.__name__} with ID: {id}")
            return True
        except NotFoundError:
            raise
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to delete {self.model.__name__} with ID {id}: {str(e)}")
            raise DatabaseError(f"Failed to delete {self.model.__name__}: {str(e)}")

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records with optional filtering.
        
        Args:
            filters: Dictionary of field-value pairs for filtering
            
        Returns:
            Number of matching records
            
        Raises:
            ValidationError: If filter validation fails
            DatabaseError: If database operation fails
        """
        try:
            query = select(self.model)
            
            if filters:
                for field, value in filters.items():
                    if hasattr(self.model, field):
                        query = query.where(getattr(self.model, field) == value)
                    else:
                        raise ValidationError(f"Invalid filter field: {field}")
            
            result = await self.db_session.execute(query)
            count = len(result.scalars().all())
            logger.debug(f"Counted {count} {self.model.__name__} instances")
            return count
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to count {self.model.__name__} instances: {str(e)}")
            raise DatabaseError(f"Failed to count {self.model.__name__} instances: {str(e)}")

    async def exists(self, id: Union[UUID, int, str]) -> bool:
        """
        Check if a record exists by its ID.
        
        Args:
            id: Primary key value (UUID, int, or string)
            
        Returns:
            True if record exists, False otherwise
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            instance = await self.get(id)
            return instance is not None
        except Exception as e:
            logger.error(f"Failed to check existence of {self.model.__name__} with ID {id}: {str(e)}")
            raise DatabaseError(f"Failed to check existence of {self.model.__name__}: {str(e)}")

    async def bulk_create(self, schemas: List[CreateSchemaType]) -> List[ModelType]:
        """
        Create multiple records in a single transaction.
        
        Args:
            schemas: List of Pydantic schemas with creation data
            
        Returns:
            List of created model instances
            
        Raises:
            ValidationError: If schema validation fails
            DatabaseError: If database operation fails
        """
        try:
            instances = []
            for schema in schemas:
                validated_data = schema.model_dump(exclude_unset=True)
                instance = self.model(**validated_data)
                self.db_session.add(instance)
                instances.append(instance)
            
            await self.db_session.commit()
            
            # Refresh all instances
            for instance in instances:
                await self.db_session.refresh(instance)
            
            logger.info(f"Bulk created {len(instances)} {self.model.__name__} instances")
            return instances
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to bulk create {self.model.__name__} instances: {str(e)}")
            raise DatabaseError(f"Failed to bulk create {self.model.__name__} instances: {str(e)}")

    async def bulk_delete(self, ids: List[Union[UUID, int, str]]) -> int:
        """
        Delete multiple records by their IDs.
        
        Args:
            ids: List of primary key values
            
        Returns:
            Number of deleted records
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = delete(self.model).where(self.model.id.in_(ids))
            result = await self.db_session.execute(query)
            await self.db_session.commit()
            deleted_count = result.rowcount
            logger.info(f"Bulk deleted {deleted_count} {self.model.__name__} instances")
            return deleted_count
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to bulk delete {self.model.__name__} instances: {str(e)}")
            raise DatabaseError(f"Failed to bulk delete {self.model.__name__} instances: {str(e)}")

    async def execute_raw_query(self, query: Select) -> List[ModelType]:
        """
        Execute a raw SQLAlchemy select query.
        
        Args:
            query: SQLAlchemy Select statement
            
        Returns:
            List of model instances
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            result = await self.db_session.execute(query)
            instances = list(result.scalars().all())
            logger.debug(f"Executed raw query, retrieved {len(instances)} instances")
            return instances
        except Exception as e:
            logger.error(f"Failed to execute raw query: {str(e)}")
            raise DatabaseError(f"Failed to execute raw query: {str(e)}")

    async def refresh(self, instance: ModelType) -> ModelType:
        """
        Refresh a model instance from the database.
        
        Args:
            instance: Model instance to refresh
            
        Returns:
            Refreshed model instance
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            await self.db_session.refresh(instance)
            return instance
        except Exception as e:
            logger.error(f"Failed to refresh {self.model.__name__} instance: {str(e)}")
            raise DatabaseError(f"Failed to refresh {self.model.__name__} instance: {str(e)}")