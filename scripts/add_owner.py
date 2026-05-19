#!/usr/bin/env python3
"""
Script to add an owner to the authorized users list.

This script provides functionality to add a new owner to the system's
authorized users configuration. It handles validation, duplicate checking,
and proper error handling for all edge cases.
"""

import json
import os
import sys
import argparse
from typing import Dict, List, Optional, Union
from pathlib import Path
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OwnerManager:
    """Manages the authorized owners list with file persistence."""

    def __init__(self, config_path: Union[str, Path] = "config/authorized_owners.json"):
        """
        Initialize the OwnerManager with a configuration file path.

        Args:
            config_path: Path to the JSON configuration file containing authorized owners.

        Raises:
            ValueError: If config_path is empty or invalid.
        """
        if not config_path:
            raise ValueError("Configuration path cannot be empty")

        self.config_path = Path(config_path)
        self._ensure_config_directory()

    def _ensure_config_directory(self) -> None:
        """Ensure the configuration directory exists."""
        config_dir = self.config_path.parent
        if not config_dir.exists():
            try:
                config_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created configuration directory: {config_dir}")
            except PermissionError as e:
                logger.error(f"Permission denied creating directory {config_dir}: {e}")
                raise
            except OSError as e:
                logger.error(f"Failed to create directory {config_dir}: {e}")
                raise

    def _load_owners(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Load the current list of authorized owners from the configuration file.

        Returns:
            Dictionary containing the owners list structure.

        Raises:
            json.JSONDecodeError: If the configuration file contains invalid JSON.
            IOError: If there's an error reading the file.
        """
        if not self.config_path.exists():
            logger.info(f"Configuration file not found at {self.config_path}. Creating new file.")
            return {"owners": []}

        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                if not isinstance(data, dict) or "owners" not in data:
                    logger.warning("Invalid configuration structure. Resetting to empty list.")
                    return {"owners": []}
                return data
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise
        except IOError as e:
            logger.error(f"Error reading configuration file: {e}")
            raise

    def _save_owners(self, owners_data: Dict[str, List[Dict[str, str]]]) -> None:
        """
        Save the owners data to the configuration file.

        Args:
            owners_data: Dictionary containing the owners list to save.

        Raises:
            IOError: If there's an error writing to the file.
        """
        try:
            with open(self.config_path, 'w', encoding='utf-8') as file:
                json.dump(owners_data, file, indent=2, ensure_ascii=False)
            logger.info(f"Successfully saved owners data to {self.config_path}")
        except IOError as e:
            logger.error(f"Error writing to configuration file: {e}")
            raise

    def _validate_owner_data(self, owner_id: str, owner_name: str, email: str) -> None:
        """
        Validate the owner data fields.

        Args:
            owner_id: Unique identifier for the owner.
            owner_name: Display name of the owner.
            email: Email address of the owner.

        Raises:
            ValueError: If any of the fields are invalid.
        """
        if not owner_id or not owner_id.strip():
            raise ValueError("Owner ID cannot be empty")

        if not owner_name or not owner_name.strip():
            raise ValueError("Owner name cannot be empty")

        if not email or not email.strip():
            raise ValueError("Email cannot be empty")

        if '@' not in email or '.' not in email.split('@')[-1]:
            raise ValueError(f"Invalid email format: {email}")

        if not owner_id.isalnum() and '_' not in owner_id:
            raise ValueError(f"Owner ID must be alphanumeric (underscores allowed): {owner_id}")

    def _is_duplicate(self, owners_data: Dict[str, List[Dict[str, str]]], owner_id: str) -> bool:
        """
        Check if an owner with the given ID already exists.

        Args:
            owners_data: Current owners data structure.
            owner_id: Owner ID to check for duplicates.

        Returns:
            True if duplicate found, False otherwise.
        """
        return any(
            owner.get("id") == owner_id
            for owner in owners_data.get("owners", [])
        )

    def add_owner(
        self,
        owner_id: str,
        owner_name: str,
        email: str,
        role: str = "owner",
        overwrite: bool = False
    ) -> bool:
        """
        Add a new owner to the authorized users list.

        Args:
            owner_id: Unique identifier for the owner.
            owner_name: Display name of the owner.
            email: Email address of the owner.
            role: Role assigned to the owner (default: "owner").
            overwrite: If True, overwrite existing owner with same ID (default: False).

        Returns:
            True if owner was successfully added, False if duplicate found and not overwritten.

        Raises:
            ValueError: If validation fails.
            IOError: If file operations fail.
        """
        try:
            self._validate_owner_data(owner_id, owner_name, email)
        except ValueError as e:
            logger.error(f"Validation failed: {e}")
            raise

        owners_data = self._load_owners()

        if self._is_duplicate(owners_data, owner_id):
            if overwrite:
                logger.info(f"Overwriting existing owner with ID: {owner_id}")
                owners_data["owners"] = [
                    owner for owner in owners_data["owners"]
                    if owner.get("id") != owner_id
                ]
            else:
                logger.warning(f"Owner with ID '{owner_id}' already exists. Use --overwrite to replace.")
                return False

        new_owner = {
            "id": owner_id,
            "name": owner_name,
            "email": email,
            "role": role,
            "added_at": datetime.utcnow().isoformat(),
            "active": True
        }

        owners_data["owners"].append(new_owner)
        self._save_owners(owners_data)
        logger.info(f"Successfully added owner: {owner_id} ({owner_name})")
        return True

    def list_owners(self) -> List[Dict[str, str]]:
        """
        List all authorized owners.

        Returns:
            List of owner dictionaries.

        Raises:
            IOError: If there's an error reading the configuration file.
        """
        owners_data = self._load_owners()
        return owners_data.get("owners", [])


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments for the add_owner script.

    Returns:
            Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Add an owner to the authorized users list",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --id john_doe --name "John Doe" --email john@example.com
  %(prog)s --id jane_smith --name "Jane Smith" --email jane@example.com --role admin
  %(prog)s --id john_doe --name "John Doe" --email john@example.com --overwrite
        """
    )

    parser.add_argument(
        '--id',
        required=True,
        help='Unique identifier for the owner (alphanumeric, underscores allowed)'
    )

    parser.add_argument(
        '--name',
        required=True,
        help='Display name of the owner'
    )

    parser.add_argument(
        '--email',
        required=True,
        help='Email address of the owner'
    )

    parser.add_argument(
        '--role',
        default='owner',
        choices=['owner', 'admin', 'viewer'],
        help='Role assigned to the owner (default: owner)'
    )

    parser.add_argument(
        '--config',
        default='config/authorized_owners.json',
        help='Path to configuration file (default: config/authorized_owners.json)'
    )

    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing owner if ID already exists'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging output'
    )

    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the add_owner script.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    args = parse_arguments()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        manager = OwnerManager(args.config)

        success = manager.add_owner(
            owner_id=args.id,
            owner_name=args.name,
            email=args.email,
            role=args.role,
            overwrite=args.overwrite
        )

        if success:
            logger.info(f"Owner '{args.id}' has been added successfully.")
            return 0
        else:
            logger.warning(f"Owner '{args.id}' already exists. Use --overwrite to replace.")
            return 1

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return 1
    except json.JSONDecodeError as e:
        logger.error(f"Configuration file error: {e}")
        return 1
    except IOError as e:
        logger.error(f"File operation error: {e}")
        return 1
    except PermissionError as e:
        logger.error(f"Permission error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())