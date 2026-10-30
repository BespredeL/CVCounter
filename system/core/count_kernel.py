# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Pure counting geometry: zone mask rasterization and motion-direction acceptance."""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence

import cv2
import numpy as np

from system.utils.counting_area import DIRECTION_VECTORS

MIN_DISPLACEMENT_PX = 5.0
DIRECTION_COSINE = 0.5


def build_zone_mask(frame_shape: Sequence[int], zones: Sequence[dict]) -> np.ndarray:
    """
    Rasterize counting zones into one int16 mask where each pixel holds zone index + 1.

    Args:
        frame_shape (Sequence[int]): (height, width[, channels]) of the frame.
        zones (Sequence[dict]): Zones with a 'points' key; fewer than 3 points are skipped.

    Returns:
        numpy.ndarray: Mask of shape (height, width), dtype int16, 0 outside every zone.
    """
    height, width = frame_shape[:2]
    mask: np.ndarray = np.zeros((height, width), dtype=np.int16)

    for idx, zone in enumerate(zones):
        points = zone.get('points') or []
        if len(points) < 3:
            continue
        pts = np.asarray(points, dtype=np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(mask, [pts], idx + 1)

    return mask


def direction_matches(center: tuple[int, int], history: deque, direction: str) -> bool:
    """
    Accept motion only when the travel from the first recorded center points along
    the zone direction within a ±60° cone.

    Args:
        center (tuple[int, int]): Current object center (cx, cy).
        history (deque): Recorded centers for this track id, oldest first.
        direction (str): Zone direction key from DIRECTION_VECTORS, or 'any'.

    Returns:
        bool: True when the object may be counted for this zone.
    """
    if direction == 'any':
        return True

    vec = DIRECTION_VECTORS.get(direction)
    if not vec:
        return True

    if len(history) < 2:
        return False

    start_x, start_y = history[0]
    cx, cy = center
    dx = cx - start_x
    dy = cy - start_y
    dist = (dx * dx + dy * dy) ** 0.5

    # Displacement below the floor is stationary jitter, not a crossing.
    if dist < MIN_DISPLACEMENT_PX:
        return False

    ux, uy = vec
    return ((dx * ux + dy * uy) / dist) >= DIRECTION_COSINE
