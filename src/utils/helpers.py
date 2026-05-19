"""
Helper functions for the application.

This module provides utility functions for common operations such as
data validation, formatting, and general-purpose helpers.
"""

import re
import json
import hashlib
import logging
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path

logger = logging.getLogger(__name__)


def validate_email(email: str) -> bool:
    """
    Validate an email address format.

    Args:
        email: Email address to validate.

    Returns:
        True if email format is valid, False otherwise.
    """
    if not isinstance(email, str) or not email.strip():
        return False

    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def validate_phone(phone: str) -> bool:
    """
    Validate a phone number format (supports international formats).

    Args:
        phone: Phone number to validate.

    Returns:
        True if phone format is valid, False otherwise.
    """
    if not isinstance(phone, str) or not phone.strip():
        return False

    # Remove common separators
    cleaned = re.sub(r'[\s\-\(\)\.]', '', phone)
    # Allow optional + prefix, digits only
    pattern = r'^\+?\d{7,15}$'
    return bool(re.match(pattern, cleaned))


def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize a string by stripping whitespace and optionally truncating.

    Args:
        value: Input string to sanitize.
        max_length: Maximum allowed length (optional).

    Returns:
        Sanitized string.
    """
    if not isinstance(value, str):
        raise TypeError(f"Expected string, got {type(value).__name__}")

    sanitized = value.strip()

    if max_length is not None and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized


def parse_date(date_string: str, formats: Optional[List[str]] = None) -> Optional[date]:
    """
    Parse a date string into a date object.

    Args:
        date_string: Date string to parse.
        formats: List of date format strings to try (default: ISO formats).

    Returns:
        Date object if parsing succeeds, None otherwise.
    """
    if not isinstance(date_string, str) or not date_string.strip():
        return None

    if formats is None:
        formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%d-%m-%Y',
            '%d/%m/%Y',
            '%m-%d-%Y',
            '%m/%d/%Y',
            '%Y%m%d',
        ]

    for fmt in formats:
        try:
            return datetime.strptime(date_string.strip(), fmt).date()
        except ValueError:
            continue

    logger.warning(f"Unable to parse date string: {date_string}")
    return None


def format_currency(amount: Union[int, float, Decimal, str], currency_symbol: str = '$') -> str:
    """
    Format a numeric value as currency string.

    Args:
        amount: Numeric value to format.
        currency_symbol: Currency symbol to prepend (default: $).

    Returns:
        Formatted currency string.

    Raises:
        ValueError: If amount cannot be converted to Decimal.
    """
    try:
        if isinstance(amount, str):
            amount = Decimal(amount)
        elif not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        # Round to 2 decimal places
        amount = amount.quantize(Decimal('0.01'))

        # Format with commas for thousands
        parts = str(amount).split('.')
        integer_part = parts[0]
        decimal_part = parts[1] if len(parts) > 1 else '00'

        # Add commas to integer part
        formatted_integer = ''
        for i, digit in enumerate(reversed(integer_part)):
            if i > 0 and i % 3 == 0:
                formatted_integer = ',' + formatted_integer
            formatted_integer = digit + formatted_integer

        return f"{currency_symbol}{formatted_integer}.{decimal_part}"

    except (InvalidOperation, ValueError, TypeError) as e:
        raise ValueError(f"Invalid currency amount: {amount}") from e


def generate_hash(data: str, algorithm: str = 'sha256') -> str:
    """
    Generate a hash of the input string.

    Args:
        data: Input string to hash.
        algorithm: Hash algorithm to use (default: sha256).

    Returns:
        Hexadecimal hash string.

    Raises:
        ValueError: If algorithm is not supported.
    """
    if not isinstance(data, str):
        raise TypeError(f"Expected string, got {type(data).__name__}")

    supported_algorithms = {'md5', 'sha1', 'sha256', 'sha512'}

    if algorithm not in supported_algorithms:
        raise ValueError(f"Unsupported algorithm: {algorithm}. "
                         f"Supported: {', '.join(sorted(supported_algorithms))}")

    try:
        hash_obj = hashlib.new(algorithm, data.encode('utf-8'))
        return hash_obj.hexdigest()
    except ValueError as e:
        raise ValueError(f"Hash generation failed: {e}") from e


def safe_json_loads(json_string: str, default: Any = None) -> Any:
    """
    Safely parse a JSON string with error handling.

    Args:
        json_string: JSON string to parse.
        default: Default value to return if parsing fails.

    Returns:
        Parsed JSON data or default value.
    """
    if not isinstance(json_string, str):
        return default

    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        return default


def chunk_list(data: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split a list into smaller chunks.

    Args:
        data: List to split.
        chunk_size: Maximum size of each chunk.

    Returns:
        List of chunks.

    Raises:
        ValueError: If chunk_size is less than 1.
    """
    if chunk_size < 1:
        raise ValueError(f"Chunk size must be >= 1, got {chunk_size}")

    if not data:
        return []

    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]


