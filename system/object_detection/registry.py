# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
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


def is_tensorrt_available() -> bool:
    """
    Check if dependencies for TensorRT inference are installed and usable.
    """
    try:
        import tensorrt  # noqa: F401
        return True
    except ImportError:
        return False


def find_fallback_weights(weights: Optional[str]) -> Optional[str]:
    """
    Find an alternative weights file (.pt or .onnx) when the requested format
    (e.g., .engine / .trt) cannot be loaded on the current system.
    """
    if not weights:
        return None
    p = Path(weights)
    candidates = []
    # If Ultralytics / YOLO backend is available, prefer .pt
    if is_backend_available('yolo'):
        candidates.append(p.with_suffix('.pt'))
    # If ONNX Runtime is available, candidate .onnx
    if is_backend_available('onnx') or is_backend_available('opencv'):
        candidates.append(p.with_suffix('.onnx'))
    # Also check general .pt / .onnx
    candidates.append(p.with_suffix('.pt'))
    candidates.append(p.with_suffix('.onnx'))

    for cand in candidates:
        if cand.is_file():
            return str(cand)

    # If no file with same stem exists, check common default models in the same directory
    if p.parent.is_dir():
        for fallback_name in ('yolov8n.pt', 'yolo11n.pt', 'yolo11m.pt', 'yolov8n.onnx', 'yolo11n.onnx'):
            cand = p.parent / fallback_name
            if cand.is_file():
                return str(cand)

    return None


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

    if ext in ('.pt', '.pth'):
        return 'yolo'

    if ext in ('.engine', '.trt'):
        if is_tensorrt_available():
            return 'yolo'
        fallback = find_fallback_weights(weights)
        if fallback:
            fb_ext = Path(fallback).suffix.lower()
            if fb_ext in ('.pt', '.pth'):
                return 'yolo'
            elif fb_ext == '.onnx':
                return 'onnx' if is_backend_available('onnx') else 'opencv'
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


def load_detector(model_type: str, weights: str | None, **kwargs) -> BaseObjectDetectionService | None:
    """
    Load a detector instance, automatically resolving 'auto' model_type if needed.
    Returns None if weights is empty or model_type is 'none' / 'preview'.

    Args:
        model_type (str): The model type to load (or 'auto').
        weights (str): The weights to load.
        **kwargs: Additional keyword arguments.

    Returns:
        BaseObjectDetectionService | None: The loaded detector instance or None.
    """
    if not weights or str(model_type).lower() in ('none', 'preview', 'passthrough'):
        return None

    from system.utils.utils import pr_color

    ext = Path(weights).suffix.lower() if weights else ''

    # Guard against .engine / .trt when tensorrt is not installed
    if ext in ('.engine', '.trt') and not is_tensorrt_available():
        fallback = find_fallback_weights(weights)
        if fallback and fallback != weights:
            pr_color(
                f"[WARN] Weights '{weights}' is a TensorRT engine, but module 'tensorrt' is not installed. "
                f"Falling back to '{fallback}'.",
                'yellow'
            )
            weights = fallback
            if model_type == 'auto' or (model_type or '').strip().lower() in ('yolo', 'ultralytics'):
                model_type = 'auto'
        else:
            raise ModelLoadingError(
                f"Model '{weights}' requires the 'tensorrt' package and an NVIDIA GPU, but 'tensorrt' is not installed. "
                f"Please use a .pt or .onnx model."
            )

    resolved_type = resolve_model_type(model_type, weights)
    detector = create_detector(resolved_type)

    try:
        detector.load_model(weights, **kwargs)
    except Exception as e:
        if ext in ('.engine', '.trt'):
            fallback = find_fallback_weights(weights)
            if fallback and fallback != weights:
                pr_color(
                    f"[WARN] Failed to load TensorRT engine '{weights}': {e}. "
                    f"Falling back to '{fallback}'.",
                    'yellow'
                )
                fallback_type = resolve_model_type(model_type, fallback)
                detector = create_detector(fallback_type)
                detector.load_model(fallback, **kwargs)
                return detector
        raise

    return detector
