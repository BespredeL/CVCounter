# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.12.2024
# Updated: 09.06.2026
# Website: https://bespredel.name

from abc import ABC, abstractmethod
from typing import Tuple
from numpy import ndarray

DetectionResult = Tuple[ndarray, ndarray, ndarray]


class BaseObjectDetectionService(ABC):
    """Base class for object detection backends."""

    @abstractmethod
    def detect(self, image: ndarray, **kwargs) -> DetectionResult:
        """
        Detect objects in an image.

        Returns:
            tuple: (boxes_xyxy, confidences, classes)
                - boxes_xyxy: ndarray (N, 4)
                - confidences: ndarray (N,)
                - classes: ndarray (N,) integer class IDs
        """

    @abstractmethod
    def load_model(self, weights: str, **kwargs) -> None:
        """Load model weights and apply runtime settings from kwargs."""

    def cleanup(self) -> None:
        """Release backend resources."""
