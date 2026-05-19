"""
Services package initialization.

This module provides the core service layer for the application,
implementing business logic, data processing, and external integrations.
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum, auto
import logging
from pathlib import Path
import json
import yaml
from datetime import datetime, timezone

# Configure module logger
logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Enumeration of possible service statuses."""
    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    ERROR = auto()
    SHUTDOWN = auto()


@dataclass
class ServiceConfig:
    """Configuration dataclass for service initialization.
    
    Attributes:
        name: Service identifier name
        version: Service version string
        debug: Enable debug mode
        max_retries: Maximum retry attempts for operations
        timeout_seconds: Default timeout for operations
        config_path: Path to configuration file
        environment: Deployment environment name
    """
    name: str = "default-service"
    version: str = "1.0.0"
    debug: bool = False
    max_retries: int = 3
    timeout_seconds: int = 30
    config_path: Optional[Path] = None
    environment: str = "development"


@dataclass
class ServiceMetrics:
    """Metrics tracking for service operations.
    
    Attributes:
        start_time: Service start timestamp
        request_count: Total requests processed
        error_count: Total errors encountered
        last_activity: Last activity timestamp
        active_connections: Current active connections
    """
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    request_count: int = 0
    error_count: int = 0
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active_connections: int = 0


class ServiceError(Exception):
    """Base exception for service layer errors."""
    
    def __init__(
        self,
        message: str,
        service_name: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize ServiceError.
        
        Args:
            message: Human-readable error description
            service_name: Name of the service that raised the error
            error_code: Optional error code for categorization
            details: Optional dictionary with additional error context
        """
        self.message = message
        self.service_name = service_name
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc)
        
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """Format error message with context.
        
        Returns:
            Formatted error string
        """
        base = f"[{self.service_name}] {self.message}"
        if self.error_code:
            base = f"[{self.error_code}] {base}"
        if self.details:
            base = f"{base} | Details: {json.dumps(self.details, default=str)}"
        return base
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation.
        
        Returns:
            Dictionary with error details
        """
        return {
            "error_code": self.error_code,
            "message": self.message,
            "service_name": self.service_name,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }


class ServiceInitializationError(ServiceError):
    """Exception raised when service initialization fails."""
    
    def __init__(
        self,
        message: str,
        service_name: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize ServiceInitializationError.
        
        Args:
            message: Error description
            service_name: Name of the service
            details: Additional error context
        """
        super().__init__(
            message=message,
            service_name=service_name,
            error_code="INIT_ERROR",
            details=details
        )


class ServiceTimeoutError(ServiceError):
    """Exception raised when service operation times out."""
    
    def __init__(
        self,
        message: str,
        service_name: str,
        timeout_seconds: float,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize ServiceTimeoutError.
        
        Args:
            message: Error description
            service_name: Name of the service
            timeout_seconds: Timeout duration that was exceeded
            details: Additional error context
        """
        super().__init__(
            message=message,
            service_name=service_name,
            error_code="TIMEOUT_ERROR",
            details={
                "timeout_seconds": timeout_seconds,
                **(details or {})
            }
        )


class BaseService:
    """Base class for all services in the application.
    
    Provides common functionality for service lifecycle management,
    configuration handling, and metrics tracking.
    """
    
    def __init__(
        self,
        config: Optional[ServiceConfig] = None,
        service_name: Optional[str] = None
    ) -> None:
        """Initialize BaseService.
        
        Args:
            config: Service configuration object
            service_name: Override service name from config
        
        Raises:
            ServiceInitializationError: If initialization fails
        """
        try:
            self.config = config or ServiceConfig()
            self.service_name = service_name or self.config.name
            self.status = ServiceStatus.INITIALIZING
            self.metrics = ServiceMetrics()
            self._initialized = False
            
            logger.info(
                f"Initializing service: {self.service_name} "
                f"(version: {self.config.version})"
            )
            
            self._load_configuration()
            self._validate_configuration()
            
            self.status = ServiceStatus.READY
            self._initialized = True
            
            logger.info(f"Service {self.service_name} initialized successfully")
            
        except Exception as e:
            self.status = ServiceStatus.ERROR
            error_msg = f"Failed to initialize service {self.service_name}: {str(e)}"
            logger.error(error_msg)
            raise ServiceInitializationError(
                message=error_msg,
                service_name=self.service_name,
                details={"original_error": str(e)}
            ) from e
    
    def _load_configuration(self) -> None:
        """Load configuration from file if specified.
        
        Raises:
            ServiceInitializationError: If configuration loading fails
        """
        if not self.config.config_path:
            return
        
        config_path = self.config.config_path
        if not config_path.exists():
            logger.warning(f"Configuration file not found: {config_path}")
            return
        
        try:
            with open(config_path, 'r') as f:
                if config_path.suffix in ['.yaml', '.yml']:
                    file_config = yaml.safe_load(f)
                elif config_path.suffix == '.json':
                    file_config = json.load(f)
                else:
                    raise ValueError(f"Unsupported config format: {config_path.suffix}")
            
            if file_config and isinstance(file_config, dict):
                for key, value in file_config.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
                        
            logger.debug(f"Configuration loaded from {config_path}")
            
        except Exception as e:
            raise ServiceInitializationError(
                message=f"Failed to load configuration from {config_path}",
                service_name=self.service_name,
                details={"error": str(e)}
            ) from e
    
    def _validate_configuration(self) -> None:
        """Validate service configuration.
        
        Raises:
            ServiceInitializationError: If configuration is invalid
        """
        if not self.config.name:
            raise ServiceInitializationError(
                message="Service name cannot be empty",
                service_name=self.service_name
            )
        
        if self.config.max_retries < 0:
            raise ServiceInitializationError(
                message="max_retries must be non-negative",
                service_name=self.service_name,
                details={"max_retries": self.config.max_retries}
            )
        
        if self.config.timeout_seconds <= 0:
            raise ServiceInitializationError(
                message="timeout_seconds must be positive",
                service_name=self.service_name,
                details={"timeout_seconds": self.config.timeout_seconds}
            )
    
    def update_metrics(self, error: bool = False) -> None:
        """Update service metrics.
        
        Args:
            error: Whether the operation resulted in an error
        """
        self.metrics.request_count += 1
        if error:
            self.metrics.error_count += 1
        self.metrics.last_activity = datetime.now(timezone.utc)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of service metrics.
        
        Returns:
            Dictionary with metrics summary
        """
        uptime = datetime.now(timezone.utc) - self.metrics.start_time
        return {
            "service_name": self.service_name,
            "status": self.status.name,
            "uptime_seconds": uptime.total_seconds(),
            "request_count": self.metrics.request_count,
            "error_count": self.metrics.error_count,
            "error_rate": (
                self.metrics.error_count / self.metrics.request_count
                if self.metrics.request_count > 0
                else 0.0
            ),
            "active_connections": self.metrics.active_connections,
            "last_activity": self.metrics.last_activity.isoformat()
        }
    
    def shutdown(self) -> None:
        """Gracefully shutdown the service.
        
        Raises:
            ServiceError: If shutdown fails
        """
        try:
            self.status = ServiceStatus.SHUTDOWN
            logger.info(f"Service {self.service_name} shutting down")
            self._cleanup()
            logger.info(f"Service {self.service_name} shutdown complete")
        except Exception as e:
            error_msg = f"Error during service shutdown: {str(e)}"
            logger.error(error_msg)
            raise ServiceError(
                message=error_msg,
                service_name=self.service_name,
                error_code="SHUTDOWN_ERROR"
            ) from e
    
    def _cleanup(self) -> None:
        """Perform cleanup operations. Override in subclasses."""
        pass
    
    def __enter__(self) -> 'BaseService':
        """Context manager entry."""
        return self
    
    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[object]
    ) -> None:
        """Context manager exit with cleanup."""
        self.shutdown()


# Package-level exports
__all__ = [
    'ServiceStatus',
    'ServiceConfig',
    'ServiceMetrics',
    'ServiceError',
    'ServiceInitializationError',
    'ServiceTimeoutError',
    'BaseService',
]

# Package metadata
__version__ = "1.0.0"
__author__ = "Enterprise Services Team"
__description__ = "Core service layer for enterprise application"