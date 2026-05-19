"""
Main entry point for the application.

This module serves as the primary entry point for the application,
initializing core components, configuring logging, and orchestrating
the main execution flow.
"""

import sys
import logging
import argparse
from typing import Optional, NoReturn
from pathlib import Path
from datetime import datetime

from src.config import AppConfig, load_config
from src.logger import setup_logging, get_logger
from src.exceptions import ApplicationError, ConfigurationError
from src.core import ApplicationCore

logger = get_logger(__name__)


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments for the application.

    Returns:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Enterprise-grade application entry point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main --config config.yaml
  python -m src.main --verbose --dry-run
  python -m src.main --log-level DEBUG
        """
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without making changes"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level (default: INFO)"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory for output files (default: output)"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
        help="Show version information and exit"
    )

    return parser.parse_args()


def validate_environment() -> None:
    """
    Validate the runtime environment meets application requirements.

    Raises:
        ConfigurationError: If environment validation fails.
    """
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 9):
        raise ConfigurationError(
            f"Python 3.9+ is required. Current version: {python_version.major}.{python_version.minor}"
        )

    required_env_vars = ["APP_ENV", "APP_NAME"]
    missing_vars = [var for var in required_env_vars if var not in os.environ]
    if missing_vars:
        logger.warning(f"Missing recommended environment variables: {', '.join(missing_vars)}")


def initialize_application(args: argparse.Namespace) -> AppConfig:
    """
    Initialize the application with provided arguments.

    Args:
        args: Parsed command-line arguments.

    Returns:
        AppConfig: Initialized application configuration.

    Raises:
        ConfigurationError: If initialization fails.
    """
    try:
        # Setup logging first
        log_level = getattr(logging, args.log_level.upper())
        setup_logging(level=log_level, verbose=args.verbose)

        logger.info("Initializing application...")
        logger.debug(f"Command-line arguments: {args}")

        # Load configuration
        config_path = Path(args.config)
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")

        config = load_config(config_path)

        # Override config with command-line arguments
        if args.output_dir:
            config.output_dir = Path(args.output_dir)
            config.output_dir.mkdir(parents=True, exist_ok=True)

        config.dry_run = args.dry_run
        config.verbose = args.verbose

        # Validate environment
        validate_environment()

        logger.info(f"Application initialized successfully. Environment: {os.environ.get('APP_ENV', 'development')}")
        return config

    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise ConfigurationError(f"Initialization failed: {e}") from e


def run_application(config: AppConfig) -> int:
    """
    Execute the main application logic.

    Args:
        config: Application configuration.

    Returns:
        int: Exit code (0 for success, non-zero for failure).

    Raises:
        ApplicationError: If application execution fails.
    """
    start_time = datetime.now()
    logger.info(f"Starting application execution at {start_time.isoformat()}")

    try:
        # Create and initialize core application
        app_core = ApplicationCore(config)

        # Execute main application logic
        if config.dry_run:
            logger.info("DRY RUN: No changes will be made")
            result = app_core.dry_run()
        else:
            result = app_core.execute()

        # Process results
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Application execution completed in {execution_time:.2f} seconds")

        if result:
            logger.info(f"Application completed successfully with result: {result}")
            return 0
        else:
            logger.warning("Application completed with no results")
            return 0

    except ApplicationError as e:
        logger.error(f"Application error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error during execution: {e}", exc_info=True)
        return 2


def cleanup(config: AppConfig) -> None:
    """
    Perform cleanup operations before application exit.

    Args:
        config: Application configuration for cleanup context.
    """
    logger.info("Performing cleanup operations...")
    try:
        # Close any open resources
        if hasattr(config, 'cleanup'):
            config.cleanup()

        # Flush and close logging handlers
        for handler in logging.getLogger().handlers:
            handler.flush()
            handler.close()

        logger.info("Cleanup completed successfully")

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


def main() -> NoReturn:
    """
    Main entry point for the application.

    This function orchestrates the entire application lifecycle:
    1. Parse command-line arguments
    2. Initialize application components
    3. Execute main logic
    4. Perform cleanup
    5. Exit with appropriate status code

    Returns:
        NoReturn: This function always exits the process.
    """
    exit_code = 0
    config: Optional[AppConfig] = None

    try:
        # Parse arguments
        args = parse_arguments()

        # Initialize application
        config = initialize_application(args)

        # Run application
        exit_code = run_application(config)

    except ConfigurationError as e:
        logger.critical(f"Configuration error: {e}")
        exit_code = 3
    except KeyboardInterrupt:
        logger.warning("Application interrupted by user")
        exit_code = 130
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        exit_code = 4
    finally:
        # Always perform cleanup
        if config:
            cleanup(config)

        logger.info(f"Application exiting with code {exit_code}")
        sys.exit(exit_code)


if __name__ == "__main__":
    main()