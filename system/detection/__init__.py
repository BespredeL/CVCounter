# -*- coding: utf-8 -*-
# ! python3

from system.detection.interface import IDetector, ModelInfo
from system.detection.result import Detection, DetectionFrameResult
from system.detection.registry import (
    canonical_architecture,
    create_detector,
    get_supported_architectures,
    load_detector,
    register_detector,
    resolve_architecture,
)

__all__ = [
    'IDetector',
    'ModelInfo',
    'Detection',
    'DetectionFrameResult',
    'canonical_architecture',
    'create_detector',
    'get_supported_architectures',
    'load_detector',
    'register_detector',
    'resolve_architecture',
]
