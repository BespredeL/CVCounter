# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 20.05.2026
# Updated: 09.06.2026
# Website: https://bespredel.name

from typing import Optional

from numpy import ndarray

from system.object_detection.base_object_detection import BaseObjectDetectionService, DetectionResult
from system.object_detection.registry import register
from system.object_detection.utils import create_blob, normalize_input_size, parse_yolo_outputs
from system.utils.exception_handler import ModelLoadingError, ModelNotFoundError


@register('onnx')
@register('onnxruntime')
class ObjectDetectionONNX(BaseObjectDetectionService):
    """
    ONNX Runtime backend for exported YOLO models.

    Config options (optional):
        input_size: int or [width, height], default 640
        providers: list of ORT providers, e.g. ["CUDAExecutionProvider", "CPUExecutionProvider"]
    """

    def __init__(self) -> None:
        self.session = None
        self.input_name: Optional[str] = None
        self.output_names: list[str] = []
        self.confidence = 0.5
        self.iou = 0.7
        self.input_size = (640, 640)
        self.classes_list = None
        self.providers: list[str] = []

    def detect(self, image: ndarray, **kwargs) -> DetectionResult:
        if self.session is None or self.input_name is None:
            raise ModelNotFoundError('Model is not loaded')

        blob = create_blob(image, self.input_size)
        outputs = self.session.run(self.output_names, {self.input_name: blob})
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

        self.confidence = float(kwargs.get('confidence', 0.5))
        self.iou = float(kwargs.get('iou', 0.7))
        self.input_size = normalize_input_size(kwargs.get('input_size', 640))
        self.classes_list = kwargs.get('classes_list', None)
        self.providers = self._resolve_providers(kwargs.get('providers'), kwargs.get('device'))

        try:
            import onnxruntime as ort
        except ImportError as e:
            raise ModelLoadingError(
                "onnxruntime is required for model_type 'onnx'. Install onnxruntime or onnxruntime-gpu."
            ) from e

        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        try:
            self.session = ort.InferenceSession(
                weights,
                sess_options=session_options,
                providers=self.providers,
            )
        except Exception as e:
            raise ModelLoadingError(f"Error loading ONNX model: {e}")

        inputs = self.session.get_inputs()
        outputs = self.session.get_outputs()
        if not inputs:
            raise ModelLoadingError('ONNX model has no inputs')

        self.input_name = inputs[0].name
        self.output_names = [output.name for output in outputs]

    def cleanup(self) -> None:
        self.session = None
        self.input_name = None
        self.output_names = []

    @staticmethod
    def _resolve_providers(providers: Optional[list], device) -> list[str]:
        if providers:
            return list(providers)

        device_str = str(device).lower()
        use_cuda = device_str not in ('', 'cpu', 'none') and not device_str.startswith('-')
        if use_cuda:
            return ['CUDAExecutionProvider', 'CPUExecutionProvider']
        return ['CPUExecutionProvider']
