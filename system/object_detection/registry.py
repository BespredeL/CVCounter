# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 20.05.2026
# Updated: 09.06.2026
# Website: https://bespredel.name

from typing import Callable, Dict, Type
from system.object_detection.base_object_detection import BaseObjectDetectionService
from system.utils.exception_handler import ModelLoadingError

DetectorFactory = Callable[[], BaseObjectDetectionService]

""" Registry of object detection backends. """
_REGISTRY: Dict[str, DetectorFactory] = {}


def register(model_type: str) -> Callable[[Type[BaseObjectDetectionService]], Type[BaseObjectDetectionService]]:
    """
    Register an object detection backend.

    Usage:
        @register('yolo')
        class ObjectDetectionYOLO(BaseObjectDetectionService):
            ...
    """

    normalized_type = model_type.strip().lower()

    def decorator(cls: Type[BaseObjectDetectionService]) -> Type[BaseObjectDetectionService]:
        if normalized_type in _REGISTRY:
            raise ValueError(f"Detector '{normalized_type}' is already registered")
        _REGISTRY[normalized_type] = cls
        return cls

    return decorator


def supported_model_types() -> list[str]:
    """
    Get a list of supported model types.

    Returns:
        list[str]: A list of supported model types.
    """
    return sorted(_REGISTRY.keys())


def create_detector(model_type: str) -> BaseObjectDetectionService:
    """
    Create a detector instance.

    Args:
        model_type (str): The model type to create.

    Returns:
        BaseObjectDetectionService: The created detector instance.
    """
    normalized_type = (model_type or '').strip().lower()
    factory = _REGISTRY.get(normalized_type)
    if factory is None:
        supported = ', '.join(supported_model_types()) or 'none'
        raise ModelLoadingError(
            f"Unsupported model_type '{model_type}'. Supported types: {supported}"
        )
    return factory()


def load_detector(model_type: str, weights: str, **kwargs) -> BaseObjectDetectionService:
    """
    Load a detector instance.

    Args:
        model_type (str): The model type to load.
        weights (str): The weights to load.
        **kwargs: Additional keyword arguments.

    Returns:
        BaseObjectDetectionService: The loaded detector instance.
    """
    detector = create_detector(model_type)
    detector.load_model(weights, **kwargs)
    return detector
