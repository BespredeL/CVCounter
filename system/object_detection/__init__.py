# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from system.object_detection.base_object_detection import (
    BaseObjectDetectionService,
    DetectionBatch,
    DetectionResult,
)
from system.object_detection.registry import (
    available_model_types,
    create_detector,
    get_provider_status,
    get_provider_statuses,
    is_backend_available,
    load_detector,
    register,
    resolve_model_type,
    supported_model_types,
)
from system.object_detection.metadata import (
    extract_model_classes,
    get_model_metadata,
    parse_names_dict,
)
from system.object_detection.model_spec import (
    ModelManifest,
    ModelSpec,
    check_provider_compatibility,
    load_model_manifest,
    resolve_model_spec,
)

__all__ = [
    'BaseObjectDetectionService',
    'DetectionBatch',
    'DetectionResult',
    'ModelManifest',
    'ModelSpec',
    'available_model_types',
    'create_detector',
    'check_provider_compatibility',
    'extract_model_classes',
    'get_provider_status',
    'get_provider_statuses',
    'get_model_metadata',
    'is_backend_available',
    'load_detector',
    'load_model_manifest',
    'parse_names_dict',
    'register',
    'resolve_model_type',
    'resolve_model_spec',
    'supported_model_types',
]
