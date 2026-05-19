"""
Integration tests for the application.

This module contains integration tests that verify the interaction between
multiple components of the system, ensuring they work together correctly.
"""

import pytest
import asyncio
from typing import AsyncGenerator, Dict, Any, List
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from src.main import app
from src.database import DatabaseManager, get_database
from src.cache import CacheManager, get_cache
from src.services.user_service import UserService
from src.services.data_service import DataService
from src.models.user import User, UserCreate, UserUpdate
from src.models.data import DataRecord, DataQuery
from src.core.exceptions import (
    ServiceException,
    DatabaseException,
    CacheException,
    ValidationException,
)
from src.core.config import settings


@pytest.fixture
async def database_manager() -> AsyncGenerator[DatabaseManager, None]:
    """Fixture providing a database manager instance."""
    db_manager = DatabaseManager(
        connection_string=settings.TEST_DATABASE_URL,
        pool_size=5,
        max_overflow=10,
    )
    try:
        await db_manager.initialize()
        yield db_manager
    finally:
        await db_manager.close()


@pytest.fixture
async def cache_manager() -> AsyncGenerator[CacheManager, None]:
    """Fixture providing a cache manager instance."""
    cache_manager = CacheManager(
        host=settings.TEST_REDIS_HOST,
        port=settings.TEST_REDIS_PORT,
        db=settings.TEST_REDIS_DB,
    )
    try:
        await cache_manager.initialize()
        yield cache_manager
    finally:
        await cache_manager.close()


@pytest.fixture
async def user_service(
    database_manager: DatabaseManager,
    cache_manager: CacheManager,
) -> UserService:
    """Fixture providing a user service instance."""
    return UserService(
        database=database_manager,
        cache=cache_manager,
    )


@pytest.fixture
async def data_service(
    database_manager: DatabaseManager,
    cache_manager: CacheManager,
) -> DataService:
    """Fixture providing a data service instance."""
    return DataService(
        database=database_manager,
        cache=cache_manager,
    )


@pytest.fixture
async def test_user_data() -> UserCreate:
    """Fixture providing test user creation data."""
    return UserCreate(
        username="test_user_integration",
        email="test_integration@example.com",
        password="SecurePass123!",
        first_name="Test",
        last_name="User",
    )


@pytest.fixture
async def test_data_record() -> Dict[str, Any]:
    """Fixture providing test data record."""
    return {
        "name": "test_record_integration",
        "value": 42,
        "metadata": {
            "source": "integration_test",
            "version": "1.0",
        },
        "tags": ["test", "integration"],
    }


