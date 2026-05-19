"""Input validators for the application.

This module provides robust validation functions for common input types
used throughout the application. All validators raise appropriate exceptions
with descriptive messages when validation fails.
"""

import re
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, date
from uuid import UUID


class ValidationError(Exception):
    """Exception raised for validation errors."""
    pass


def validate_string(
    value: Any,
    field_name: str = "value",
    min_length: int = 0,
    max_length: Optional[int] = None,
    allow_empty: bool = False,
    pattern: Optional[str] = None,
    strip: bool = True
) -> str:
    """Validate and return a string value.

    Args:
        value: The value to validate.
        field_name: Name of the field for error messages.
        min_length: Minimum allowed length (default 0).
        max_length: Maximum allowed length (optional).
        allow_empty: Whether empty strings are allowed (default False).
        pattern: Optional regex pattern the string must match.
        strip: Whether to strip whitespace (default True).

    Returns:
        The validated string.

    Raises:
        ValidationError: If validation fails.
    """
    if value is None:
        raise ValidationError(f"{field_name} is required")

    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string, got {type(value).__name__}")

    processed = value.strip() if strip else value

    if not allow_empty and not processed:
        raise ValidationError(f"{field_name} cannot be empty")

    if len(processed) < min_length:
        raise ValidationError(
            f"{field_name} must be at least {min_length} characters long"
        )

    if max_length is not None and len(processed) > max_length:
        raise ValidationError(
            f"{field_name} must be at most {max_length} characters long"
        )

    if pattern is not None and not re.match(pattern, processed):
        raise ValidationError(f"{field_name} does not match required pattern")

    return processed


def validate_integer(
    value: Any,
    field_name: str = "value",
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
    allow_none: bool = False
) -> int:
    """Validate and return an integer value.

    Args:
        value: The value to validate.
        field_name: Name of the field for error messages.
        min_value: Minimum allowed value (optional).
        max_value: Maximum allowed value (optional).
        allow_none: Whether None is allowed (default False).

    Returns:
        The validated integer.

    Raises:
        ValidationError: If validation fails.
    """
    if value is None:
        if allow_none:
            return None
        raise ValidationError(f"{field_name} is required")

    if isinstance(value, bool):
        raise ValidationError(f"{field_name} must be an integer, got boolean")

    try:
        int_value = int(value)
    except (TypeError, ValueError):
        raise ValidationError(
            f"{field_name} must be an integer, got {type(value).__name__}"
        )

    if min_value is not None and int_value < min_value:
        raise ValidationError(
            f"{field_name} must be at least {min_value}"
        )

    if max_value is not None and int_value > max_value:
        raise ValidationError(
            f"{field_name} must be at most {max_value}"
        )

    return int_value


def validate_float(
    value: Any,
    field_name: str = "value",
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    allow_none: bool = False
) -> float:
    """Validate and return a float value.

    Args:
        value: The value to validate.
        field_name: Name of the field for error messages.
        min_value: Minimum allowed value (optional).
        max_value: Maximum allowed value (optional).
        allow_none: Whether None is allowed (default False).

    Returns:
        The validated float.

    Raises:
        ValidationError: If validation fails.
    """
    if value is None:
        if allow_none:
            return None
        raise ValidationError(f"{field_name} is required")

    if isinstance(value, bool):
        raise ValidationError(f"{field_name} must be a number, got boolean")

    try:
        float_value = float(value)
    except (TypeError, ValueError):
        raise ValidationError(
            f"{field_name} must be a number, got {type(value).__name__}"
        )

    if min_value is not None and float_value < min_value:
        raise ValidationError(
            f"{field_name} must be at least {min_value}"
        )

    if max_value is not None and float_value > max_value:
        raise ValidationError(
            f"{field_name} must be at most {max_value}"
        )

    return float_value


def validate_boolean(
    value: Any,
    field_name: str = "value",
    allow_none: bool = False
) -> bool:
    """Validate and return a boolean value.

    Args:
        value: The value to validate.
        field_name: Name of the field for error messages.
        allow_none: Whether None is allowed (default False).

    Returns:
        The validated boolean.

    Raises:
        ValidationError: If validation fails.
    """
    if value is None:
        if allow_none:
            return None
        raise ValidationError(f"{field_name} is required")

    if not isinstance(value, bool):
        raise ValidationError(
            f"{field_name} must be a boolean, got {type(value).__name__}"
        )

    return value


def validate_email(
    value: Any,
    field_name: str = "email",
    allow_none: bool = False
) -> str:
    """Validate and return an email address.

    Args:
        value: The value to validate.
        field_name: Name of the field for error messages.
        allow_none: Whether None is allowed (default False).

    Returns:
        The validated email string.

    Raises:
        ValidationError: If validation fails.
    """
    if value is None:
        if allow_none:
            return None
        raise ValidationError(f"{field_name} is required")

    email = validate_string(value, field_name=field_name, allow_empty=False)

    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValidationError(f"{field_name} is not a valid email address")

    return email


