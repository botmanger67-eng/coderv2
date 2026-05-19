"""
Bot package initialization module.

This module initializes the bot package, setting up logging, configuration,
and providing a centralized entry point for bot operations.
"""

import logging
import os
from typing import Optional, Dict, Any, Final
from pathlib import Path

# Package metadata
__version__: Final[str] = "1.0.0"
__author__: Final[str] = "Enterprise Bot Team"
__description__: Final[str] = "Enterprise-grade bot package for automated operations"

# Package-level logger
logger: logging.Logger = logging.getLogger(__name__)

# Package configuration defaults
DEFAULT_CONFIG_PATH: Final[str] = "config/bot_config.yaml"
DEFAULT_LOG_LEVEL: Final[str] = "INFO"
DEFAULT_LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Package constants
PACKAGE_ROOT: Final[Path] = Path(__file__).parent.parent
CONFIG_DIR: Final[Path] = PACKAGE_ROOT / "config"
LOG_DIR: Final[Path] = PACKAGE_ROOT / "logs"


def setup_logging(
    log_level: str = DEFAULT_LOG_LEVEL,
    log_format: str = DEFAULT_LOG_FORMAT,
    log_file: Optional[str] = None
) -> None:
    """
    Configure logging for the bot package.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format string for log messages
        log_file: Optional path to log file. If None, logs to console only.

    Raises:
        ValueError: If log_level is invalid
        PermissionError: If log file cannot be created
        OSError: If log directory cannot be created
    """
    valid_levels: Dict[str, int] = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }

    if log_level.upper() not in valid_levels:
        raise ValueError(
            f"Invalid log level: {log_level}. "
            f"Must be one of: {', '.join(valid_levels.keys())}"
        )

    try:
        # Configure root logger
        root_logger: logging.Logger = logging.getLogger()
        root_logger.setLevel(valid_levels[log_level.upper()])

        # Create formatter
        formatter: logging.Formatter = logging.Formatter(log_format)

        # Console handler
        console_handler: logging.StreamHandler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # File handler (if specified)
        if log_file:
            log_path: Path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler: logging.FileHandler = logging.FileHandler(
                log_path,
                mode='a',
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        logger.info(
            "Logging configured successfully: level=%s, file=%s",
            log_level,
            log_file or "console only"
        )

    except PermissionError as e:
        raise PermissionError(
            f"Cannot create log file at {log_file}: {e}"
        ) from e
    except OSError as e:
        raise OSError(
            f"Cannot create log directory: {e}"
        ) from e


def load_configuration(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load bot configuration from file.

    Args:
        config_path: Path to configuration file. If None, uses default path.

    Returns:
        Dictionary containing configuration parameters

    Raises:
        FileNotFoundError: If configuration file does not exist
        ValueError: If configuration file is invalid
        PermissionError: If configuration file cannot be read
    """
    import yaml

    config_file: str = config_path or str(CONFIG_DIR / "bot_config.yaml")
    config_path_obj: Path = Path(config_file)

    if not config_path_obj.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_file}"
        )

    try:
        with open(config_path_obj, 'r', encoding='utf-8') as f:
            config: Dict[str, Any] = yaml.safe_load(f)

        if config is None:
            raise ValueError(
                f"Configuration file is empty: {config_file}"
            )

        logger.info(
            "Configuration loaded successfully from: %s",
            config_file
        )
        return config

    except yaml.YAMLError as e:
        raise ValueError(
            f"Invalid YAML configuration in {config_file}: {e}"
        ) from e
    except PermissionError as e:
        raise PermissionError(
            f"Cannot read configuration file {config_file}: {e}"
        ) from e


def initialize_bot(
    config_path: Optional[str] = None,
    log_level: str = DEFAULT_LOG_LEVEL,
    log_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Initialize the bot package with logging and configuration.

    This function should be called once at application startup.

    Args:
        config_path: Path to configuration file
        log_level: Logging level
        log_file: Optional log file path

    Returns:
        Configuration dictionary

    Raises:
        RuntimeError: If initialization fails
    """
    try:
        # Setup logging first
        setup_logging(
            log_level=log_level,
            log_file=log_file
        )

        # Load configuration
        config: Dict[str, Any] = load_configuration(
            config_path=config_path
        )

        # Create necessary directories
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Bot package initialized successfully (version: %s)",
            __version__
        )

        return config

    except (FileNotFoundError, ValueError, PermissionError, OSError) as e:
        error_msg: str = f"Bot initialization failed: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


def get_package_info() -> Dict[str, Any]:
    """
    Get package metadata information.

    Returns:
        Dictionary containing package metadata
    """
    return {
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "package_root": str(PACKAGE_ROOT),
        "config_dir": str(CONFIG_DIR),
        "log_dir": str(LOG_DIR)
    }


# Initialize package-level logger with default configuration
setup_logging()

# Export public API
__all__: list[str] = [
    "setup_logging",
    "load_configuration",
    "initialize_bot",
    "get_package_info",
    "logger",
    "PACKAGE_ROOT",
    "CONFIG_DIR",
    "LOG_DIR",
    "__version__",
    "__author__",
    "__description__"
]