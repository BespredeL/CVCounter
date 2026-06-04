# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 03.06.2026
# Updated: 03.06.2026
# Website: https://bespredel.name

import re
from pathlib import Path

import cv2
from numpy import ndarray

PREVIEW_DIR = Path('yolo_cfg/counter_previews')
PREVIEW_MAX_WIDTH = 480
PREVIEW_JPEG_QUALITY = 85


def _safe_location_slug(location: str) -> str:
    slug = re.sub(r'[^A-Za-z0-9-_]+', '_', location).strip('_')
    return slug or 'counter'


def get_preview_path(location: str) -> Path:
    """
    Filesystem path for a location's dashboard preview JPEG.

    Args:
        location: Detection location identifier.

    Returns:
        Path: Preview file path.
    """
    return PREVIEW_DIR / f'{_safe_location_slug(location)}.jpg'


def preview_exists(location: str) -> bool:
    """Return True if a saved preview exists for the location."""
    return get_preview_path(location).is_file()


def save_counter_preview(location: str, frame: ndarray | None) -> bool:
    """
    Persist one JPEG thumbnail for the dashboard.

    Args:
        location: Detection location identifier.
        frame: BGR frame; skipped when None or empty.

    Returns:
        bool: True when the file was written.
    """
    if frame is None or getattr(frame, 'size', 0) == 0:
        return False

    path = get_preview_path(location)
    path.parent.mkdir(parents=True, exist_ok=True)

    height, width = frame.shape[:2]
    if width > PREVIEW_MAX_WIDTH:
        scale = PREVIEW_MAX_WIDTH / width
        frame = cv2.resize(
            frame,
            (PREVIEW_MAX_WIDTH, int(height * scale)),
            interpolation=cv2.INTER_AREA,
        )

    return bool(
        cv2.imwrite(
            str(path),
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), PREVIEW_JPEG_QUALITY],
        )
    )
