"""Database connection and session management module.

This module provides a robust database connection manager with session handling,
connection pooling, and transaction management capabilities. It supports both
synchronous and asynchronous database operations with proper error handling.
"""

import asyncio
import logging
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, AsyncIterator, Dict, Generator, List, Optional, Tuple, Union

import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection, Result
from sqlalchemy.exc import (
    DatabaseError,
    IntegrityError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
    TimeoutError,
)
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from src.core.config import DatabaseConfig
from src.core.exceptions import (
    DatabaseConnectionError,
    DatabaseIntegrityError,
    DatabaseOperationError,
    DatabaseTimeoutError,
)
from src.core.logging import get_logger

logger = get_logger(__name__)


class DatabaseType(Enum):
    """Supported database types."""

    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    ORACLE = "oracle"
    MSSQL = "mssql"


@dataclass
class ConnectionPoolConfig:
    """Configuration for database connection pool."""

    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: float = 30.0
    pool_recycle: int = 3600
    pool_pre_ping: bool = True
    echo: bool = False
    hide_parameters: bool = True


@dataclass
class DatabaseHealth:
    """Database health check result."""

    is_healthy: bool
    latency_ms: float
    error_message: Optional[str] = None
    connection_count: int = 0
    active_connections: int = 0


class DatabaseManager:
    """Manages database connections and sessions with connection pooling.

    This class provides a centralized interface for database operations including
    connection management, session handling, transaction management, and health
    monitoring.

    Attributes:
        config: Database configuration object.
        engine: SQLAlchemy engine instance.
        async_engine: Async SQLAlchemy engine instance.
        session_factory: Synchronous session factory.
        async_session_factory: Asynchronous session factory.
    """

    def __init__(
        self,
        config: DatabaseConfig,
        pool_config: Optional[ConnectionPoolConfig] = None,
    ) -> None:
        """Initialize the database manager.

        Args:
            config: Database configuration object.
            pool_config: Optional connection pool configuration.

        Raises:
            DatabaseConnectionError: If initialization fails.
        """
        self.config = config
        self.pool_config = pool_config or ConnectionPoolConfig()
        self._engine: Optional[Engine] = None
        self._async_engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._async_session_factory: Optional[async_sessionmaker] = None
        self._is_initialized: bool = False
        self._connection_count: int = 0
        self._active_connections: int = 0

    def initialize(self) -> None:
        """Initialize database engines and session factories.

        Creates synchronous and asynchronous engines with connection pooling
        configuration.

        Raises:
            DatabaseConnectionError: If engine creation fails.
        """
        try:
            self._create_sync_engine()
            self._create_async_engine()
            self._create_session_factories()
            self._is_initialized = True
            logger.info(
                "Database manager initialized successfully",
                extra={
                    "database_type": self.config.database_type.value,
                    "host": self.config.host,
                    "port": self.config.port,
                },
            )
        except SQLAlchemyError as error:
            raise DatabaseConnectionError(
                f"Failed to initialize database manager: {error}"
            ) from error

    def _create_sync_engine(self) -> None:
        """Create synchronous SQLAlchemy engine with connection pooling."""
        connection_url = self._build_connection_url()
        pool_kwargs = self._get_pool_kwargs()

        self._engine = create_engine(
            connection_url,
            **pool_kwargs,
            echo=self.pool_config.echo,
            hide_parameters=self.pool_config.hide_parameters,
        )

    def _create_async_engine(self) -> None:
        """Create asynchronous SQLAlchemy engine with connection pooling."""
        connection_url = self._build_async_connection_url()
        pool_kwargs = self._get_pool_kwargs()

        self._async_engine = create_async_engine(
            connection_url,
            **pool_kwargs,
            echo=self.pool_config.echo,
            hide_parameters=self.pool_config.hide_parameters,
        )

    def _create_session_factories(self) -> None:
        """Create session factories for both sync and async operations."""
        if self._engine:
            self._session_factory = sessionmaker(
                bind=self._engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )

        if self._async_engine:
            self._async_session_factory = async_sessionmaker(
                bind=self._async_engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )

    def _build_connection_url(self) -> str:
        """Build synchronous database connection URL.

        Returns:
            Database connection URL string.

        Raises:
            DatabaseConnectionError: If URL construction fails.
        """
        try:
            return self.config.get_connection_url()
        except ValueError as error:
            raise DatabaseConnectionError(
                f"Invalid database configuration: {error}"
            ) from error

    def _build_async_connection_url(self) -> str:
        """Build asynchronous database connection URL.

        Returns:
            Async database connection URL string.

        Raises:
            DatabaseConnectionError: If URL construction fails.
        """
        try:
            return self.config.get_async_connection_url()
        except ValueError as error:
            raise DatabaseConnectionError(
                f"Invalid async database configuration: {error}"
            ) from error

    def _get_pool_kwargs(self) -> Dict[str, Any]:
        """Get connection pool keyword arguments.

        Returns:
            Dictionary of pool configuration parameters.
        """
        if self.config.database_type == DatabaseType.SQLITE:
            return {"poolclass": NullPool}

        return {
            "poolclass": QueuePool,
            "pool_size": self.pool_config.pool_size,
            "max_overflow": self.pool_config.max_overflow,
            "pool_timeout": self.pool_config.pool_timeout,
            "pool_recycle": self.pool_config.pool_recycle,
            "pool_pre_ping": self.pool_config.pool_pre_ping,
        }

    @property
    def engine(self) -> Engine:
        """Get synchronous engine instance.

        Returns:
            SQLAlchemy Engine instance.

        Raises:
            DatabaseConnectionError: If engine is not initialized.
        """
        if not self._engine:
            raise DatabaseConnectionError("Database engine not initialized")
        return self._engine

    @property
    def async_engine(self) -> AsyncEngine:
        """Get asynchronous engine instance.

        Returns:
            SQLAlchemy AsyncEngine instance.

        Raises:
            DatabaseConnectionError: If async engine is not initialized.
        """
        if not self._async_engine:
            raise DatabaseConnectionError("Async database engine not initialized")
        return self._async_engine

    @property
    def session_factory(self) -> sessionmaker:
        """Get synchronous session factory.

        Returns:
            SQLAlchemy sessionmaker instance.

        Raises:
            DatabaseConnectionError: If session factory is not initialized.
        """
        if not self._session_factory:
            raise DatabaseConnectionError("Session factory not initialized")
        return self._session_factory

    @property
    def async_session_factory(self) -> async_sessionmaker:
        """Get asynchronous session factory.

        Returns:
            SQLAlchemy async_sessionmaker instance.

        Raises:
            DatabaseConnectionError: If async session factory is not initialized.
        """
        if not self._async_session_factory:
            raise DatabaseConnectionError("Async session factory not initialized")
        return self._async_session_factory

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a synchronous database session with context management.

        Yields:
            SQLAlchemy Session instance.

        Raises:
            DatabaseConnectionError: If session creation fails.
        """
        session: Session = self.session_factory()
        try:
            self._connection_count += 1
            self._active_connections += 1
            yield session
            session.commit()
        except IntegrityError as error:
            session.rollback()
            raise DatabaseIntegrityError(
                f"Database integrity error: {error}"
            ) from error
        except OperationalError as error:
            session.rollback()
            raise DatabaseConnectionError(
                f"Database operational error: {error}"
            ) from error
        except TimeoutError as error:
            session.rollback()
            raise DatabaseTimeoutError(
                f"Database timeout error: {error}"
            ) from error
        except SQLAlchemyError as error:
            session.rollback()
            raise DatabaseOperationError(
                f"Database operation error: {error}"
            ) from error
        finally:
            self._active_connections -= 1
            session.close()

    @asynccontextmanager
    async def get_async_session(
        self,
    ) -> AsyncIterator[AsyncSession]:
        """Get an asynchronous database session with context management.

        Yields:
            SQLAlchemy AsyncSession instance.

        Raises:
            DatabaseConnectionError: If session creation fails.
        """
        async with self.async_session_factory() as session:
            try:
                self._connection_count += 1
                self._active_connections += 1
                yield session
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise DatabaseIntegrityError(
                    f"Database integrity error: {error}"
                ) from error
            except OperationalError as error:
                await session.rollback()
                raise DatabaseConnectionError(
                    f"Database operational error: {error}"
                ) from error
            except TimeoutError as error:
                await session.rollback()
                raise DatabaseTimeoutError(
                    f"Database timeout error: {error}"
                ) from error
            except SQLAlchemyError as error:
                await session.rollback()
                raise DatabaseOperationError(
                    f"Database operation error: {error}"
                ) from error
            finally:
                self._active_connections -= 1

    @contextmanager
    def get_connection(self) -> Generator[Connection, None, None]:
        """Get a raw database connection with context management.

        Yields:
            SQLAlchemy Connection instance.

        Raises:
            DatabaseConnectionError: If connection acquisition fails.
        """
        try:
            with self.engine.connect() as connection:
                self._connection_count += 1
                self._active_connections += 1
                yield connection
        except SQLAlchemyError as error:
            raise DatabaseConnectionError(
                f"Failed to acquire database connection: {error}"
            ) from error
        finally:
            self._active_connections -= 1

    @asynccontextmanager
    async def get_async_connection(
        self,
    ) -> AsyncIterator[AsyncConnection]:
        """Get an asynchronous raw database connection with context management.

        Yields:
            SQLAlchemy AsyncConnection instance.

        Raises:
            DatabaseConnectionError: If connection acquisition fails.
        """
        try:
            async with self.async_engine.connect() as connection:
                self._connection_count += 1
                self._active_connections += 1
                yield connection
        except SQLAlchemyError as error:
            raise DatabaseConnectionError(
                f"Failed to acquire async database connection: {error}"
            ) from error
        finally:
            self._active_connections -= 1

    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Result:
        """Execute a synchronous SQL query.

        Args:
            query: SQL query string.
            params: Optional query parameters.

        Returns:
            SQLAlchemy Result instance.

        Raises:
            DatabaseOperationError: If query execution fails.
        """
        try:
            with self.get_connection() as connection:
                result = connection.execute(text(query), params or {})
                connection.commit()
                return result
        except SQLAlchemyError as error:
            raise DatabaseOperationError(
                f"Query execution failed: {error}"
            ) from error

    async def execute_async_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Result:
        """Execute an asynchronous SQL query.

        Args:
            query: SQL query string.
            params: Optional query parameters.

        Returns:
            SQLAlchemy Result instance.

        Raises:
            DatabaseOperationError: If query execution fails.
        """
        try:
            async with self.get_async_connection() as connection:
                result = await connection.execute(text(query), params or {})
                await connection.commit()
                return result
        except SQLAlchemyError as error:
            raise DatabaseOperationError(
                f"Async query execution failed: {error}"
            ) from error

    def execute_many(
        self,
        query: str,
        params_list: List[Dict[str, Any]],
    ) -> None:
        """Execute a synchronous query with multiple parameter sets.

        Args:
            query: SQL query string.
            params_list: List of parameter dictionaries.

        Raises:
            DatabaseOperationError: If bulk execution fails.
        """
        try:
            with self.get_connection() as connection:
                connection.execute(text(query), params_list)
                connection.commit()
        except SQLAlchemyError as error:
            raise DatabaseOperationError(
                f"Bulk query execution failed: {error}"
            ) from error

    async def execute_async_many(
        self,
        query: str,
        params_list: List[Dict[str, Any]],
    ) -> None:
        """Execute an asynchronous query with multiple parameter sets.

        Args:
            query: SQL query string.
            params_list: List of parameter dictionaries.

        Raises:
            DatabaseOperationError: If bulk execution fails.
        """
        try:
            async with self.get_async_connection() as connection:
                await connection.execute(text(query), params_list)
                await connection.commit()
        except SQLAlchemyError as error:
            raise DatabaseOperationError(
                f"Async bulk query execution failed: {error}"
            ) from error

    def check_health(self) -> DatabaseHealth:
        """Perform a database health check.

        Returns:
            DatabaseHealth object with health status information.
        """
        import time

        start_time = time.monotonic()
        try:
            with self.get_connection() as connection:
                connection.execute(text("SELECT 1"))
                latency = (time.monotonic() - start_time) * 1000
                return DatabaseHealth(
                    is_healthy=True,
                    latency_ms=latency,
                    connection_count=self._connection_count,
                    active_connections=self._active_connections,
                )
        except (SQLAlchemyError, DatabaseConnectionError) as error:
            latency = (time.monotonic() - start_time) * 1000
            return DatabaseHealth(
                is_healthy=False,
                latency_ms=latency,
                error_message=str(error),
                connection_count=self._connection_count,
                active_connections=self._active_connections,
            )

    async def check_async_health(self) -> DatabaseHealth:
        """Perform an asynchronous database health check.

        Returns:
            DatabaseHealth object with health status information.
        """
        import time

        start_time = time.monotonic()
        try:
            async with self.get_async_connection() as connection:
                await connection.execute(text("SELECT 1"))
                latency = (time.monotonic() - start_time) * 1000
                return DatabaseHealth(
                    is_healthy=True,
                    latency_ms=latency,
                    connection_count=self._connection_count,
                    active_connections=self._active_connections,
                )
        except (SQLAlchemyError, DatabaseConnectionError) as error:
            latency = (time.monotonic() - start_time) * 1000
            return DatabaseHealth(
                is_healthy=False,
                latency_ms=latency,
                error_message=str(error),
                connection_count=self._connection_count,
                active_connections=self._active_connections,
            )

    def run_migrations(self) -> None:
        """Run database migrations using Alembic.

        Raises:
            DatabaseOperationError: If migration execution fails.
        """
        try:
            from alembic.config import Config
            from alembic import command

            alembic_cfg = Config("alembic.ini")
            command.upgrade(alembic_cfg, "head")
            logger.info("Database migrations completed successfully")
        except Exception as error:
            raise DatabaseOperationError(
                f"Database migration failed: {error}"
            ) from error

    def dispose(self) -> None:
        """Dispose of all database engines and connections.

        This method should be called during application shutdown.
        """
        if self._engine:
            self._engine.dispose()
            logger.debug("Synchronous engine disposed")

        if self._async_engine:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self._async_engine.dispose())
                else:
                    loop.run_until_complete(self._async_engine.dispose())
            except RuntimeError:
                asyncio.run(self._async_engine.dispose())
            logger.debug("Asynchronous engine disposed")

        self._is_initialized = False
        logger.info("Database manager disposed")

    def __enter__(self) -> "DatabaseManager":
        """Context manager entry point."""
        if not self._is_initialized:
            self.initialize()
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        """Context manager exit point."""
        self.dispose()

    async def __aenter__(self) -> "DatabaseManager":
        """Async context manager entry point."""
        if not self._is_initialized:
            self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        """Async context manager exit point."""
        self.dispose()


# Global database manager instance
db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance.

    Returns:
        DatabaseManager instance.

    Raises:
        DatabaseConnectionError: If database manager is not initialized.
    """
    global db_manager
    if db_manager is None:
        raise DatabaseConnectionError(
            "Database manager not initialized. Call initialize_database() first."
        )
    return db_manager


def initialize_database(
    config: DatabaseConfig,
    pool_config: Optional[ConnectionPoolConfig] = None,
) -> DatabaseManager:
    """Initialize the global database manager.

    Args:
        config: Database configuration object.
        pool_config: Optional connection pool configuration.

    Returns:
        Initialized DatabaseManager instance.

    Raises:
        DatabaseConnectionError: If initialization fails.
    """
    global db_manager
    if db_manager is not None:
        logger.warning("Database manager already initialized, disposing old instance")
        db_manager.dispose()

    db_manager = DatabaseManager(config, pool_config)
    db_manager.initialize()
    return db_manager


def shutdown_database() -> None:
    """Shutdown the global database manager.

    This function should be called during application shutdown.
    """
    global db_manager
    if db_manager is not None:
        db_manager.dispose()
        db_manager = None
        logger.info("Database manager shutdown complete")