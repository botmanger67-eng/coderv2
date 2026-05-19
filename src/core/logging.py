"""
Core logging module for the application.

Provides centralized logging configuration and utilities for consistent
log management across the entire application. Supports structured logging,
log rotation, and multiple output destinations.
"""

import json
import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union
from uuid import uuid4

# Default log format with structured fields
DEFAULT_LOG_FORMAT: str = (
    "%(asctime)s | %(levelname)-8s | %(correlation_id)s | "
    "%(name)s:%(funcName)s:%(lineno)d | %(message)s"
)

# JSON format for structured logging
JSON_LOG_FORMAT: str = (
    '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
    '"correlation_id": "%(correlation_id)s", '
    '"logger": "%(name)s", "function": "%(funcName)s", '
    '"line": %(lineno)d, "message": "%(message)s"}'
)

# Default log levels
DEFAULT_LOG_LEVEL: str = "INFO"
DEFAULT_FILE_LOG_LEVEL: str = "DEBUG"
DEFAULT_CONSOLE_LOG_LEVEL: str = "INFO"

# Log rotation settings
MAX_LOG_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB
MAX_LOG_FILE_COUNT: int = 5
LOG_FILE_ENCODING: str = "utf-8"


class CorrelationIdFilter(logging.Filter):
    """
    Custom logging filter that adds a correlation ID to log records.

    The correlation ID helps trace requests across distributed systems
    and can be set per-thread or per-request context.
    """

    def __init__(self, correlation_id: Optional[str] = None) -> None:
        """
        Initialize the correlation ID filter.

        Args:
            correlation_id: Optional correlation ID. If not provided,
                          a new UUID will be generated.
        """
        super().__init__()
        self._correlation_id: str = correlation_id or str(uuid4())

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add correlation ID to the log record.

        Args:
            record: The log record to modify.

        Returns:
            True to include the record in the log output.
        """
        record.correlation_id = self._correlation_id
        return True


class SensitiveDataFilter(logging.Filter):
    """
    Filter that masks sensitive data in log messages.

    Masks common sensitive fields like passwords, tokens, and credit card
    numbers to prevent accidental exposure in logs.
    """

    SENSITIVE_PATTERNS: Dict[str, str] = {
        "password": "***MASKED***",
        "secret": "***MASKED***",
        "token": "***MASKED***",
        "api_key": "***MASKED***",
        "credit_card": "***MASKED***",
        "ssn": "***MASKED***",
    }

    def __init__(self, additional_patterns: Optional[Dict[str, str]] = None) -> None:
        """
        Initialize the sensitive data filter.

        Args:
            additional_patterns: Additional patterns to mask.
        """
        super().__init__()
        self._patterns: Dict[str, str] = {
            **self.SENSITIVE_PATTERNS,
            **(additional_patterns or {}),
        }

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Mask sensitive data in the log message.

        Args:
            record: The log record to process.

        Returns:
            True to include the record in the log output.
        """
        if isinstance(record.msg, str):
            for pattern, replacement in self._patterns.items():
                if pattern.lower() in record.msg.lower():
                    record.msg = record.msg.replace(pattern, replacement)
                    record.msg = record.msg.replace(pattern.upper(), replacement)
                    record.msg = record.msg.replace(pattern.capitalize(), replacement)
        return True


class StructuredLogFormatter(logging.Formatter):
    """
    Custom formatter that supports structured logging in JSON format.

    Provides additional context fields and handles exception formatting
    for structured log output.
    """

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        style: str = "%",
        use_json: bool = False,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize the structured log formatter.

        Args:
            fmt: Log format string.
            datefmt: Date format string.
            style: Format style ('%', '{', '$').
            use_json: Whether to output logs in JSON format.
            extra_fields: Additional fields to include in all log records.
        """
        super().__init__(fmt, datefmt, style)
        self._use_json: bool = use_json
        self._extra_fields: Dict[str, Any] = extra_fields or {}

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record with additional context.

        Args:
            record: The log record to format.

        Returns:
            Formatted log string.
        """
        # Add extra fields to the record
        for key, value in self._extra_fields.items():
            if not hasattr(record, key):
                setattr(record, key, value)

        # Add exception info if present
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)

        if self._use_json:
            return self._format_json(record)
        return super().format(record)

    def _format_json(self, record: logging.LogRecord) -> str:
        """
        Format the log record as JSON.

        Args:
            record: The log record to format.

        Returns:
            JSON-formatted log string.
        """
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None),
        }

        # Add exception info if present
        if record.exc_text:
            log_data["exception"] = record.exc_text

        # Add extra fields
        for key, value in self._extra_fields.items():
            log_data[key] = value

        return json.dumps(log_data, default=str)


