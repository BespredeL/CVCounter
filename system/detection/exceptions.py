# -*- coding: utf-8 -*-
# ! python3

"""Detection subsystem exception hierarchy."""

from typing import Optional
from system.utils.exception_handler import BaseError


class DetectionError(BaseError):
    """Basic object detection subsystem exception (replacement for ObjectDetectionError)."""

    def __init__(self, message: str, errors: Optional[dict] = None, **kwargs):
        super().__init__(message, errors=errors, **kwargs)


class ModelNotFoundError(DetectionError):
    """The scale file was not found or was not accessible."""

    pass


class ModelLoadingError(DetectionError):
    """Scale initialization error or runtime incompatibility."""

    pass


class InferenceError(DetectionError):
    """Error performing inference on frame."""

    pass


class UnsupportedModelFormatError(DetectionError):
    """Attempt to load scales of unsupported format (Darknet .weights/.cfg, OpenVINO IR .xml)."""

    pass


__all__ = [
    "DetectionError",
    "ModelNotFoundError",
    "ModelLoadingError",
    "InferenceError",
    "UnsupportedModelFormatError",
]

