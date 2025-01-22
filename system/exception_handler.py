# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.12.2024
# Updated: 26.12.2024
# Website: https://bespredel.name

from typing import Optional


# --------------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------------

class BaseError(Exception):
    """Base class for exceptions."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message)
        self.message = message
        self.details = kwargs

    def __str__(self):
        return f"{self.message}. Details: {self.details}" if self.details else self.message


# --------------------------------------------------------------------------------
# Configuration Exceptions
# --------------------------------------------------------------------------------

class ConfigError(BaseError):
    """Base class for configuration-related exceptions."""

    def __init__(self, filepath: str):
        super().__init__(f"Configuration file '{filepath}' not found", filepath=filepath)


class ConfigNotFoundError(BaseError):
    """Raised when the configuration file is not found."""

    def __init__(self, filepath: str):
        super().__init__(f"Configuration file '{filepath}' not found", filepath=filepath)


class InvalidConfigError(BaseError):
    """Raised when the configuration file contains invalid data."""

    def __init__(self, message: str, errors: Optional[dict] = None):
        super().__init__(message, errors=errors)


# --------------------------------------------------------------------------------
# Notification Exceptions
# --------------------------------------------------------------------------------

class NotificationError(BaseError):
    """Base class for all notification-related errors."""

    def __init__(self, message: str, errors: Optional[dict] = None):
        super().__init__(message, errors=errors)


class MissingSocketInstanceError(NotificationError):
    """Raised when the socketio instance is not provided."""

    def __init__(self, message: str, errors: Optional[dict] = None):
        super().__init__(message, errors=errors)


class InvalidLocationError(NotificationError):
    """Raised when the location is not a valid string."""

    def __init__(self, message: str, errors: Optional[dict] = None):
        super().__init__(message, errors=errors)


# --------------------------------------------------------------------------------
# VideoStream Exceptions
# --------------------------------------------------------------------------------

class VideoStreamError(BaseError):
    """Base class for all video stream-related errors."""

    def __init__(self, message: str, errors: Optional[dict] = None):
        super().__init__(message, errors=errors)


class StreamSourceError(VideoStreamError):
    """Raised when the video stream source is invalid or missing."""

    def __init__(self, message: str, errors: Optional[dict] = None):
        super().__init__(message, errors=errors)


class StreamConnectionError(VideoStreamError):
    """Raised when the video stream cannot be opened or reconnected."""

    def __init__(self, message: str, errors: Optional[dict] = None):
        super().__init__(message, errors=errors)


class FrameCaptureError(VideoStreamError):
    """Raised when a frame cannot be captured."""

    def __init__(self, message: str, errors: Optional[dict] = None):
        super().__init__(message, errors=errors)


class FrameEncodingError(VideoStreamError):
    """Raised when a frame cannot be encoded."""

    def __init__(self, message: str, errors: Optional[dict] = None):
        super().__init__(message, errors=errors)


# --------------------------------------------------------------------------------
# Object Detection Exceptions
# --------------------------------------------------------------------------------

class ObjectDetectionError(BaseError):
    """Base class for all object detection-related errors."""

    def __init__(self, message: str, errors: Optional[dict] = None):
        super().__init__(message, errors=errors)


class ModelNotFoundError(ObjectDetectionError):
    """Raised when the model is not found."""

    def __init__(self, message: str, errors: Optional[dict] = None):
        super().__init__(message, errors=errors)


class ModelLoadingError(ObjectDetectionError):
    """Raised when the model cannot be loaded."""

    def __init__(self, message: str, errors: Optional[dict] = None):
        super().__init__(message, errors=errors)