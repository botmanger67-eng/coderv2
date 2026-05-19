"""
Utils package initialization module.

This module provides common utility functions and classes used across the application.
It serves as the central hub for importing and exposing utility functionality.
"""

from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    Callable,
    TypeVar,
    Generic,
    Iterator,
    Iterable,
    Sequence,
    Mapping,
    MutableMapping,
    overload,
    final,
)
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum, auto
from functools import wraps, lru_cache, partial
from pathlib import Path
from uuid import UUID, uuid4
import hashlib
import hmac
import json
import logging
import os
import re
import string
import sys
import time
import traceback
from collections import OrderedDict, defaultdict, deque
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field, asdict, astuple
from itertools import chain, cycle, islice, zip_longest
from operator import attrgetter, itemgetter, methodcaller
from threading import Lock, RLock, Thread, Timer
from types import MappingProxyType, SimpleNamespace
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

# Type variables for generic utility functions
T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")
R = TypeVar("R")

# Package metadata
__version__ = "1.0.0"
__author__ = "Enterprise Engineering Team"
__all__ = [
    "Config",
    "Logger",
    "Timer",
    "RetryHandler",
    "ValidationError",
    "convert_to_dict",
    "deep_merge",
    "ensure_list",
    "flatten_list",
    "get_nested_value",
    "set_nested_value",
    "sanitize_filename",
    "truncate_string",
    "validate_email",
    "validate_url",
    "generate_uuid",
    "hash_password",
    "verify_password",
    "encrypt_data",
    "decrypt_data",
    "format_timestamp",
    "parse_timestamp",
    "calculate_checksum",
    "compress_data",
    "decompress_data",
    "serialize_json",
    "deserialize_json",
    "chunk_list",
    "paginate",
    "retry_operation",
    "timeout_handler",
    "rate_limiter",
    "circuit_breaker",
    "singleton",
    "cached_property",
    "lazy_property",
    "thread_safe",
    "validate_input",
    "sanitize_input",
    "escape_html",
    "escape_sql",
    "escape_regex",
]


