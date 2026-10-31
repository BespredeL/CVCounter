# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Font and text-badge rendering for detection indicators, plus the MJPEG placeholder chunk."""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from system.utils.frame_utils import FrameUtils

_PLACEHOLDER_MJPEG_CHUNK: bytes | None = None
_LABEL_FONT: ImageFont.ImageFont | None = None
_LABEL_FONT_SIZE: int = 13

_BADGE_CACHE: dict[tuple[str, tuple[int, int, int]], np.ndarray] = {}
_MAX_BADGE_CACHE_SIZE: int = 500


def get_label_font(size: int = 13) -> ImageFont.ImageFont | None:
    """
    Get a cached TrueType font that supports Unicode / Cyrillic, falling back to default.
    """
    global _LABEL_FONT, _LABEL_FONT_SIZE
    if _LABEL_FONT is not None and _LABEL_FONT_SIZE == size:
        return _LABEL_FONT

    font_candidates = [
        "arial.ttf",
        "segoeui.ttf",
        "tahoma.ttf",
        "calibri.ttf",
        "DejaVuSans.ttf",
        "LiberationSans-Regular.ttf",
        "FreeSans.ttf",
    ]
    for font_name in font_candidates:
        try:
            _LABEL_FONT = ImageFont.truetype(font_name, size)
            _LABEL_FONT_SIZE = size
            return _LABEL_FONT
        except Exception:
            continue

    try:
        _LABEL_FONT = ImageFont.load_default()
        _LABEL_FONT_SIZE = size
    except Exception:
        _LABEL_FONT = None
    return _LABEL_FONT


def render_cached_badge(label: str, color: tuple[int, int, int], font: ImageFont.ImageFont) -> np.ndarray:
    """
    Renders or fetches a cached text badge image for bounding box indicators.
    """
    key = (label, color)
    cached = _BADGE_CACHE.get(key)
    if cached is not None:
        return cached

    mask_w, mask_h = font.getmask(label).size
    pad_x, pad_y = 5, 3
    badge_w = mask_w + pad_x * 2
    badge_h = mask_h + pad_y * 2 + 2

    # BGR to RGB for PIL
    rgb_color = (int(color[2]), int(color[1]), int(color[0]))
    img = Image.new('RGB', (badge_w, badge_h), color=rgb_color)
    draw = ImageDraw.Draw(img)
    draw.text((pad_x, pad_y), label, font=font, fill=(0, 0, 0))
    badge_np = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)

    if len(_BADGE_CACHE) >= _MAX_BADGE_CACHE_SIZE:
        _BADGE_CACHE.clear()
    _BADGE_CACHE[key] = badge_np
    return badge_np


def placeholder_mjpeg_chunk() -> bytes:
    """
    Minimal multipart JPEG chunk so Werkzeug commits headers before the first real frame.
    """
    global _PLACEHOLDER_MJPEG_CHUNK
    if _PLACEHOLDER_MJPEG_CHUNK is None:
        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        _PLACEHOLDER_MJPEG_CHUNK = FrameUtils.multipart_chunk(FrameUtils.encode_jpeg(frame, 60))
    return _PLACEHOLDER_MJPEG_CHUNK
