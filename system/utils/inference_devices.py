# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""
Canonical value contract for the camera ``device`` parameter.

Kept free of web and inference-framework imports so the config validator and every
detection backend read and write the same vocabulary.
"""

from __future__ import annotations

from typing import Any

DEVICE_CPU = 'cpu'
DEVICE_AUTO = 'auto'

# OpenVINO addresses accelerators by name; the other backends index CUDA devices instead.
ACCELERATOR_DEVICES: tuple[str, ...] = ('gpu', 'gpu.0', 'gpu.1', 'npu')
ACCELERATOR_MODEL_TYPES: tuple[str, ...] = ('openvino', 'openvino_dnn')


def _rejected(model_type: Any) -> str:
    """Build the error text describing the accepted values for a backend."""
    options = [DEVICE_CPU, DEVICE_AUTO]
    if str(model_type or '').lower() in ACCELERATOR_MODEL_TYPES:
        options += list(ACCELERATOR_DEVICES)
    return f"must be a GPU index (integer) or one of: '{', '.join(options)}'"


def normalize_device(value: Any, model_type: Any = None) -> int | str:
    """
    Coerce a configured device value into the form the backends expect.

    Args:
        value: The raw configured value - a GPU index as int or digit string, or a device name.
        model_type: Optional backend name; accelerator device names are accepted only for
            OpenVINO, which selects by name rather than by CUDA index.

    Returns:
        int | str: The GPU index, or the lower-cased device name.

    Raises:
        ValueError: The value is not a device the backend can address.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return value

    if isinstance(value, str):
        text = value.strip()
        try:
            return int(text)
        except ValueError:
            pass
        lowered = text.lower()
        if lowered in (DEVICE_CPU, DEVICE_AUTO):
            return lowered
        if lowered in ACCELERATOR_DEVICES and str(model_type or '').lower() in ACCELERATOR_MODEL_TYPES:
            return lowered

    raise ValueError(_rejected(model_type))
