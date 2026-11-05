# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

from flask import Blueprint

datasets_bp = Blueprint('datasets', __name__)

from . import capture, common, images, management, pages, training  # noqa: F401
from .common import (
    _service,
    invalidate_available_weights_cache,
    invalidate_detector_models_cache,
)

__all__ = [
    '_service',
    'datasets_bp',
    'invalidate_available_weights_cache',
    'invalidate_detector_models_cache',
]