class LoggerManager:
    """
    Centralized logger manager for the application.

    Handles logger creation, configuration, and lifecycle management.
    Provides factory methods for creating configured loggers.
    """

    _instance: Optional["LoggerManager"] = None
    _initialized: bool = False

    def __new__(cls) -> "LoggerManager":
        """
        Create or return the singleton instance.

        Returns:
            The singleton LoggerManager instance.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the logger manager if not already initialized."""
        if not self._initialized:
            self._loggers: Dict[str, logging.Logger] = {}
            self._handlers: Dict[str, logging.Handler] = {}
            self._default_config: Dict[str, Any] = {
                "level": DEFAULT_LOG_LEVEL,
                "format": DEFAULT_LOG_FORMAT,
                "date_format": "%Y-%m-%d %H:%M:%S",
                "use_json": False,
            }
            self._initialized = True

    def configure(
        self,
        log_level: Optional[str] = None,
        log_format: Optional[str] = None,
        date_format: Optional[str] = None,
        use_json: bool = False,
        log_file: Optional[Union[str, Path]] = None,
        console_output: bool = True,
        correlation_id: Optional[str] = None,
        sensitive_data_filter: bool = True,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Configure the logging system.

        Args:
            log_level: Global log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            log_format: Log format string.
            date_format: Date format string.
            use_json: Whether to use JSON format for logs.
            log_file: Path to log file for file output.
            console_output: Whether to output logs to console.
            correlation_id: Correlation ID for request tracing.
            sensitive_data_filter: Whether to enable sensitive data masking.
            extra_fields: Additional fields to include in all log records.

        Raises:
            ValueError: If invalid log level is provided.
            OSError: If log file cannot be created.
        """
        # Validate log level
        if log_level:
            log_level = log_level.upper()
            if log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                raise ValueError(f"Invalid log level: {log_level}")

        # Update default configuration
        self._default_config.update({
            "level": log_level or DEFAULT_LOG_LEVEL,
            "format": log_format or DEFAULT_LOG_FORMAT,
            "date_format": date_format or "%Y-%m-%d %H:%M:%S",
            "use_json": use_json,
        })

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self._default_config["level"]))

        # Remove existing handlers
        root_logger.handlers.clear()

        # Create formatter
        formatter = StructuredLogFormatter(
            fmt=self._default_config["format"],
            datefmt=self._default_config["date_format"],
            use_json=use_json,
            extra_fields=extra_fields,
        )

        # Add console handler
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, DEFAULT_CONSOLE_LOG_LEVEL))
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
            self._handlers["console"] = console_handler

        # Add file handler
        if log_file:
            try:
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)

                file_handler = logging.handlers.RotatingFileHandler(
                    filename=str(log_path),
                    maxBytes=MAX_LOG_FILE_SIZE,
                    backupCount=MAX_LOG_FILE_COUNT,
                    encoding=LOG_FILE_ENCODING,
                )
                file_handler.setLevel(getattr(logging, DEFAULT_FILE_LOG_LEVEL))
                file_handler.setFormatter(formatter)
                root_logger.addHandler(file_handler)
                self._handlers["file"] = file_handler
            except OSError as e:
                raise OSError(f"Failed to create log file {log_file}: {e}")

        # Add correlation ID filter
        if correlation_id:
            correlation_filter = CorrelationIdFilter(correlation_id)
            root_logger.addFilter(correlation_filter)

        # Add sensitive data filter
        if sensitive_data_filter:
            sensitive_filter = SensitiveDataFilter()
            root_logger.addFilter(sensitive_filter)

    def get_logger(
        self,
        name: str,
        level: Optional[str] = None,
        propagate: bool = True,
    ) -> logging.Logger:
        """
        Get or create a configured logger.

        Args:
            name: Logger name (typically __name__).
            level: Logger-specific log level.
            propagate: Whether to propagate messages to parent loggers.

        Returns:
            Configured logger instance.
        """
        if name in self._loggers:
            return self._loggers[name]

        logger = logging.getLogger(name)

        if level:
            logger.setLevel(getattr(logging, level.upper()))

        logger.propagate = propagate
        self._loggers[name] = logger
        return logger

    def add_handler(
        self,
        handler: logging.Handler,
        handler_name: str,
        level: Optional[str] = None,
    ) -> None:
        """
        Add a custom handler to the root logger.

        Args:
            handler: The handler to add.
            handler_name: Unique name for the handler.
            level: Handler-specific log level.

        Raises:
            ValueError: If handler name already exists.
        """
        if handler_name in self._handlers:
            raise ValueError(f"Handler '{handler_name}' already exists")

        if level:
            handler.setLevel(getattr(logging, level.upper()))

        logging.getLogger().addHandler(handler)
        self._handlers[handler_name] = handler

    def remove_handler(self, handler_name: str) -> None:
        """
        Remove a handler from the root logger.

        Args:
            handler_name: Name of the handler to remove.

        Raises:
            KeyError: If handler name does not exist.
        """
        if handler_name not in self._handlers:
            raise KeyError(f"Handler '{handler_name}' not found")

        handler = self._handlers.pop(handler_name)
        logging.getLogger().removeHandler(handler)
        handler.close()

    def set_level(self, level: str) -> None:
        """
        Set the global log level.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).

        Raises:
            ValueError: If invalid log level is provided.
        """
        level = level.upper()
        if level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError(f"Invalid log level: {level}")

        logging.getLogger().setLevel(getattr(logging, level))
        self._default_config["level"] = level

    def shutdown(self) -> None:
        """Shutdown the logging system and release resources."""
        logging.shutdown()
        self._loggers.clear()
        self._handlers.clear()
        self._initialized = False


# Global logger manager instance
logger_manager = LoggerManager()


def get_logger(
    name: str,
    level: Optional[str] = None,
    propagate: bool = True,
) -> logging.Logger:
    """
    Convenience function to get a configured logger.

    Args:
        name: Logger name (typically __name__).
        level: Logger-specific log level.
        propagate: Whether to propagate messages to parent loggers.

    Returns:
        Configured logger instance.
    """
    return logger_manager.get_logger(name, level, propagate)


def configure_logging(
    log_level: Optional[str] = None,
    log_format: Optional[str] = None,
    date_format: Optional[str] = None,
    use_json: bool = False,
    log_file: Optional[Union[str, Path]] = None,
    console_output: bool = True,
    correlation_id: Optional[str] = None,
    sensitive_data_filter: bool = True,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Convenience function to configure the logging system.

    Args:
        log_level: Global log level.
        log_format: Log format string.
        date_format: Date format string.
        use_json: Whether to use JSON format.
        log_file: Path to log file.
        console_output: Whether to output to console.
        correlation_id: Correlation ID for request tracing.
        sensitive_data_filter: Whether to enable sensitive data masking.
        extra_fields: Additional fields to include in all log records.
    """
    logger_manager.configure(
        log_level=log_level,
        log_format=log_format,
        date_format=date_format,
        use_json=use_json,
        log_file=log_file,
        console_output=console_output,
        correlation_id=correlation_id,
        sensitive_data_filter=sensitive_data_filter,
        extra_fields=extra_fields,
    )