def validate_url(
    value: Any,
    field_name: str = "url",
    allow_none: bool = False,
    require_https: bool = False
) -> str:
    """Validate and return a URL.

    Args:
        value: The value to validate.
        field_name: Name of the field for error messages.
        allow_none: Whether None is allowed (default False).
        require_https: Whether HTTPS is required (default False).

    Returns:
        The validated URL string.

    Raises:
        ValidationError: If validation fails.
    """
    if value is None:
        if allow_none:
            return None
        raise ValidationError(f"{field_name} is required")

    url = validate_string(value, field_name=field_name, allow_empty=False)

    # URL regex pattern
    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    if not re.match(pattern, url):
        raise ValidationError(f"{field_name} is not a valid URL")

    if require_https and not url.startswith('https://'):
        raise ValidationError(f"{field_name} must use HTTPS")

    return url


def validate_uuid(
    value: Any,
    field_name: str = "uuid",
    allow_none: bool = False,
    version: Optional[int] = None
) -> UUID:
    """Validate and return a UUID.

    Args:
        value: The value to validate.
        field_name: Name of the field for error messages.
        allow_none: Whether None is allowed (default False).
        version: Required UUID version (1-5, optional).

    Returns:
        The validated UUID object.

    Raises:
        ValidationError: If validation fails.
    """
    if value is None:
        if allow_none:
            return None
        raise ValidationError(f"{field_name} is required")

    if isinstance(value, UUID):
        uuid_value = value
    else:
        try:
            uuid_value = UUID(str(value))
        except (ValueError, AttributeError):
            raise ValidationError(f"{field_name} is not a valid UUID")

    if version is not None and uuid_value.version != version:
        raise ValidationError(
            f"{field_name} must be UUID version {version}, "
            f"got version {uuid_value.version}"
        )

    return uuid_value


def validate_date(
    value: Any,
    field_name: str = "date",
    allow_none: bool = False,
    min_date: Optional[date] = None,
    max_date: Optional[date] = None
) -> date:
    """Validate and return a date value.

    Args:
        value: The value to validate (date object or ISO format string).
        field_name: Name of the field for error messages.
        allow_none: Whether None is allowed (default False).
        min_date: Minimum allowed date (optional).
        max_date: Maximum allowed date (optional).

    Returns:
        The validated date object.

    Raises:
        ValidationError: If validation fails.
    """
    if value is None:
        if allow_none:
            return None
        raise ValidationError(f"{field_name} is required")

    if isinstance(value, date) and not isinstance(value, datetime):
        date_value = value
    elif isinstance(value, str):
        try:
            date_value = date.fromisoformat(value)
        except ValueError:
            raise ValidationError(
                f"{field_name} is not a valid date (expected ISO format YYYY-MM-DD)"
            )
    elif isinstance(value, datetime):
        date_value = value.date()
    else:
        raise ValidationError(
            f"{field_name} must be a date, string, or datetime, "
            f"got {type(value).__name__}"
        )

    if min_date is not None and date_value < min_date:
        raise ValidationError(
            f"{field_name} must be on or after {min_date.isoformat()}"
        )

    if max_date is not None and date_value > max_date:
        raise ValidationError(
            f"{field_name} must be on or before {max_date.isoformat()}"
        )

    return date_value


def validate_datetime(
    value: Any,
    field_name: str = "datetime",
    allow_none: bool = False,
    min_datetime: Optional[datetime] = None,
    max_datetime: Optional[datetime] = None
) -> datetime:
    """Validate and return a datetime value.

    Args:
        value: The value to validate (datetime object or ISO format string).
        field_name: Name of the field for error messages.
        allow_none: Whether None is allowed (default False).
        min_datetime: Minimum allowed datetime (optional).
        max_datetime: Maximum allowed datetime (optional).

    Returns:
        The validated datetime object.

    Raises:
        ValidationError: If validation fails.
    """
    if value is None:
        if allow_none:
            return None
        raise ValidationError(f"{field_name} is required")

    if isinstance(value, datetime):
        datetime_value = value
    elif isinstance(value, str):
        try:
            datetime_value = datetime.fromisoformat(value)
        except ValueError:
            raise ValidationError(
                f"{field_name} is not a valid datetime (expected ISO format)"
            )
    else:
        raise ValidationError(
            f"{field_name} must be a datetime or string, "
            f"got {type(value).__name__}"
        )

    if min_datetime is not None and datetime_value < min_datetime:
        raise ValidationError(
            f"{field_name} must be on or after {min_datetime.isoformat()}"
        )

    if max_datetime is not None and datetime_value > max_datetime:
        raise ValidationError(
            f"{field_name} must be on or before {max_datetime.isoformat()}"
        )

    return datetime_value


