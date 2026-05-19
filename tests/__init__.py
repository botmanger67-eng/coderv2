"""
Tests package initialization.

This module initializes the tests package and provides common test utilities,
fixtures, and configuration for the test suite.

The package follows a modular structure:
- unit/: Unit tests for individual components
- integration/: Integration tests for component interactions
- e2e/: End-to-end tests for complete workflows
- fixtures/: Shared test fixtures and data
- mocks/: Mock objects and services
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Any, Final
from pathlib import Path
from dataclasses import dataclass, field

# Configure test logging
logging.basicConfig(
    level=logging.DEBUG if os.getenv("TEST_DEBUG") else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger: Final[logging.Logger] = logging.getLogger(__name__)

# Package metadata
__version__: Final[str] = "1.0.0"
__author__: Final[str] = "Enterprise Engineering Team"
__description__: Final[str] = "Enterprise-grade test suite package"

# Test configuration constants
TEST_ROOT: Final[Path] = Path(__file__).parent.resolve()
PROJECT_ROOT: Final[Path] = TEST_ROOT.parent.resolve()
TEST_DATA_DIR: Final[Path] = TEST_ROOT / "fixtures" / "data"
TEST_CONFIG_DIR: Final[Path] = TEST_ROOT / "fixtures" / "config"

# Ensure test data directories exist
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
TEST_CONFIG_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class TestConfig:
    """
    Immutable test configuration dataclass.
    
    Attributes:
        debug: Enable debug logging
        timeout: Default test timeout in seconds
        retry_count: Number of retries for flaky tests
        parallel_execution: Enable parallel test execution
        coverage_enabled: Enable code coverage reporting
        environment: Test environment name
        database_url: Test database connection string
        api_base_url: Base URL for API tests
        mock_external_services: Flag to mock external services
    """
    debug: bool = False
    timeout: int = 30
    retry_count: int = 3
    parallel_execution: bool = True
    coverage_enabled: bool = True
    environment: str = "test"
    database_url: str = "sqlite:///:memory:"
    api_base_url: str = "http://localhost:8000"
    mock_external_services: bool = True


def get_test_config() -> TestConfig:
    """
    Retrieve test configuration from environment variables with defaults.
    
    Returns:
        TestConfig: Configuration object with values from environment or defaults
        
    Raises:
        ValueError: If environment variables contain invalid values
    """
    try:
        return TestConfig(
            debug=os.getenv("TEST_DEBUG", "false").lower() == "true",
            timeout=int(os.getenv("TEST_TIMEOUT", "30")),
            retry_count=int(os.getenv("TEST_RETRY_COUNT", "3")),
            parallel_execution=os.getenv("TEST_PARALLEL", "true").lower() == "true",
            coverage_enabled=os.getenv("TEST_COVERAGE", "true").lower() == "true",
            environment=os.getenv("TEST_ENVIRONMENT", "test"),
            database_url=os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:"),
            api_base_url=os.getenv("TEST_API_BASE_URL", "http://localhost:8000"),
            mock_external_services=os.getenv("TEST_MOCK_EXTERNAL", "true").lower() == "true",
        )
    except (ValueError, TypeError) as error:
        logger.error("Failed to parse test configuration: %s", error)
        raise ValueError(f"Invalid test configuration: {error}") from error


def setup_test_environment(config: Optional[TestConfig] = None) -> None:
    """
    Initialize the test environment with proper configuration.
    
    Args:
        config: Optional TestConfig instance. If None, loads from environment.
        
    Raises:
        RuntimeError: If environment setup fails
    """
    try:
        test_config = config or get_test_config()
        
        # Set environment variables for test configuration
        os.environ.setdefault("APP_ENVIRONMENT", test_config.environment)
        os.environ.setdefault("DATABASE_URL", test_config.database_url)
        os.environ.setdefault("API_BASE_URL", test_config.api_base_url)
        
        # Add project root to Python path for imports
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        
        # Configure logging based on debug flag
        if test_config.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Test environment configured with debug logging")
        
        logger.info(
            "Test environment initialized: environment=%s, parallel=%s, coverage=%s",
            test_config.environment,
            test_config.parallel_execution,
            test_config.coverage_enabled,
        )
        
    except Exception as error:
        logger.error("Failed to setup test environment: %s", error)
        raise RuntimeError(f"Test environment setup failed: {error}") from error


def cleanup_test_environment() -> None:
    """
    Clean up test environment resources.
    
    This function should be called after all tests complete to ensure
    proper cleanup of temporary files, connections, and other resources.
    """
    try:
        # Remove test data directories if they exist
        for directory in [TEST_DATA_DIR, TEST_CONFIG_DIR]:
            if directory.exists():
                for item in directory.iterdir():
                    try:
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            import shutil
                            shutil.rmtree(item)
                    except OSError as error:
                        logger.warning("Failed to clean up %s: %s", item, error)
        
        logger.info("Test environment cleaned up successfully")
        
    except Exception as error:
        logger.error("Failed to cleanup test environment: %s", error)
        raise RuntimeError(f"Test environment cleanup failed: {error}") from error


def discover_test_modules() -> List[str]:
    """
    Discover all test modules in the tests package.
    
    Returns:
        List[str]: Sorted list of discovered test module names
        
    Raises:
        RuntimeError: If module discovery fails
    """
    try:
        test_modules: List[str] = []
        
        for path in TEST_ROOT.rglob("test_*.py"):
            if path.is_file():
                # Convert path to module name relative to tests package
                relative_path = path.relative_to(TEST_ROOT)
                module_name = ".".join(relative_path.with_suffix("").parts)
                test_modules.append(module_name)
        
        return sorted(test_modules)
        
    except Exception as error:
        logger.error("Failed to discover test modules: %s", error)
        raise RuntimeError(f"Test module discovery failed: {error}") from error


def validate_test_environment() -> Dict[str, bool]:
    """
    Validate that the test environment is properly configured.
    
    Returns:
        Dict[str, bool]: Dictionary of validation checks and their status
        
    Raises:
        RuntimeError: If validation encounters an error
    """
    try:
        validation_results: Dict[str, bool] = {
            "project_root_exists": PROJECT_ROOT.exists(),
            "test_root_exists": TEST_ROOT.exists(),
            "test_data_dir_exists": TEST_DATA_DIR.exists(),
            "test_config_dir_exists": TEST_CONFIG_DIR.exists(),
            "project_root_in_path": str(PROJECT_ROOT) in sys.path,
            "logging_configured": logging.getLogger().hasHandlers(),
        }
        
        # Log validation results
        for check, status in validation_results.items():
            if status:
                logger.debug("Validation passed: %s", check)
            else:
                logger.warning("Validation failed: %s", check)
        
        return validation_results
        
    except Exception as error:
        logger.error("Failed to validate test environment: %s", error)
        raise RuntimeError(f"Test environment validation failed: {error}") from error


# Initialize test environment on package import
try:
    setup_test_environment()
    logger.debug("Tests package initialized successfully")
except Exception as error:
    logger.error("Failed to initialize tests package: %s", error)
    raise

# Export public API
__all__: Final[List[str]] = [
    "TestConfig",
    "get_test_config",
    "setup_test_environment",
    "cleanup_test_environment",
    "discover_test_modules",
    "validate_test_environment",
    "TEST_ROOT",
    "PROJECT_ROOT",
    "TEST_DATA_DIR",
    "TEST_CONFIG_DIR",
]