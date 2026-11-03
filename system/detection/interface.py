# -*- coding: utf-8 -*-
# ! python3

"""
Unified IDetector contract for CVCounter.
All object detection architecture adapters implement this contract while retaining
100% backward compatibility with BaseObjectDetectionService.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np

from system.detection.result import DetectionFrameResult
from system.object_detection.base_object_detection import BaseObjectDetectionService, DetectionResult


@dataclass
class ModelInfo:
    """Standardized metadata about a loaded detector model."""

    architecture: str
    model_name: str
    model_variant: str = ""
    version: str = "1.0.0"
    weights_path: Optional[str] = None
    device: str = "cpu"
    inference_backend: str = "pytorch"
    num_classes: int = 0
    classes: dict[int, str] = field(default_factory=dict)
    input_size: tuple[int, int] = (640, 640)
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'architecture': self.architecture,
            'model_name': self.model_name,
            'model_variant': self.model_variant,
            'version': self.version,
            'weights_path': self.weights_path,
            'device': self.device,
            'inference_backend': self.inference_backend,
            'num_classes': self.num_classes,
            'classes': self.classes,
            'input_size': list(self.input_size),
            'parameters': self.parameters,
        }


class IDetector(BaseObjectDetectionService, ABC):
    """
    Unified contract for all object detectors in CVCounter.
    Extends BaseObjectDetectionService for total drop-in backward compatibility.
    """

    @abstractmethod
    def load(self, weights: str, **kwargs) -> None:
        """
        Load model weights, set device and prepare backend resources.

        Args:
            weights (str): Path to model weights or model identifier.
            **kwargs: Configuration parameters (device, conf, iou, input_size, etc.).
        """

    @abstractmethod
    def unload(self) -> None:
        """Release all model resources, clear GPU memory, and reset loaded state."""

    @abstractmethod
    def predict(self, image: np.ndarray, **kwargs) -> DetectionFrameResult:
        """
        Perform object detection on an image frame.

        Args:
            image (np.ndarray): Input image in BGR format (H, W, C).
            **kwargs: Dynamic inference options (confidence, iou, classes_list, etc.).

        Returns:
            DetectionFrameResult: Standardized frame detection result.
        """

    @abstractmethod
    def get_model_info(self) -> ModelInfo:
        """Return standardized information and capabilities of the loaded model."""

    @abstractmethod
    def get_classes(self) -> dict[int, str]:
        """Return class ID to class name mapping."""

    @abstractmethod
    def configure(self, **kwargs) -> None:
        """
        Update runtime detector configuration (e.g. confidence_threshold, iou, input_size).

        Args:
            **kwargs: Parameters to update.
        """

    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if the model is currently loaded in memory and ready for inference."""

    # -------------------------------------------------------------------------
    # Backward compatibility bridges for BaseObjectDetectionService
    # -------------------------------------------------------------------------

    def detect(self, image: np.ndarray, **kwargs) -> DetectionResult:
        """
        Legacy detection interface returning (boxes_xyxy, confidences, classes).
        Directly delegates to predict() and converts to legacy 3-tuple.
        """
        frame_result = self.predict(image, **kwargs)
        return frame_result.to_legacy()

    def load_model(self, weights: str, **kwargs) -> None:
        """Legacy model loading interface delegating to load()."""
        self.load(weights, **kwargs)

    def cleanup(self) -> None:
        """Legacy resource release interface delegating to unload()."""
        self.unload()