def validate_list(
    value: Any,
    field_name: str = "list",
    allow_none: bool = False,
    min_length: int = 0,
    max_length: Optional[int] = None,
    item_validator: Optional[callable] = None
) -> List[Any]:
    """Validate and return a list value.

    Args:
        value: The value to validate.
        field_name: Name of the field for error messages.
        allow_none: Whether None is allowed (default False).
        min_length: Minimum allowed length (default 0).
        max_length: Maximum allowed length (optional).
        item_validator: Optional callable to validate each item.

    Returns:
        The validated list.

    Raises:
        ValidationError: If validation fails.
    """
    if value is None:
        if allow_none:
            return None
        raise ValidationError(f"{field_name} is required")

    if not isinstance(value, list):
        raise ValidationError(
            f"{field_name} must be a list, got {type(value).__name__}"
        )

    if len(value) < min_length:
        raise ValidationError(
            f"{field_name} must have at least {min_length} items"
        )

    if max_length is not None and len(value) > max_length:
        raise ValidationError(
            f"{field_name} must have at most {max_length} items"
        )

    if item_validator is not None:
        validated_items = []
        for index, item in enumerate(value):
            try:
                validated_item = item_validator(item)
                validated_items.append(validated_item)
            except ValidationError as e:
                raise ValidationError(
                    f"{field_name}[{index}]: {str(e)}"
                )
        return validated_items

    return value


def validate_dict(
    value: Any,
    field_name: str = "dict",
    allow_none: bool = False,
    required_keys: Optional[List[str]] = None,
    optional_keys: Optional[List[str]] = None,
    key_validator: Optional[callable] = None,
    value_validator: Optional[callable] = None
) -> Dict[str, Any]:
    """Validate and return a dictionary value.

    Args:
        value: The value to validate.
        field_name: Name of the field for error messages.
        allow_none: Whether None is allowed (default False).
        required_keys: List of keys that must be present.
        optional_keys: List of keys that are allowed (optional).
        key_validator: Optional callable to validate each key.
        value_validator: Optional callable to validate each value.

    Returns:
        The validated dictionary.

    Raises:
        ValidationError: If validation fails.
    """
    if value is None:
        if allow_none:
            return None
        raise ValidationError(f"{field_name} is required")

    if not isinstance(value, dict):
        raise ValidationError(
            f"{field_name} must be a dictionary, got {type(value).__name__}"
        )

    if required_keys:
        missing_keys = [key for key in required_keys if key not in value]
        if missing_keys:
            raise ValidationError(
                f"{field_name} is missing required keys: {', '.join(missing_keys)}"
            )

    if optional_keys is not None:
        allowed_keys = set(required_keys or []) | set(optional_keys)
        extra_keys = set(value.keys()) - allowed_keys
        if extra_keys:
            raise ValidationError(
                f"{field_name} has unexpected keys: {', '.join(extra_keys)}"
            )

    if key_validator is not None or value_validator is not None:
        validated_dict = {}
        for key, val in value.items():
            validated_key = key_validator(key) if key_validator else key
            validated_val = value_validator(val) if value_validator else val
            validated_dict[validated_key] = validated_val
        return validated_dict

    return value


def validate_phone(
    value: Any,
    field_name: str = "phone",
    allow_none: bool = False,
    country_code: Optional[str] = None
) -> str:
    """Validate and return a phone number.

    Args:
        value: The value to validate.
        field_name: Name of the field for error messages.
        allow_none: Whether None is allowed (default False).
        country_code: Optional country code prefix (e.g., '+1').

    Returns:
        The validated phone number string.

    Raises:
        ValidationError: If validation fails.
    """
    if value is None:
        if allow_none:
            return None
        raise ValidationError(f"{field_name} is required")

    phone = validate_string(value, field_name=field_name, allow_empty=False)

    # Remove common separators
    cleaned = re.sub(r'[\s\-\(\)\.]', '', phone)

    # Basic phone validation (at least 7 digits, at most 15)
    if not re.match(r'^\+?\d{7,15}$', cleaned):
        raise ValidationError(f"{field_name} is not a valid phone number")

    if country_code and not cleaned.startswith(country_code):
        raise ValidationError(
            f"{field_name} must start with country code {country_code}"
        )

    return cleaned


def validate_choice(
    value: Any,
    choices: List[Any],
    field_name: str = "value",
    allow_none: bool = False
) -> Any:
    """Validate that a value is one of the allowed choices.

    Args:
        value: The value to validate.
        choices: List of allowed values.
        field_name: Name of the field for error messages.
        allow_none: Whether None is allowed (default False).

    Returns:
        The validated value.

    Raises:
        ValidationError: If validation fails.
    """
    if value is None:
        if allow_none:
            return None
        raise ValidationError(f"{field_name} is required")

    if value not in choices:
        choices_str = ', '.join(str(c) for c in choices)
        raise ValidationError(
            f"{field_name} must be one of: {choices_str}"
        )

    return value