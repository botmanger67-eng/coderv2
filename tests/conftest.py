"""
Test configuration and fixtures for the application test suite.

This module provides shared fixtures and configuration for all test modules.
It includes fixtures for database setup, HTTP client, authentication tokens,
and common test data generators.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User, Organization, Project, Task
from app.schemas.auth import TokenResponse
from app.services.auth import create_access_token, hash_password
from app.config import settings


# ---------------------------------------------------------------------------
# Database Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    """
    Create a SQLite in-memory engine for testing.

    Yields:
        Engine: SQLAlchemy engine configured for testing.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # Enable foreign key enforcement for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def test_session_factory(
    test_engine: Engine,
) -> Generator[sessionmaker, None, None]:
    """
    Create a session factory bound to the test engine.

    Args:
        test_engine: SQLAlchemy engine for testing.

    Yields:
        sessionmaker: Factory for creating test database sessions.
    """
    Base.metadata.create_all(bind=test_engine)
    factory = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    yield factory
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session(
    test_session_factory: sessionmaker,
) -> Generator[Session, None, None]:
    """
    Provide a transactional database session for each test.

    Args:
        test_session_factory: Factory for creating test sessions.

    Yields:
        Session: Database session with transaction rollback on teardown.
    """
    session = test_session_factory()
    try:
        yield session
        session.rollback()
    finally:
        session.close()


@pytest.fixture
def override_get_db(db_session: Session) -> Generator[None, None, None]:
    """
    Override the FastAPI dependency injection to use the test database session.

    Args:
        db_session: Test database session.

    Yields:
        None
    """
    def _get_db_override() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override
    yield
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# HTTP Client Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client(
    override_get_db: None,
) -> Generator[AsyncClient, None, None]:
    """
    Provide an async HTTP client for testing API endpoints.

    Args:
        override_get_db: Fixture to override database dependency.

    Yields:
        AsyncClient: HTTPX async client configured for the test app.
    """
    transport = ASGITransport(app=app)
    with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest_asyncio.fixture
