# -*- coding: utf-8 -*-
# ! python3

"""
Unified Object Detection Subsystem for CVCounter.
Provides public interfaces, results, registry, and metadata extractors.
"""

from system.detection.interface import IDetector, ModelInfo
from system.detection.result import Detection, DetectionFrameResult
from system.detection.exceptions import (
    DetectionError,
    ModelNotFoundError,
    ModelLoadingError,
    InferenceError,
    UnsupportedModelFormatError,
)
from system.detection.registry import (
    canonical_architecture,
    create_detector,
    find_fallback_weights,
    get_provider_status,
    get_provider_statuses,
    get_supported_architectures,
    is_backend_available,
    is_tensorrt_available,
    load_detector,
    register_detector,
    resolve_architecture,
)
from system.detection.metadata import (
    ModelManifest,
    extract_class_name,
    extract_model_classes,
    load_model_manifest,
    sanitize_classes_list,
)

__all__ = [
    # Contracts & DTOs
    "IDetector",
    "ModelInfo",
    "Detection",
    "DetectionFrameResult",
    "ModelManifest",
    # Registry & Factories
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
    # Metadata
    "extract_class_name",
    "extract_model_classes",
    "load_model_manifest",
    "sanitize_classes_list",
    # Exceptions
    "DetectionError",
    "ModelNotFoundError",
    "ModelLoadingError",
    "InferenceError",
    "UnsupportedModelFormatError",
]
