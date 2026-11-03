# -*- coding: utf-8 -*-
# ! python3

"""
Unified Detection Engine Registry for CVCounter.
Provides registration, factory creation, and lifecycle management for all detector adapters.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional, Type

from system.detection.interface import IDetector
from system.utils.exception_handler import ModelLoadingError

logger = logging.getLogger("cvcounter.detection.registry")

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


def register_detector(alias: str, factory: DetectorFactory) -> None:
    norm = alias.strip().lower()
    _DETECTOR_REGISTRY[norm] = factory


def canonical_architecture(arch: Optional[str]) -> str:
    key = (arch or "ultralytics").strip().lower().replace("-", "_")
    return _ARCHITECTURE_ALIASES.get(key, key)


def get_supported_architectures() -> list[str]:
    return sorted(list(set(_ARCHITECTURE_ALIASES.values())))


def create_detector(architecture: str) -> IDetector:
    """Create an uninitialized detector adapter instance by architecture name."""
    canon = canonical_architecture(architecture)

    # Lazy registration of built-in adapters
    if canon not in _DETECTOR_REGISTRY:
        _ensure_builtins_registered()

    factory = _DETECTOR_REGISTRY.get(canon)
    if factory is None:
        supported = ", ".join(get_supported_architectures())
        raise ModelLoadingError(f"Unsupported architecture '{architecture}'. Supported architectures: {supported}")

    return factory()


def resolve_architecture(architecture: Optional[str], weights: Optional[str] = None) -> str:
    """
    Resolve the intended architecture from user parameter or weights file name/extension.
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
    if ext in (".pt", ".engine", ".trt"):
        return "ultralytics"
    if ext == ".onnx":
        return "onnx"

    return "ultralytics"


def load_detector(architecture: Optional[str], weights: Optional[str], **kwargs) -> Optional[IDetector]:
    """
    Instantiate and load a detector for the given architecture and weights.
    Returns None if weights are empty or architecture is 'none'/'preview'.
    """
    if not weights or str(architecture).lower() in ("none", "preview", "passthrough"):
        return None

    resolved_arch = resolve_architecture(architecture, weights)
    detector = create_detector(resolved_arch)
    detector.load(weights, **kwargs)
    return detector


def _ensure_builtins_registered() -> None:
    from system.detection.adapters.ultralytics_adapter import UltralyticsYOLOAdapter
    from system.detection.adapters.rf_detr_adapter import RFDETRAdapter
    from system.detection.adapters.d_fine_adapter import DFINEAdapter
    from system.detection.adapters.rtmdet_adapter import RTMDetAdapter
    from system.detection.adapters.onnx_adapter import GenericONNXAdapter

    register_detector("ultralytics", lambda: UltralyticsYOLOAdapter())
    register_detector("yolo", lambda: UltralyticsYOLOAdapter())
    register_detector("rf_detr", lambda: RFDETRAdapter())
    register_detector("rfdetr", lambda: RFDETRAdapter())
    register_detector("d_fine", lambda: DFINEAdapter())
    register_detector("dfine", lambda: DFINEAdapter())
    register_detector("rtmdet", lambda: RTMDetAdapter())
    register_detector("onnx", lambda: GenericONNXAdapter())
    register_detector("onnxruntime", lambda: GenericONNXAdapter())


# Initialize built-ins immediately
_ensure_builtins_registered()
