"""User repository module for database operations."""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.sql import func

from src.models.user import User
from src.schemas.user import UserCreate, UserUpdate
from src.core.exceptions import (
    DatabaseError,
    NotFoundError,
    DuplicateEntryError,
    ValidationError
)
from src.core.logging import get_logger

logger = get_logger(__name__)


class UserRepository:
    """Repository for User database operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def create(self, user_data: UserCreate) -> User:
        """Create a new user.

        Args:
            user_data: User creation schema

        Returns:
            Created User instance

        Raises:
            DuplicateEntryError: If user with same email exists
            DatabaseError: If database operation fails
        """
        try:
            existing_user = await self.get_by_email(user_data.email)
            if existing_user:
                raise DuplicateEntryError(
                    f"User with email {user_data.email} already exists"
                )

            user = User(
                email=user_data.email,
                username=user_data.username,
                hashed_password=user_data.password,
                is_active=user_data.is_active if hasattr(user_data, 'is_active') else True,
                is_verified=user_data.is_verified if hasattr(user_data, 'is_verified') else False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)

            logger.info(f"Created user: {user.id}")
            return user

        except IntegrityError as e:
            await self.session.rollback()
            logger.error(f"Integrity error creating user: {e}")
            raise DuplicateEntryError("User with this email or username already exists")
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Database error creating user: {e}")
            raise DatabaseError(f"Failed to create user: {str(e)}")

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID.

        Args:
            user_id: User UUID

        Returns:
            User instance if found, None otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            result = await self.session.execute(
                select(User).where(User.id == user_id)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching user by ID {user_id}: {e}")
            raise DatabaseError(f"Failed to fetch user: {str(e)}")

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email.

        Args:
            email: User email address

        Returns:
            User instance if found, None otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            result = await self.session.execute(
                select(User).where(User.email == email)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching user by email {email}: {e}")
            raise DatabaseError(f"Failed to fetch user by email: {str(e)}")

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username.

        Args:
            username: Username

        Returns:
            User instance if found, None otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            result = await self.session.execute(
                select(User).where(User.username == username)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching user by username {username}: {e}")
            raise DatabaseError(f"Failed to fetch user by username: {str(e)}")

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_desc: bool = False
    ) -> List[User]:
        """Get all users with pagination and filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Optional filters dictionary
            sort_by: Field to sort by
            sort_desc: Sort in descending order if True

        Returns:
            List of User instances

        Raises:
            ValidationError: If invalid sort field provided
            DatabaseError: If database operation fails
        """
        try:
            query = select(User)

            # Apply filters
            if filters:
                conditions = []
                for key, value in filters.items():
                    if hasattr(User, key):
                        if isinstance(value, list):
                            conditions.append(getattr(User, key).in_(value))
                        elif isinstance(value, str) and '%' in value:
                            conditions.append(getattr(User, key).like(value))
                        else:
                            conditions.append(getattr(User, key) == value)
                if conditions:
                    query = query.where(and_(*conditions))

            # Apply sorting
            if sort_by:
                if not hasattr(User, sort_by):
                    raise ValidationError(f"Invalid sort field: {sort_by}")
                sort_column = getattr(User, sort_by)
                if sort_desc:
                    query = query.order_by(sort_column.desc())
                else:
                    query = query.order_by(sort_column.asc())
            else:
                query = query.order_by(User.created_at.desc())

            # Apply pagination
            query = query.offset(skip).limit(limit)

            result = await self.session.execute(query)
            return list(result.scalars().all())

        except ValidationError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching users: {e}")
            raise DatabaseError(f"Failed to fetch users: {str(e)}")

    async def update(self, user_id: UUID, update_data: UserUpdate) -> User:
        """Update user information.

        Args:
            user_id: User UUID
            update_data: User update schema

        Returns:
            Updated User instance

        Raises:
            NotFoundError: If user not found
            DuplicateEntryError: If email/username already taken
            DatabaseError: If database operation fails
        """
        try:
            user = await self.get_by_id(user_id)
            if not user:
                raise NotFoundError(f"User with ID {user_id} not found")

            # Check for duplicate email
            if update_data.email and update_data.email != user.email:
                existing = await self.get_by_email(update_data.email)
                if existing:
                    raise DuplicateEntryError(
                        f"Email {update_data.email} already in use"
                    )

            # Check for duplicate username
            if update_data.username and update_data.username != user.username:
                existing = await self.get_by_username(update_data.username)
                if existing:
                    raise DuplicateEntryError(
                        f"Username {update_data.username} already taken"
                    )

            update_dict = update_data.dict(exclude_unset=True)
            update_dict['updated_at'] = datetime.utcnow()

            stmt = (
                update(User)
                .where(User.id == user_id)
                .values(**update_dict)
                .returning(User)
            )

            result = await self.session.execute(stmt)
            await self.session.commit()

            updated_user = result.scalar_one()
            logger.info(f"Updated user: {user_id}")
            return updated_user

        except (NotFoundError, DuplicateEntryError):
            await self.session.rollback()
            raise
        except IntegrityError as e:
            await self.session.rollback()
            logger.error(f"Integrity error updating user {user_id}: {e}")
            raise DuplicateEntryError("Email or username already exists")
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Database error updating user {user_id}: {e}")
            raise DatabaseError(f"Failed to update user: {str(e)}")

    async def delete(self, user_id: UUID, soft_delete: bool = True) -> None:
        """Delete a user.

        Args:
            user_id: User UUID
            soft_delete: If True, mark as inactive instead of deleting

        Raises:
            NotFoundError: If user not found
            DatabaseError: If database operation fails
        """
        try:
            user = await self.get_by_id(user_id)
            if not user:
                raise NotFoundError(f"User with ID {user_id} not found")

            if soft_delete:
                stmt = (
                    update(User)
                    .where(User.id == user_id)
                    .values(
                        is_active=False,
                        deleted_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                )
            else:
                stmt = delete(User).where(User.id == user_id)

            await self.session.execute(stmt)
            await self.session.commit()

            logger.info(f"{'Soft' if soft_delete else 'Hard'} deleted user: {user_id}")

        except NotFoundError:
            await self.session.rollback()
            raise
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Database error deleting user {user_id}: {e}")
            raise DatabaseError(f"Failed to delete user: {str(e)}")

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count users with optional filters.

        Args:
            filters: Optional filters dictionary

        Returns:
            Count of matching users

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = select(func.count(User.id))

            if filters:
                conditions = []
                for key, value in filters.items():
                    if hasattr(User, key):
                        conditions.append(getattr(User, key) == value)
                if conditions:
                    query = query.where(and_(*conditions))

            result = await self.session.execute(query)
            return result.scalar()

        except SQLAlchemyError as e:
            logger.error(f"Database error counting users: {e}")
            raise DatabaseError(f"Failed to count users: {str(e)}")

    async def exists(self, user_id: UUID) -> bool:
        """Check if user exists.

        Args:
            user_id: User UUID

        Returns:
            True if user exists, False otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            result = await self.session.execute(
                select(User.id).where(User.id == user_id)
            )
            return result.scalar() is not None
        except SQLAlchemyError as e:
            logger.error(f"Database error checking user existence {user_id}: {e}")
            raise DatabaseError(f"Failed to check user existence: {str(e)}")

    async def email_exists(self, email: str) -> bool:
        """Check if email is already registered.

        Args:
            email: Email address to check

        Returns:
            True if email exists, False otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            result = await self.session.execute(
                select(User.id).where(User.email == email)
            )
            return result.scalar() is not None
        except SQLAlchemyError as e:
            logger.error(f"Database error checking email existence {email}: {e}")
            raise DatabaseError(f"Failed to check email existence: {str(e)}")

    async def username_exists(self, username: str) -> bool:
        """Check if username is already taken.

        Args:
            username: Username to check

        Returns:
            True if username exists, False otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            result = await self.session.execute(
                select(User.id).where(User.username == username)
            )
            return result.scalar() is not None
        except SQLAlchemyError as e:
            logger.error(f"Database error checking username existence {username}: {e}")
            raise DatabaseError(f"Failed to check username existence: {str(e)}")

    async def bulk_create(self, users_data: List[UserCreate]) -> List[User]:
        """Create multiple users in bulk.

        Args:
            users_data: List of user creation schemas

        Returns:
            List of created User instances

        Raises:
            DuplicateEntryError: If any user data conflicts
            DatabaseError: If database operation fails
        """
        try:
            users = []
            for user_data in users_data:
                user = User(
                    email=user_data.email,
                    username=user_data.username,
                    hashed_password=user_data.password,
                    is_active=True,
                    is_verified=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                users.append(user)

            self.session.add_all(users)
            await self.session.commit()

            for user in users:
                await self.session.refresh(user)

            logger.info(f"Bulk created {len(users)} users")
            return users

        except IntegrityError as e:
            await self.session.rollback()
            logger.error(f"Integrity error in bulk create: {e}")
            raise DuplicateEntryError("Duplicate email or username in bulk create")
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Database error in bulk create: {e}")
            raise DatabaseError(f"Failed to bulk create users: {str(e)}")

    async def search(
        self,
        query: str,
        fields: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """Search users by query string.

        Args:
            query: Search query string
            fields: Fields to search in (default: email, username)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of matching User instances

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            if not fields:
                fields = ['email', 'username']

            conditions = []
            for field in fields:
                if hasattr(User, field):
                    conditions.append(
                        getattr(User, field).ilike(f'%{query}%')
                    )

            if not conditions:
                return []

            stmt = (
                select(User)
                .where(or_(*conditions))
                .offset(skip)
                .limit(limit)
                .order_by(User.created_at.desc())
            )

            result = await self.session.execute(stmt)
            return list(result.scalars().all())

        except SQLAlchemyError as e:
            logger.error(f"Database error searching users: {e}")
            raise DatabaseError(f"Failed to search users: {str(e)}")