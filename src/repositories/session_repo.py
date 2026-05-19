"""Session repository module for database operations."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.models.session import Session
from src.core.exceptions import (
    RepositoryError,
    NotFoundError,
    DuplicateEntryError,
    DatabaseConnectionError
)
from src.core.logging import get_logger

logger = get_logger(__name__)


class SessionRepository:
    """Repository for managing session data in the database."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Initialize SessionRepository with database session.

        Args:
            db_session: Async SQLAlchemy database session.

        Raises:
            DatabaseConnectionError: If database session is invalid.
        """
        if db_session is None:
            raise DatabaseConnectionError("Database session cannot be None")
        self._db_session = db_session

    async def create(self, session_data: Dict[str, Any]) -> Session:
        """Create a new session record.

        Args:
            session_data: Dictionary containing session attributes.

        Returns:
            Created Session instance.

        Raises:
            DuplicateEntryError: If session with same ID already exists.
            RepositoryError: If database operation fails.
        """
        try:
            session = Session(**session_data)
            if not session.id:
                session.id = uuid4()
            if not session.created_at:
                session.created_at = datetime.utcnow()
            if not session.updated_at:
                session.updated_at = datetime.utcnow()

            self._db_session.add(session)
            await self._db_session.flush()
            await self._db_session.refresh(session)

            logger.info(f"Created session with ID: {session.id}")
            return session

        except IntegrityError as exc:
            await self._db_session.rollback()
            logger.error(f"Duplicate session entry: {exc}")
            raise DuplicateEntryError(
                f"Session with ID {session_data.get('id')} already exists"
            ) from exc
        except SQLAlchemyError as exc:
            await self._db_session.rollback()
            logger.error(f"Failed to create session: {exc}")
            raise RepositoryError(f"Failed to create session: {exc}") from exc

    async def get_by_id(self, session_id: UUID) -> Optional[Session]:
        """Retrieve a session by its ID.

        Args:
            session_id: UUID of the session to retrieve.

        Returns:
            Session instance if found, None otherwise.

        Raises:
            RepositoryError: If database operation fails.
        """
        try:
            query = select(Session).where(Session.id == session_id)
            result = await self._db_session.execute(query)
            session = result.scalar_one_or_none()

            if session:
                logger.debug(f"Retrieved session with ID: {session_id}")
            else:
                logger.debug(f"Session not found with ID: {session_id}")

            return session

        except SQLAlchemyError as exc:
            logger.error(f"Failed to retrieve session {session_id}: {exc}")
            raise RepositoryError(
                f"Failed to retrieve session {session_id}: {exc}"
            ) from exc

    async def get_by_user_id(self, user_id: UUID) -> List[Session]:
        """Retrieve all sessions for a specific user.

        Args:
            user_id: UUID of the user.

        Returns:
            List of Session instances.

        Raises:
            RepositoryError: If database operation fails.
        """
        try:
            query = (
                select(Session)
                .where(Session.user_id == user_id)
                .order_by(Session.created_at.desc())
            )
            result = await self._db_session.execute(query)
            sessions = list(result.scalars().all())

            logger.debug(f"Retrieved {len(sessions)} sessions for user {user_id}")
            return sessions

        except SQLAlchemyError as exc:
            logger.error(f"Failed to retrieve sessions for user {user_id}: {exc}")
            raise RepositoryError(
                f"Failed to retrieve sessions for user {user_id}: {exc}"
            ) from exc

    async def get_active_sessions(self, user_id: UUID) -> List[Session]:
        """Retrieve all active sessions for a specific user.

        Args:
            user_id: UUID of the user.

        Returns:
            List of active Session instances.

        Raises:
            RepositoryError: If database operation fails.
        """
        try:
            query = (
                select(Session)
                .where(
                    and_(
                        Session.user_id == user_id,
                        Session.is_active == True,
                        Session.expires_at > datetime.utcnow()
                    )
                )
                .order_by(Session.created_at.desc())
            )
            result = await self._db_session.execute(query)
            sessions = list(result.scalars().all())

            logger.debug(
                f"Retrieved {len(sessions)} active sessions for user {user_id}"
            )
            return sessions

        except SQLAlchemyError as exc:
            logger.error(
                f"Failed to retrieve active sessions for user {user_id}: {exc}"
            )
            raise RepositoryError(
                f"Failed to retrieve active sessions for user {user_id}: {exc}"
            ) from exc

    async def update(self, session_id: UUID, update_data: Dict[str, Any]) -> Session:
        """Update a session record.

        Args:
            session_id: UUID of the session to update.
            update_data: Dictionary containing attributes to update.

        Returns:
            Updated Session instance.

        Raises:
            NotFoundError: If session not found.
            RepositoryError: If database operation fails.
        """
        try:
            session = await self.get_by_id(session_id)
            if not session:
                raise NotFoundError(f"Session with ID {session_id} not found")

            update_data["updated_at"] = datetime.utcnow()

            query = (
                update(Session)
                .where(Session.id == session_id)
                .values(**update_data)
                .returning(Session)
            )
            result = await self._db_session.execute(query)
            await self._db_session.flush()

            updated_session = result.scalar_one()
            await self._db_session.refresh(updated_session)

            logger.info(f"Updated session with ID: {session_id}")
            return updated_session

        except NotFoundError:
            raise
        except SQLAlchemyError as exc:
            await self._db_session.rollback()
            logger.error(f"Failed to update session {session_id}: {exc}")
            raise RepositoryError(
                f"Failed to update session {session_id}: {exc}"
            ) from exc

    async def delete(self, session_id: UUID) -> None:
        """Delete a session record.

        Args:
            session_id: UUID of the session to delete.

        Raises:
            NotFoundError: If session not found.
            RepositoryError: If database operation fails.
        """
        try:
            session = await self.get_by_id(session_id)
            if not session:
                raise NotFoundError(f"Session with ID {session_id} not found")

            query = delete(Session).where(Session.id == session_id)
            await self._db_session.execute(query)
            await self._db_session.flush()

            logger.info(f"Deleted session with ID: {session_id}")

        except NotFoundError:
            raise
        except SQLAlchemyError as exc:
            await self._db_session.rollback()
            logger.error(f"Failed to delete session {session_id}: {exc}")
            raise RepositoryError(
                f"Failed to delete session {session_id}: {exc}"
            ) from exc

    async def deactivate_user_sessions(self, user_id: UUID) -> int:
        """Deactivate all active sessions for a user.

        Args:
            user_id: UUID of the user.

        Returns:
            Number of deactivated sessions.

        Raises:
            RepositoryError: If database operation fails.
        """
        try:
            query = (
                update(Session)
                .where(
                    and_(
                        Session.user_id == user_id,
                        Session.is_active == True
                    )
                )
                .values(
                    is_active=False,
                    updated_at=datetime.utcnow()
                )
            )
            result = await self._db_session.execute(query)
            await self._db_session.flush()

            deactivated_count = result.rowcount
            logger.info(
                f"Deactivated {deactivated_count} sessions for user {user_id}"
            )
            return deactivated_count

        except SQLAlchemyError as exc:
            await self._db_session.rollback()
            logger.error(
                f"Failed to deactivate sessions for user {user_id}: {exc}"
            )
            raise RepositoryError(
                f"Failed to deactivate sessions for user {user_id}: {exc}"
            ) from exc

    async def cleanup_expired_sessions(self) -> int:
        """Delete all expired sessions from the database.

        Returns:
            Number of deleted sessions.

        Raises:
            RepositoryError: If database operation fails.
        """
        try:
            query = delete(Session).where(
                Session.expires_at <= datetime.utcnow()
            )
            result = await self._db_session.execute(query)
            await self._db_session.flush()

            deleted_count = result.rowcount
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired sessions")

            return deleted_count

        except SQLAlchemyError as exc:
            await self._db_session.rollback()
            logger.error(f"Failed to cleanup expired sessions: {exc}")
            raise RepositoryError(
                f"Failed to cleanup expired sessions: {exc}"
            ) from exc

    async def count_active_sessions(self, user_id: UUID) -> int:
        """Count active sessions for a user.

        Args:
            user_id: UUID of the user.

        Returns:
            Number of active sessions.

        Raises:
            RepositoryError: If database operation fails.
        """
        try:
            query = (
                select(Session)
                .where(
                    and_(
                        Session.user_id == user_id,
                        Session.is_active == True,
                        Session.expires_at > datetime.utcnow()
                    )
                )
            )
            result = await self._db_session.execute(query)
            count = len(result.scalars().all())

            logger.debug(f"User {user_id} has {count} active sessions")
            return count

        except SQLAlchemyError as exc:
            logger.error(
                f"Failed to count active sessions for user {user_id}: {exc}"
            )
            raise RepositoryError(
                f"Failed to count active sessions for user {user_id}: {exc}"
            ) from exc

    async def __aenter__(self) -> "SessionRepository":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object]
    ) -> None:
        """Async context manager exit with proper cleanup."""
        if exc_type is not None:
            await self._db_session.rollback()
        await self._db_session.close()