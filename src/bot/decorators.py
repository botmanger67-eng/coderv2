"""Decorators for authorization and rate limiting in the bot system.

This module provides decorators that can be applied to bot command handlers
to enforce access control and rate limiting policies.
"""

import asyncio
import functools
import inspect
import logging
import time
from collections import defaultdict
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
    cast,
)

logger = logging.getLogger(__name__)

# Type variables for decorator signatures
F = TypeVar("F", bound=Callable[..., Any])
HandlerFunc = TypeVar("HandlerFunc", bound=Callable[..., Any])


class AccessLevel(Enum):
    """Enumeration of access levels for authorization."""

    PUBLIC = "public"
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class RateLimitExceeded(Exception):
    """Exception raised when a rate limit is exceeded."""

    def __init__(
        self,
        user_id: Union[int, str],
        limit: int,
        window: int,
        retry_after: float,
    ) -> None:
        """Initialize the rate limit exceeded exception.

        Args:
            user_id: The identifier of the user who exceeded the limit.
            limit: The maximum number of requests allowed.
            window: The time window in seconds.
            retry_after: The number of seconds to wait before retrying.
        """
        self.user_id = user_id
        self.limit = limit
        self.window = window
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded for user {user_id}. "
            f"Limit: {limit} requests per {window} seconds. "
            f"Retry after {retry_after:.2f} seconds."
        )


class AuthorizationError(Exception):
    """Exception raised when a user is not authorized to perform an action."""

    def __init__(
        self,
        user_id: Union[int, str],
        required_level: AccessLevel,
        current_level: Optional[AccessLevel] = None,
    ) -> None:
        """Initialize the authorization error exception.

        Args:
            user_id: The identifier of the user who is not authorized.
            required_level: The access level required for the action.
            current_level: The current access level of the user, if available.
        """
        self.user_id = user_id
        self.required_level = required_level
        self.current_level = current_level
        message = (
            f"User {user_id} is not authorized. "
            f"Required level: {required_level.value}."
        )
        if current_level is not None:
            message += f" Current level: {current_level.value}."
        super().__init__(message)


