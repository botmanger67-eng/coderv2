"""
Configuration management module for the application.

This module provides a centralized configuration management system that loads
configuration from environment variables, configuration files, and provides
type-safe access to configuration values with validation and error handling.
"""

import os
import json
import yaml
from typing import Any, Dict, Optional, Union, List, TypeVar, Generic, cast
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field, asdict
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ConfigError(Exception):
    """Base exception for configuration errors."""
    pass


class ConfigNotFoundError(ConfigError):
    """Raised when a configuration key is not found."""
    pass


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails."""
    pass


class ConfigTypeError(ConfigError):
    """Raised when configuration value type is incorrect."""
    pass


class Environment(Enum):
    """Application environment enumeration."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    host: str = "localhost"
    port: int = 5432
    database: str = "app_db"
    username: str = "app_user"
    password: str = ""
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False
    ssl_mode: str = "prefer"
    connection_uri: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate database configuration after initialization."""
        if self.port < 1 or self.port > 65535:
            raise ConfigValidationError(f"Invalid port number: {self.port}")
        if self.pool_size < 1:
            raise ConfigValidationError(f"Invalid pool size: {self.pool_size}")
        if self.max_overflow < 0:
            raise ConfigValidationError(f"Invalid max overflow: {self.max_overflow}")


@dataclass
class RedisConfig:
    """Redis configuration settings."""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    retry_on_timeout: bool = True
    max_connections: int = 10
    ssl: bool = False
    connection_uri: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate Redis configuration after initialization."""
        if self.port < 1 or self.port > 65535:
            raise ConfigValidationError(f"Invalid Redis port: {self.port}")
        if self.db < 0 or self.db > 15:
            raise ConfigValidationError(f"Invalid Redis database: {self.db}")


@dataclass
class LoggingConfig:
    """Logging configuration settings."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10 MB
    backup_count: int = 5
    json_format: bool = False
    sensitive_fields: List[str] = field(default_factory=lambda: ["password", "secret", "token", "key"])


@dataclass
class SecurityConfig:
    """Security configuration settings."""
    secret_key: str = ""
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30
    jwt_refresh_expiration_days: int = 7
    bcrypt_rounds: int = 12
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    allowed_hosts: List[str] = field(default_factory=lambda: ["*"])
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60


@dataclass
class AppConfig:
    """Main application configuration."""
    app_name: str = "FastAPI Application"
    version: str = "1.0.0"
    debug: bool = False
    environment: Environment = Environment.DEVELOPMENT
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    reload: bool = False
    api_prefix: str = "/api/v1"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate application configuration after initialization."""
        if self.port < 1 or self.port > 65535:
            raise ConfigValidationError(f"Invalid application port: {self.port}")
        if self.workers < 1:
            raise ConfigValidationError(f"Invalid workers count: {self.workers}")
        if not self.app_name:
            raise ConfigValidationError("Application name cannot be empty")


