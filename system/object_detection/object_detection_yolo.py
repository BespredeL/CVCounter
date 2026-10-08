# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.12.2024
# Updated: 09.06.2026
# Website: https://bespredel.name

import gc
from typing import Optional
from numpy import ndarray

try:
    import torch
except ImportError:
    torch = None

try:
    from ultralytics import YOLO, settings
    _ULTRALYTICS_AVAILABLE = True
except ImportError:
    YOLO = None
    settings = None
    _ULTRALYTICS_AVAILABLE = False

from system.object_detection.base_object_detection import BaseObjectDetectionService, DetectionResult
from system.object_detection.registry import register
from system.utils.exception_handler import ModelLoadingError, ModelNotFoundError
from system.utils.utils import pr_color


@register('yolo')
@register('ultralytics')
class ObjectDetectionYOLO(BaseObjectDetectionService):
    def __init__(self) -> None:
        self.model = None
        self.confidence = 0.5
        self.iou = 0.7
        self.device = 'cpu'
        self.vid_stride = 1
        self.classes_list = None
        self.verbose = False

        if settings is not None:
            try:
                settings.update({'sync': False})
            except Exception:
                pass

    def detect(self, image: ndarray, **kwargs) -> DetectionResult:
        """
        Detect objects in an image.

        Args:
            image: ndarray - The image to detect objects in.
            kwargs: dict - Additional keyword arguments.

        Returns:
            DetectionResult - The detection result.
        """
        if self.model is None:
            raise ModelNotFoundError('Model is not loaded')

        results = self.model.predict(
            image,
            conf=self.confidence,
            iou=self.iou,
            device=self.device,
            vid_stride=self.vid_stride,
            classes=self.classes_list,
            verbose=kwargs.get('verbose', self.verbose),
        )

        boxes = results[0].boxes
        boxes_xyxy = boxes.xyxy.cpu().numpy()
        confidences = boxes.conf.cpu().numpy()
        classes = boxes.cls.cpu().numpy().astype(int)

        return boxes_xyxy, confidences, classes

    def load_model(self, weights: str, **kwargs) -> None:
        """
        Load a model from a weights file.
        
        Args:
            weights: str - The path to the model weights.
            kwargs: dict - Additional keyword arguments.
        
        Returns:
            None
        """
        if not weights:
            raise ModelNotFoundError('Model is not found')

        self.confidence = kwargs.get('confidence', 0.5)
        self.iou = kwargs.get('iou', 0.7)
        self.device = kwargs.get('device', 'cpu')
        self.vid_stride = kwargs.get('vid_stride', 1)
        self.classes_list = kwargs.get('classes_list', None)
        self.verbose = bool(kwargs.get('verbose', kwargs.get('debug', False)))

        if not _ULTRALYTICS_AVAILABLE or YOLO is None:
            raise ModelLoadingError(
                "Ultralytics YOLO backend is not available because the 'ultralytics' package is not installed. "
                "Install it via 'pip install ultralytics' or use model_type='onnx' with ONNX Runtime (MIT)."
            )

        try:
            self.model = YOLO(weights)
        except Exception as e:
            raise ModelLoadingError(f"Error loading model: {e}")

    def get_classes(self) -> dict[int, str]:
        """Return mapping of class IDs to class names from loaded model."""
        if self.model is not None:
            names = getattr(self.model, 'names', None)
            if names and isinstance(names, dict):
                return {int(k): str(v) for k, v in names.items()}
        return {}

    def cleanup(self) -> None:
        """
        Cleanup the model.
        
        Args:
            None

        Returns:
            None
        """
        self.model = None
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
            pr_color("Context cleared", 'green')