async def async_client(
    override_get_db: None,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Provide an async HTTP client for testing async endpoints.

    Args:
        override_get_db: Fixture to override database dependency.

    Yields:
        AsyncClient: HTTPX async client configured for the test app.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Authentication Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_password() -> str:
    """
    Provide a standard test password.

    Returns:
        str: Plain text password for test users.
    """
    return "TestPassword123!"


@pytest.fixture
def hashed_test_password(test_password: str) -> str:
    """
    Provide a hashed version of the test password.

    Args:
        test_password: Plain text test password.

    Returns:
        str: Bcrypt hashed password.
    """
    return hash_password(test_password)


@pytest.fixture
def test_user_data() -> Dict[str, Any]:
    """
    Provide standard test user data.

    Returns:
        Dict[str, Any]: Dictionary with user creation fields.
    """
    return {
        "email": f"test_{uuid4().hex[:8]}@example.com",
        "username": f"testuser_{uuid4().hex[:8]}",
        "password": "TestPassword123!",
        "full_name": "Test User",
        "is_active": True,
    }


@pytest.fixture
def test_user(
    db_session: Session,
    test_user_data: Dict[str, Any],
    hashed_test_password: str,
) -> User:
    """
    Create and persist a test user in the database.

    Args:
        db_session: Test database session.
        test_user_data: User creation data.
        hashed_test_password: Hashed password for the user.

    Returns:
        User: Created user instance.
    """
    user = User(
        email=test_user_data["email"],
        username=test_user_data["username"],
        hashed_password=hashed_test_password,
        full_name=test_user_data["full_name"],
        is_active=test_user_data["is_active"],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user_token(test_user: User) -> str:
    """
    Generate an access token for the test user.

    Args:
        test_user: Test user instance.

    Returns:
        str: JWT access token.
    """
    return create_access_token(
        data={"sub": test_user.email, "user_id": str(test_user.id)},
        expires_delta=timedelta(hours=1),
    )


@pytest.fixture
def authorized_client(
    client: AsyncClient,
    test_user_token: str,
) -> AsyncClient:
    """
    Provide an HTTP client with authorization headers.

    Args:
        client: Base async HTTP client.
        test_user_token: JWT access token.

    Returns:
        AsyncClient: Client with Bearer token in headers.
    """
    client.headers.update({"Authorization": f"Bearer {test_user_token}"})
    return client


# ---------------------------------------------------------------------------
# Organization Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_organization_data() -> Dict[str, Any]:
    """
    Provide standard test organization data.

    Returns:
        Dict[str, Any]: Dictionary with organization creation fields.
    """
    return {
        "name": f"Test Organization {uuid4().hex[:8]}",
        "description": "Organization created for testing purposes.",
        "is_active": True,
    }


@pytest.fixture
def test_organization(
    db_session: Session,
    test_user: User,
    test_organization_data: Dict[str, Any],
) -> Organization:
    """
    Create and persist a test organization owned by the test user.

    Args:
        db_session: Test database session.
        test_user: Owner of the organization.
        test_organization_data: Organization creation data.

    Returns:
        Organization: Created organization instance.
    """
    organization = Organization(
        **test_organization_data,
        owner_id=test_user.id,
    )
    db_session.add(organization)
    db_session.commit()
    db_session.refresh(organization)
    return organization


# ---------------------------------------------------------------------------
# Project Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_project_data() -> Dict[str, Any]:
    """
    Provide standard test project data.

    Returns:
        Dict[str, Any]: Dictionary with project creation fields.
    """
    return {
        "name": f"Test Project {uuid4().hex[:8]}",
        "description": "Project created for testing purposes.",
        "status": "active",
        "priority": "medium",
    }


@pytest.fixture
def test_project(
    db_session: Session,
    test_organization: Organization,
    test_user: User,
    test_project_data: Dict[str, Any],
) -> Project:
    """
    Create and persist a test project under the test organization.

    Args:
        db_session: Test database session.
        test_organization: Parent organization.
        test_user: Creator of the project.
        test_project_data: Project creation data.

    Returns:
        Project: Created project instance.
    """
    project = Project(
        **test_project_data,
        organization_id=test_organization.id,
        created_by_id=test_user.id,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


# ---------------------------------------------------------------------------
# Task Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_task_data() -> Dict[str, Any]:
    """
    Provide standard test task data.

    Returns:
        Dict[str, Any]: Dictionary with task creation fields.
    """
    return {
        "title": f"Test Task {uuid4().hex[:8]}",
        "description": "Task created for testing purposes.",
        "status": "todo",
        "priority": "medium",
        "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
    }


@pytest.fixture
def test_task(
    db_session: Session,
    test_project: Project,
    test_user: User,
    test_task_data: Dict[str, Any],
) -> Task:
    """
    Create and persist a test task under the test project.

    Args:
        db_session: Test database session.
        test_project: Parent project.
        test_user: Assignee of the task.
        test_task_data: Task creation data.

    Returns:
        Task: Created task instance.
    """
    task = Task(
        **test_task_data,
        project_id=test_project.id,
        assignee_id=test_user.id,
        created_by_id=test_user.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


# ---------------------------------------------------------------------------
# Utility Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_payload() -> Dict[str, Any]:
    """
    Provide a generic sample JSON payload for testing.

    Returns:
        Dict[str, Any]: Sample payload dictionary.
    """
    return {
        "key1": "value1",
        "key2": 42,
        "key3": [1, 2, 3],
        "key4": {"nested": "data"},
    }


@pytest.fixture
def invalid_uuid() -> str:
    """
    Provide an invalid UUID string for testing error handling.

    Returns:
        str: Invalid UUID string.
    """
    return "invalid-uuid-format"


@pytest.fixture
def non_existent_uuid() -> str:
    """
    Provide a valid but non-existent UUID for testing 404 scenarios.

    Returns:
        str: Valid UUID that does not exist in the database.
    """
    return str(uuid4())


# ---------------------------------------------------------------------------
# Cleanup Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def cleanup_test_data(db_session: Session) -> Generator[None, None, None]:
    """
    Automatically clean up test data after each test.

    Args:
        db_session: Test database session.

    Yields:
        None
    """
    yield
    # Rollback any uncommitted changes
    db_session.rollback()
    # Clean up all tables
    for table in reversed(Base.metadata.sorted_tables):
        db_session.execute(table.delete())
    db_session.commit()


# ---------------------------------------------------------------------------
# Configuration Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_settings() -> Dict[str, Any]:
    """
    Provide test-specific configuration overrides.

    Returns:
        Dict[str, Any]: Dictionary of test settings.
    """
    return {
        "DATABASE_URL": "sqlite:///:memory:",
        "SECRET_KEY": "test-secret-key-for-testing-only",
        "ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": 30,
        "REFRESH_TOKEN_EXPIRE_DAYS": 7,
        "TESTING": True,
    }


@pytest.fixture(autouse=True)
def override_settings(test_settings: Dict[str, Any]) -> Generator[None, None, None]:
    """
    Override application settings with test values.

    Args:
        test_settings: Test configuration overrides.

    Yields:
        None
    """
    original_values = {}
    for key, value in test_settings.items():
        if hasattr(settings, key):
            original_values[key] = getattr(settings, key)
            setattr(settings, key, value)

    yield

    for key, value in original_values.items():
        setattr(settings, key, value)


# ---------------------------------------------------------------------------
# Async Support Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Create an event loop for the test session.

    Yields:
        asyncio.AbstractEventLoop: Event loop instance.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_db_session(
    test_session_factory: sessionmaker,
) -> AsyncGenerator[Session, None]:
    """
    Provide an async-compatible database session.

    Args:
        test_session_factory: Factory for creating test sessions.

    Yields:
        Session: Database session for async tests.
    """
    session = test_session_factory()
    try:
        yield session
        session.rollback()
    finally:
        session.close()