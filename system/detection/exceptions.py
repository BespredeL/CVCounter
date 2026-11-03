# -*- coding: utf-8 -*-
# ! python3

"""Detection subsystem exception hierarchy."""

from typing import Optional
from system.utils.exception_handler import BaseError


class DetectionError(BaseError):
    """Базовое исключение подсистемы детекции объектов (замена ObjectDetectionError)."""

    def __init__(self, message: str, errors: Optional[dict] = None, **kwargs):
        super().__init__(message, errors=errors, **kwargs)


class ModelNotFoundError(DetectionError):
    """Файл весов не найден или недоступен."""

    pass


class ModelLoadingError(DetectionError):
    """Ошибка инициализации весов или несовместимость среды исполнения."""

    pass


class InferenceError(DetectionError):
    """Ошибка выполнения инференса на кадре."""

    pass


class UnsupportedModelFormatError(DetectionError):
    """Попытка загрузки весов неподдерживаемого формата (Darknet .weights/.cfg, OpenVINO IR .xml)."""

    pass


__all__ = [
    "DetectionError",
    "ModelNotFoundError",
    "ModelLoadingError",
    "InferenceError",
    "UnsupportedModelFormatError",
]