class ConfigManager:
    """
    Configuration manager that handles loading, caching, and accessing configuration.
    
    This class provides a centralized way to manage application configuration,
    supporting multiple configuration sources with proper error handling and
    type safety.
    """

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        env_prefix: str = "APP_",
        auto_load: bool = True
    ) -> None:
        """
        Initialize the configuration manager.

        Args:
            config_path: Path to configuration file (YAML or JSON)
            env_prefix: Prefix for environment variables
            auto_load: Whether to automatically load configuration on initialization

        Raises:
            ConfigError: If configuration loading fails
        """
        self._config_path: Optional[Path] = Path(config_path) if config_path else None
        self._env_prefix: str = env_prefix
        self._config: Optional[AppConfig] = None
        self._raw_config: Dict[str, Any] = {}
        
        if auto_load:
            self.load()

    def load(self) -> None:
        """
        Load configuration from all available sources.

        Configuration sources are loaded in order (later sources override earlier ones):
        1. Default values
        2. Configuration file (if provided)
        3. Environment variables

        Raises:
            ConfigError: If configuration loading fails
        """
        try:
            # Start with default configuration
            config_dict: Dict[str, Any] = asdict(AppConfig())
            
            # Load from file if provided
            if self._config_path and self._config_path.exists():
                file_config = self._load_from_file(self._config_path)
                self._deep_merge(config_dict, file_config)
            
            # Load from environment variables
            env_config = self._load_from_environment()
            self._deep_merge(config_dict, env_config)
            
            # Store raw configuration
            self._raw_config = config_dict
            
            # Create AppConfig instance
            self._config = self._dict_to_config(config_dict)
            
            logger.info(
                "Configuration loaded successfully",
                extra={
                    "source": str(self._config_path) if self._config_path else "defaults",
                    "environment": self._config.environment.value
                }
            )
            
        except Exception as e:
            raise ConfigError(f"Failed to load configuration: {str(e)}") from e

    def _load_from_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Load configuration from a file.

        Args:
            file_path: Path to the configuration file

        Returns:
            Dictionary containing configuration values

        Raises:
            ConfigError: If file loading fails
        """
        if not file_path.exists():
            raise ConfigNotFoundError(f"Configuration file not found: {file_path}")
        
        try:
            with open(file_path, 'r') as f:
                if file_path.suffix in ('.yaml', '.yml'):
                    return cast(Dict[str, Any], yaml.safe_load(f))
                elif file_path.suffix == '.json':
                    return cast(Dict[str, Any], json.load(f))
                else:
                    raise ConfigError(f"Unsupported configuration file format: {file_path.suffix}")
        except yaml.YAMLError as e:
            raise ConfigError(f"Failed to parse YAML configuration: {str(e)}") from e
        except json.JSONDecodeError as e:
            raise ConfigError(f"Failed to parse JSON configuration: {str(e)}") from e
        except IOError as e:
            raise ConfigError(f"Failed to read configuration file: {str(e)}") from e

    def _load_from_environment(self) -> Dict[str, Any]:
        """
        Load configuration from environment variables.

        Environment variables should follow the pattern: {PREFIX}{SECTION}__{KEY}
        Example: APP_DATABASE__HOST=localhost

        Returns:
            Dictionary containing configuration values from environment
        """
        env_config: Dict[str, Any] = {}
        
        for key, value in os.environ.items():
            if not key.startswith(self._env_prefix):
                continue
            
            # Remove prefix and split into parts
            config_key = key[len(self._env_prefix):]
            parts = config_key.lower().split('__')
            
            # Build nested dictionary
            current = env_config
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    # Try to convert value to appropriate type
                    current[part] = self._convert_value(value)
                else:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
        
        return env_config

    def _convert_value(self, value: str) -> Any:
        """
        Convert string value to appropriate Python type.

        Args:
            value: String value to convert

        Returns:
            Converted value
        """
        # Try boolean
        if value.lower() in ('true', 'yes', '1'):
            return True
        if value.lower() in ('false', 'no', '0'):
            return False
        
        # Try integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Try JSON
        if value.startswith(('{', '[')):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        
        # Return as string
        return value

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """
        Deep merge two dictionaries.

        Args:
            base: Base dictionary to merge into
            override: Dictionary with override values
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _dict_to_config(self, config_dict: Dict[str, Any]) -> AppConfig:
        """
        Convert dictionary to AppConfig dataclass.

        Args:
            config_dict: Dictionary containing configuration values

        Returns:
            AppConfig instance

        Raises:
            ConfigValidationError: If configuration validation fails
        """
        try:
            # Handle nested dataclasses
            if 'database' in config_dict and isinstance(config_dict['database'], dict):
                config_dict['database'] = DatabaseConfig(**config_dict['database'])
            if 'redis' in config_dict and isinstance(config_dict['redis'], dict):
                config_dict['redis'] = RedisConfig(**config_dict['redis'])
            if 'logging' in config_dict and isinstance(config_dict['logging'], dict):
                config_dict['logging'] = LoggingConfig(**config_dict['logging'])
            if 'security' in config_dict and isinstance(config_dict['security'], dict):
                config_dict['security'] = SecurityConfig(**config_dict['security'])
            
            # Handle environment enum
            if 'environment' in config_dict and isinstance(config_dict['environment'], str):
                try:
                    config_dict['environment'] = Environment(config_dict['environment'].lower())
                except ValueError:
                    raise ConfigValidationError(
                        f"Invalid environment value: {config_dict['environment']}"
                    )
            
            return AppConfig(**config_dict)
            
        except TypeError as e:
            raise ConfigValidationError(f"Invalid configuration structure: {str(e)}") from e

    @property
    def config(self) -> AppConfig:
        """
        Get the current configuration.

        Returns:
            AppConfig instance

        Raises:
            ConfigError: If configuration has not been loaded
        """
        if self._config is None:
            raise ConfigError("Configuration has not been loaded. Call load() first.")
        return self._config

    def get(self, key: str, default: Optional[T] = None) -> Optional[Any]:
        """
        Get a configuration value by dot-separated key.

        Args:
            key: Dot-separated configuration key (e.g., 'database.host')
            default: Default value if key is not found

        Returns:
            Configuration value or default

        Raises:
            ConfigNotFoundError: If key is not found and no default is provided
        """
        if self._config is None:
            raise ConfigError("Configuration has not been loaded. Call load() first.")
        
        try:
            value = self._raw_config
            for part in key.split('.'):
                if isinstance(value, dict):
                    value = value[part]
                else:
                    raise KeyError(part)
            return value
        except (KeyError, TypeError):
            if default is not None:
                return default
            raise ConfigNotFoundError(f"Configuration key not found: {key}")

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value at runtime.

        Args:
            key: Dot-separated configuration key
            value: Value to set

        Raises:
            ConfigError: If configuration has not been loaded
        """
        if self._config is None:
            raise ConfigError("Configuration has not been loaded. Call load() first.")
        
        # Update raw config
        parts = key.split('.')
        current = self._raw_config
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
        
        # Reload configuration
        self._config = self._dict_to_config(self._raw_config)

    def reload(self) -> None:
        """
        Reload configuration from all sources.

        Raises:
            ConfigError: If configuration reloading fails
        """
        self.load()

    def validate(self) -> bool:
        """
        Validate the current configuration.

        Returns:
            True if configuration is valid

        Raises:
            ConfigValidationError: If configuration validation fails
        """
        if self._config is None:
            raise ConfigError("Configuration has not been loaded. Call load() first.")
        
        # Validate required fields
        if not self._config.security.secret_key and self._config.environment == Environment.PRODUCTION:
            raise ConfigValidationError("Secret key is required in production environment")
        
        if not self._config.security.jwt_secret and self._config.environment == Environment.PRODUCTION:
            raise ConfigValidationError("JWT secret is required in production environment")
        
        return True

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.

        Returns:
            Dictionary representation of configuration

        Raises:
            ConfigError: If configuration has not been loaded
        """
        if self._config is None:
            raise ConfigError("Configuration has not been loaded. Call load() first.")
        
        return self._raw_config.copy()

    def to_json(self, indent: int = 2) -> str:
        """
        Convert configuration to JSON string.

        Args:
            indent: JSON indentation level

        Returns:
            JSON string representation of configuration

        Raises:
            ConfigError: If configuration has not been loaded
        """
        if self._config is None:
            raise ConfigError("Configuration has not been loaded. Call load() first.")
        
        return json.dumps(self._raw_config, indent=indent, default=str)

    def __repr__(self) -> str:
        """String representation of the configuration manager."""
        return f"ConfigManager(environment={self._config.environment.value if self._config else 'not loaded'})"