def retry_on_failure(
    max_retries: int = 3,
    delay_seconds: float = 1.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    Decorator to retry a function on failure.

    Args:
        max_retries: Maximum number of retry attempts.
        delay_seconds: Delay between retries in seconds.
        exceptions: Tuple of exceptions to catch.

    Returns:
        Decorated function with retry logic.

    Raises:
        ValueError: If max_retries or delay_seconds are invalid.
    """
    import time
    from functools import wraps

    if max_retries < 1:
        raise ValueError(f"max_retries must be >= 1, got {max_retries}")
    if delay_seconds < 0:
        raise ValueError(f"delay_seconds must be >= 0, got {delay_seconds}")

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for "
                            f"{func.__name__}: {e}. Retrying in {delay_seconds}s..."
                        )
                        time.sleep(delay_seconds)
                    else:
                        logger.error(
                            f"All {max_retries} attempts failed for "
                            f"{func.__name__}: {e}"
                        )
            raise last_exception  # type: ignore
        return wrapper
    return decorator


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path to ensure exists.

    Returns:
        Path object for the directory.

    Raises:
        OSError: If directory creation fails.
    """
    path_obj = Path(path) if isinstance(path, str) else path

    try:
        path_obj.mkdir(parents=True, exist_ok=True)
        return path_obj
    except OSError as e:
        logger.error(f"Failed to create directory {path_obj}: {e}")
        raise


def truncate_string(value: str, max_length: int, suffix: str = '...') -> str:
    """
    Truncate a string to a maximum length with an optional suffix.

    Args:
        value: String to truncate.
        max_length: Maximum length of the result.
        suffix: Suffix to append when truncated (default: ...).

    Returns:
        Truncated string.
    """
    if not isinstance(value, str):
        raise TypeError(f"Expected string, got {type(value).__name__}")

    if max_length < len(suffix):
        raise ValueError(f"max_length ({max_length}) must be >= suffix length ({len(suffix)})")

    if len(value) <= max_length:
        return value

    return value[:max_length - len(suffix)] + suffix


def is_valid_url(url: str) -> bool:
    """
    Validate a URL format.

    Args:
        url: URL string to validate.

    Returns:
        True if URL format is valid, False otherwise.
    """
    if not isinstance(url, str) or not url.strip():
        return False

    pattern = (
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?'
        r'|localhost'
        r'|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$'
    )

    return bool(re.match(pattern, url, re.IGNORECASE))


def merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries. Override values take precedence.

    Args:
        base: Base dictionary.
        override: Override dictionary with higher priority.

    Returns:
        Merged dictionary.
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value

    return result


def slugify(text: str) -> str:
    """
    Convert text to URL-friendly slug.

    Args:
        text: Text to convert.

    Returns:
        Slugified string.
    """
    if not isinstance(text, str):
        raise TypeError(f"Expected string, got {type(text).__name__}")

    # Convert to lowercase
    text = text.lower().strip()

    # Replace spaces with hyphens
    text = re.sub(r'\s+', '-', text)

    # Remove non-alphanumeric characters except hyphens
    text = re.sub(r'[^a-z0-9-]', '', text)

    # Remove consecutive hyphens
    text = re.sub(r'-+', '-', text)

    # Remove leading/trailing hyphens
    text = text.strip('-')

    return text


def get_file_extension(filename: str) -> str:
    """
    Get the file extension from a filename.

    Args:
        filename: Filename to extract extension from.

    Returns:
        File extension (lowercase, without dot).
    """
    if not isinstance(filename, str) or not filename.strip():
        return ''

    path = Path(filename.strip())
    extension = path.suffix.lower().lstrip('.')

    return extension


def is_valid_json(data: str) -> bool:
    """
    Check if a string is valid JSON.

    Args:
        data: String to check.

    Returns:
        True if string is valid JSON, False otherwise.
    """
    if not isinstance(data, str):
        return False

    try:
        json.loads(data)
        return True
    except json.JSONDecodeError:
        return False