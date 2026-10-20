# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

import gc
from pathlib import Path
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
        self.weights = None
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

        try:
            results = self.model.predict(
                image,
                conf=self.confidence,
                iou=self.iou,
                device=self.device,
                vid_stride=self.vid_stride,
                classes=self.classes_list,
                verbose=kwargs.get('verbose', self.verbose),
            )
        except Exception as e:
            if hasattr(self, 'weights') and self.weights and Path(self.weights).suffix.lower() in ('.engine', '.trt'):
                from system.object_detection.registry import find_fallback_weights
                fallback = find_fallback_weights(self.weights)
                if fallback and Path(fallback).suffix.lower() == '.pt':
                    pr_color(f"[WARN] TensorRT prediction failed ({e}). Falling back to '{fallback}'...", 'yellow')
                    self.load_model(
                        fallback,
                        confidence=self.confidence,
                        iou=self.iou,
                        device=self.device,
                        vid_stride=self.vid_stride,
                        classes_list=self.classes_list,
                    )
                    results = self.model.predict(
                        image,
                        conf=self.confidence,
                        iou=self.iou,
                        device=self.device,
                        vid_stride=self.vid_stride,
                        classes=self.classes_list,
                        verbose=kwargs.get('verbose', self.verbose),
                    )
                else:
                    raise
            else:
                raise

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

        self.weights = weights
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

        ext = Path(weights).suffix.lower() if weights else ''
        if ext in ('.engine', '.trt'):
            from system.object_detection.registry import is_tensorrt_available, find_fallback_weights
            if not is_tensorrt_available():
                fallback = find_fallback_weights(weights)
                if fallback and Path(fallback).suffix.lower() == '.pt':
                    pr_color(
                        f"[WARN] TensorRT (.engine) is not available ('tensorrt' module not installed). "
                        f"Falling back to '{fallback}'.",
                        'yellow'
                    )
                    weights = fallback
                    self.weights = fallback
                    ext = '.pt'
                else:
                    raise ModelLoadingError(
                        f"Model '{weights}' requires the 'tensorrt' package and NVIDIA GPU. "
                        f"Please use a .pt or .onnx model."
                    )

        try:
            self.model = YOLO(weights)
            # If TensorRT engine, do quick warmup verification to catch missing backend or CUDA mismatch early
            if ext in ('.engine', '.trt'):
                import numpy as np
                dummy = np.zeros((64, 64, 3), dtype=np.uint8)
                self.model.predict(dummy, device=self.device, verbose=False)
        except Exception as e:
            if ext in ('.engine', '.trt'):
                from system.object_detection.registry import find_fallback_weights
                fallback = find_fallback_weights(weights)
                if fallback and Path(fallback).suffix.lower() == '.pt':
                    pr_color(
                        f"[WARN] TensorRT engine '{weights}' failed to initialize ({e}). "
                        f"Falling back to '{fallback}'.",
                        'yellow'
                    )
                    self.model = YOLO(fallback)
                    self.weights = fallback
                    return
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
