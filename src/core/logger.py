"""
Core logging configuration module for the application.

Provides centralized logging setup with structured logging support,
rotation handlers, and configurable log levels.
"""

import json
import logging
import logging.config
import logging.handlers
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

from src.core.exceptions import ConfigurationError

# Default logging configuration
DEFAULT_LOG_FORMAT: str = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
)
DEFAULT_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S %Z"
DEFAULT_LOG_LEVEL: str = "INFO"
DEFAULT_LOG_DIR: str = "logs"
DEFAULT_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB
DEFAULT_BACKUP_COUNT: int = 5

# Structured logging format for JSON output
STRUCTURED_LOG_FORMAT: str = (
    '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
    '"logger": "%(name)s", "module": "%(filename)s", '
    '"line": %(lineno)d, "message": "%(message)s"}'
)


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs in structured JSON format.
    
    Supports additional context fields and exception serialization.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as a JSON string.
        
        Args:
            record: The log record to format.
            
        Returns:
            Formatted JSON string representation of the log record.
        """
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Add exception information if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "value": str(record.exc_info[1]),
                "traceback": "".join(
                    traceback.format_exception(*record.exc_info)
                ).strip(),
            }

        # Add extra fields from the record
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            log_entry.update(record.extra_fields)

        return json.dumps(log_entry, default=str)


class LoggerFactory:
    """
    Factory class for creating and configuring loggers.
    
    Provides centralized logger creation with consistent configuration
    across the application.
    """

    _initialized: bool = False
    _loggers: Dict[str, logging.Logger] = {}

    @classmethod
    def initialize(
        cls,
        log_level: Optional[str] = None,
        log_format: Optional[str] = None,
        log_dir: Optional[str] = None,
        structured: bool = False,
        console_output: bool = True,
        file_output: bool = True,
        max_bytes: int = DEFAULT_MAX_BYTES,
        backup_count: int = DEFAULT_BACKUP_COUNT,
    ) -> None:
        """
        Initialize the logging system with the specified configuration.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            log_format: Format string for log messages.
            log_dir: Directory for log files.
            structured: Whether to use structured JSON logging.
            console_output: Whether to output logs to console.
            file_output: Whether to output logs to file.
            max_bytes: Maximum size of log files before rotation.
            backup_count: Number of backup log files to keep.
            
        Raises:
            ConfigurationError: If initialization fails due to invalid configuration.
        """
        if cls._initialized:
            return

        try:
            # Set default values
            log_level = log_level or DEFAULT_LOG_LEVEL
            log_format = log_format or DEFAULT_LOG_FORMAT
            log_dir = log_dir or DEFAULT_LOG_DIR

            # Validate log level
            numeric_level: int = getattr(logging, log_level.upper(), None)
            if not isinstance(numeric_level, int):
                raise ConfigurationError(
                    f"Invalid log level: {log_level}. "
                    f"Valid levels: DEBUG, INFO, WARNING, ERROR, CRITICAL"
                )

            # Create log directory if needed
            if file_output:
                log_path: Path = Path(log_dir)
                log_path.mkdir(parents=True, exist_ok=True)

            # Configure root logger
            root_logger: logging.Logger = logging.getLogger()
            root_logger.setLevel(numeric_level)

            # Remove existing handlers
            root_logger.handlers.clear()

            # Create formatter
            if structured:
                formatter: logging.Formatter = StructuredFormatter()
            else:
                formatter = logging.Formatter(
                    fmt=log_format, datefmt=DEFAULT_DATE_FORMAT
                )

            # Add console handler
            if console_output:
                console_handler: logging.StreamHandler = logging.StreamHandler(sys.stdout)
                console_handler.setLevel(numeric_level)
                console_handler.setFormatter(formatter)
                root_logger.addHandler(console_handler)

            # Add file handler with rotation
            if file_output:
                file_handler: logging.handlers.RotatingFileHandler = (
                    logging.handlers.RotatingFileHandler(
                        filename=str(log_path / "application.log"),
                        maxBytes=max_bytes,
                        backupCount=backup_count,
                        encoding="utf-8",
                    )
                )
                file_handler.setLevel(numeric_level)
                file_handler.setFormatter(formatter)
                root_logger.addHandler(file_handler)

            # Add error-specific file handler
            if file_output:
                error_handler: logging.handlers.RotatingFileHandler = (
                    logging.handlers.RotatingFileHandler(
                        filename=str(log_path / "error.log"),
                        maxBytes=max_bytes,
                        backupCount=backup_count,
                        encoding="utf-8",
                    )
                )
                error_handler.setLevel(logging.ERROR)
                error_handler.setFormatter(formatter)
                root_logger.addHandler(error_handler)

            cls._initialized = True

        except Exception as e:
            raise ConfigurationError(
                f"Failed to initialize logging system: {str(e)}"
            ) from e

    @classmethod
    def get_logger(
        cls,
        name: str,
        log_level: Optional[str] = None,
    ) -> logging.Logger:
        """
        Get or create a logger with the specified name.
        
        Args:
            name: Name of the logger (typically __name__).
            log_level: Optional specific log level for this logger.
            
        Returns:
            Configured logger instance.
            
        Raises:
            ConfigurationError: If logging system is not initialized.
        """
        if not cls._initialized:
            raise ConfigurationError(
                "Logging system not initialized. Call LoggerFactory.initialize() first."
            )

        if name in cls._loggers:
            return cls._loggers[name]

        logger: logging.Logger = logging.getLogger(name)

        if log_level:
            numeric_level: int = getattr(logging, log_level.upper(), None)
            if isinstance(numeric_level, int):
                logger.setLevel(numeric_level)

        cls._loggers[name] = logger
        return logger

    @classmethod
    def reset(cls) -> None:
        """
        Reset the logging system to its initial state.
        
        Removes all handlers and clears the logger cache.
        """
        root_logger: logging.Logger = logging.getLogger()
        root_logger.handlers.clear()
        cls._loggers.clear()
        cls._initialized = False


def get_logger(
    name: str,
    log_level: Optional[str] = None,
) -> logging.Logger:
    """
    Convenience function to get a configured logger.
    
    Args:
        name: Name of the logger (typically __name__).
        log_level: Optional specific log level for this logger.
        
    Returns:
        Configured logger instance.
        
    Raises:
        ConfigurationError: If logging system is not initialized.
    """
    return LoggerFactory.get_logger(name, log_level)


def configure_logging(
    log_level: Optional[str] = None,
    log_format: Optional[str] = None,
    log_dir: Optional[str] = None,
    structured: bool = False,
    console_output: bool = True,
    file_output: bool = True,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> None:
    """
    Configure the logging system with the specified settings.
    
    This is the main entry point for configuring application logging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Format string for log messages.
        log_dir: Directory for log files.
        structured: Whether to use structured JSON logging.
        console_output: Whether to output logs to console.
        file_output: Whether to output logs to file.
        max_bytes: Maximum size of log files before rotation.
        backup_count: Number of backup log files to keep.
        
    Example:
        >>> configure_logging(log_level="DEBUG", structured=True)
        >>> logger = get_logger(__name__)
        >>> logger.info("Application started")
    """
    LoggerFactory.initialize(
        log_level=log_level,
        log_format=log_format,
        log_dir=log_dir,
        structured=structured,
        console_output=console_output,
        file_output=file_output,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )


def get_log_level_from_env() -> str:
    """
    Get log level from environment variable with fallback to default.
    
    Returns:
        Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    return os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()


