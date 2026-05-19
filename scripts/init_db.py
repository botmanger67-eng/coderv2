"""
Database initialization script for the application.

This script creates all necessary database tables and initializes
any required default data. It should be run once during initial setup
or after schema changes.

Usage:
    python -m scripts.init_db
"""

import os
import sys
import logging
from typing import Optional, Dict, Any
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db_engine
from app.models import User, Role, Permission  # noqa: F401 - Required for table creation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(project_root) / "logs" / "db_init.log"),
    ],
)
logger = logging.getLogger(__name__)


def create_database_if_not_exists(database_url: str) -> None:
    """
    Create the database if it does not exist.

    Args:
        database_url: Full database URL including database name.

    Raises:
        RuntimeError: If database creation fails.
    """
    try:
        # Parse database URL to extract connection without database name
        from urllib.parse import urlparse, urlunparse

        parsed_url = urlparse(database_url)
        db_name = parsed_url.path.lstrip("/")

        # Create connection to default database (postgres)
        default_url = urlunparse((
            parsed_url.scheme,
            f"{parsed_url.netloc}",
            "/postgres",
            parsed_url.params,
            parsed_url.query,
            parsed_url.fragment,
        ))

        engine = create_engine(default_url, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            # Check if database exists
            result = conn.execute(
                text(f"SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": db_name}
            )
            if not result.fetchone():
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                logger.info(f"Database '{db_name}' created successfully.")
            else:
                logger.info(f"Database '{db_name}' already exists.")

        engine.dispose()
    except SQLAlchemyError as e:
        error_msg = f"Failed to create database: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


def initialize_schema(engine: Engine) -> None:
    """
    Create all database tables defined in the SQLAlchemy models.

    Args:
        engine: SQLAlchemy engine instance.

    Raises:
        RuntimeError: If schema initialization fails.
    """
    try:
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
    except SQLAlchemyError as e:
        error_msg = f"Failed to initialize database schema: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


def seed_default_data(db_session: Session) -> None:
    """
    Insert default data required for application startup.

    Args:
        db_session: SQLAlchemy database session.

    Raises:
        RuntimeError: If seeding fails.
    """
    try:
        logger.info("Seeding default data...")

        # Check if default roles exist
        from app.models.role import Role as RoleModel
        from app.models.permission import Permission as PermissionModel

        existing_roles = db_session.query(RoleModel).count()
        if existing_roles == 0:
            # Create default roles
            admin_role = RoleModel(name="admin", description="Administrator with full access")
            user_role = RoleModel(name="user", description="Standard user with limited access")
            viewer_role = RoleModel(name="viewer", description="Read-only access")

            db_session.add_all([admin_role, user_role, viewer_role])
            db_session.flush()

            # Create default permissions
            permissions = [
                PermissionModel(name="read", description="Read resources", resource="*"),
                PermissionModel(name="write", description="Write resources", resource="*"),
                PermissionModel(name="delete", description="Delete resources", resource="*"),
                PermissionModel(name="admin", description="Admin operations", resource="*"),
            ]
            db_session.add_all(permissions)
            db_session.flush()

            # Assign permissions to roles
            admin_role.permissions.extend(permissions)
            user_role.permissions.extend([p for p in permissions if p.name != "admin" and p.name != "delete"])
            viewer_role.permissions.extend([p for p in permissions if p.name == "read"])

            db_session.commit()
            logger.info("Default roles and permissions seeded successfully.")
        else:
            logger.info("Default data already exists. Skipping seed.")

    except SQLAlchemyError as e:
        db_session.rollback()
        error_msg = f"Failed to seed default data: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


def verify_connection(engine: Engine) -> bool:
    """
    Verify database connection is working.

    Args:
        engine: SQLAlchemy engine instance.

    Returns:
        True if connection is successful, False otherwise.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified successfully.")
        return True
    except OperationalError as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False


def run_migrations(engine: Engine) -> None:
    """
    Run any pending database migrations using Alembic.

    Args:
        engine: SQLAlchemy engine instance.

    Raises:
        RuntimeError: If migrations fail.
    """
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config(str(project_root / "alembic.ini"))
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied successfully.")
    except ImportError:
        logger.warning("Alembic not installed. Skipping migrations.")
    except Exception as e:
        error_msg = f"Failed to run migrations: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


def main() -> None:
    """
    Main entry point for database initialization.

    This function orchestrates the entire initialization process:
    1. Creates database if it doesn't exist
    2. Verifies database connection
    3. Creates all tables
    4. Seeds default data
    5. Runs migrations

    Raises:
        SystemExit: If initialization fails.
    """
    logger.info("Starting database initialization...")

    try:
        # Get database URL from settings
        database_url: str = settings.SQLALCHEMY_DATABASE_URI

        # Step 1: Create database if not exists
        logger.info("Step 1/5: Creating database if not exists...")
        create_database_if_not_exists(database_url)

        # Step 2: Create engine and verify connection
        logger.info("Step 2/5: Verifying database connection...")
        engine: Engine = get_db_engine()
        if not verify_connection(engine):
            raise RuntimeError("Cannot establish database connection.")

        # Step 3: Initialize schema
        logger.info("Step 3/5: Initializing database schema...")
        initialize_schema(engine)

        # Step 4: Seed default data
        logger.info("Step 4/5: Seeding default data...")
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db_session: Session = SessionLocal()
        try:
            seed_default_data(db_session)
        finally:
            db_session.close()

        # Step 5: Run migrations
        logger.info("Step 5/5: Running database migrations...")
        run_migrations(engine)

        logger.info("Database initialization completed successfully.")
        sys.exit(0)

    except (RuntimeError, SQLAlchemyError) as e:
        logger.error(f"Database initialization failed: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during initialization: {str(e)}")
        sys.exit(1)
    finally:
        # Clean up engine if it was created
        if 'engine' in locals():
            engine.dispose()


if __name__ == "__main__":
    main()