class RateLimiter:
    """In-memory rate limiter using sliding window algorithm.

    This class implements a sliding window rate limiting algorithm to track
    and enforce request limits per user or resource.
    """

    def __init__(self) -> None:
        """Initialize the rate limiter with empty tracking data."""
        self._windows: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> Tuple[bool, float]:
        """Check if a request is within the rate limit.

        Args:
            key: The identifier to check (e.g., user ID, IP address).
            max_requests: Maximum number of requests allowed in the window.
            window_seconds: The time window in seconds.

        Returns:
            A tuple containing:
                - True if the request is allowed, False otherwise.
                - The number of seconds to wait before retrying if rate limited.
        """
        async with self._lock:
            now = time.time()
            window_start = now - window_seconds

            # Remove expired timestamps
            self._windows[key] = [
                timestamp
                for timestamp in self._windows[key]
                if timestamp > window_start
            ]

            # Check if limit is exceeded
            if len(self._windows[key]) >= max_requests:
                oldest_timestamp = self._windows[key][0]
                retry_after = oldest_timestamp + window_seconds - now
                return False, max(0.0, retry_after)

            # Record the request
            self._windows[key].append(now)
            return True, 0.0

    async def get_remaining_requests(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> int:
        """Get the number of remaining requests for a key.

        Args:
            key: The identifier to check.
            max_requests: Maximum number of requests allowed in the window.
            window_seconds: The time window in seconds.

        Returns:
            The number of remaining requests.
        """
        async with self._lock:
            now = time.time()
            window_start = now - window_seconds

            # Remove expired timestamps
            self._windows[key] = [
                timestamp
                for timestamp in self._windows[key]
                if timestamp > window_start
            ]

            return max(0, max_requests - len(self._windows[key]))

    async def reset_rate_limit(self, key: str) -> None:
        """Reset the rate limit for a specific key.

        Args:
            key: The identifier to reset.
        """
        async with self._lock:
            self._windows[key] = []


# Global rate limiter instance
_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance.

    Returns:
        The global RateLimiter instance.
    """
    return _rate_limiter


def require_access_level(
    required_level: AccessLevel,
    user_id_extractor: Optional[Callable[..., Union[int, str]]] = None,
    level_extractor: Optional[Callable[..., AccessLevel]] = None,
) -> Callable[[F], F]:
    """Decorator to require a minimum access level for a handler.

    This decorator checks if the user has the required access level before
    allowing the handler to execute.

    Args:
        required_level: The minimum access level required.
        user_id_extractor: Optional function to extract the user ID from
            the handler arguments. If not provided, the first argument
            is assumed to be the user ID.
        level_extractor: Optional function to extract the user's access
            level from the handler arguments. If not provided, the
            second argument is assumed to be the access level.

    Returns:
        A decorator function that wraps the handler with authorization check.

    Raises:
        AuthorizationError: If the user does not have the required access level.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract user ID
            if user_id_extractor is not None:
                user_id = user_id_extractor(*args, **kwargs)
            else:
                user_id = args[0] if args else kwargs.get("user_id", "unknown")

            # Extract access level
            if level_extractor is not None:
                user_level = level_extractor(*args, **kwargs)
            else:
                user_level = args[1] if len(args) > 1 else kwargs.get("access_level", AccessLevel.PUBLIC)

            # Validate access level
            if not isinstance(user_level, AccessLevel):
                try:
                    user_level = AccessLevel(user_level)
                except (ValueError, TypeError):
                    raise AuthorizationError(
                        user_id=user_id,
                        required_level=required_level,
                        current_level=None,
                    )

            # Check if user has required level
            level_order = list(AccessLevel)
            required_index = level_order.index(required_level)
            user_index = level_order.index(user_level)

            if user_index < required_index:
                raise AuthorizationError(
                    user_id=user_id,
                    required_level=required_level,
                    current_level=user_level,
                )

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract user ID
            if user_id_extractor is not None:
                user_id = user_id_extractor(*args, **kwargs)
            else:
                user_id = args[0] if args else kwargs.get("user_id", "unknown")

            # Extract access level
            if level_extractor is not None:
                user_level = level_extractor(*args, **kwargs)
            else:
                user_level = args[1] if len(args) > 1 else kwargs.get("access_level", AccessLevel.PUBLIC)

            # Validate access level
            if not isinstance(user_level, AccessLevel):
                try:
                    user_level = AccessLevel(user_level)
                except (ValueError, TypeError):
                    raise AuthorizationError(
                        user_id=user_id,
                        required_level=required_level,
                        current_level=None,
                    )

            # Check if user has required level
            level_order = list(AccessLevel)
            required_index = level_order.index(required_level)
            user_index = level_order.index(user_level)

            if user_index < required_index:
                raise AuthorizationError(
                    user_id=user_id,
                    required_level=required_level,
                    current_level=user_level,
                )

            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


def rate_limit(
    max_requests: int,
    window_seconds: int,
    key_extractor: Optional[Callable[..., str]] = None,
    raise_on_limit: bool = True,
) -> Callable[[F], F]:
    """Decorator to apply rate limiting to a handler.

    This decorator limits the number of times a handler can be called
    within a specified time window.

    Args:
        max_requests: Maximum number of requests allowed in the window.
        window_seconds: The time window in seconds.
        key_extractor: Optional function to extract the rate limit key
            from the handler arguments. If not provided, the first
            argument is used as the key.
        raise_on_limit: If True, raises RateLimitExceeded when limit is
            exceeded. If False, returns None or a default response.

    Returns:
        A decorator function that wraps the handler with rate limiting.

    Raises:
        RateLimitExceeded: If the rate limit is exceeded and raise_on_limit
            is True.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract rate limit key
            if key_extractor is not None:
                key = key_extractor(*args, **kwargs)
            else:
                key = str(args[0]) if args else "default"

            # Check rate limit
            limiter = get_rate_limiter()
            allowed, retry_after = await limiter.check_rate_limit(
                key=key,
                max_requests=max_requests,
                window_seconds=window_seconds,
            )

            if not allowed:
                if raise_on_limit:
                    raise RateLimitExceeded(
                        user_id=key,
                        limit=max_requests,
                        window=window_seconds,
                        retry_after=retry_after,
                    )
                logger.warning(
                    "Rate limit exceeded for key '%s'. "
                    "Retry after %.2f seconds.",
                    key,
                    retry_after,
                )
                return None

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract rate limit key
            if key_extractor is not None:
                key = key_extractor(*args, **kwargs)
            else:
                key = str(args[0]) if args else "default"

            # Check rate limit (synchronous version uses blocking call)
            limiter = get_rate_limiter()
            loop = asyncio.new_event_loop()
            try:
                allowed, retry_after = loop.run_until_complete(
                    limiter.check_rate_limit(
                        key=key,
                        max_requests=max_requests,
                        window_seconds=window_seconds,
                    )
                )
            finally:
                loop.close()

            if not allowed:
                if raise_on_limit:
                    raise RateLimitExceeded(
                        user_id=key,
                        limit=max_requests,
                        window=window_seconds,
                        retry_after=retry_after,
                    )
                logger.warning(
                    "Rate limit exceeded for key '%s'. "
                    "Retry after %.2f seconds.",
                    key,
                    retry_after,
                )
                return None

            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


def require_permissions(
    permissions: Set[str],
    permission_extractor: Optional[Callable[..., Set[str]]] = None,
) -> Callable[[F], F]:
    """Decorator to require specific permissions for a handler.

    This decorator checks if the user has all the required permissions
    before allowing the handler to execute.

    Args:
        permissions: A set of required permission strings.
        permission_extractor: Optional function to extract the user's
            permissions from the handler arguments. If not provided,
            the third argument is assumed to be a set of permissions.

    Returns:
        A decorator function that wraps the handler with permission check.

    Raises:
        PermissionError: If the user does not have all required permissions.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract permissions
            if permission_extractor is not None:
                user_permissions = permission_extractor(*args, **kwargs)
            else:
                user_permissions = args[2] if len(args) > 2 else kwargs.get("permissions", set())

            # Validate permissions
            if not isinstance(user_permissions, (set, list, tuple)):
                raise PermissionError(
                    f"Invalid permissions format: {type(user_permissions)}"
                )

            user_permissions_set = set(user_permissions)
            missing_permissions = permissions - user_permissions_set

            if missing_permissions:
                raise PermissionError(
                    f"Missing required permissions: {', '.join(sorted(missing_permissions))}"
                )

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract permissions
            if permission_extractor is not None:
                user_permissions = permission_extractor(*args, **kwargs)
            else:
                user_permissions = args[2] if len(args) > 2 else kwargs.get("permissions", set())

            # Validate permissions
            if not isinstance(user_permissions, (set, list, tuple)):
                raise PermissionError(
                    f"Invalid permissions format: {type(user_permissions)}"
                )

            user_permissions_set = set(user_permissions)
            missing_permissions = permissions - user_permissions_set

            if missing_permissions:
                raise PermissionError(
                    f"Missing required permissions: {', '.join(sorted(missing_permissions))}"
                )

            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


def admin_only(
    user_id_extractor: Optional[Callable[..., Union[int, str]]] = None,
    level_extractor: Optional[Callable[..., AccessLevel]] = None,
) -> Callable[[F], F]:
    """Decorator to restrict a handler to admin users only.

    This is a convenience decorator that wraps require_access_level
    with the ADMIN level.

    Args:
        user_id_extractor: Optional function to extract the user ID.
        level_extractor: Optional function to extract the access level.

    Returns:
        A decorator function that wraps the handler with admin check.
    """
    return require_access_level(
        required_level=AccessLevel.ADMIN,
        user_id_extractor=user_id_extractor,
        level_extractor=level_extractor,
    )


def moderator_only(
    user_id_extractor: Optional[Callable[..., Union[int, str]]] = None,
    level_extractor: Optional[Callable[..., AccessLevel]] = None,
) -> Callable[[F], F]:
    """Decorator to restrict a handler to moderator users and above.

    This is a convenience decorator that wraps require_access_level
    with the MODERATOR level.

    Args:
        user_id_extractor: Optional function to extract the user ID.
        level_extractor: Optional function to extract the access level.

    Returns:
        A decorator function that wraps the handler with moderator check.
    """
    return require_access_level(
        required_level=AccessLevel.MODERATOR,
        user_id_extractor=user_id_extractor,
        level_extractor=level_extractor,
    )


def user_only(
    user_id_extractor: Optional[Callable[..., Union[int, str]]] = None,
    level_extractor: Optional[Callable[..., AccessLevel]] = None,
) -> Callable[[F], F]:
    """Decorator to restrict a handler to authenticated users only.

    This is a convenience decorator that wraps require_access_level
    with the USER level.

    Args:
        user_id_extractor: Optional function to extract the user ID.
        level_extractor: Optional function to extract the access level.

    Returns:
        A decorator function that wraps the handler with user check.
    """
    return require_access_level(
        required_level=AccessLevel.USER,
        user_id_extractor=user_id_extractor,
        level_extractor=level_extractor,
    )


def rate_limit_per_user(
    max_requests: int,
    window_seconds: int,
    user_id_extractor: Optional[Callable[..., Union[int, str]]] = None,
    raise_on_limit: bool = True,
) -> Callable[[F], F]:
    """Decorator to apply per-user rate limiting.

    This is a convenience decorator that wraps rate_limit with a
    user-specific key.

    Args:
        max_requests: Maximum number of requests allowed in the window.
        window_seconds: The time window in seconds.
        user_id_extractor: Optional function to extract the user ID.
            If not provided, the first argument is used as the user ID.
        raise_on_limit: If True, raises RateLimitExceeded when limit is
            exceeded.

    Returns:
        A decorator function that wraps the handler with per-user rate limiting.
    """
    def key_extractor(*args: Any, **kwargs: Any) -> str:
        if user_id_extractor is not None:
            user_id = user_id_extractor(*args, **kwargs)
        else:
            user_id = args[0] if args else kwargs.get("user_id", "unknown")
        return f"user:{user_id}"

    return rate_limit(
        max_requests=max_requests,
        window_seconds=window_seconds,
        key_extractor=key_extractor,
        raise_on_limit=raise_on_limit,
    )


def rate_limit_per_chat(
    max_requests: int,
    window_seconds: int,
    chat_id_extractor: Optional[Callable[..., Union[int, str]]] = None,
    raise_on_limit: bool = True,
) -> Callable[[F], F]:
    """Decorator to apply per-chat rate limiting.

    This is a convenience decorator that wraps rate_limit with a
    chat-specific key.

    Args:
        max_requests: Maximum number of requests allowed in the window.
        window_seconds: The time window in seconds.
        chat_id_extractor: Optional function to extract the chat ID.
            If not provided, the second argument is used as the chat ID.
        raise_on_limit: If True, raises RateLimitExceeded when limit is
            exceeded.

    Returns:
        A decorator function that wraps the handler with per-chat rate limiting.
    """
    def key_extractor(*args: Any, **kwargs: Any) -> str:
        if chat_id_extractor is not None:
            chat_id = chat_id_extractor(*args, **kwargs)
        else:
            chat_id = args[1] if len(args) > 1 else kwargs.get("chat_id", "unknown")
        return f"chat:{chat_id}"

    return rate_limit(
        max_requests=max_requests,
        window_seconds=window_seconds,
        key_extractor=key_extractor,
        raise_on_limit=raise_on_limit,
    )


def combined_auth(
    required_level: AccessLevel = AccessLevel.USER,
    max_requests: int = 10,
    window_seconds: int = 60,
    user_id_extractor: Optional[Callable[..., Union[int, str]]] = None,
    level_extractor: Optional[Callable[..., AccessLevel]] = None,
    raise_on_limit: bool = True,
) -> Callable[[F], F]:
    """Decorator that combines authorization and rate limiting.

    This decorator applies both access level checking and rate limiting
    to a handler. The authorization check is performed first, followed
    by the rate limit check.

    Args:
        required_level: The minimum access level required.
        max_requests: Maximum number of requests allowed in the window.
        window_seconds: The time window in seconds.
        user_id_extractor: Optional function to extract the user ID.
        level_extractor: Optional function to extract the access level.
        raise_on_limit: If True, raises RateLimitExceeded when limit is
            exceeded.

    Returns:
        A decorator function that wraps the handler with combined checks.
    """
    def decorator(func: F) -> F:
        # Apply authorization first, then rate limiting
        auth_decorator = require_access_level(
            required_level=required_level,
            user_id_extractor=user_id_extractor,
            level_extractor=level_extractor,
        )
        rate_decorator = rate_limit_per_user(
            max_requests=max_requests,
            window_seconds=window_seconds,
            user_id_extractor=user_id_extractor,
            raise_on_limit=raise_on_limit,
        )

        # Apply decorators from bottom to top (rate limiting wraps authorization)
        return cast(F, rate_decorator(auth_decorator(func)))

    return decorator


def log_execution_time(
    logger_name: Optional[str] = None,
    log_level: int = logging.DEBUG,
) -> Callable[[F], F]:
    """Decorator to log the execution time of a handler.

    This decorator measures and logs how long a handler takes to execute.

    Args:
        logger_name: Optional name for the logger. If not provided,
            the handler's module logger is used.
        log_level: The logging level to use (default: DEBUG).

    Returns:
        A decorator function that wraps the handler with timing logging.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            log = logging.getLogger(logger_name or func.__module__)
            start_time = time.monotonic()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                elapsed = time.monotonic() - start_time
                log.log(
                    log_level,
                    "Handler '%s' executed in %.4f seconds",
                    func.__qualname__,
                    elapsed,
                )

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            log = logging.getLogger(logger_name or func.__module__)
            start_time = time.monotonic()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = time.monotonic() - start_time
                log.log(
                    log_level,
                    "Handler '%s' executed in %.4f seconds",
                    func.__qualname__,
                    elapsed,
                )

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


def retry_on_failure(
    max_retries: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[type, ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator to retry a handler on failure.

    This decorator retries the handler a specified number of times
    with exponential backoff if it raises certain exceptions.

    Args:
        max_retries: Maximum number of retry attempts.
        delay_seconds: Initial delay between retries in seconds.
        backoff_factor: Multiplier for the delay after each retry.
        exceptions: Tuple of exception types to catch and retry on.

    Returns:
        A decorator function that wraps the handler with retry logic.

    Raises:
        The last exception raised if all retries are exhausted.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None
            current_delay = delay_seconds

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            "Handler '%s' failed on attempt %d/%d: %s. "
                            "Retrying in %.2f seconds...",
                            func.__qualname__,
                            attempt + 1,
                            max_retries + 1,
                            str(e),
                            current_delay,
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff_factor
                    else:
                        logger.error(
                            "Handler '%s' failed after %d attempts: %s",
                            func.__qualname__,
                            max_retries + 1,
                            str(e),
                        )

            if last_exception is not None:
                raise last_exception

            # This should never be reached, but satisfies type checking
            raise RuntimeError("Unexpected error in retry decorator")

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None
            current_delay = delay_seconds

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            "Handler '%s' failed on attempt %d/%d: %s. "
                            "Retrying in %.2f seconds...",
                            func.__qualname__,
                            attempt + 1,
                            max_retries + 1,
                            str(e),
                            current_delay,
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff_factor
                    else:
                        logger.error(
                            "Handler '%s' failed after %d attempts: %s",
                            func.__qualname__,
                            max_retries + 1,
                            str(e),
                        )

            if last_exception is not None:
                raise last_exception

            # This should never be reached, but satisfies type checking
            raise RuntimeError("Unexpected error in retry decorator")

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


__all__ = [
    "AccessLevel",
    "RateLimitExceeded",
    "AuthorizationError",
    "RateLimiter",
    "get_rate_limiter",
    "require_access_level",
    "rate_limit",
    "require_permissions",
    "admin_only",
    "moderator_only",
    "user_only",
    "rate_limit_per_user",
    "rate_limit_per_chat",
    "combined_auth",
    "log_execution_time",
    "retry_on_failure",
]