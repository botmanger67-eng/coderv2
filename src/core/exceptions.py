"""
Custom exception classes for the application.

This module defines a hierarchy of custom exceptions used throughout
the application to provide consistent error handling and reporting.
"""

from typing import Any, Dict, List, Optional, Tuple, Union


class ApplicationError(Exception):
    """
    Base exception for all application-specific errors.
    
    All custom exceptions should inherit from this class to ensure
    consistent error handling and logging capabilities.
    
    Attributes:
        message: Human-readable error description
        code: Optional error code for programmatic handling
        details: Optional dictionary with additional error context
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the ApplicationError.
        
        Args:
            message: Human-readable error description
            code: Optional error code for programmatic handling
            details: Optional dictionary with additional error context
        """
        self.message = message
        self.code = code or "APPLICATION_ERROR"
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the exception to a dictionary representation.
        
        Returns:
            Dictionary with error details suitable for serialization
        """
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "details": self.details
        }

    def __str__(self) -> str:
        """Return string representation of the error."""
        parts = [f"[{self.code}] {self.message}"]
        if self.details:
            parts.append(f"Details: {self.details}")
        return " | ".join(parts)


class ConfigurationError(ApplicationError):
    """
    Exception raised for configuration-related errors.
    
    This includes invalid configuration values, missing required
    configuration, or configuration file parsing errors.
    """

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the ConfigurationError.
        
        Args:
            message: Human-readable error description
            config_key: The configuration key that caused the error
            config_value: The invalid configuration value
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if config_key:
            error_details["config_key"] = config_key
        if config_value is not None:
            error_details["config_value"] = str(config_value)
        
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            details=error_details
        )
        self.config_key = config_key
        self.config_value = config_value


class ValidationError(ApplicationError):
    """
    Exception raised for data validation failures.
    
    This includes input validation, business rule validation,
    and data integrity validation errors.
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        constraints: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the ValidationError.
        
        Args:
            message: Human-readable error description
            field: The field that failed validation
            value: The invalid value
            constraints: Dictionary of validation constraints that were violated
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if field:
            error_details["field"] = field
        if value is not None:
            error_details["value"] = str(value)
        if constraints:
            error_details["constraints"] = constraints
        
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=error_details
        )
        self.field = field
        self.value = value
        self.constraints = constraints or {}


