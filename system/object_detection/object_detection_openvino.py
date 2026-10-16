# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 08.10.2026
# Website: https://bespredel.name

"""
Intel OpenVINO backend for high-performance CPU, GPU, and NPU inference.
Licensed under Apache-2.0.
Supports YOLOv5/v8/v9/v10/v11, RT-DETR in .xml/.bin or .onnx formats.
"""

from pathlib import Path
from typing import Optional
from numpy import ndarray

from system.object_detection.base_object_detection import BaseObjectDetectionService, DetectionResult
from system.object_detection.registry import register
from system.object_detection.utils import create_blob, normalize_input_size, parse_yolo_outputs
from system.utils.exception_handler import ModelLoadingError, ModelNotFoundError


@register('openvino')
@register('openvino_dnn')
class ObjectDetectionOpenVINO(BaseObjectDetectionService):
    """
    OpenVINO backend for object detection models.
    Supports Intel CPU, GPU (iGPU/dGPU), and NPU acceleration.
    """

    def __init__(self) -> None:
        self.compiled_model = None
        self.input_layer = None
        self.output_layers = []
        self.confidence = 0.5
        self.iou = 0.7
        self.input_size = (640, 640)
        self.classes_list = None
        self.classes_map: dict[int, str] = {}
        self.is_end2end: Optional[bool] = None
        self.device = 'CPU'

    def detect(self, image: ndarray, **kwargs) -> DetectionResult:
        """
        Detect objects in an image using OpenVINO.

        Args:
            image (ndarray): BGR image frame.

        Returns:
            DetectionResult: (boxes_xyxy, confidences, classes)
        """
        if self.compiled_model is None:
            raise ModelNotFoundError('OpenVINO model is not loaded')

        blob = create_blob(image, self.input_size)
        results = self.compiled_model([blob])
        outputs = [results[out] for out in self.output_layers]

        return parse_yolo_outputs(
            outputs,
            confidence=self.confidence,
            iou=self.iou,
            input_size=self.input_size,
            image_shape=image.shape,
            classes_list=self.classes_list,
            is_end2end=self.is_end2end,
        )

    def load_model(self, weights: str, **kwargs) -> None:
        """
        Load an OpenVINO model from .xml (with .bin) or .onnx weights.

        Args:
            weights (str): Path to model file.
            **kwargs: Additional runtime arguments (device, confidence, iou, etc.).
        """
        if not weights:
            raise ModelNotFoundError('Model weights path is empty')

        path = Path(weights)
        if not path.is_file():
            raise ModelNotFoundError(f"OpenVINO model weights not found: {weights}")

        self.confidence = float(kwargs.get('confidence', 0.5))
        self.iou = float(kwargs.get('iou', 0.7))
        has_custom_size = 'input_size' in kwargs
        self.input_size = normalize_input_size(kwargs.get('input_size', 640))
        self.classes_list = kwargs.get('classes_list', None)
        self.device = self._resolve_device(kwargs.get('device', 'CPU'))

        try:
            import openvino as ov
        except ImportError as exc:
            raise ModelLoadingError(
                "openvino is required for model_type 'openvino'. "
                "Install it via 'pip install openvino'."
            ) from exc

        try:
            core = ov.Core()
            model = core.read_model(str(path))
            self.compiled_model = core.compile_model(model, device_name=self.device)
        except Exception as e:
            raise ModelLoadingError(f"Error loading OpenVINO model from '{weights}': {e}")

        inputs = self.compiled_model.inputs
        outputs = self.compiled_model.outputs
        if not inputs:
            raise ModelLoadingError('OpenVINO model has no input layers')

        self.input_layer = inputs[0]
        self.output_layers = list(outputs)

        # Adapt input size if static shape is available
        if not has_custom_size:
            try:
                shape = list(self.input_layer.shape)
                if len(shape) == 4 and isinstance(shape[2], int) and isinstance(shape[3], int):
                    self.input_size = (shape[3], shape[2])
            except Exception:
                pass

        # Load class names from model metadata or sidecar files
        from system.object_detection.metadata import extract_model_classes
        classes, _ = extract_model_classes(weights)
        self.classes_map = classes or {}

    def get_classes(self) -> dict[int, str]:
        """Return mapping of class IDs to class names."""
        return self.classes_map or {}

    def cleanup(self) -> None:
        """Release OpenVINO resources."""
        self.compiled_model = None
        self.input_layer = None
        self.output_layers = []

    @staticmethod
    def _resolve_device(device_val: Optional[str]) -> str:
        """
        Normalize device name for OpenVINO (CPU, GPU, AUTO, NPU).
        """
        if not device_val:
            return 'CPU'
        val = str(device_val).strip().upper()
        if val in ('CPU', 'GPU', 'GPU.0', 'GPU.1', 'AUTO', 'NPU'):
            return val
        if val.startswith('CUDA') or val.isdigit():
            # If user had CUDA configured, fallback to GPU or CPU in OpenVINO
            return 'GPU' if 'GPU' in val else 'CPU'
        return 'CPU'