def get_log_dir_from_env() -> str:
    """
    Get log directory from environment variable with fallback to default.
    
    Returns:
        Path string for log directory.
    """
    return os.environ.get("LOG_DIR", DEFAULT_LOG_DIR)


def is_structured_logging_enabled() -> bool:
    """
    Check if structured logging is enabled via environment variable.
    
    Returns:
        True if structured logging is enabled, False otherwise.
    """
    return os.environ.get("STRUCTURED_LOGGING", "false").lower() == "true"


# Initialize logging with environment-based configuration
def initialize_from_environment() -> None:
    """
    Initialize logging using environment variables.
    
    Reads LOG_LEVEL, LOG_DIR, and STRUCTURED_LOGGING environment variables
    to configure the logging system.
    """
    configure_logging(
        log_level=get_log_level_from_env(),
        log_dir=get_log_dir_from_env(),
        structured=is_structured_logging_enabled(),
    )


# Auto-initialize on import if not already initialized
if not LoggerFactory._initialized:
    try:
        initialize_from_environment()
    except ConfigurationError:
        # Fall back to basic configuration if environment-based init fails
        logging.basicConfig(
            level=getattr(logging, DEFAULT_LOG_LEVEL),
            format=DEFAULT_LOG_FORMAT,
            datefmt=DEFAULT_DATE_FORMAT,
        )