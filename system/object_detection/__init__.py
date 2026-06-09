# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 20.05.2026
# Updated: 09.06.2026
# Website: https://bespredel.name

from system.object_detection.registry import (
    create_detector,
    load_detector,
    register,
    supported_model_types,
)

# Import backends to populate the registry.
from system.object_detection import object_detection_onnx  # noqa: F401
from system.object_detection import object_detection_opencv  # noqa: F401
from system.object_detection import object_detection_yolo  # noqa: F401

__all__ = [
    'create_detector',
    'load_detector',
    'register',
    'supported_model_types',
]
