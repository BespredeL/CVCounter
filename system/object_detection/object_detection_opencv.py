# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 22.05.2026
# Updated: 09.06.2026
# Website: https://bespredel.name

import os
from typing import Optional
import cv2
from numpy import ndarray
from system.object_detection.base_object_detection import BaseObjectDetectionService, DetectionResult
from system.object_detection.registry import register
from system.object_detection.utils import create_blob, normalize_input_size, parse_yolo_outputs
from system.utils.exception_handler import ModelLoadingError, ModelNotFoundError


@register('opencv')
@register('opencv_dnn')
class ObjectDetectionOpenCV(BaseObjectDetectionService):
    """
    OpenCV DNN backend for ONNX, Darknet and other DNN-supported formats.

    Config options (optional):
        model_config_path: path to .cfg for Darknet models
        input_size: int or [width, height], default 640
        backend: OpenCV DNN backend constant name, e.g. OPENCV, CUDA
        target: OpenCV DNN target constant name, e.g. CPU, CUDA
    """

    _BACKEND_MAP = {
        'DEFAULT': cv2.dnn.DNN_BACKEND_DEFAULT,
        'OPENCV': cv2.dnn.DNN_BACKEND_OPENCV,
        'CUDA': cv2.dnn.DNN_BACKEND_CUDA,
        'TIMVX': cv2.dnn.DNN_BACKEND_TIMVX,
        'CANN': cv2.dnn.DNN_BACKEND_CANN,
    }
    _TARGET_MAP = {
        'CPU': cv2.dnn.DNN_TARGET_CPU,
        'OPENCL': cv2.dnn.DNN_TARGET_OPENCL,
        'OPENCL_FP16': cv2.dnn.DNN_TARGET_OPENCL_FP16,
        'MYRIAD': cv2.dnn.DNN_TARGET_MYRIAD,
        'VULKAN': cv2.dnn.DNN_TARGET_VULKAN,
        'CUDA': cv2.dnn.DNN_TARGET_CUDA,
        'CUDA_FP16': cv2.dnn.DNN_TARGET_CUDA_FP16,
        'NPU': cv2.dnn.DNN_TARGET_NPU,
    }

    def __init__(self) -> None:
        self.net: Optional[cv2.dnn.Net] = None
        self.confidence = 0.5
        self.iou = 0.7
        self.input_size = (640, 640)
        self.classes_list = None
        self.output_layer_names: list[str] = []

    def detect(self, image: ndarray, **kwargs) -> DetectionResult:
        if self.net is None:
            raise ModelNotFoundError('Model is not loaded')

        blob = create_blob(image, self.input_size)
        self.net.setInput(blob)
        outputs = self.net.forward(self.output_layer_names)
        return parse_yolo_outputs(
            outputs,
            confidence=self.confidence,
            iou=self.iou,
            input_size=self.input_size,
            image_shape=image.shape,
            classes_list=self.classes_list,
        )

    def load_model(self, weights: str, **kwargs) -> None:
        if not weights:
            raise ModelNotFoundError('Model is not found')
        if not os.path.exists(weights):
            raise ModelNotFoundError(f"Model weights not found: {weights}")

        self.confidence = float(kwargs.get('confidence', 0.5))
        self.iou = float(kwargs.get('iou', 0.7))
        self.input_size = normalize_input_size(kwargs.get('input_size', 640))
        self.classes_list = kwargs.get('classes_list', None)

        config_path = kwargs.get('model_config_path') or kwargs.get('config_path')
        weights_lower = weights.lower()

        try:
            if config_path:
                self.net = cv2.dnn.readNetFromDarknet(config_path, weights)
            elif weights_lower.endswith('.onnx'):
                self.net = cv2.dnn.readNetFromONNX(weights)
            elif weights_lower.endswith('.pb'):
                self.net = cv2.dnn.readNetFromTensorflow(weights)
            else:
                raise ModelLoadingError(
                    "OpenCV DNN requires ONNX/PB weights or Darknet pair "
                    "(weights_path + model_config_path)"
                )
        except ModelLoadingError:
            raise
        except Exception as e:
            raise ModelLoadingError(f"Error loading OpenCV DNN model: {e}")

        backend = self._resolve_dnn_option(kwargs.get('backend'), self._BACKEND_MAP, 'backend')
        target = self._resolve_dnn_option(kwargs.get('target'), self._TARGET_MAP, 'target')
        if backend is not None:
            self.net.setPreferableBackend(backend)
        if target is not None:
            self.net.setPreferableTarget(target)

        self.output_layer_names = self.net.getUnconnectedOutLayersNames()

    def cleanup(self) -> None:
        self.net = None
        self.output_layer_names = []

    @classmethod
    def _resolve_dnn_option(cls, value: Optional[str], mapping: dict, option_name: str) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        key = str(value).strip().upper()
        if key not in mapping:
            supported = ', '.join(sorted(mapping.keys()))
            raise ModelLoadingError(f"Unsupported OpenCV DNN {option_name}: '{value}'. Expected one of: {supported}")
        return mapping[key]
