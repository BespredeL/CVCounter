# -*- coding: utf-8 -*-
# ! python3

"""
Unified Detection Engine Registry for CVCounter.
Provides registration, factory creation, provider telemetry, and lifecycle management
for all detector adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Type, Union

from system.detection.exceptions import (
    DetectionError,
    ModelLoadingError,
    ModelNotFoundError,
    UnsupportedModelFormatError,
)
from system.detection.interface import IDetector
from system.utils.logger import Logger

logger = Logger()

DetectorFactory = Callable[[], IDetector]

_DETECTOR_REGISTRY: dict[str, DetectorFactory] = {}

_ARCHITECTURE_ALIASES: dict[str, str] = {
    "yolo": "ultralytics",
    "ultralytics": "ultralytics",
    "rf_detr": "rf_detr",
    "rfdetr": "rf_detr",
    "rf-detr": "rf_detr",
    "d_fine": "d_fine",
    "dfine": "d_fine",
    "d-fine": "d_fine",
    "rtmdet": "rtmdet",
    "rtm-det": "rtmdet",
    "onnx": "onnx",
    "onnxruntime": "onnx",
}


@dataclass(frozen=True)
class BuiltinProvider:
    """Declarative metadata for a built-in detection provider."""

    id: str
    aliases: tuple[str, ...]
    dependencies: tuple[str, ...]
    optional_dependencies: tuple[str, ...] = ()
    tasks: tuple[str, ...] = ("object_detection",)
    architectures: tuple[str, ...] = ()
    formats: tuple[str, ...] = ()


_BUILTIN_PROVIDERS: tuple[BuiltinProvider, ...] = (
    BuiltinProvider(
        id="ultralytics",
        aliases=("yolo", "ultralytics"),
        dependencies=("torch", "ultralytics"),
        optional_dependencies=("tensorrt",),
        tasks=("object_detection", "training", "export"),
        architectures=("yolo",),
        formats=(".pt", ".pth", ".engine", ".trt"),
    ),
    BuiltinProvider(
        id="onnxruntime",
        aliases=("onnx", "onnxruntime"),
        dependencies=("onnxruntime",),
        optional_dependencies=("onnx", "onnxslim"),
        tasks=("object_detection",),
        architectures=("yolo", "rf_detr", "d_fine", "rtmdet"),
        formats=(".onnx",),
    ),
    BuiltinProvider(
        id="rf_detr",
        aliases=("rf_detr", "rfdetr", "rf-detr"),
        dependencies=("torch", "rfdetr"),
        optional_dependencies=(),
        tasks=("object_detection",),
        architectures=("rf_detr",),
        formats=(".pth", ".pt", ".onnx"),
    ),
    BuiltinProvider(
        id="d_fine",
        aliases=("d_fine", "dfine", "d-fine"),
        dependencies=("torch",),
        optional_dependencies=(),
        tasks=("object_detection",),
        architectures=("d_fine",),
        formats=(".pth", ".pt", ".onnx"),
    ),
    BuiltinProvider(
        id="rtmdet",
        aliases=("rtmdet", "rtm-det"),
        dependencies=("torch", "mmdet"),
        optional_dependencies=("mmcv",),
        tasks=("object_detection",),
        architectures=("rtmdet",),
        formats=(".pth", ".onnx"),
    ),
)

_PROVIDER_BY_ALIAS: dict[str, BuiltinProvider] = {
    alias: provider
    for provider in _BUILTIN_PROVIDERS
    for alias in provider.aliases
}


def _has_dependency(module_name: str) -> bool:
    """Check if a Python package or module is importable."""
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def is_backend_available(model_type: str) -> bool:
    """Check if runtime dependencies for an architecture or provider are installed for inference."""
    norm = (model_type or "").strip().lower()
    return bool(get_provider_status(norm).get("inference_available", False))


def is_tensorrt_available() -> bool:
    """Check if TensorRT is installed and usable."""
    return _has_dependency("tensorrt")


def get_provider_status(model_type: str) -> dict[str, Any]:
    """Return availability and declared capabilities for one provider."""
    normalized = (model_type or "").strip().lower()
    provider = _PROVIDER_BY_ALIAS.get(normalized)

    # Check if adapter is registered in _DETECTOR_REGISTRY
    adapter_registered = (
        normalized in _DETECTOR_REGISTRY
        or (provider is not None and any(a in _DETECTOR_REGISTRY for a in provider.aliases))
        or (provider is not None and provider.id in _DETECTOR_REGISTRY)
    )

    if provider is None:
        available = adapter_registered
        return {
            "id": normalized,
            "aliases": [normalized] if normalized else [],
            "status": "available" if available else "unavailable",
            "available": available,
            "architecture_registered": adapter_registered,
            "adapter_registered": adapter_registered,
            "backend_available": _has_dependency("torch"),
            "inference_available": available,
            "inference_supported": available,
            "dependencies": {},
            "optional_dependencies": {},
            "capabilities": {
                "architecture_registered": adapter_registered,
                "adapter_registered": adapter_registered,
                "backend_available": _has_dependency("torch"),
                "inference_available": available,
                "inference_supported": available,
            },
            "error": None if available else f"Unknown provider '{model_type}'",
        }

    dep_status = {dep: _has_dependency(dep) for dep in provider.dependencies}
    opt_dep_status = {dep: _has_dependency(dep) for dep in provider.optional_dependencies}
    missing = [name for name, installed in dep_status.items() if not installed]

    architecture_registered = True
    backend_available = _has_dependency("torch") if ("torch" in provider.dependencies or "torch" in provider.optional_dependencies) else _has_dependency("onnxruntime")
    inference_available = adapter_registered and (len(missing) == 0)
    available = inference_available

    return {
        "id": provider.id,
        "aliases": list(provider.aliases),
        "status": "available" if inference_available else "unavailable",
        "available": available,
        "architecture_registered": architecture_registered,
        "adapter_registered": adapter_registered,
        "backend_available": backend_available,
        "inference_available": inference_available,
        "inference_supported": inference_available,
        "dependencies": dep_status,
        "optional_dependencies": opt_dep_status,
        "capabilities": {
            "tasks": list(provider.tasks),
            "architectures": list(provider.architectures),
            "formats": list(provider.formats),
            "architecture_registered": architecture_registered,
            "adapter_registered": adapter_registered,
            "backend_available": backend_available,
            "inference_available": inference_available,
            "inference_supported": inference_available,
        },
        "error": f"Missing dependencies: {', '.join(missing)}" if missing else None,
    }


def get_provider_statuses() -> list[dict[str, Any]]:
    """Return health and capability information for all built-in detection providers."""
    return [get_provider_status(provider.id) for provider in _BUILTIN_PROVIDERS]


def find_fallback_weights(weights: Optional[str]) -> Optional[str]:
    """
    Find an alternative weights file (.pt or .onnx) when the requested format
    (e.g., .engine / .trt) cannot be loaded on the current system.
    """
    if not weights:
        return None
    p = Path(weights)
    candidates: list[Path] = []

    # Check same stem with .pt or .onnx
    candidates.append(p.with_suffix(".pt"))
    candidates.append(p.with_suffix(".onnx"))

    for cand in candidates:
        if cand.is_file():
            return str(cand)

    # Check common default models in the parent folder
    if p.parent.is_dir():
        for fallback_name in (
            "yolo26n.pt",
            "yolo11n.pt",
            "yolov8n.pt",
            "yolo26n.onnx",
            "yolo11n.onnx",
            "yolov8n.onnx",
        ):
            cand = p.parent / fallback_name
            if cand.is_file():
                return str(cand)

    return None


def register_detector(alias: str, factory: DetectorFactory) -> None:
    """Register a factory for an architecture alias."""
    norm = alias.strip().lower()
    _DETECTOR_REGISTRY[norm] = factory


def canonical_architecture(arch: Optional[str]) -> str:
    """Resolve architecture alias to canonical internal name."""
    key = (arch or "ultralytics").strip().lower().replace("-", "_")
    return _ARCHITECTURE_ALIASES.get(key, key)


def get_supported_architectures() -> list[str]:
    """Return list of supported architecture identifiers including 'auto' and aliases."""
    return sorted(list({"auto", *set(_ARCHITECTURE_ALIASES.keys()), *set(_ARCHITECTURE_ALIASES.values())}))


def create_detector(architecture: str) -> IDetector:
    """Create an uninitialized detector adapter instance by architecture name."""
    canon = canonical_architecture(architecture)

    if canon not in _DETECTOR_REGISTRY:
        _ensure_builtins_registered()

    factory = _DETECTOR_REGISTRY.get(canon)
    if factory is None:
        supported = ", ".join(get_supported_architectures())
        raise ModelLoadingError(
            f"Unsupported architecture '{architecture}'. Supported architectures: {supported}"
        )

    return factory()


def resolve_architecture(architecture: Optional[str] = None, weights: Optional[str] = None) -> str:
    """
    Resolve the intended architecture from user parameter or weights filename / extension.
    """
    arch = (architecture or "").strip().lower()
    if arch and arch not in ("auto", "none", "preview"):
        return canonical_architecture(arch)

    if not weights:
        return "ultralytics"

    w_lower = Path(weights).name.lower()

    if "rf" in w_lower and "detr" in w_lower:
        return "rf_detr"
    if "dfine" in w_lower or "d_fine" in w_lower or "d-fine" in w_lower:
        return "d_fine"
    if "rtmdet" in w_lower:
        return "rtmdet"

    ext = Path(weights).suffix.lower()
    if ext in (".pt", ".pth", ".engine", ".trt"):
        return "ultralytics"
    if ext == ".onnx":
        return "onnx"

    return "ultralytics"


def load_detector(
    architecture: Optional[str] = None,
    weights: Optional[str] = None,
    **kwargs: Any,
) -> Optional[IDetector]:
    """
    Instantiate and load a detector for the given architecture and weights.

    Args:
        architecture: Architecture alias ('yolo', 'ultralytics', 'onnx', 'rf_detr', 'd_fine', 'rtmdet')
                      or 'auto'.
        weights: Path to model weights file.
        **kwargs: Runtime parameters (confidence, iou, device, providers, etc.).

    Returns:
        Loaded IDetector instance, or None if weights are empty or architecture is 'none'/'preview'.

    Raises:
        UnsupportedModelFormatError: If an obsolete format (.weights, .cfg, .xml) is passed.
        ModelNotFoundError: If weights file does not exist.
        ModelLoadingError: If initialization fails.
    """
    # Backward compatibility: accept model_type as alias for architecture
    if architecture is None and "model_type" in kwargs:
        architecture = kwargs.pop("model_type")

    if not weights or str(architecture).lower() in ("none", "preview", "passthrough"):
        return None

    path = Path(weights)
    ext = path.suffix.lower()

    # Reject obsolete formats per architecture audit
    if ext in (".weights", ".cfg", ".pb"):
        raise UnsupportedModelFormatError(
            f"Darknet / OpenCV format '{weights}' (.weights, .cfg) is discontinued and not supported. "
            f"Please convert your model to ONNX (.onnx) or PyTorch (.pt) format."
        )

    if ext in (".xml", ".bin"):
        raise UnsupportedModelFormatError(
            f"Intel OpenVINO IR format '{weights}' (.xml, .bin) is discontinued. "
            f"Please convert your model to ONNX format to leverage OpenVINOExecutionProvider via ONNX Runtime."
        )

    # TensorRT engine check and automatic fallback
    if ext in (".engine", ".trt") and not is_tensorrt_available():
        fallback = find_fallback_weights(str(weights))
        if fallback and fallback != str(weights):
            logger.warning(
                f"Weights '{weights}' is a TensorRT engine, but 'tensorrt' package is not installed. "
                f"Falling back to '{fallback}'."
            )
            weights = fallback
            ext = Path(weights).suffix.lower()
            if architecture in ("auto", None):
                architecture = "auto"
        else:
            raise ModelLoadingError(
                f"Model '{weights}' requires 'tensorrt' package and NVIDIA GPU, but 'tensorrt' is not installed. "
                f"Please install TensorRT or provide a .pt / .onnx model."
            )

    resolved_arch = resolve_architecture(architecture, str(weights))
    detector = create_detector(resolved_arch)

    try:
        detector.load_model(str(weights), **kwargs)
    except Exception as exc:
        if ext in (".engine", ".trt"):
            fallback = find_fallback_weights(str(weights))
            if fallback and fallback != str(weights):
                logger.warning(
                    f"Failed to load TensorRT engine '{weights}': {exc}. "
                    f"Falling back to '{fallback}'."
                )
                fb_arch = resolve_architecture(architecture, fallback)
                detector = create_detector(fb_arch)
                detector.load_model(fallback, **kwargs)
                return detector
        raise

    return detector


def _ensure_builtins_registered() -> None:
    from system.detection.adapters.yolo_adapter import YOLOAdapter
    from system.detection.adapters.rf_detr_adapter import RFDETRAdapter
    from system.detection.adapters.d_fine_adapter import DFINEAdapter
    from system.detection.adapters.rtmdet_adapter import RTMDetAdapter
    from system.detection.adapters.onnx_adapter import GenericONNXAdapter

    register_detector("ultralytics", lambda: YOLOAdapter())
    register_detector("yolo", lambda: YOLOAdapter())
    register_detector("rf_detr", lambda: RFDETRAdapter())
    register_detector("rfdetr", lambda: RFDETRAdapter())
    register_detector("d_fine", lambda: DFINEAdapter())
    register_detector("dfine", lambda: DFINEAdapter())
    register_detector("rtmdet", lambda: RTMDetAdapter())
    register_detector("onnx", lambda: GenericONNXAdapter())
    register_detector("onnxruntime", lambda: GenericONNXAdapter())


# Initialize built-ins immediately
_ensure_builtins_registered()

__all__ = [
    "canonical_architecture",
    "create_detector",
    "find_fallback_weights",
    "get_provider_status",
    "get_provider_statuses",
    "get_supported_architectures",
    "is_backend_available",
    "is_tensorrt_available",
    "load_detector",
    "register_detector",
    "resolve_architecture",
]
