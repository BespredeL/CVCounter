# -*- coding: utf-8 -*-
# ! python3

"""Image preprocessing and geometric transformation utilities for object detection."""

from typing import Any, Dict, Optional, Sequence, Tuple
import cv2
import numpy as np
from numpy import ndarray


def normalize_input_size(input_size: int | Sequence[int]) -> Tuple[int, int]:
    """
    Normalize the input size to a (width, height) tuple.

    Args:
        input_size: An integer for square input (e.g. 640) or a sequence [width, height].

    Returns:
        Tuple[int, int]: The normalized (width, height).
    """
    if isinstance(input_size, (list, tuple)):
        if len(input_size) != 2:
            raise ValueError("'input_size' must be an int or a pair [width, height]")
        return int(input_size[0]), int(input_size[1])
    size = int(input_size)
    return size, size


def letterbox_image(image: ndarray, input_size: Tuple[int, int], pad_value: int = 114) -> ndarray:
    """
    Resize an image preserving its aspect ratio and center it on a padded canvas.

    Args:
        image: Source image (BGR or RGB).
        input_size: The target (width, height).
        pad_value: The canvas fill value (default: 114 for YOLO/DETR gray padding).

    Returns:
        ndarray: The letterboxed image matching input_size.
    """
    target_width, target_height = input_size
    height, width = image.shape[:2]
    gain = min(target_width / width, target_height / height)
    new_w = int(round(width * gain))
    new_h = int(round(height * gain))

    resized = cv2.resize(
        image,
        (new_w, new_h),
        interpolation=cv2.INTER_LINEAR,
    )
    canvas = np.full((target_height, target_width, 3), pad_value, dtype=image.dtype)
    offset_x = (target_width - new_w) // 2
    offset_y = (target_height - new_h) // 2
    canvas[offset_y:offset_y + new_h, offset_x:offset_x + new_w] = resized
    return canvas


def preprocessing_from_manifest(manifest: Any) -> Dict[str, Any]:
    """
    Translate a model manifest's declared preprocessing and input contract into
    create_blob options. Returns default empty dict if manifest is absent.

    Args:
        manifest: Loaded ModelManifest or None.

    Returns:
        Dict[str, Any]: Options dictionary accepted by create_blob.
    """
    if manifest is None:
        return {}

    prep = getattr(manifest, 'preprocessing', None) or {}
    contract = getattr(manifest, 'input_contract', None) or {}
    options: Dict[str, Any] = {
        'color_order': str(prep.get('color_order', 'RGB')).upper(),
        'resize': str(prep.get('resize', 'letterbox')).lower(),
        'scale': float(prep.get('scale', 1 / 255.0)),
        'mean': tuple(prep.get('mean', (0, 0, 0))),
        'crop': bool(prep.get('crop', False)),
    }
    if contract.get('layout'):
        options['layout'] = str(contract['layout']).upper()
    if contract.get('dtype'):
        options['dtype'] = np.dtype(contract['dtype'])
    return options


def create_blob(
    image: ndarray,
    input_size: Tuple[int, int],
    preprocessing: Optional[Dict[str, Any]] = None,
) -> ndarray:
    """
    Create a 4D batch tensor (blob) from an image for neural network inference.

    Args:
        image: The raw input image (BGR format from OpenCV).
        input_size: The target (width, height) tuple.
        preprocessing: Optional options dictionary with color_order, resize,
            scale, mean, crop, layout and dtype.

    Returns:
        ndarray: 4D numpy array ready for inference (e.g. NCHW float32).
    """
    options = preprocessing or {}
    color_order = str(options.get('color_order', 'RGB')).upper()
    resize = str(options.get('resize', 'letterbox')).lower()
    scale = float(options.get('scale', 1 / 255.0))
    mean = tuple(options.get('mean', (0, 0, 0)))
    crop = bool(options.get('crop', False))
    layout = str(options.get('layout', 'NCHW')).upper()
    dtype = options.get('dtype', np.float32)

    source = image
    if color_order == 'RGB':
        source = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    elif color_order != 'BGR':
        raise ValueError(f"Unsupported preprocessing color order: '{color_order}'")

    if resize == 'letterbox':
        source = letterbox_image(source, input_size)
    elif resize != 'stretch':
        raise ValueError(f"Unsupported preprocessing resize mode: '{resize}'")

    blob = cv2.dnn.blobFromImage(
        source,
        scalefactor=scale,
        size=input_size,
        mean=mean,
        swapRB=False,
        crop=crop,
    )

    if layout == 'NHWC':
        blob = np.transpose(blob, (0, 2, 3, 1))
    elif layout != 'NCHW':
        raise ValueError(f"Unsupported preprocessing input layout: '{layout}'")

    return blob.astype(dtype, copy=False)


__all__ = [
    "normalize_input_size",
    "letterbox_image",
    "preprocessing_from_manifest",
    "create_blob",
]
