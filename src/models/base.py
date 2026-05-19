"""Base model class for all machine learning models in the system."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Tuple, TypeVar, Union
import json
import pickle
from pathlib import Path
import logging
from datetime import datetime
import numpy as np

from src.exceptions import ModelError, ModelNotTrainedError, ModelSerializationError

logger = logging.getLogger(__name__)

T = TypeVar('T')
PredictionType = TypeVar('PredictionType')
FeatureType = TypeVar('FeatureType')
TargetType = TypeVar('TargetType')


class BaseModel(ABC, Generic[FeatureType, TargetType, PredictionType]):
    """Abstract base class for all machine learning models.
    
    This class provides a standardized interface for model training, prediction,
    serialization, and evaluation. All concrete model implementations should
    inherit from this class and implement the abstract methods.
    
    Attributes:
        model_id: Unique identifier for the model instance.
        model_name: Human-readable name of the model.
        version: Version string for the model.
        is_trained: Boolean flag indicating if the model has been trained.
        training_metadata: Dictionary containing training metadata.
        created_at: Timestamp of model creation.
        updated_at: Timestamp of last update.
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        model_name: str = "base_model",
        version: str = "1.0.0",
        hyperparameters: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize the base model.
        
        Args:
            model_id: Unique identifier. If None, generates one based on timestamp.
            model_name: Human-readable name for the model.
            version: Version string for the model.
            hyperparameters: Dictionary of model hyperparameters.
            
        Raises:
            ValueError: If model_name is empty or version is invalid.
        """
        if not model_name or not isinstance(model_name, str):
            raise ValueError("model_name must be a non-empty string")
        
        if not version or not isinstance(version, str):
            raise ValueError("version must be a non-empty string")
        
        self.model_id: str = model_id or f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self.model_name: str = model_name
        self.version: str = version
        self.hyperparameters: Dict[str, Any] = hyperparameters or {}
        self.is_trained: bool = False
        self.training_metadata: Dict[str, Any] = {}
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()
        self._model: Any = None
        self._feature_names: Optional[List[str]] = None
        self._target_name: Optional[str] = None
        
        logger.info(f"Initialized {self.model_name} model with ID: {self.model_id}")

    @abstractmethod
    def train(
        self,
        features: FeatureType,
        targets: TargetType,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Train the model on provided data.
        
        Args:
            features: Training features/data.
            targets: Training targets/labels.
            **kwargs: Additional training parameters.
            
        Returns:
            Dictionary containing training metrics and metadata.
            
        Raises:
            ValueError: If features or targets are invalid.
            ModelError: If training fails.
        """
        pass

    @abstractmethod
    def predict(
        self,
        features: FeatureType,
        **kwargs: Any
    ) -> PredictionType:
        """Make predictions using the trained model.
        
        Args:
            features: Features for prediction.
            **kwargs: Additional prediction parameters.
            
        Returns:
            Model predictions.
            
        Raises:
            ModelNotTrainedError: If model hasn't been trained.
            ValueError: If features are invalid.
            ModelError: If prediction fails.
        """
        pass

    @abstractmethod
    def evaluate(
        self,
        features: FeatureType,
        targets: TargetType,
        **kwargs: Any
    ) -> Dict[str, float]:
        """Evaluate model performance on test data.
        
        Args:
            features: Test features.
            targets: Test targets.
            **kwargs: Additional evaluation parameters.
            
        Returns:
            Dictionary of evaluation metrics.
            
        Raises:
            ModelNotTrainedError: If model hasn't been trained.
            ValueError: If features or targets are invalid.
            ModelError: If evaluation fails.
        """
        pass

    def save(self, filepath: Union[str, Path]) -> Path:
        """Save the model to disk.
        
        Args:
            filepath: Path where to save the model.
            
        Returns:
            Path to the saved model file.
            
        Raises:
            ModelNotTrainedError: If model hasn't been trained.
            ModelSerializationError: If saving fails.
        """
        if not self.is_trained:
            raise ModelNotTrainedError(
                f"Cannot save untrained model: {self.model_name}"
            )
        
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            model_data = {
                'model_id': self.model_id,
                'model_name': self.model_name,
                'version': self.version,
                'hyperparameters': self.hyperparameters,
                'is_trained': self.is_trained,
                'training_metadata': self.training_metadata,
                'created_at': self.created_at.isoformat(),
                'updated_at': self.updated_at.isoformat(),
                'feature_names': self._feature_names,
                'target_name': self._target_name,
                'model': self._serialize_model()
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"Model saved to {filepath}")
            return filepath
            
        except Exception as e:
            raise ModelSerializationError(
                f"Failed to save model to {filepath}: {str(e)}"
            ) from e

    def load(self, filepath: Union[str, Path]) -> 'BaseModel':
        """Load a model from disk.
        
        Args:
            filepath: Path to the saved model file.
            
        Returns:
            Loaded model instance.
            
        Raises:
            ModelSerializationError: If loading fails.
            FileNotFoundError: If file doesn't exist.
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)
            
            self.model_id = model_data['model_id']
            self.model_name = model_data['model_name']
            self.version = model_data['version']
            self.hyperparameters = model_data['hyperparameters']
            self.is_trained = model_data['is_trained']
            self.training_metadata = model_data['training_metadata']
            self.created_at = datetime.fromisoformat(model_data['created_at'])
            self.updated_at = datetime.fromisoformat(model_data['updated_at'])
            self._feature_names = model_data['feature_names']
            self._target_name = model_data['target_name']
            self._deserialize_model(model_data['model'])
            
            logger.info(f"Model loaded from {filepath}")
            return self
            
        except Exception as e:
            raise ModelSerializationError(
                f"Failed to load model from {filepath}: {str(e)}"
            ) from e

    def save_metadata(self, filepath: Union[str, Path]) -> Path:
        """Save model metadata as JSON.
        
        Args:
            filepath: Path where to save metadata.
            
        Returns:
            Path to the saved metadata file.
            
        Raises:
            ModelSerializationError: If saving fails.
        """
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            metadata = {
                'model_id': self.model_id,
                'model_name': self.model_name,
                'version': self.version,
                'hyperparameters': self.hyperparameters,
                'is_trained': self.is_trained,
                'training_metadata': self.training_metadata,
                'created_at': self.created_at.isoformat(),
                'updated_at': self.updated_at.isoformat(),
                'feature_names': self._feature_names,
                'target_name': self._target_name
            }
            
            with open(filepath, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Metadata saved to {filepath}")
            return filepath
            
        except Exception as e:
            raise ModelSerializationError(
                f"Failed to save metadata to {filepath}: {str(e)}"
            ) from e

    def get_params(self) -> Dict[str, Any]:
        """Get model parameters.
        
        Returns:
            Dictionary of model parameters.
        """
        return {
            'model_id': self.model_id,
            'model_name': self.model_name,
            'version': self.version,
            'hyperparameters': self.hyperparameters,
            'is_trained': self.is_trained,
            'feature_names': self._feature_names,
            'target_name': self._target_name
        }

    def set_params(self, **params: Any) -> None:
        """Set model parameters.
        
        Args:
            **params: Parameters to set.
            
        Raises:
            ValueError: If parameter name is invalid.
        """
        valid_params = {
            'hyperparameters', 'feature_names', 'target_name'
        }
        
        for key, value in params.items():
            if key not in valid_params:
                raise ValueError(f"Invalid parameter name: {key}")
            
            if key == 'hyperparameters':
                self.hyperparameters = value
            elif key == 'feature_names':
                self._feature_names = value
            elif key == 'target_name':
                self._target_name = value
        
        self.updated_at = datetime.now()

    def _validate_features(self, features: FeatureType) -> None:
        """Validate input features.
        
        Args:
            features: Features to validate.
            
        Raises:
            ValueError: If features are invalid.
        """
        if features is None:
            raise ValueError("Features cannot be None")
        
        if isinstance(features, (list, np.ndarray)) and len(features) == 0:
            raise ValueError("Features cannot be empty")

    def _validate_targets(self, targets: TargetType) -> None:
        """Validate target values.
        
        Args:
            targets: Targets to validate.
            
        Raises:
            ValueError: If targets are invalid.
        """
        if targets is None:
            raise ValueError("Targets cannot be None")
        
        if isinstance(targets, (list, np.ndarray)) and len(targets) == 0:
            raise ValueError("Targets cannot be empty")

    def _check_trained(self) -> None:
        """Check if model is trained.
        
        Raises:
            ModelNotTrainedError: If model hasn't been trained.
        """
        if not self.is_trained:
            raise ModelNotTrainedError(
                f"Model {self.model_name} has not been trained yet"
            )

    def _serialize_model(self) -> bytes:
        """Serialize the internal model.
        
        Returns:
            Serialized model bytes.
            
        Raises:
            ModelSerializationError: If serialization fails.
        """
        try:
            return pickle.dumps(self._model)
        except Exception as e:
            raise ModelSerializationError(
                f"Failed to serialize model: {str(e)}"
            ) from e

    def _deserialize_model(self, model_bytes: bytes) -> None:
        """Deserialize the internal model.
        
        Args:
            model_bytes: Serialized model bytes.
            
        Raises:
            ModelSerializationError: If deserialization fails.
        """
        try:
            self._model = pickle.loads(model_bytes)
        except Exception as e:
            raise ModelSerializationError(
                f"Failed to deserialize model: {str(e)}"
            ) from e

    def __str__(self) -> str:
        """String representation of the model."""
        return (
            f"{self.model_name}(id={self.model_id}, "
            f"version={self.version}, "
            f"trained={self.is_trained})"
        )

    def __repr__(self) -> str:
        """Detailed string representation of the model."""
        return (
            f"{self.__class__.__name__}("
            f"model_id='{self.model_id}', "
            f"model_name='{self.model_name}', "
            f"version='{self.version}', "
            f"hyperparameters={self.hyperparameters}, "
            f"is_trained={self.is_trained})"
        )