# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 20.05.2026
# Updated: 08.10.2026
# Website: https://bespredel.name

from system.object_detection.base_object_detection import BaseObjectDetectionService, DetectionResult
from system.object_detection.registry import (
    available_model_types,
    create_detector,
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

# Safely import backends to populate the registry without failing if optional dependencies are missing.
try:
    from system.object_detection import object_detection_onnx
except Exception:
    pass

try:
    from system.object_detection import object_detection_opencv
except Exception:
    pass

try:
    from system.object_detection import object_detection_yolo
except Exception:
    pass

try:
    from system.object_detection import object_detection_openvino
except Exception:
    pass

__all__ = [
    'BaseObjectDetectionService',
    'DetectionResult',
    'available_model_types',
    'create_detector',
    'extract_model_classes',
    'get_model_metadata',
    'is_backend_available',
    'load_detector',
    'parse_names_dict',
    'register',
    'resolve_model_type',
    'supported_model_types',
]
