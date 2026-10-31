# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""
Canonical value contract for the browser preview settings.

Kept free of web and OpenCV imports so the config validator, the camera schema and the
counter settings all read the same ranges and the same defaults.
"""

from __future__ import annotations

from typing import Any

# Preview scale and JPEG quality are percentages, and the settings form offers them
# from 5 to 100 in steps of 5; the ranges below are what that form can produce.
PREVIEW_SCALE_MIN: int = 5
PREVIEW_SCALE_MAX: int = 100
PREVIEW_QUALITY_MIN: int = 5
PREVIEW_QUALITY_MAX: int = 100
# 0 means "no limit": the stream pace then follows the camera instead of a fixed rate.
PREVIEW_FPS_MIN: int = 0
PREVIEW_FPS_MAX: int = 240

DEFAULT_PREVIEW_SCALE: int = 70
DEFAULT_PREVIEW_QUALITY: int = 50
DEFAULT_PREVIEW_FPS: int = 0

_NOT_WHOLE = 'must be a whole number'


def _coerce_whole_number(value: Any) -> int:
    """
    Read the value in whatever form a config file or a form field can hold it.

    Args:
        value: The raw configured value - an int, an integral float or a digit string.

    Returns:
        int: The value as an integer.

    Raises:
        TypeError: The value is not a whole number at all.
    """
    if isinstance(value, bool):
        raise TypeError('a boolean is not a number')
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise TypeError('a fraction is not a whole number')
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            raise TypeError('a word is not a number') from None
    raise TypeError('not a number')


def _bounded_int(value: Any, low: int, high: int) -> int:
    """
    Coerce a configured number into a whole number inside a range.

    Args:
        value: The raw configured value.
        low: Smallest accepted value.
        high: Largest accepted value.

    Returns:
        int: The value as an integer.

    Raises:
        ValueError: The value is not a whole number inside the range.
    """
    try:
        number = _coerce_whole_number(value)
    except TypeError:
        raise ValueError(_NOT_WHOLE) from None

    if number < low or number > high:
        raise ValueError(f'must be between {low} and {high}')
    return number


def normalize_preview_scale(value: Any) -> int:
    """
    Coerce ``video_show_scale`` into a preview percentage.

    Args:
        value: The raw configured value.

    Returns:
        int: The percentage of the source frame the browser picture is scaled to.

    Raises:
        ValueError: The value is not a usable percentage.
    """
    return _bounded_int(value, PREVIEW_SCALE_MIN, PREVIEW_SCALE_MAX)


def normalize_preview_quality(value: Any) -> int:
    """
    Coerce ``video_show_quality`` into a JPEG quality.

    Args:
        value: The raw configured value.

    Returns:
        int: The JPEG quality the preview frames are encoded with.

    Raises:
        ValueError: The value is not a usable JPEG quality.
    """
    return _bounded_int(value, PREVIEW_QUALITY_MIN, PREVIEW_QUALITY_MAX)


def normalize_preview_fps(value: Any) -> int:
    """
    Coerce ``video_fps`` into a frame rate.

    Args:
        value: The raw configured value; 0 asks for the rate of the source.

    Returns:
        int: The frame rate the counter paces itself to.

    Raises:
        ValueError: The value is not a usable frame rate.
    """
    return _bounded_int(value, PREVIEW_FPS_MIN, PREVIEW_FPS_MAX)
