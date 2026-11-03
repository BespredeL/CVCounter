# -*- coding: utf-8 -*-
# ! python3

"""
Unified IDetector contract and ModelInfo runtime descriptor for CVCounter.
Provides an abstract contract for all object detection architecture adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np

from system.detection.result import DetectionFrameResult


@dataclass
class ModelInfo:
    """Runtime information and capabilities of an active loaded model."""

    architecture: str
    model_name: str
    model_variant: str = ""
    version: str = "1.0.0"
    weights_path: Optional[str] = None
    device: str = "cpu"
    active_provider: str = ""
    inference_backend: str = "pytorch"
    num_classes: int = 0
    classes: dict[int, str] = field(default_factory=dict)
    input_size: tuple[int, int] = (640, 640)
    confidence: float = 0.5
    iou: float = 0.7
    is_loaded: bool = True
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "architecture": self.architecture,
            "model_name": self.model_name,
            "model_variant": self.model_variant,
            "version": self.version,
            "weights_path": self.weights_path,
            "device": self.device,
            "active_provider": self.active_provider,
            "inference_backend": self.inference_backend,
            "num_classes": self.num_classes,
            "classes": self.classes,
            "input_size": list(self.input_size),
            "confidence": self.confidence,
            "iou": self.iou,
            "is_loaded": self.is_loaded,
            "parameters": self.parameters,
        }


class IDetector(ABC):
    """
    Unified standalone contract for all object detectors in CVCounter.
    Fully decoupled from legacy services.
    """

    @abstractmethod
    def unload(self) -> None:
        """Release all model resources, clear GPU memory, and reset loaded state."""
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if the model is currently loaded in memory and ready for inference."""
        pass

    def load_model(self, weights: Union[str, Path], **kwargs: Any) -> None:
        """
        Load model weights, set target device, and initialize backend resources.
        Subclasses may override either load_model() or load().
        """
        if type(self).load is not IDetector.load:
            return self.load(str(weights), **kwargs)
        raise NotImplementedError("IDetector subclasses must implement load_model() or load()")

    def load(self, weights: Union[str, Path], **kwargs: Any) -> None:
        """Alias for load_model()."""
        return self.load_model(weights, **kwargs)

    def detect(self, image: np.ndarray, **kwargs: Any) -> DetectionFrameResult:
        """
        Perform object detection on an image frame.
        Subclasses may override either detect() or predict().
        """
        if type(self).predict is not IDetector.predict:
            return self.predict(image, **kwargs)
        raise NotImplementedError("IDetector subclasses must implement detect() or predict()")

    def predict(self, image: np.ndarray, **kwargs: Any) -> DetectionFrameResult:
        """Alias for detect()."""
        return self.detect(image, **kwargs)

    def model_info(self) -> ModelInfo:
        """
        Return standardized information and capabilities of the loaded model.
        Subclasses may override either model_info() or get_model_info().
        """
        if type(self).get_model_info is not IDetector.get_model_info:
            return self.get_model_info()
        raise NotImplementedError("IDetector subclasses must implement model_info() or get_model_info()")

    def get_model_info(self) -> ModelInfo:
        """Alias for model_info()."""
        return self.model_info()

    def get_classes(self) -> dict[int, str]:
        """Return mapping of class IDs to class names."""
        info = self.model_info()
        return info.classes

    def configure(self, **kwargs: Any) -> None:
        """Update runtime detector configuration."""
        pass

    def warmup(self, input_size: Optional[tuple[int, int]] = None) -> None:
        """Warm up the model with a dummy tensor to stabilize initial inference latency."""
        pass

    def cleanup(self) -> None:
        """Alias for unload()."""
        self.unload()


__all__ = ["IDetector", "ModelInfo"]
