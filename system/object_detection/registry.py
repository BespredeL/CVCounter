# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

import importlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional, Type
from system.object_detection.base_object_detection import BaseObjectDetectionService
from system.utils.exception_handler import ModelLoadingError

DetectorFactory = Callable[[], BaseObjectDetectionService]

""" Registry of object detection backends. """
_REGISTRY: Dict[str, DetectorFactory] = {}


@dataclass(frozen=True)
class BuiltinProvider:
    """Declarative metadata for a built-in inference provider."""

    id: str
    aliases: tuple[str, ...]
    module: str
    dependencies: tuple[str, ...]
    tasks: tuple[str, ...]
    architectures: tuple[str, ...]
    formats: tuple[str, ...]
    decoders: tuple[str, ...] = ()
    optional_dependencies: tuple[str, ...] = ()


_BUILTIN_PROVIDERS = (
    BuiltinProvider(
        'onnxruntime',
        ('onnx', 'onnxruntime'),
        'system.object_detection.object_detection_onnx',
        ('onnxruntime',),
        ('object_detection',),
        ('yolo', 'rt-detr'),
        ('.onnx',),
        ('yolo_outputs',),
    ),
    BuiltinProvider(
        'opencv_dnn',
        ('opencv', 'opencv_dnn'),
        'system.object_detection.object_detection_opencv',
        ('cv2',),
        ('object_detection',),
        ('yolo', 'darknet'),
        ('.onnx', '.pb', 'Darknet .cfg + .weights'),
        ('yolo_outputs',),
    ),
    BuiltinProvider(
        'openvino',
        ('openvino', 'openvino_dnn'),
        'system.object_detection.object_detection_openvino',
        ('openvino',),
        ('object_detection',),
        ('yolo', 'rt-detr'),
        ('.xml', '.bin', '.onnx'),
        ('yolo_outputs',),
    ),
    BuiltinProvider(
        'ultralytics',
        ('yolo', 'ultralytics'),
        'system.object_detection.object_detection_yolo',
        ('torch', 'ultralytics'),
        ('object_detection', 'training', 'export'),
        ('yolo',),
        ('.pt', '.pth', '.engine', '.trt'),
        ('ultralytics_results',),
        ('tensorrt',),
    ),
)
_PROVIDER_BY_ALIAS = {
    alias: provider
    for provider in _BUILTIN_PROVIDERS
    for alias in provider.aliases
}


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


def _has_dependency(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _provider_dependencies_available(model_type: str) -> bool:
    provider = _PROVIDER_BY_ALIAS.get((model_type or '').strip().lower())
    if provider is None:
        return (model_type or '').strip().lower() in _REGISTRY
    return all(_has_dependency(dependency) for dependency in provider.dependencies)


def _ensure_provider_loaded(provider: BuiltinProvider) -> None:
    if all(alias in _REGISTRY for alias in provider.aliases):
        return

    missing = [name for name in provider.dependencies if not _has_dependency(name)]
    if missing:
        raise ModelLoadingError(
            f"Provider '{provider.id}' is unavailable; missing dependencies: {', '.join(missing)}"
        )

    try:
        importlib.import_module(provider.module)
    except Exception as exc:
        raise ModelLoadingError(f"Provider '{provider.id}' failed to load: {exc}") from exc

    missing_aliases = [alias for alias in provider.aliases if alias not in _REGISTRY]
    if missing_aliases:
        raise ModelLoadingError(
            f"Provider '{provider.id}' did not register aliases: {', '.join(missing_aliases)}"
        )


def get_provider_status(model_type: str) -> dict:
    """Return isolated availability and declared capabilities for one provider."""
    normalized = (model_type or '').strip().lower()
    provider = _PROVIDER_BY_ALIAS.get(normalized)
    if provider is None:
        available = normalized in _REGISTRY
        return {
            'id': normalized,
            'aliases': [normalized] if normalized else [],
            'status': 'available' if available else 'unavailable',
            'available': available,
            'dependencies': [],
            'optional_dependencies': {},
            'capabilities': {},
            'error': None if available else f"Unknown provider '{model_type}'",
        }

    dependency_status = {
        dependency: _has_dependency(dependency)
        for dependency in provider.dependencies
    }
    optional_dependency_status = {
        dependency: _has_dependency(dependency)
        for dependency in provider.optional_dependencies
    }
    missing = [name for name, installed in dependency_status.items() if not installed]
    error = None
    status = 'unavailable' if missing else 'available'
    if missing:
        error = f"Missing dependencies: {', '.join(missing)}"
    else:
        try:
            _ensure_provider_loaded(provider)
        except Exception as exc:
            status = 'error'
            error = str(exc)

    available = status == 'available'
    return {
        'id': provider.id,
        'aliases': list(provider.aliases),
        'status': status,
        'available': available,
        'dependencies': dependency_status,
        'optional_dependencies': optional_dependency_status,
        'capabilities': {
            'tasks': list(provider.tasks),
            'architectures': list(provider.architectures),
            'formats': list(provider.formats),
            'decoders': list(provider.decoders),
        },
        'error': error,
    }


def get_provider_statuses() -> list[dict]:
    """Return independent health and capability information for built-in providers."""
    return [get_provider_status(provider.id) for provider in _BUILTIN_PROVIDERS]


def is_backend_available(model_type: str) -> bool:
    """
    Check if dependencies for a specific detection backend are installed.
    """
    norm = (model_type or '').strip().lower()
    return get_provider_status(norm)['available']


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
    if _provider_dependencies_available('yolo'):
        candidates.append(p.with_suffix('.pt'))
    # If ONNX Runtime is available, candidate .onnx
    if _provider_dependencies_available('onnx') or _provider_dependencies_available('opencv'):
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
    return [
        model_type
        for model_type in supported_model_types()
        if model_type != 'auto' and is_backend_available(model_type)
    ]


def supported_model_types() -> list[str]:
    """
    Get a list of all registered model types including 'auto'.
    """
    types = {'auto'} | set(_REGISTRY.keys()) | set(_PROVIDER_BY_ALIAS)
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
        if norm_type in ('yolo', 'ultralytics') and ext == '.onnx' and _provider_dependencies_available('onnx'):
            return 'onnx'
        return norm_type

    # Auto-detection from weights file extension
    if ext == '.onnx':
        if _provider_dependencies_available('onnx'):
            return 'onnx'
        if _provider_dependencies_available('opencv'):
            return 'opencv'
        return 'onnx'

    if ext in ('.weights', '.cfg', '.pb'):
        return 'opencv'

    if ext in ('.xml', '.bin'):
        return 'openvino' if _provider_dependencies_available('openvino') else 'opencv'

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
                return 'onnx' if _provider_dependencies_available('onnx') else 'opencv'
        return 'yolo'

    # Fallback when extension is unknown
    if _provider_dependencies_available('onnx'):
        return 'onnx'
    if _provider_dependencies_available('yolo'):
        return 'yolo'
    if _provider_dependencies_available('opencv'):
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
    provider = _PROVIDER_BY_ALIAS.get(normalized_type)
    if provider is not None:
        _ensure_provider_loaded(provider)
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