# Global configuration instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> AppConfig:
    """
    Get the global application configuration.

    Returns:
        AppConfig instance

    Raises:
        ConfigError: If configuration has not been initialized
    """
    global _config_manager
    
    if _config_manager is None:
        _config_manager = ConfigManager()
    
    return _config_manager.config


def init_config(
    config_path: Optional[Union[str, Path]] = None,
    env_prefix: str = "APP_"
) -> AppConfig:
    """
    Initialize the global configuration.

    Args:
        config_path: Path to configuration file
        env_prefix: Prefix for environment variables

    Returns:
        AppConfig instance

    Raises:
        ConfigError: If configuration initialization fails
    """
    global _config_manager
    
    _config_manager = ConfigManager(
        config_path=config_path,
        env_prefix=env_prefix,
        auto_load=True
    )
    
    return _config_manager.config


def reset_config() -> None:
    """Reset the global configuration instance."""
    global _config_manager
    _config_manager = None


__all__ = [
    'AppConfig',
    'ConfigManager',
    'ConfigError',
    'ConfigNotFoundError',
    'ConfigValidationError',
    'ConfigTypeError',
    'DatabaseConfig',
    'Environment',
    'LoggingConfig',
    'RedisConfig',
    'SecurityConfig',
    'get_config',
    'init_config',
    'reset_config',
]