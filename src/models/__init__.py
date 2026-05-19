"""Models package initialization.

This module provides the base model class and utilities for all data models
used throughout the application. It serves as the central registry for model
definitions and ensures consistent model behavior across the codebase.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

from pydantic import BaseModel, Field, ValidationError, validator

logger = logging.getLogger(__name__)

# Type variable for generic model support
T = TypeVar("T", bound="BaseDomainModel")


class BaseDomainModel(BaseModel, ABC):
    """Abstract base class for all domain models.

    Provides common functionality such as timestamps, serialization,
    and validation that all models in the application should inherit.

    Attributes:
        created_at: Timestamp when the model instance was created.
        updated_at: Timestamp when the model instance was last updated.
        is_active: Flag indicating if the model instance is active.
    """

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)

    class Config:
        """Pydantic configuration for domain models."""

        arbitrary_types_allowed = True
        validate_assignment = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @validator("updated_at", always=True)
    def validate_updated_at(cls, value: datetime, values: Dict[str, Any]) -> datetime:
        """Ensure updated_at is not before created_at.

        Args:
            value: The updated_at timestamp to validate.
            values: Dictionary of all field values.

        Returns:
            The validated updated_at timestamp.

        Raises:
            ValueError: If updated_at is before created_at.
        """
        created_at = values.get("created_at")
        if created_at and value < created_at:
            raise ValueError("updated_at cannot be before created_at")
        return value

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary representation.

        Returns:
            Dictionary containing all model fields.
        """
        return self.dict()

    @abstractmethod
    def to_json(self) -> str:
        """Convert model instance to JSON string.

        Returns:
            JSON string representation of the model.
        """
        return self.json()

    @classmethod
    def from_dict(cls: type[T], data: Dict[str, Any]) -> T:
        """Create model instance from dictionary.

        Args:
            data: Dictionary containing model field values.

        Returns:
            New model instance.

        Raises:
            ValidationError: If the dictionary data is invalid.
        """
        try:
            return cls(**data)
        except ValidationError as e:
            logger.error(f"Failed to create {cls.__name__} from dict: {e}")
            raise

    @classmethod
    def from_json(cls: type[T], json_str: str) -> T:
        """Create model instance from JSON string.

        Args:
            json_str: JSON string containing model field values.

        Returns:
            New model instance.

        Raises:
            ValidationError: If the JSON data is invalid.
        """
        try:
            return cls.parse_raw(json_str)
        except ValidationError as e:
            logger.error(f"Failed to create {cls.__name__} from JSON: {e}")
            raise

    def update(self: T, **kwargs: Any) -> T:
        """Update model fields with provided values.

        Args:
            **kwargs: Field names and their new values.

        Returns:
            Updated model instance.

        Raises:
            ValidationError: If the update values are invalid.
        """
        try:
            for field, value in kwargs.items():
                setattr(self, field, value)
            self.updated_at = datetime.utcnow()
            return self
        except ValidationError as e:
            logger.error(f"Failed to update {self.__class__.__name__}: {e}")
            raise

    def deactivate(self) -> None:
        """Mark the model instance as inactive."""
        self.is_active = False
        self.updated_at = datetime.utcnow()

    def activate(self) -> None:
        """Mark the model instance as active."""
        self.is_active = True
        self.updated_at = datetime.utcnow()


class ModelRegistry:
    """Registry for managing model classes and their metadata.

    Provides a centralized registry for model discovery, serialization,
    and deserialization across the application.
    """

    def __init__(self) -> None:
        """Initialize the model registry with empty storage."""
        self._models: Dict[str, type[BaseDomainModel]] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        model_class: type[BaseDomainModel],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a model class in the registry.

        Args:
            model_class: The model class to register.
            metadata: Optional metadata associated with the model.

        Raises:
            ValueError: If the model class is already registered.
        """
        model_name = model_class.__name__
        if model_name in self._models:
            raise ValueError(f"Model '{model_name}' is already registered")

        self._models[model_name] = model_class
        self._metadata[model_name] = metadata or {}
        logger.info(f"Registered model: {model_name}")

    def unregister(self, model_name: str) -> None:
        """Unregister a model class from the registry.

        Args:
            model_name: The name of the model to unregister.

        Raises:
            KeyError: If the model is not found in the registry.
        """
        if model_name not in self._models:
            raise KeyError(f"Model '{model_name}' is not registered")

        del self._models[model_name]
        del self._metadata[model_name]
        logger.info(f"Unregistered model: {model_name}")

    def get_model(self, model_name: str) -> type[BaseDomainModel]:
        """Retrieve a registered model class by name.

        Args:
            model_name: The name of the model to retrieve.

        Returns:
            The registered model class.

        Raises:
            KeyError: If the model is not found in the registry.
        """
        if model_name not in self._models:
            raise KeyError(f"Model '{model_name}' is not registered")

        return self._models[model_name]

    def get_metadata(self, model_name: str) -> Dict[str, Any]:
        """Retrieve metadata for a registered model.

        Args:
            model_name: The name of the model.

        Returns:
            Dictionary of metadata for the model.

        Raises:
            KeyError: If the model is not found in the registry.
        """
        if model_name not in self._metadata:
            raise KeyError(f"Model '{model_name}' is not registered")

        return self._metadata[model_name]

    def list_models(self) -> List[str]:
        """List all registered model names.

        Returns:
            List of registered model names.
        """
        return list(self._models.keys())

    def clear(self) -> None:
        """Clear all registered models and metadata."""
        self._models.clear()
        self._metadata.clear()
        logger.info("Cleared all registered models")


# Global model registry instance
model_registry = ModelRegistry()


def register_model(
    model_class: type[BaseDomainModel],
    metadata: Optional[Dict[str, Any]] = None,
) -> type[BaseDomainModel]:
    """Decorator to register a model class in the global registry.

    Args:
        model_class: The model class to register.
        metadata: Optional metadata associated with the model.

    Returns:
        The registered model class unchanged.

    Example:
        @register_model
        class User(BaseDomainModel):
            name: str
            email: str
    """
    model_registry.register(model_class, metadata)
    return model_class


def get_model(model_name: str) -> type[BaseDomainModel]:
    """Convenience function to retrieve a model from the global registry.

    Args:
        model_name: The name of the model to retrieve.

    Returns:
        The registered model class.

    Raises:
        KeyError: If the model is not found.
    """
    return model_registry.get_model(model_name)


__all__ = [
    "BaseDomainModel",
    "ModelRegistry",
    "model_registry",
    "register_model",
    "get_model",
]