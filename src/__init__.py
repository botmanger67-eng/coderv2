"""
src package initialization module.

This module initializes the src package and provides common utilities
and configuration for all submodules within the package.
"""

import logging
import os
from typing import Any, Dict, Optional

# Package metadata
__version__ = "1.0.0"
__author__ = "Enterprise Engineering Team"
__description__ = "Enterprise-grade source package for core application logic"

# Configure package-level logger
logger = logging.getLogger(__name__)

# Package-level configuration
_package_config: Dict[str, Any] = {
    "debug_mode": os.environ.get("SRC_DEBUG", "false").lower() == "true",
    "log_level": os.environ.get("SRC_LOG_LEVEL", "INFO").upper(),
    "max_retries": int(os.environ.get("SRC_MAX_RETRIES", "3")),
    "timeout_seconds": int(os.environ.get("SRC_TIMEOUT_SECONDS", "30")),
}


def configure_logging(level: Optional[str] = None) -> None:
    """
    Configure package-level logging with the specified level.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               If None, uses the value from environment variable or defaults to INFO.

    Raises:
        ValueError: If the provided log level is invalid.
    """
    log_level = (level or _package_config["log_level"]).upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

    if log_level not in valid_levels:
        raise ValueError(
            f"Invalid log level: {log_level}. "
            f"Must be one of: {', '.join(sorted(valid_levels))}"
        )

    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("Package logging configured with level: %s", log_level)


def get_config(key: str, default: Any = None) -> Any:
    """
    Retrieve a package configuration value by key.

    Args:
        key: Configuration key to look up.
        default: Default value to return if key is not found.

    Returns:
        The configuration value associated with the key, or the default value.

    Raises:
        KeyError: If the key is not found and no default is provided.
    """
    if key in _package_config:
        return _package_config[key]
    if default is not None:
        return default
    raise KeyError(f"Configuration key '{key}' not found and no default provided.")


def set_config(key: str, value: Any) -> None:
    """
    Set a package configuration value.

    Args:
        key: Configuration key to set.
        value: Value to assign to the configuration key.

    Raises:
        TypeError: If the key is not a string.
    """
    if not isinstance(key, str):
        raise TypeError(f"Configuration key must be a string, got {type(key).__name__}")
    _package_config[key] = value
    logger.debug("Configuration updated: %s = %s", key, value)


def is_debug_mode() -> bool:
    """
    Check if the package is running in debug mode.

    Returns:
        True if debug mode is enabled, False otherwise.
    """
    return _package_config.get("debug_mode", False)


# Initialize package logging on import
configure_logging()

# Export public API
__all__: list[str] = [
    "__version__",
    "__author__",
    "__description__",
    "configure_logging",
    "get_config",
    "set_config",
    "is_debug_mode",
    "logger",
]