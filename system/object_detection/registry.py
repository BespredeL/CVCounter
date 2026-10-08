# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 20.05.2026
# Updated: 08.10.2026
# Website: https://bespredel.name

from pathlib import Path
from typing import Callable, Dict, Optional, Type
from system.object_detection.base_object_detection import BaseObjectDetectionService
from system.utils.exception_handler import ModelLoadingError

DetectorFactory = Callable[[], BaseObjectDetectionService]

""" Registry of object detection backends. """
_REGISTRY: Dict[str, DetectorFactory] = {}


def register(model_type: str) -> Callable[[Type[BaseObjectDetectionService]], Type[BaseObjectDetectionService]]:
    """
    Register an object detection backend.

    Usage:
        @register('onnx')
        class ObjectDetectionONNX(BaseObjectDetectionService):
            ...
    """

    normalized_type = model_type.strip().lower()

    def decorator(cls: Type[BaseObjectDetectionService]) -> Type[BaseObjectDetectionService]:
        """
        Decorator to register an object detection backend.
        
        Args:
            cls: Type[BaseObjectDetectionService] - The class to register.
        
        Returns:
            Type[BaseObjectDetectionService]: The registered class.
        """
        if normalized_type in _REGISTRY:
            # Allow re-registering or overriding without crashing
            _REGISTRY[normalized_type] = cls
            return cls
        _REGISTRY[normalized_type] = cls
        return cls

    return decorator


def is_backend_available(model_type: str) -> bool:
    """
    Check if dependencies for a specific detection backend are installed.
    """
    norm = (model_type or '').strip().lower()
    if norm in ('onnx', 'onnxruntime'):
        try:
            import onnxruntime  # noqa: F401
            return True
        except ImportError:
            return False
    elif norm in ('opencv', 'opencv_dnn'):
        try:
            import cv2  # noqa: F401
            return True
        except ImportError:
            return False
    elif norm in ('yolo', 'ultralytics'):
        try:
            from ultralytics import YOLO  # noqa: F401
            return True
        except ImportError:
            return False
    elif norm in ('openvino', 'openvino_dnn'):
        try:
            import openvino  # noqa: F401
            return True
        except ImportError:
            return False
    return norm in _REGISTRY


def available_model_types() -> list[str]:
    """
    Get a list of model types whose runtime dependencies are currently installed.
    """
    return [m for m in sorted(_REGISTRY.keys()) if is_backend_available(m)]


def supported_model_types() -> list[str]:
    """
    Get a list of all registered model types including 'auto'.
    """
    types = {'auto'} | set(_REGISTRY.keys())
    return sorted(types)


def resolve_model_type(model_type: Optional[str] = None, weights: Optional[str] = None) -> str:
    """
    Resolve model_type, supporting 'auto', None, or explicit backend.
    Infers backend from weights extension if 'auto' or unspecified.
    
    Args:
        model_type (Optional[str]): Requested model type, e.g. 'auto', 'onnx', 'yolo'.
        weights (Optional[str]): Path to model weights file.
        
    Returns:
        str: Resolved model type (e.g. 'onnx', 'opencv', 'yolo').
    """
    norm_type = (model_type or 'auto').strip().lower()
    weights_path = Path(weights) if weights else None
    ext = weights_path.suffix.lower() if weights_path else ''

    # If explicit type is provided and not 'auto'
    if norm_type not in ('auto', '', 'none'):
        # Graceful redirect: if user configured 'yolo' but weights is .onnx, use onnx
        if norm_type in ('yolo', 'ultralytics') and ext == '.onnx' and is_backend_available('onnx'):
            return 'onnx'
        return norm_type

    # Auto-detection from weights file extension
    if ext == '.onnx':
        if is_backend_available('onnx'):
            return 'onnx'
        if is_backend_available('opencv'):
            return 'opencv'
        return 'onnx'

    if ext in ('.weights', '.cfg', '.pb'):
        return 'opencv'

    if ext in ('.xml', '.bin'):
        return 'openvino' if is_backend_available('openvino') else 'opencv'

    if ext in ('.pt', '.pth', '.engine', '.trt'):
        return 'yolo'

    # Fallback when extension is unknown
    if is_backend_available('onnx'):
        return 'onnx'
    if is_backend_available('yolo'):
        return 'yolo'
    if is_backend_available('opencv'):
        return 'opencv'

    return 'onnx'


def create_detector(model_type: str) -> BaseObjectDetectionService:
    """
    Create a detector instance by model type.

    Args:
        model_type (str): The model type to create.

    Returns:
        BaseObjectDetectionService: The created detector instance.
    """
    normalized_type = (model_type or '').strip().lower()
    factory = _REGISTRY.get(normalized_type)
    if factory is None:
        supported = ', '.join(supported_model_types()) or 'none'
        raise ModelLoadingError(
            f"Unsupported model_type '{model_type}'. Supported types: {supported}"
        )
    return factory()


def load_detector(model_type: str, weights: str, **kwargs) -> BaseObjectDetectionService:
    """
    Load a detector instance, automatically resolving 'auto' model_type if needed.

    Args:
        model_type (str): The model type to load (or 'auto').
        weights (str): The weights to load.
        **kwargs: Additional keyword arguments.

    Returns:
        BaseObjectDetectionService: The loaded detector instance.
    """
    resolved_type = resolve_model_type(model_type, weights)
    detector = create_detector(resolved_type)
    detector.load_model(weights, **kwargs)
    return detector
