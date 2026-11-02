# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple
from numpy import ndarray

DetectionResult = Tuple[ndarray, ndarray, ndarray]


@dataclass(frozen=True)
class DetectionBatch:
    """Named view over the legacy detector tuple; does not alter its consumers."""

    boxes_xyxy: ndarray
    confidences: ndarray
    classes: ndarray

    @classmethod
    def from_legacy(cls, result: DetectionResult | 'DetectionBatch') -> 'DetectionBatch':
        if isinstance(result, cls):
            return result
        boxes, confidences, classes = result
        return cls(boxes, confidences, classes)

    def to_legacy(self) -> DetectionResult:
        return self.boxes_xyxy, self.confidences, self.classes


class BaseObjectDetectionService(ABC):
    """Base class for object detection backends."""

    @abstractmethod
    def detect(self, image: ndarray, **kwargs) -> DetectionResult:
        """
        Detect objects in an image.

        Args:
            image (ndarray): The image to detect objects in.
            **kwargs: Additional keyword arguments.

        Returns:
            tuple: (boxes_xyxy, confidences, classes)
                - boxes_xyxy: ndarray (N, 4)
                - confidences: ndarray (N,)
                - classes: ndarray (N,) integer class IDs
        """

    @abstractmethod
    def load_model(self, weights: str, **kwargs) -> None:
        """
        Load model weights and apply runtime settings from kwargs.
        
        Args:
            weights (str): The path to the model weights.
            **kwargs: Additional keyword arguments.

        Returns:
            None
        """

    def cleanup(self) -> None:
        """
        Release backend resources.
        
        Args:
            None

        Returns:
            None
        """

    def get_classes(self) -> dict[int, str]:
        """
        Return mapping of class IDs to class names if available.

        Returns:
            dict[int, str]: Mapping of integer class IDs to class names, or empty dict.
        """
        return getattr(self, 'classes_map', {}) or {}
