"""
Package setup configuration for the project.

This module defines the package metadata and dependencies for distribution.
It uses setuptools to configure the package for installation via pip.
"""

import os
import sys
from typing import Dict, List, Optional

from setuptools import find_packages, setup

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HERE: str = os.path.abspath(os.path.dirname(__file__))

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def read_file(file_path: str) -> str:
    """
    Read the content of a file and return it as a string.

    Args:
        file_path: Path to the file relative to the project root.

    Returns:
        Content of the file as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
        IOError: If the file cannot be read.
    """
    full_path: str = os.path.join(HERE, file_path)
    try:
        with open(full_path, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Required file not found: {full_path}") from exc
    except IOError as exc:
        raise IOError(f"Error reading file {full_path}: {exc}") from exc


def get_version() -> str:
    """
    Extract the package version from the VERSION file.

    Returns:
        Version string (e.g., '1.0.0').

    Raises:
        ValueError: If the version file is empty or malformed.
    """
    version: str = read_file("VERSION")
    if not version:
        raise ValueError("VERSION file is empty or missing version string.")
    return version


def get_long_description() -> str:
    """
    Read the long description from README.md.

    Returns:
        Content of README.md as a string.
    """
    return read_file("README.md")


def get_requirements() -> List[str]:
    """
    Parse the requirements.txt file and return a list of dependencies.

    Returns:
        List of dependency strings.

    Raises:
        FileNotFoundError: If requirements.txt is missing.
    """
    content: str = read_file("requirements.txt")
    requirements: List[str] = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return requirements


def get_optional_dependencies() -> Dict[str, List[str]]:
    """
    Define optional dependency groups (extras).

    Returns:
        Dictionary mapping extra names to lists of dependencies.
    """
    return {
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "black>=23.0",
            "flake8>=6.0",
            "mypy>=1.0",
            "pre-commit>=3.0",
        ],
        "docs": [
            "sphinx>=5.0",
            "sphinx-rtd-theme>=1.0",
        ],
    }


# ---------------------------------------------------------------------------
# Package metadata
# ---------------------------------------------------------------------------

PACKAGE_NAME: str = "my_package"
PACKAGE_VERSION: str = get_version()
PACKAGE_DESCRIPTION: str = "A short description of the package."
PACKAGE_LONG_DESCRIPTION: str = get_long_description()
PACKAGE_LONG_DESCRIPTION_CONTENT_TYPE: str = "text/markdown"
PACKAGE_AUTHOR: str = "Your Name"
PACKAGE_AUTHOR_EMAIL: str = "your.email@example.com"
PACKAGE_URL: str = "https://github.com/yourusername/my_package"
PACKAGE_LICENSE: str = "MIT"
PACKAGE_CLASSIFIERS: List[str] = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Operating System :: OS Independent",
]
PACKAGE_KEYWORDS: List[str] = ["example", "template", "package"]
PACKAGE_PYTHON_REQUIRES: str = ">=3.9"
PACKAGE_INSTALL_REQUIRES: List[str] = get_requirements()
PACKAGE_EXTRAS_REQUIRE: Dict[str, List[str]] = get_optional_dependencies()
PACKAGE_PACKAGES: List[str] = find_packages(
    where="src",
    exclude=["tests", "tests.*", "docs", "docs.*"],
)
PACKAGE_PACKAGE_DIR: Dict[str, str] = {"": "src"}
PACKAGE_INCLUDE_PACKAGE_DATA: bool = True
PACKAGE_ZIP_SAFE: bool = False

# ---------------------------------------------------------------------------
# Entry points (console scripts)
# ---------------------------------------------------------------------------

PACKAGE_ENTRY_POINTS: Dict[str, List[str]] = {
    "console_scripts": [
        "my_command=my_package.cli:main",
    ],
}

# ---------------------------------------------------------------------------
# Setup call
# ---------------------------------------------------------------------------


def main() -> None:
    """
    Execute the package setup.

    This function is the entry point for setuptools. It configures all
    package metadata and dependencies for distribution.

    Raises:
        SystemExit: If setup fails due to configuration errors.
    """
    try:
        setup(
            name=PACKAGE_NAME,
            version=PACKAGE_VERSION,
            description=PACKAGE_DESCRIPTION,
            long_description=PACKAGE_LONG_DESCRIPTION,
            long_description_content_type=PACKAGE_LONG_DESCRIPTION_CONTENT_TYPE,
            author=PACKAGE_AUTHOR,
            author_email=PACKAGE_AUTHOR_EMAIL,
            url=PACKAGE_URL,
            license=PACKAGE_LICENSE,
            classifiers=PACKAGE_CLASSIFIERS,
            keywords=PACKAGE_KEYWORDS,
            python_requires=PACKAGE_PYTHON_REQUIRES,
            install_requires=PACKAGE_INSTALL_REQUIRES,
            extras_require=PACKAGE_EXTRAS_REQUIRE,
            packages=PACKAGE_PACKAGES,
            package_dir=PACKAGE_PACKAGE_DIR,
            include_package_data=PACKAGE_INCLUDE_PACKAGE_DATA,
            zip_safe=PACKAGE_ZIP_SAFE,
            entry_points=PACKAGE_ENTRY_POINTS,
        )
    except Exception as exc:
        print(f"Error during setup: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()