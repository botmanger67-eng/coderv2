"""
Core package initialization module.

This module provides the foundational components for the application,
including configuration management, logging setup, and core utilities.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

# Package metadata
__version__ = "1.0.0"
__author__ = "Enterprise Engineering Team"
__description__ = "Core package for enterprise application infrastructure"

# Public API exports
__all__: list[str] = [
    "ConfigManager",
    "setup_logging",
    "get_logger",
    "CoreError",
    "ConfigurationError",
    "LoggingError",
    "validate_config",
    "get_core_version",
]

# Type aliases
ConfigDict = Dict[str, Any]
LoggerInstance = logging.Logger


class CoreError(Exception):
    """Base exception for all core package errors."""

    def __init__(self, message: str, error_code: Optional[str] = None) -> None:
        """
        Initialize CoreError.

        Args:
            message: Human-readable error description
            error_code: Optional error code for tracking
        """
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return string representation with error code if available."""
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class ConfigurationError(CoreError):
    """Exception raised for configuration-related errors."""

    def __init__(self, message: str, config_key: Optional[str] = None) -> None:
        """
        Initialize ConfigurationError.

        Args:
            message: Human-readable error description
            config_key: Optional configuration key that caused the error
        """
        self.config_key = config_key
        error_code = "CONFIG_ERR"
        super().__init__(message, error_code)


class LoggingError(CoreError):
    """Exception raised for logging-related errors."""

    def __init__(self, message: str, logger_name: Optional[str] = None) -> None:
        """
        Initialize LoggingError.

        Args:
            message: Human-readable error description
            logger_name: Optional name of the logger that caused the error
        """
        self.logger_name = logger_name
        error_code = "LOG_ERR"
        super().__init__(message, error_code)


class ConfigManager:
    """
    Centralized configuration manager for the application.

    Handles loading, validation, and access to configuration settings
    from environment variables and configuration files.

    Attributes:
        config: Dictionary containing all configuration values
        config_path: Path to the configuration file if loaded from file
    """

    def __init__(self, config_path: Optional[Union[str, Path]] = None) -> None:
        """
        Initialize ConfigManager.

        Args:
            config_path: Optional path to configuration file

        Raises:
            ConfigurationError: If config_path is provided but invalid
        """
        self.config: ConfigDict = {}
        self.config_path: Optional[Path] = None

        if config_path is not None:
            self._load_config_file(config_path)

        self._load_environment_variables()

    def _load_config_file(self, config_path: Union[str, Path]) -> None:
        """
        Load configuration from a file.

        Args:
            config_path: Path to configuration file

        Raises:
            ConfigurationError: If file cannot be read or parsed
        """
        try:
            path = Path(config_path)
            if not path.exists():
                raise ConfigurationError(
                    f"Configuration file not found: {path}",
                    config_key=str(path)
                )

            self.config_path = path
            # Placeholder for actual config file parsing logic
            # In production, this would parse YAML/JSON/INI files
            self.config.update({"config_file_loaded": True})

        except PermissionError as e:
            raise ConfigurationError(
                f"Permission denied reading config file: {e}",
                config_key=str(config_path)
            ) from e
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load configuration file: {e}",
                config_key=str(config_path)
            ) from e

    def _load_environment_variables(self) -> None:
        """
        Load configuration from environment variables.

        Environment variables are loaded with 'APP_' prefix and
        converted to lowercase keys.
        """
        env_prefix = "APP_"
        for key, value in os.environ.items():
            if key.startswith(env_prefix):
                config_key = key[len(env_prefix):].lower()
                self.config[config_key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.

        Args:
            key: Configuration key to retrieve
            default: Default value if key not found

        Returns:
            Configuration value or default if not found
        """
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: Configuration key to set
            value: Value to assign

        Raises:
            ConfigurationError: If key is invalid
        """
        if not isinstance(key, str) or not key.strip():
            raise ConfigurationError(
                "Configuration key must be a non-empty string",
                config_key=str(key)
            )
        self.config[key.strip()] = value

    def validate(self, required_keys: list[str]) -> bool:
        """
        Validate that required configuration keys exist.

        Args:
            required_keys: List of required configuration keys

        Returns:
            True if all required keys are present

        Raises:
            ConfigurationError: If any required key is missing
        """
        missing_keys = [key for key in required_keys if key not in self.config]
        if missing_keys:
            raise ConfigurationError(
                f"Missing required configuration keys: {', '.join(missing_keys)}",
                config_key=", ".join(missing_keys)
            )
        return True

    def to_dict(self) -> ConfigDict:
        """
        Return a copy of the configuration dictionary.

        Returns:
            Dictionary containing all configuration values
        """
        return self.config.copy()


def setup_logging(
    level: Union[str, int] = logging.INFO,
    log_format: Optional[str] = None,
    log_file: Optional[Union[str, Path]] = None
) -> None:
    """
    Configure application-wide logging.

    Sets up logging with consistent formatting and optional file output.

    Args:
        level: Logging level (default: INFO)
        log_format: Custom log format string
        log_file: Optional path to log file

    Raises:
        LoggingError: If logging setup fails
    """
    try:
        # Default log format
        if log_format is None:
            log_format = (
                "%(asctime)s - %(name)s - %(levelname)s - "
                "%(filename)s:%(lineno)d - %(message)s"
            )

        # Convert string level to numeric if needed
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level)

        # Remove existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_formatter = logging.Formatter(log_format)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # Create file handler if log file specified
        if log_file is not None:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setLevel(level)
            file_formatter = logging.Formatter(log_format)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)

    except Exception as e:
        raise LoggingError(f"Failed to setup logging: {e}") from e


def get_logger(name: str) -> LoggerInstance:
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance

    Raises:
        LoggingError: If logger creation fails
    """
    try:
        if not name or not isinstance(name, str):
            raise LoggingError(
                "Logger name must be a non-empty string",
                logger_name=str(name)
            )
        return logging.getLogger(name)
    except Exception as e:
        raise LoggingError(
            f"Failed to create logger '{name}': {e}",
            logger_name=name
        ) from e


def validate_config(config: ConfigDict, schema: Dict[str, type]) -> bool:
    """
    Validate configuration against a schema.

    Args:
        config: Configuration dictionary to validate
        schema: Dictionary mapping keys to expected types

    Returns:
        True if configuration is valid

    Raises:
        ConfigurationError: If validation fails
    """
    try:
        for key, expected_type in schema.items():
            if key not in config:
                raise ConfigurationError(
                    f"Missing required config key: {key}",
                    config_key=key
                )

            value = config[key]
            if not isinstance(value, expected_type):
                raise ConfigurationError(
                    f"Config key '{key}' expected type {expected_type.__name__}, "
                    f"got {type(value).__name__}",
                    config_key=key
                )
        return True

    except ConfigurationError:
        raise
    except Exception as e:
        raise ConfigurationError(
            f"Configuration validation failed: {e}"
        ) from e


def get_core_version() -> str:
    """
    Get the current version of the core package.

    Returns:
        Version string in semantic versioning format
    """
    return __version__


# Initialize default logger for the core package
_logger = get_logger(__name__)

# Log package initialization
_logger.debug(
    "Core package initialized (version: %s)",
    __version__
)