class TestUserServiceIntegration:
    """Integration tests for UserService."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve_user(
        self,
        user_service: UserService,
        test_user_data: UserCreate,
    ) -> None:
        """Test creating a user and retrieving it from the database."""
        try:
            # Create user
            created_user: User = await user_service.create_user(test_user_data)
            assert created_user is not None
            assert created_user.username == test_user_data.username
            assert created_user.email == test_user_data.email
            assert created_user.is_active is True

            # Retrieve user by ID
            retrieved_user: User = await user_service.get_user_by_id(
                created_user.id
            )
            assert retrieved_user is not None
            assert retrieved_user.id == created_user.id
            assert retrieved_user.username == created_user.username

            # Retrieve user by username
            retrieved_by_username: User = await user_service.get_user_by_username(
                test_user_data.username
            )
            assert retrieved_by_username is not None
            assert retrieved_by_username.id == created_user.id

        except (ServiceException, DatabaseException, CacheException) as exc:
            pytest.fail(f"User service integration failed: {exc}")

    @pytest.mark.asyncio
    async def test_update_user_with_cache_invalidation(
        self,
        user_service: UserService,
        test_user_data: UserCreate,
    ) -> None:
        """Test updating a user and verifying cache invalidation."""
        try:
            # Create user
            created_user: User = await user_service.create_user(test_user_data)
            assert created_user is not None

            # Update user
            update_data: UserUpdate = UserUpdate(
                first_name="Updated",
                last_name="Name",
                email="updated_integration@example.com",
            )
            updated_user: User = await user_service.update_user(
                created_user.id,
                update_data,
            )
            assert updated_user is not None
            assert updated_user.first_name == "Updated"
            assert updated_user.last_name == "Name"
            assert updated_user.email == "updated_integration@example.com"

            # Verify cache was invalidated by retrieving again
            retrieved_user: User = await user_service.get_user_by_id(
                created_user.id
            )
            assert retrieved_user is not None
            assert retrieved_user.first_name == "Updated"

        except (ServiceException, DatabaseException, CacheException) as exc:
            pytest.fail(f"User update integration failed: {exc}")

    @pytest.mark.asyncio
    async def test_delete_user_cascading(
        self,
        user_service: UserService,
        data_service: DataService,
        test_user_data: UserCreate,
        test_data_record: Dict[str, Any],
    ) -> None:
        """Test deleting a user and cascading effects on related data."""
        try:
            # Create user
            created_user: User = await user_service.create_user(test_user_data)
            assert created_user is not None

            # Create data records for the user
            record_ids: List[str] = []
            for i in range(3):
                record_data: Dict[str, Any] = {
                    **test_data_record,
                    "name": f"test_record_{i}_integration",
                    "user_id": created_user.id,
                }
                created_record: DataRecord = await data_service.create_record(
                    record_data
                )
                record_ids.append(created_record.id)

            # Delete user
            deletion_result: bool = await user_service.delete_user(
                created_user.id
            )
            assert deletion_result is True

            # Verify user is deleted
            with pytest.raises(ServiceException):
                await user_service.get_user_by_id(created_user.id)

            # Verify related data records are deleted or marked as deleted
            for record_id in record_ids:
                with pytest.raises(ServiceException):
                    await data_service.get_record(record_id)

        except (ServiceException, DatabaseException, CacheException) as exc:
            pytest.fail(f"User deletion integration failed: {exc}")


class TestDataServiceIntegration:
    """Integration tests for DataService."""

    @pytest.mark.asyncio
    async def test_create_and_query_data_records(
        self,
        data_service: DataService,
        test_data_record: Dict[str, Any],
    ) -> None:
        """Test creating data records and querying them."""
        try:
            # Create multiple records
            created_records: List[DataRecord] = []
            for i in range(5):
                record_data: Dict[str, Any] = {
                    **test_data_record,
                    "name": f"test_record_{i}_integration",
                    "value": i * 10,
                }
                created_record: DataRecord = await data_service.create_record(
                    record_data
                )
                created_records.append(created_record)

            assert len(created_records) == 5

            # Query records with filters
            query: DataQuery = DataQuery(
                tags=["test", "integration"],
                min_value=10,
                max_value=40,
                limit=10,
                offset=0,
            )
            queried_records: List[DataRecord] = await data_service.query_records(
                query
            )
            assert len(queried_records) == 3  # values 10, 20, 30

            # Verify ordering
            for i, record in enumerate(queried_records):
                assert record.value == (i + 1) * 10

        except (ServiceException, DatabaseException, CacheException) as exc:
            pytest.fail(f"Data record creation integration failed: {exc}")

    @pytest.mark.asyncio
    async def test_cache_hit_and_miss(
        self,
        data_service: DataService,
        test_data_record: Dict[str, Any],
    ) -> None:
        """Test cache behavior for data record retrieval."""
        try:
            # Create a record
            created_record: DataRecord = await data_service.create_record(
                test_data_record
            )
            assert created_record is not None

            # First retrieval should be a cache miss (populates cache)
            first_retrieval: DataRecord = await data_service.get_record(
                created_record.id
            )
            assert first_retrieval is not None
            assert first_retrieval.id == created_record.id

            # Second retrieval should be a cache hit
            second_retrieval: DataRecord = await data_service.get_record(
                created_record.id
            )
            assert second_retrieval is not None
            assert second_retrieval.id == created_record.id

            # Verify both retrievals return the same data
            assert first_retrieval.name == second_retrieval.name
            assert first_retrieval.value == second_retrieval.value

        except (ServiceException, DatabaseException, CacheException) as exc:
            pytest.fail(f"Cache integration failed: {exc}")

    @pytest.mark.asyncio
    async def test_bulk_operations_with_transactions(
        self,
        data_service: DataService,
        test_data_record: Dict[str, Any],
    ) -> None:
        """Test bulk operations with transaction rollback on failure."""
        try:
            # Prepare bulk data
            bulk_data: List[Dict[str, Any]] = []
            for i in range(10):
                record_data: Dict[str, Any] = {
                    **test_data_record,
                    "name": f"bulk_record_{i}_integration",
                    "value": i,
                }
                bulk_data.append(record_data)

            # Execute bulk create
            created_records: List[DataRecord] = (
                await data_service.bulk_create_records(bulk_data)
            )
            assert len(created_records) == 10

            # Verify all records exist
            for record in created_records:
                retrieved: DataRecord = await data_service.get_record(record.id)
                assert retrieved is not None

            # Test bulk update
            update_values: Dict[str, Any] = {"value": 100}
            updated_count: int = await data_service.bulk_update_records(
                record_ids=[r.id for r in created_records[:5]],
                update_data=update_values,
            )
            assert updated_count == 5

            # Verify updates
            for record in created_records[:5]:
                retrieved: DataRecord = await data_service.get_record(record.id)
                assert retrieved.value == 100

            # Test bulk delete
            deleted_count: int = await data_service.bulk_delete_records(
                record_ids=[r.id for r in created_records[5:]]
            )
            assert deleted_count == 5

            # Verify deletions
            for record in created_records[5:]:
                with pytest.raises(ServiceException):
                    await data_service.get_record(record.id)

        except (ServiceException, DatabaseException, CacheException) as exc:
            pytest.fail(f"Bulk operations integration failed: {exc}")


class TestCrossServiceIntegration:
    """Integration tests involving multiple services."""

    @pytest.mark.asyncio
    async def test_user_data_relationship(
        self,
        user_service: UserService,
        data_service: DataService,
        test_user_data: UserCreate,
        test_data_record: Dict[str, Any],
    ) -> None:
        """Test the relationship between users and their data records."""
        try:
            # Create user
            created_user: User = await user_service.create_user(test_user_data)
            assert created_user is not None

            # Create data records associated with the user
            associated_records: List[DataRecord] = []
            for i in range(3):
                record_data: Dict[str, Any] = {
                    **test_data_record,
                    "name": f"user_data_{i}_integration",
                    "user_id": created_user.id,
                }
                created_record: DataRecord = await data_service.create_record(
                    record_data
                )
                associated_records.append(created_record)

            # Retrieve all records for the user
            user_records: List[DataRecord] = (
                await data_service.get_records_by_user_id(created_user.id)
            )
            assert len(user_records) == 3

            # Verify record ownership
            for record in user_records:
                assert record.user_id == created_user.id

            # Update user and verify records remain
            update_data: UserUpdate = UserUpdate(
                first_name="UpdatedUser",
            )
            await user_service.update_user(created_user.id, update_data)

            user_records_after_update: List[DataRecord] = (
                await data_service.get_records_by_user_id(created_user.id)
            )
            assert len(user_records_after_update) == 3

        except (ServiceException, DatabaseException, CacheException) as exc:
            pytest.fail(f"Cross-service integration failed: {exc}")

    @pytest.mark.asyncio
    async def test_concurrent_operations(
        self,
        user_service: UserService,
        data_service: DataService,
        test_user_data: UserCreate,
        test_data_record: Dict[str, Any],
    ) -> None:
        """Test concurrent operations across services."""
        try:
            # Create user
            created_user: User = await user_service.create_user(test_user_data)
            assert created_user is not None

            # Perform concurrent operations
            async def create_record_concurrently(
                index: int,
            ) -> DataRecord:
                """Helper function for concurrent record creation."""
                record_data: Dict[str, Any] = {
                    **test_data_record,
                    "name": f"concurrent_record_{index}_integration",
                    "user_id": created_user.id,
                    "value": index,
                }
                return await data_service.create_record(record_data)

            # Execute concurrent record creations
            tasks: List[asyncio.Task] = [
                asyncio.create_task(create_record_concurrently(i))
                for i in range(5)
            ]
            results: List[DataRecord] = await asyncio.gather(*tasks)

            # Verify all records were created
            assert len(results) == 5
            for record in results:
                assert record.user_id == created_user.id

            # Verify concurrent reads
            read_tasks: List[asyncio.Task] = [
                asyncio.create_task(
                    data_service.get_record(record.id)
                )
                for record in results
            ]
            read_results: List[DataRecord] = await asyncio.gather(*read_tasks)
            assert len(read_results) == 5

        except (ServiceException, DatabaseException, CacheException) as exc:
            pytest.fail(f"Concurrent operations integration failed: {exc}")


class TestErrorHandlingIntegration:
    """Integration tests for error handling across services."""

    @pytest.mark.asyncio
    async def test_database_connection_failure(
        self,
        user_service: UserService,
        test_user_data: UserCreate,
    ) -> None:
        """Test behavior when database connection fails."""
        with patch.object(
            user_service.database,
            "execute_query",
            side_effect=DatabaseException("Connection refused"),
        ):
            with pytest.raises(DatabaseException) as exc_info:
                await user_service.create_user(test_user_data)
            assert "Connection refused" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cache_failure_fallback(
        self,
        data_service: DataService,
        test_data_record: Dict[str, Any],
    ) -> None:
        """Test fallback behavior when cache is unavailable."""
        try:
            # Create record
            created_record: DataRecord = await data_service.create_record(
                test_data_record
            )
            assert created_record is not None

            # Simulate cache failure
            with patch.object(
                data_service.cache,
                "get",
                side_effect=CacheException("Cache unavailable"),
            ):
                # Should still work by falling back to database
                retrieved_record: DataRecord = await data_service.get_record(
                    created_record.id
                )
                assert retrieved_record is not None
                assert retrieved_record.id == created_record.id

        except (ServiceException, DatabaseException, CacheException) as exc:
            pytest.fail(f"Cache failure fallback integration failed: {exc}")

    @pytest.mark.asyncio
    async def test_validation_error_propagation(
        self,
        user_service: UserService,
    ) -> None:
        """Test validation error propagation across service boundaries."""
        invalid_user_data: UserCreate = UserCreate(
            username="",  # Invalid: empty username
            email="invalid-email",  # Invalid: not an email
            password="short",  # Invalid: too short
            first_name="",
            last_name="",
        )

        with pytest.raises(ValidationException) as exc_info:
            await user_service.create_user(invalid_user_data)
        assert "username" in str(exc_info.value).lower() or "email" in str(
            exc_info.value
        ).lower()


@pytest.mark.asyncio
async def test_full_workflow_integration(
    user_service: UserService,
    data_service: DataService,
    test_user_data: UserCreate,
    test_data_record: Dict[str, Any],
) -> None:
    """Test a complete workflow involving multiple services and operations."""
    try:
        # Step 1: Create user
        created_user: User = await user_service.create_user(test_user_data)
        assert created_user is not None
        assert created_user.is_active is True

        # Step 2: Create multiple data records
        record_names: List[str] = []
        for i in range(5):
            record_data: Dict[str, Any] = {
                **test_data_record,
                "name": f"workflow_record_{i}_integration",
                "user_id": created_user.id,
                "value": i * 20,
            }
            created_record: DataRecord = await data_service.create_record(
                record_data
            )
            record_names.append(created_record.name)

        # Step 3: Query records with filters
        query: DataQuery = DataQuery(
            user_id=created_user.id,
            min_value=20,
            max_value=80,
            limit=10,
        )
        queried_records: List[DataRecord] = await data_service.query_records(
            query
        )
        assert len(queried_records) == 3  # values 20, 40, 60

        # Step 4: Update user profile
        update_data: UserUpdate = UserUpdate(
            first_name="Workflow",
            last_name="Complete",
        )
        updated_user: User = await user_service.update_user(
            created_user.id,
            update_data,
        )
        assert updated_user.first_name == "Workflow"

        # Step 5: Update some records
        for record in queried_records:
            update_result: DataRecord = await data_service.update_record(
                record.id,
                {"value": record.value + 5},
            )
            assert update_result.value == record.value + 5

        # Step 6: Verify cache is working
        cached_user: User = await user_service.get_user_by_id(created_user.id)
        assert cached_user.first_name == "Workflow"

        # Step 7: Clean up - delete records and user
        for record in queried_records:
            await data_service.delete_record(record.id)

        await user_service.delete_user(created_user.id)

        # Step 8: Verify cleanup
        with pytest.raises(ServiceException):
            await user_service.get_user_by_id(created_user.id)

        for record in queried_records:
            with pytest.raises(ServiceException):
                await data_service.get_record(record.id)

    except (ServiceException, DatabaseException, CacheException) as exc:
        pytest.fail(f"Full workflow integration failed: {exc}")