class AuthenticationError(ApplicationError):
    """
    Exception raised for authentication failures.
    
    This includes invalid credentials, expired tokens,
    and unauthorized access attempts.
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        user_id: Optional[str] = None,
        auth_method: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the AuthenticationError.
        
        Args:
            message: Human-readable error description
            user_id: The user ID that failed authentication
            auth_method: The authentication method used
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if user_id:
            error_details["user_id"] = user_id
        if auth_method:
            error_details["auth_method"] = auth_method
        
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            details=error_details
        )
        self.user_id = user_id
        self.auth_method = auth_method


class AuthorizationError(ApplicationError):
    """
    Exception raised for authorization failures.
    
    This includes insufficient permissions, role-based access
    control violations, and resource access restrictions.
    """

    def __init__(
        self,
        message: str = "Access denied",
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        required_permission: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the AuthorizationError.
        
        Args:
            message: Human-readable error description
            user_id: The user ID that was denied access
            resource: The resource that was being accessed
            required_permission: The permission required for access
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if user_id:
            error_details["user_id"] = user_id
        if resource:
            error_details["resource"] = resource
        if required_permission:
            error_details["required_permission"] = required_permission
        
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            details=error_details
        )
        self.user_id = user_id
        self.resource = resource
        self.required_permission = required_permission


class NotFoundError(ApplicationError):
    """
    Exception raised when a requested resource is not found.
    
    This includes database records, files, API endpoints,
    and other resources that cannot be located.
    """

    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: Optional[str] = None,
        resource_id: Optional[Union[str, int]] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the NotFoundError.
        
        Args:
            message: Human-readable error description
            resource_type: The type of resource that was not found
            resource_id: The identifier of the resource
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if resource_type:
            error_details["resource_type"] = resource_type
        if resource_id is not None:
            error_details["resource_id"] = str(resource_id)
        
        super().__init__(
            message=message,
            code="NOT_FOUND",
            details=error_details
        )
        self.resource_type = resource_type
        self.resource_id = resource_id


class ConflictError(ApplicationError):
    """
    Exception raised for resource conflicts.
    
    This includes duplicate entries, version conflicts,
    and state conflicts in concurrent operations.
    """

    def __init__(
        self,
        message: str = "Resource conflict",
        resource_type: Optional[str] = None,
        resource_id: Optional[Union[str, int]] = None,
        conflicting_value: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the ConflictError.
        
        Args:
            message: Human-readable error description
            resource_type: The type of resource involved in the conflict
            resource_id: The identifier of the resource
            conflicting_value: The value that caused the conflict
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if resource_type:
            error_details["resource_type"] = resource_type
        if resource_id is not None:
            error_details["resource_id"] = str(resource_id)
        if conflicting_value:
            error_details["conflicting_value"] = conflicting_value
        
        super().__init__(
            message=message,
            code="CONFLICT",
            details=error_details
        )
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.conflicting_value = conflicting_value


class RateLimitError(ApplicationError):
    """
    Exception raised when rate limits are exceeded.
    
    This includes API rate limits, request throttling,
    and resource usage limits.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        window: Optional[int] = None,
        retry_after: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the RateLimitError.
        
        Args:
            message: Human-readable error description
            limit: The maximum number of requests allowed
            window: The time window in seconds
            retry_after: Seconds until the rate limit resets
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if limit is not None:
            error_details["limit"] = limit
        if window is not None:
            error_details["window"] = window
        if retry_after is not None:
            error_details["retry_after"] = retry_after
        
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            details=error_details
        )
        self.limit = limit
        self.window = window
        self.retry_after = retry_after