def log_exception(
    logger: logging.Logger,
    exception: Exception,
    message: str = "An error occurred",
    level: str = "ERROR",
    include_traceback: bool = True,
) -> None:
    """
    Log an exception with consistent formatting.

    Args:
        logger: Logger instance to use.
        exception: The exception to log.
        message: Custom message to include.
        level: Log level for the message.
        include_traceback: Whether to include traceback in the log.
    """
    log_method = getattr(logger, level.lower(), logger.error)

    if include_traceback:
        tb = traceback.format_exc()
        log_method(f"{message}: {str(exception)}\nTraceback:\n{tb}")
    else:
        log_method(f"{message}: {str(exception)}")


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> None:
    """
    Log a message with additional context.

    Args:
        logger: Logger instance to use.
        level: Log level for the message.
        message: The message to log.
        context: Additional context dictionary.
        **kwargs: Additional keyword arguments to include.
    """
    log_method = getattr(logger, level.lower(), logger.info)

    if context or kwargs:
        context_data = {**(context or {}), **kwargs}
        context_str = " | ".join(
            f"{k}={v}" for k, v in context_data.items()
        )
        log_method(f"{message} | {context_str}")
    else:
        log_method(message)


# Initialize default logging configuration
configure_logging()

__all__ = [
    "LoggerManager",
    "CorrelationIdFilter",
    "SensitiveDataFilter",
    "StructuredLogFormatter",
    "logger_manager",
    "get_logger",
    "configure_logging",
    "log_exception",
    "log_with_context",
]