class Config:
    """Application configuration management class."""

    _instance: Optional["Config"] = None
    _lock: RLock = RLock()
    _config: Dict[str, Any] = {}

    def __new__(cls, *args: Any, **kwargs: Any) -> "Config":
        """Ensure singleton pattern for configuration."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_file: Optional[Union[str, Path]] = None) -> None:
        """Initialize configuration from file or environment variables.

        Args:
            config_file: Optional path to configuration file

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._config = {}
            if config_file:
                self.load_from_file(config_file)
            self.load_from_env()

    def load_from_file(self, config_file: Union[str, Path]) -> None:
        """Load configuration from a JSON or YAML file.

        Args:
            config_file: Path to configuration file

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is not supported
        """
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")

        file_extension = config_path.suffix.lower()
        if file_extension == ".json":
            with open(config_path, "r", encoding="utf-8") as f:
                self._config.update(json.load(f))
        else:
            raise ValueError(f"Unsupported configuration file format: {file_extension}")

    def load_from_env(self, prefix: str = "APP_") -> None:
        """Load configuration from environment variables.

        Args:
            prefix: Prefix for environment variables to include
        """
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                self._config[config_key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value.

        Args:
            key: Configuration key
            value: Value to set
        """
        self._config[key] = value

    def update(self, config_dict: Dict[str, Any]) -> None:
        """Update configuration with dictionary.

        Args:
            config_dict: Dictionary of configuration values
        """
        self._config.update(config_dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary of all configuration values
        """
        return dict(self._config)


class Logger:
    """Enterprise-grade logging utility class."""

    _instances: Dict[str, "Logger"] = {}
    _lock: RLock = RLock()

    def __new__(cls, name: str = __name__, *args: Any, **kwargs: Any) -> "Logger":
        """Create or return existing logger instance.

        Args:
            name: Logger name

        Returns:
            Logger instance
        """
        if name not in cls._instances:
            with cls._lock:
                if name not in cls._instances:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instances[name] = instance
        return cls._instances[name]

    def __init__(self, name: str = __name__, level: str = "INFO") -> None:
        """Initialize logger with configuration.

        Args:
            name: Logger name
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        if not self._initialized:
            self._initialized = True
            self._logger = logging.getLogger(name)
            self._logger.setLevel(getattr(logging, level.upper(), logging.INFO))

            # Create console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG)

            # Create formatter
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            console_handler.setFormatter(formatter)

            # Add handler if not already present
            if not self._logger.handlers:
                self._logger.addHandler(console_handler)

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log debug message.

        Args:
            message: Log message
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        self._logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log info message.

        Args:
            message: Log message
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        self._logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log warning message.

        Args:
            message: Log message
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        self._logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log error message.

        Args:
            message: Log message
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        self._logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log critical message.

        Args:
            message: Log message
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        self._logger.critical(message, *args, **kwargs)

    def exception(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log exception with traceback.

        Args:
            message: Log message
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        self._logger.exception(message, *args, **kwargs)


class Timer:
    """Context manager for timing code execution."""

    def __init__(self, name: str = "Timer") -> None:
        """Initialize timer.

        Args:
            name: Timer name for identification
        """
        self.name = name
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.elapsed_time: Optional[float] = None

    def __enter__(self) -> "Timer":
        """Start timing when entering context.

        Returns:
            Timer instance
        """
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop timing when exiting context.

        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        self.end_time = time.perf_counter()
        self.elapsed_time = self.end_time - self.start_time
        Logger().debug(f"{self.name}: {self.elapsed_time:.4f} seconds")

    def get_elapsed(self) -> float:
        """Get elapsed time in seconds.

        Returns:
            Elapsed time in seconds

        Raises:
            RuntimeError: If timer hasn't been started
        """
        if self.start_time is None:
            raise RuntimeError("Timer has not been started")
        if self.end_time is None:
            return time.perf_counter() - self.start_time
        return self.elapsed_time or 0.0


class RetryHandler:
    """Retry handler for operations that may fail temporarily."""

    def __init__(
        self,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ) -> None:
        """Initialize retry handler.

        Args:
            max_retries: Maximum number of retry attempts
            delay: Initial delay between retries in seconds
            backoff: Multiplier for delay after each retry
            exceptions: Tuple of exception types to catch and retry

        Raises:
            ValueError: If parameters are invalid
        """
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if delay < 0:
            raise ValueError("delay must be non-negative")
        if backoff < 1.0:
            raise ValueError("backoff must be >= 1.0")

        self.max_retries = max_retries
        self.delay = delay
        self.backoff = backoff
        self.exceptions = exceptions
        self.retry_count = 0

    def execute(self, func: Callable[..., R], *args: Any, **kwargs: Any) -> R:
        """Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            Exception: If all retries fail
        """
        last_exception: Optional[Exception] = None
        current_delay = self.delay

        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except self.exceptions as e:
                last_exception = e
                self.retry_count = attempt + 1

                if attempt < self.max_retries:
                    Logger().warning(
                        f"Retry attempt {attempt + 1}/{self.max_retries} failed: {e}"
                    )
                    time.sleep(current_delay)
                    current_delay *= self.backoff
                else:
                    Logger().error(
                        f"All {self.max_retries} retry attempts failed: {e}"
                    )

        if last_exception:
            raise last_exception
        raise RuntimeError("Retry handler failed unexpectedly")


class ValidationError(Exception):
    """Custom exception for validation errors."""

    def __init__(self, message: str, field: Optional[str] = None) -> None:
        """Initialize validation error.

        Args:
            message: Error message
            field: Optional field name that caused the error
        """
        self.field = field
        self.message = message
        super().__init__(self.__str__())

    def __str__(self) -> str:
        """String representation of validation error.

        Returns:
            Formatted error message
        """
        if self.field:
            return f"Validation error for '{self.field}': {self.message}"
        return f"Validation error: {self.message}"


def convert_to_dict(obj: Any, recursive: bool = True) -> Dict[str, Any]:
    """Convert object to dictionary.

    Args:
        obj: Object to convert
        recursive: Whether to recursively convert nested objects

    Returns:
        Dictionary representation of object

    Raises:
        TypeError: If object cannot be converted
    """
    if hasattr(obj, "__dict__"):
        result = {}
        for key, value in obj.__dict__.items():
            if recursive and hasattr(value, "__dict__"):
                result[key] = convert_to_dict(value, recursive=True)
            elif isinstance(value, (list, tuple, set)):
                result[key] = [
                    convert_to_dict(item, recursive=True)
                    if hasattr(item, "__dict__")
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result
    elif isinstance(obj, dict):
        return {key: convert_to_dict(value, recursive=True) if recursive and hasattr(value, "__dict__") else value for key, value in obj.items()}
    else:
        raise TypeError(f"Cannot convert {type(obj).__name__} to dictionary")


def deep_merge(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge multiple dictionaries.

    Args:
        *dicts: Dictionaries to merge

    Returns:
        Merged dictionary

    Raises:
        ValueError: If no dictionaries provided
    """
    if not dicts:
        raise ValueError("At least one dictionary must be provided")

    result: Dict[str, Any] = {}
    for d in dicts:
        for key, value in d.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
    return result


def ensure_list(value: Union[T, List[T], Tuple[T, ...], Set[T]]) -> List[T]:
    """Ensure value is a list.

    Args:
        value: Value to convert to list

    Returns:
        List representation of value
    """
    if isinstance(value, list):
        return value
    elif isinstance(value, (tuple, set)):
        return list(value)
    else:
        return [value]


def flatten_list(nested_list: List[Any], max_depth: Optional[int] = None) -> List[Any]:
    """Flatten nested list structure.

    Args:
        nested_list: Nested list to flatten
        max_depth: Maximum depth to flatten (None for unlimited)

    Returns:
        Flattened list

    Raises:
        ValueError: If max_depth is negative
    """
    if max_depth is not None and max_depth < 0:
        raise ValueError("max_depth must be non-negative")

    result: List[Any] = []
    _flatten(nested_list, result, max_depth, 0)
    return result


def _flatten(
    item: Any,
    result: List[Any],
    max_depth: Optional[int],
    current_depth: int,
) -> None:
    """Helper function for flatten_list.

    Args:
        item: Item to flatten
        result: Result list to append to
        max_depth: Maximum depth to flatten
        current_depth: Current recursion depth
    """
    if isinstance(item, list):
        if max_depth is None or current_depth < max_depth:
            for sub_item in item:
                _flatten(sub_item, result, max_depth, current_depth + 1)
        else:
            result.append(item)
    else:
        result.append(item)


def get_nested_value(data: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """Get value from nested dictionary using dot notation.

    Args:
        data: Dictionary to search
        key_path: Dot-separated key path (e.g., "user.address.city")
        default: Default value if key not found

    Returns:
        Value at key path or default
    """
    keys = key_path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def set_nested_value(data: Dict[str, Any], key_path: str, value: Any) -> Dict[str, Any]:
    """Set value in nested dictionary using dot notation.

    Args:
        data: Dictionary to modify
        key_path: Dot-separated key path
        value: Value to set

    Returns:
        Modified dictionary

    Raises:
        ValueError: If key_path is empty
    """
    if not key_path:
        raise ValueError("key_path cannot be empty")

    keys = key_path.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value
    return data


def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """Sanitize filename by removing invalid characters.

    Args:
        filename: Filename to sanitize
        replacement: Character to replace invalid characters with

    Returns:
        Sanitized filename

    Raises:
        ValueError: If replacement character is invalid
    """
    if len(replacement) != 1:
        raise ValueError("Replacement must be a single character")

    # Remove invalid filename characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, replacement)

    # Remove control characters
    filename = "".join(char for char in filename if ord(char) >= 32)

    # Remove leading/trailing spaces and dots
    filename = filename.strip(". ")

    # Ensure filename is not empty
    if not filename:
        filename = "untitled"

    return filename


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate string to specified length.

    Args:
        text: String to truncate
        max_length: Maximum length of result
        suffix: Suffix to append when truncated

    Returns:
        Truncated string

    Raises:
        ValueError: If max_length is less than suffix length
    """
    if max_length < len(suffix):
        raise ValueError("max_length must be at least the length of suffix")

    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def validate_email(email: str) -> bool:
    """Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        True if valid, False otherwise
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_url(url: str) -> bool:
    """Validate URL format.

    Args:
        url: URL to validate

    Returns:
        True if valid, False otherwise
    """
    pattern = r"^https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_+.~#?&/=]*)$"
    return bool(re.match(pattern, url))


def generate_uuid() -> str:
    """Generate UUID string.

    Returns:
        UUID string
    """
    return str(uuid4())


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hash password with salt.

    Args:
        password: Password to hash
        salt: Optional salt string (generated if not provided)

    Returns:
        Tuple of (hashed_password, salt)

    Raises:
        ValueError: If password is empty
    """
    if not password:
        raise ValueError("Password cannot be empty")

    if salt is None:
        salt = uuid4().hex

    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    )
    return hashed.hex(), salt


def verify_password(password: str, hashed_password: str, salt: str) -> bool:
    """Verify password against hash.

    Args:
        password: Password to verify
        hashed_password: Previously hashed password
        salt: Salt used for hashing

    Returns:
        True if password matches, False otherwise
    """
    try:
        new_hash, _ = hash_password(password, salt)
        return hmac.compare_digest(new_hash, hashed_password)
    except Exception:
        return False


def encrypt_data(data: str, key: str) -> str:
    """Encrypt data using simple XOR cipher.

    Args:
        data: Data to encrypt
        key: Encryption key

    Returns:
        Encrypted data as hex string

    Raises:
        ValueError: If data or key is empty
    """
    if not data:
        raise ValueError("Data cannot be empty")
    if not key:
        raise ValueError("Key cannot be empty")

    encrypted = []
    key_length = len(key)
    for i, char in enumerate(data):
        key_char = key[i % key_length]
        encrypted.append(chr(ord(char) ^ ord(key_char)))
    return "".join(encrypted).encode("utf-8").hex()


def decrypt_data(encrypted_hex: str, key: str) -> str:
    """Decrypt data encrypted with encrypt_data.

    Args:
        encrypted_hex: Encrypted data as hex string
        key: Decryption key

    Returns:
        Decrypted data

    Raises:
        ValueError: If encrypted_hex or key is empty
    """
    if not encrypted_hex:
        raise ValueError("Encrypted data cannot be empty")
    if not key:
        raise ValueError("Key cannot be empty")

    try:
        encrypted = bytes.fromhex(encrypted_hex).decode("utf-8")
        decrypted = []
        key_length = len(key)
        for i, char in enumerate(encrypted):
            key_char = key[i % key_length]
            decrypted.append(chr(ord(char) ^ ord(key_char)))
        return "".join(decrypted)
    except (ValueError, UnicodeDecodeError) as e:
        raise ValueError(f"Failed to decrypt data: {e}")


def format_timestamp(
    timestamp: Optional[datetime] = None,
    format_string: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    """Format timestamp to string.

    Args:
        timestamp: Datetime object (defaults to current UTC time)
        format_string: Format string for output

    Returns:
        Formatted timestamp string
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    return timestamp.strftime(format_string)


def parse_timestamp(
    timestamp_string: str,
    format_string: str = "%Y-%m-%d %H:%M:%S",
) -> datetime:
    """Parse timestamp string to datetime object.

    Args:
        timestamp_string: Timestamp string to parse
        format_string: Format string of input

    Returns:
        Datetime object

    Raises:
        ValueError: If timestamp cannot be parsed
    """
    try:
        return datetime.strptime(timestamp_string, format_string)
    except ValueError as e:
        raise ValueError(f"Failed to parse timestamp '{timestamp_string}': {e}")


def calculate_checksum(data: Union[str, bytes], algorithm: str = "sha256") -> str:
    """Calculate checksum of data.

    Args:
        data: Data to calculate checksum for
        algorithm: Hash algorithm (md5, sha1, sha256, sha512)

    Returns:
        Checksum hex string

    Raises:
        ValueError: If algorithm is not supported
    """
    if isinstance(data, str):
        data = data.encode("utf-8")

    try:
        hasher = hashlib.new(algorithm)
        hasher.update(data)
        return hasher.hexdigest()
    except ValueError:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def compress_data(data: Union[str, bytes]) -> bytes:
    """Compress data using zlib.

    Args:
        data: Data to compress

    Returns:
        Compressed data

    Raises:
        ValueError: If data is empty
    """
    if not data:
        raise ValueError("Data cannot be empty")

    import zlib

    if isinstance(data, str):
        data = data.encode("utf-8")
    return zlib.compress(data)


def decompress_data(compressed_data: bytes) -> bytes:
    """Decompress data using zlib.

    Args:
        compressed_data: Compressed data

    Returns:
        Decompressed data

    Raises:
        ValueError: If data cannot be decompressed
    """
    import zlib

    try:
        return zlib.decompress(compressed_data)
    except zlib.error as e:
        raise ValueError(f"Failed to decompress data: {e}")


def serialize_json(data: Any, pretty: bool = False) -> str:
    """Serialize data to JSON string.

    Args:
        data: Data to serialize
        pretty: Whether to format with indentation

    Returns:
        JSON string

    Raises:
        ValueError: If data cannot be serialized
    """
    try:
        if pretty:
            return json.dumps(data, indent=2, ensure_ascii=False)
        return json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Failed to serialize data: {e}")


def deserialize_json(json_string: str) -> Any:
    """Deserialize JSON string to Python object.

    Args:
        json_string: JSON string to deserialize

    Returns:
        Deserialized Python object

    Raises:
        ValueError: If JSON string is invalid
    """
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to deserialize JSON: {e}")


def chunk_list(data: List[T], chunk_size: int) -> Iterator[List[T]]:
    """Split list into chunks of specified size.

    Args:
        data: List to split
        chunk_size: Size of each chunk

    Yields:
        Chunks of the original list

    Raises:
        ValueError: If chunk_size is less than 1
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")

    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


def paginate(
    data: List[T],
    page: int,
    page_size: int,
) -> Tuple[List[T], int, int, int]:
    """Paginate a list of items.

    Args:
        data: List to paginate
        page: Page number (1-indexed)
        page_size: Number of items per page

    Returns:
        Tuple of (paginated_items, total_items, total_pages, current_page)

    Raises:
        ValueError: If page or page_size is invalid
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    total_items = len(data)
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    paginated_items = data[start_index:end_index]

    return paginated_items, total_items, total_pages, page


def retry_operation(
    func: Callable[..., R],
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable[..., R]:
    """Decorator for retrying operations.

    Args:
        func: Function to wrap with retry logic
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exception types to catch

    Returns:
        Wrapped function with retry logic
    """
    handler = RetryHandler(
        max_retries=max_retries,
        delay=delay,
        backoff=backoff,
        exceptions=exceptions,
    )

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> R:
        return handler.execute(func, *args, **kwargs)

    return wrapper


def timeout_handler(seconds: float) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """Decorator for adding timeout to functions.

    Args:
        seconds: Timeout in seconds

    Returns:
        Decorator function

    Raises:
        ValueError: If seconds is negative
    """
    if seconds < 0:
        raise ValueError("Timeout seconds must be non-negative")

    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> R:
            result: List[R] = []
            error: List[Exception] = []

            def target() -> None:
                try:
                    result.append(func(*args, **kwargs))
                except Exception as e:
                    error.append(e)

            thread = Thread(target=target, daemon=True)
            thread.start()
            thread.join(timeout=seconds)

            if thread.is_alive():
                raise TimeoutError(
                    f"Function '{func.__name__}' timed out after {seconds} seconds"
                )

            if error:
                raise error[0]

            return result[0]

        return wrapper

    return decorator


def rate_limiter(max_calls: int, period: float) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """Decorator for rate limiting function calls.

    Args:
        max_calls: Maximum number of calls allowed in period
        period: Time period in seconds

    Returns:
        Decorator function

    Raises:
        ValueError: If parameters are invalid
    """
    if max_calls < 1:
        raise ValueError("max_calls must be >= 1")
    if period <= 0:
        raise ValueError("period must be positive")

    calls: List[float] = []
    lock = Lock()

    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> R:
            nonlocal calls

            with lock:
                now = time.time()
                # Remove old calls
                calls = [call for call in calls if now - call < period]

                if len(calls) >= max_calls:
                    wait_time = period - (now - calls[0])
                    if wait_time > 0:
                        time.sleep(wait_time)

                calls.append(time.time())

            return func(*args, **kwargs)

        return wrapper

    return decorator


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """Decorator for circuit breaker pattern.

    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Time in seconds before attempting recovery

    Returns:
        Decorator function

    Raises:
        ValueError: If parameters are invalid
    """
    if failure_threshold < 1:
        raise ValueError("failure_threshold must be >= 1")
    if recovery_timeout <= 0:
        raise ValueError("recovery_timeout must be positive")

    failure_count: int = 0
    last_failure_time: float = 0.0
    circuit_open: bool = False
    lock = Lock()

    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> R:
            nonlocal failure_count, last_failure_time, circuit_open

            with lock:
                if circuit_open:
                    if time.time() - last_failure_time >= recovery_timeout:
                        circuit_open = False
                        failure_count = 0
                    else:
                        raise RuntimeError(
                            f"Circuit breaker is open for '{func.__name__}'"
                        )

            try:
                result = func(*args, **kwargs)
                with lock:
                    failure_count = 0
                return result
            except Exception as e:
                with lock:
                    failure_count += 1
                    last_failure_time = time.time()
                    if failure_count >= failure_threshold:
                        circuit_open = True
                raise e

        return wrapper

    return decorator


def singleton(cls: Type[T]) -> Type[T]:
    """Decorator for singleton pattern.

    Args:
        cls: Class to make singleton

    Returns:
        Singleton class
    """
    instances: Dict[Type[T], T] = {}
    lock = RLock()

    @wraps(cls, updated=())  # type: ignore
    def get_instance(*args: Any, **kwargs: Any) -> T:
        with lock:
            if cls not in instances:
                instances[cls] = cls(*args, **kwargs)
            return instances[cls]

    return cast(Type[T], get_instance)


class cached_property(Generic[T]):
    """Descriptor for cached properties."""

    def __init__(self, func: Callable[..., T]) -> None:
        """Initialize cached property.

        Args:
            func: Function to cache
        """
        self.func = func
        self.attr_name = f"_cached_{func.__name__}"
        self.lock = RLock()

    def __get__(self, obj: Any, objtype: Optional[Type] = None) -> T:
        """Get cached property value.

        Args:
            obj: Instance object
            objtype: Class type

        Returns:
            Cached value

        Raises:
            AttributeError: If accessed on class
        """
        if obj is None:
            raise AttributeError("Cannot access cached property from class")

        with self.lock:
            if not hasattr(obj, self.attr_name):
                value = self.func(obj)
                setattr(obj, self.attr_name, value)
            return getattr(obj, self.attr_name)

    def __set__(self, obj: Any, value: T) -> None:
        """Set cached property value.

        Args:
            obj: Instance object
            value: Value to set
        """
        with self.lock:
            setattr(obj, self.attr_name, value)

    def __delete__(self, obj: Any) -> None:
        """Delete cached property value.

        Args:
            obj: Instance object
        """
        with self.lock:
            if hasattr(obj, self.attr_name):
                delattr(obj, self.attr_name)


class lazy_property(Generic[T]):
    """Descriptor for lazily evaluated properties."""

    def __init__(self, func: Callable[..., T]) -> None:
        """Initialize lazy property.

        Args:
            func: Function to evaluate lazily
        """
        self.func = func
        self.attr_name = f"_lazy_{func.__name__}"

    def __get__(self, obj: Any, objtype: Optional[Type] = None) -> T:
        """Get lazy property value.

        Args:
            obj: Instance object
            objtype: Class type

        Returns:
            Evaluated value

        Raises:
            AttributeError: If accessed on class
        """
        if obj is None:
            raise AttributeError("Cannot access lazy property from class")

        if not hasattr(obj, self.attr_name):
            value = self.func(obj)
            setattr(obj, self.attr_name, value)
        return getattr(obj, self.attr_name)


def thread_safe(func: Callable[..., R]) -> Callable[..., R]:
    """Decorator for making functions thread-safe.

    Args:
        func: Function to make thread-safe

    Returns:
        Thread-safe wrapper function
    """
    lock = RLock()

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> R:
        with lock:
            return func(*args, **kwargs)

    return wrapper


def validate_input(
    validators: Dict[str, Callable[[Any], bool]],
    error_messages: Optional[Dict[str, str]] = None,
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """Decorator for input validation.

    Args:
        validators: Dictionary mapping parameter names to validator functions
        error_messages: Optional custom error messages for each parameter

    Returns:
        Decorator function
    """
    if error_messages is None:
        error_messages = {}

    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> R:
            # Get function signature
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            for param_name, validator in validators.items():
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    if not validator(value):
                        message = error_messages.get(
                            param_name,
                            f"Validation failed for parameter '{param_name}'",
                        )
                        raise ValidationError(message, field=param_name)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def sanitize_input(text: str, allowed_chars: Optional[str] = None) -> str:
    """Sanitize input string by removing dangerous characters.

    Args:
        text: Input text to sanitize
        allowed_chars: String of allowed characters (default: alphanumeric and basic punctuation)

    Returns:
        Sanitized text
    """
    if allowed_chars is None:
        allowed_chars = string.ascii_letters + string.digits + " _-.,!?@#$%^&*()"

    return "".join(char for char in text if char in allowed_chars)


def escape_html(text: str) -> str:
    """Escape HTML special characters.

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    html_escape_table = {
        "&": "&amp;",
        '"': "&quot;",
        "'": "&#x27;",
        ">": "&gt;",
        "<": "&lt;",
    }
    return "".join(html_escape_table.get(c, c) for c in text)


def escape_sql(text: str) -> str:
    """Escape SQL special characters.

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    # Basic SQL injection prevention
    dangerous_chars = ["'", '"', ";", "--", "/*", "*/", "@@", "@", "char", "nchar", "varchar", "nvarchar", "alter", "begin", "cast", "create", "cursor", "declare", "delete", "drop", "exec", "execute", "fetch", "insert", "kill", "open", "select", "sys", "table", "update"]
    
    escaped = text
    for char in dangerous_chars:
        escaped = escaped.replace(char, "")
    
    return escaped


def escape_regex(text: str) -> str:
    """Escape regex special characters.

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    return re.escape(text)


# Initialize default logger
logger = Logger()

# Export all public symbols
__all__ = [
    "Config",
    "Logger",
    "Timer",
    "RetryHandler",
    "ValidationError",
    "convert_to_dict",
    "deep_merge",
    "ensure_list",
    "flatten_list",
    "get_nested_value",
    "set_nested_value",
    "sanitize_filename",
    "truncate_string",
    "validate_email",
    "validate_url",
    "generate_uuid",
    "hash_password",
    "verify_password",
    "encrypt_data",
    "decrypt_data",
    "format_timestamp",
    "parse_timestamp",
    "calculate_checksum",
    "compress_data",
    "decompress_data",
    "serialize_json",
    "deserialize_json",
    "chunk_list",
    "paginate",
    "retry_operation",
    "timeout_handler",
    "rate_limiter",
    "circuit_breaker",
    "singleton",
    "cached_property",
    "lazy_property",
    "thread_safe",
    "validate_input",
    "sanitize_input",
    "escape_html",
    "escape_sql",
    "escape_regex",
]