class ServiceUnavailableError(ApplicationError):
    """
    Exception raised when a service is unavailable.
    
    This includes downstream service failures, maintenance mode,
    and temporary service disruptions.
    """

    def __init__(
        self,
        message: str = "Service unavailable",
        service_name: Optional[str] = None,
        retry_after: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the ServiceUnavailableError.
        
        Args:
            message: Human-readable error description
            service_name: The name of the unavailable service
            retry_after: Suggested seconds to wait before retrying
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if service_name:
            error_details["service_name"] = service_name
        if retry_after is not None:
            error_details["retry_after"] = retry_after
        
        super().__init__(
            message=message,
            code="SERVICE_UNAVAILABLE",
            details=error_details
        )
        self.service_name = service_name
        self.retry_after = retry_after


class ExternalServiceError(ApplicationError):
    """
    Exception raised for errors from external services.
    
    This includes API errors from third-party services,
    database connection errors, and external system failures.
    """

    def __init__(
        self,
        message: str = "External service error",
        service_name: Optional[str] = None,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the ExternalServiceError.
        
        Args:
            message: Human-readable error description
            service_name: The name of the external service
            status_code: HTTP status code from the external service
            response_body: Response body from the external service
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if service_name:
            error_details["service_name"] = service_name
        if status_code is not None:
            error_details["status_code"] = status_code
        if response_body:
            error_details["response_body"] = response_body
        
        super().__init__(
            message=message,
            code="EXTERNAL_SERVICE_ERROR",
            details=error_details
        )
        self.service_name = service_name
        self.status_code = status_code
        self.response_body = response_body


class DatabaseError(ApplicationError):
    """
    Exception raised for database-related errors.
    
    This includes connection failures, query errors,
    constraint violations, and transaction errors.
    """

    def __init__(
        self,
        message: str = "Database error",
        query: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        constraint: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the DatabaseError.
        
        Args:
            message: Human-readable error description
            query: The SQL query that caused the error
            parameters: Query parameters
            constraint: The database constraint that was violated
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if query:
            error_details["query"] = query
        if parameters:
            error_details["parameters"] = parameters
        if constraint:
            error_details["constraint"] = constraint
        
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            details=error_details
        )
        self.query = query
        self.parameters = parameters
        self.constraint = constraint


class DataIntegrityError(ApplicationError):
    """
    Exception raised for data integrity violations.
    
    This includes corrupted data, inconsistent state,
    and referential integrity violations.
    """

    def __init__(
        self,
        message: str = "Data integrity violation",
        entity_type: Optional[str] = None,
        entity_id: Optional[Union[str, int]] = None,
        integrity_rule: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the DataIntegrityError.
        
        Args:
            message: Human-readable error description
            entity_type: The type of entity with integrity issues
            entity_id: The identifier of the entity
            integrity_rule: The integrity rule that was violated
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if entity_type:
            error_details["entity_type"] = entity_type
        if entity_id is not None:
            error_details["entity_id"] = str(entity_id)
        if integrity_rule:
            error_details["integrity_rule"] = integrity_rule
        
        super().__init__(
            message=message,
            code="DATA_INTEGRITY_ERROR",
            details=error_details
        )
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.integrity_rule = integrity_rule


class TimeoutError(ApplicationError):
    """
    Exception raised for operation timeouts.
    
    This includes request timeouts, connection timeouts,
    and long-running operation timeouts.
    """

    def __init__(
        self,
        message: str = "Operation timed out",
        operation: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the TimeoutError.
        
        Args:
            message: Human-readable error description
            operation: The operation that timed out
            timeout_seconds: The timeout value in seconds
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        if timeout_seconds is not None:
            error_details["timeout_seconds"] = timeout_seconds
        
        super().__init__(
            message=message,
            code="TIMEOUT",
            details=error_details
        )
        self.operation = operation
        self.timeout_seconds = timeout_seconds


class FileOperationError(ApplicationError):
    """
    Exception raised for file operation failures.
    
    This includes file not found, permission denied,
    disk full, and file format errors.
    """

    def __init__(
        self,
        message: str = "File operation failed",
        file_path: Optional[str] = None,
        operation_type: Optional[str] = None,
        os_error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the FileOperationError.
        
        Args:
            message: Human-readable error description
            file_path: The path to the file involved
            operation_type: The type of operation (read, write, delete, etc.)
            os_error: The underlying operating system error
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if file_path:
            error_details["file_path"] = file_path
        if operation_type:
            error_details["operation_type"] = operation_type
        if os_error:
            error_details["os_error"] = os_error
        
        super().__init__(
            message=message,
            code="FILE_OPERATION_ERROR",
            details=error_details
        )
        self.file_path = file_path
        self.operation_type = operation_type
        self.os_error = os_error


class SerializationError(ApplicationError):
    """
    Exception raised for serialization/deserialization errors.
    
    This includes JSON parsing errors, format conversion failures,
    and encoding/decoding errors.
    """

    def __init__(
        self,
        message: str = "Serialization error",
        data_type: Optional[str] = None,
        target_format: Optional[str] = None,
        parse_error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the SerializationError.
        
        Args:
            message: Human-readable error description
            data_type: The type of data being serialized
            target_format: The target serialization format
            parse_error: The parsing error details
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if data_type:
            error_details["data_type"] = data_type
        if target_format:
            error_details["target_format"] = target_format
        if parse_error:
            error_details["parse_error"] = parse_error
        
        super().__init__(
            message=message,
            code="SERIALIZATION_ERROR",
            details=error_details
        )
        self.data_type = data_type
        self.target_format = target_format
        self.parse_error = parse_error


class BusinessRuleError(ApplicationError):
    """
    Exception raised for business rule violations.
    
    This includes domain-specific rule violations,
    workflow state errors, and business logic constraints.
    """

    def __init__(
        self,
        message: str = "Business rule violation",
        rule_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[Union[str, int]] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the BusinessRuleError.
        
        Args:
            message: Human-readable error description
            rule_name: The name of the violated business rule
            entity_type: The type of entity involved
            entity_id: The identifier of the entity
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if rule_name:
            error_details["rule_name"] = rule_name
        if entity_type:
            error_details["entity_type"] = entity_type
        if entity_id is not None:
            error_details["entity_id"] = str(entity_id)
        
        super().__init__(
            message=message,
            code="BUSINESS_RULE_ERROR",
            details=error_details
        )
        self.rule_name = rule_name
        self.entity_type = entity_type
        self.entity_id = entity_id


class DependencyError(ApplicationError):
    """
    Exception raised for dependency-related errors.
    
    This includes missing dependencies, version conflicts,
    and circular dependency detection.
    """

    def __init__(
        self,
        message: str = "Dependency error",
        dependency_name: Optional[str] = None,
        required_version: Optional[str] = None,
        current_version: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the DependencyError.
        
        Args:
            message: Human-readable error description
            dependency_name: The name of the dependency
            required_version: The required version of the dependency
            current_version: The current installed version
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if dependency_name:
            error_details["dependency_name"] = dependency_name
        if required_version:
            error_details["required_version"] = required_version
        if current_version:
            error_details["current_version"] = current_version
        
        super().__init__(
            message=message,
            code="DEPENDENCY_ERROR",
            details=error_details
        )
        self.dependency_name = dependency_name
        self.required_version = required_version
        self.current_version = current_version


class NotImplementedError(ApplicationError):
    """
    Exception raised for unimplemented features.
    
    This includes placeholder methods, incomplete implementations,
    and features planned for future releases.
    """

    def __init__(
        self,
        message: str = "Feature not implemented",
        feature_name: Optional[str] = None,
        component: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the NotImplementedError.
        
        Args:
            message: Human-readable error description
            feature_name: The name of the unimplemented feature
            component: The component where the feature is missing
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if feature_name:
            error_details["feature_name"] = feature_name
        if component:
            error_details["component"] = component
        
        super().__init__(
            message=message,
            code="NOT_IMPLEMENTED",
            details=error_details
        )
        self.feature_name = feature_name
        self.component = component


class ResourceExhaustedError(ApplicationError):
    """
    Exception raised when system resources are exhausted.
    
    This includes memory limits, connection pool exhaustion,
    disk space limits, and file descriptor limits.
    """

    def __init__(
        self,
        message: str = "Resource exhausted",
        resource_type: Optional[str] = None,
        limit: Optional[int] = None,
        current_usage: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the ResourceExhaustedError.
        
        Args:
            message: Human-readable error description
            resource_type: The type of resource that was exhausted
            limit: The maximum allowed value
            current_usage: The current usage value
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if resource_type:
            error_details["resource_type"] = resource_type
        if limit is not None:
            error_details["limit"] = limit
        if current_usage is not None:
            error_details["current_usage"] = current_usage
        
        super().__init__(
            message=message,
            code="RESOURCE_EXHAUSTED",
            details=error_details
        )
        self.resource_type = resource_type
        self.limit = limit
        self.current_usage = current_usage


class InvalidStateError(ApplicationError):
    """
    Exception raised for invalid state transitions.
    
    This includes state machine violations, invalid object states,
    and operation ordering errors.
    """

    def __init__(
        self,
        message: str = "Invalid state",
        current_state: Optional[str] = None,
        expected_state: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the InvalidStateError.
        
        Args:
            message: Human-readable error description
            current_state: The current state of the object/system
            expected_state: The expected state for the operation
            operation: The operation that was attempted
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if current_state:
            error_details["current_state"] = current_state
        if expected_state:
            error_details["expected_state"] = expected_state
        if operation:
            error_details["operation"] = operation
        
        super().__init__(
            message=message,
            code="INVALID_STATE",
            details=error_details
        )
        self.current_state = current_state
        self.expected_state = expected_state
        self.operation = operation


class VersionMismatchError(ApplicationError):
    """
    Exception raised for version compatibility issues.
    
    This includes API version mismatches, data format version
    conflicts, and protocol version incompatibilities.
    """

    def __init__(
        self,
        message: str = "Version mismatch",
        expected_version: Optional[str] = None,
        actual_version: Optional[str] = None,
        component: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the VersionMismatchError.
        
        Args:
            message: Human-readable error description
            expected_version: The expected version
            actual_version: The actual version found
            component: The component with version mismatch
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if expected_version:
            error_details["expected_version"] = expected_version
        if actual_version:
            error_details["actual_version"] = actual_version
        if component:
            error_details["component"] = component
        
        super().__init__(
            message=message,
            code="VERSION_MISMATCH",
            details=error_details
        )
        self.expected_version = expected_version
        self.actual_version = actual_version
        self.component = component


class QuotaExceededError(ApplicationError):
    """
    Exception raised when usage quotas are exceeded.
    
    This includes storage quotas, API call quotas,
    and resource allocation limits.
    """

    def __init__(
        self,
        message: str = "Quota exceeded",
        quota_type: Optional[str] = None,
        limit: Optional[int] = None,
        usage: Optional[int] = None,
        reset_time: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the QuotaExceededError.
        
        Args:
            message: Human-readable error description
            quota_type: The type of quota that was exceeded
            limit: The quota limit
            usage: The current usage
            reset_time: When the quota resets
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if quota_type:
            error_details["quota_type"] = quota_type
        if limit is not None:
            error_details["limit"] = limit
        if usage is not None:
            error_details["usage"] = usage
        if reset_time:
            error_details["reset_time"] = reset_time
        
        super().__init__(
            message=message,
            code="QUOTA_EXCEEDED",
            details=error_details
        )
        self.quota_type = quota_type
        self.limit = limit
        self.usage = usage
        self.reset_time = reset_time


class CircuitBreakerError(ApplicationError):
    """
    Exception raised when a circuit breaker is open.
    
    This indicates that a downstream service is failing
    and requests are being blocked to prevent cascading failures.
    """

    def __init__(
        self,
        message: str = "Circuit breaker is open",
        service_name: Optional[str] = None,
        failure_count: Optional[int] = None,
        retry_after: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the CircuitBreakerError.
        
        Args:
            message: Human-readable error description
            service_name: The name of the protected service
            failure_count: The number of consecutive failures
            retry_after: Seconds until the circuit breaker allows retries
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if service_name:
            error_details["service_name"] = service_name
        if failure_count is not None:
            error_details["failure_count"] = failure_count
        if retry_after is not None:
            error_details["retry_after"] = retry_after
        
        super().__init__(
            message=message,
            code="CIRCUIT_BREAKER_OPEN",
            details=error_details
        )
        self.service_name = service_name
        self.failure_count = failure_count
        self.retry_after = retry_after


class RetryableError(ApplicationError):
    """
    Exception raised for errors that can be retried.
    
    This wraps other exceptions to indicate that the operation
    might succeed if retried after a brief delay.
    """

    def __init__(
        self,
        message: str = "Retryable error occurred",
        original_exception: Optional[Exception] = None,
        retry_after: Optional[float] = None,
        max_retries: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the RetryableError.
        
        Args:
            message: Human-readable error description
            original_exception: The original exception that caused this error
            retry_after: Suggested seconds to wait before retrying
            max_retries: Maximum number of retries allowed
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if original_exception:
            error_details["original_exception_type"] = type(original_exception).__name__
            error_details["original_exception_message"] = str(original_exception)
        if retry_after is not None:
            error_details["retry_after"] = retry_after
        if max_retries is not None:
            error_details["max_retries"] = max_retries
        
        super().__init__(
            message=message,
            code="RETRYABLE_ERROR",
            details=error_details
        )
        self.original_exception = original_exception
        self.retry_after = retry_after
        self.max_retries = max_retries


class NonRetryableError(ApplicationError):
    """
    Exception raised for errors that should not be retried.
    
    This wraps other exceptions to indicate that retrying
    the operation would be futile.
    """

    def __init__(
        self,
        message: str = "Non-retryable error occurred",
        original_exception: Optional[Exception] = None,
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the NonRetryableError.
        
        Args:
            message: Human-readable error description
            original_exception: The original exception that caused this error
            reason: The reason why the operation should not be retried
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if original_exception:
            error_details["original_exception_type"] = type(original_exception).__name__
            error_details["original_exception_message"] = str(original_exception)
        if reason:
            error_details["reason"] = reason
        
        super().__init__(
            message=message,
            code="NON_RETRYABLE_ERROR",
            details=error_details
        )
        self.original_exception = original_exception
        self.reason = reason


class ErrorHandler:
    """
    Utility class for handling and categorizing exceptions.
    
    Provides methods to classify exceptions and determine
    appropriate error responses.
    """

    @staticmethod
    def is_client_error(error: Exception) -> bool:
        """
        Check if the error is a client-side error (4xx).
        
        Args:
            error: The exception to check
            
        Returns:
            True if the error is a client error
        """
        return isinstance(
            error,
            (
                ValidationError,
                AuthenticationError,
                AuthorizationError,
                NotFoundError,
                ConflictError,
                RateLimitError,
                QuotaExceededError,
                BusinessRuleError,
                InvalidStateError,
                VersionMismatchError
            )
        )

    @staticmethod
    def is_server_error(error: Exception) -> bool:
        """
        Check if the error is a server-side error (5xx).
        
        Args:
            error: The exception to check
            
        Returns:
            True if the error is a server error
        """
        return isinstance(
            error,
            (
                ServiceUnavailableError,
                ExternalServiceError,
                DatabaseError,
                DataIntegrityError,
                TimeoutError,
                FileOperationError,
                SerializationError,
                DependencyError,
                ResourceExhaustedError,
                CircuitBreakerError
            )
        )

    @staticmethod
    def is_retryable(error: Exception) -> bool:
        """
        Check if the error is retryable.
        
        Args:
            error: The exception to check
            
        Returns:
            True if the error can be retried
        """
        if isinstance(error, RetryableError):
            return True
        if isinstance(error, NonRetryableError):
            return False
        return isinstance(
            error,
            (
                ServiceUnavailableError,
                TimeoutError,
                RateLimitError,
                CircuitBreakerError,
                ResourceExhaustedError
            )
        )

    @staticmethod
    def get_http_status_code(error: Exception) -> int:
        """
        Get the appropriate HTTP status code for an exception.
        
        Args:
            error: The exception to get the status code for
            
        Returns:
            HTTP status code
        """
        status_code_map: Dict[type, int] = {
            ValidationError: 400,
            AuthenticationError: 401,
            AuthorizationError: 403,
            NotFoundError: 404,
            ConflictError: 409,
            RateLimitError: 429,
            QuotaExceededError: 429,
            ServiceUnavailableError: 503,
            ExternalServiceError: 502,
            DatabaseError: 500,
            DataIntegrityError: 500,
            TimeoutError: 504,
            FileOperationError: 500,
            SerializationError: 500,
            DependencyError: 500,
            ResourceExhaustedError: 503,
            InvalidStateError: 409,
            VersionMismatchError: 409,
            BusinessRuleError: 422,
            CircuitBreakerError: 503,
            NotImplementedError: 501,
            ConfigurationError: 500,
            RetryableError: 500,
            NonRetryableError: 500
        }
        
        for exception_type, status_code in status_code_map.items():
            if isinstance(error, exception_type):
                return status_code
        
        return 500

    @staticmethod
    def format_error_response(error: Exception) -> Dict[str, Any]:
        """
        Format an exception into a standardized error response.
        
        Args:
            error: The exception to format
            
        Returns:
            Dictionary with standardized error response format
        """
        if isinstance(error, ApplicationError):
            return error.to_dict()
        
        return {
            "error": type(error).__name__,
            "message": str(error),
            "code": "UNEXPECTED_ERROR",
            "details": {}
        }