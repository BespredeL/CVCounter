# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 25.07.2026
# Updated: 25.07.2026
# Website: https://bespredel.name

"""Helpers for single- and multi-zone counting areas."""

from __future__ import annotations
from typing import Any, Iterable, Mapping, Sequence

DEFAULT_COUNTING_AREA_COLOR: list[int] = [67, 211, 255]


def _as_color(value: Any, fallback: Sequence[int] | None = None) -> list[int]:
    """
    Normalize a BGR color to three ints in 0..255.

    Args:
        value: The color to normalize.
        fallback: The fallback color to use if the value is invalid.

    Returns:
        The normalized color.
    """
    base = list(fallback) if fallback is not None else list(DEFAULT_COUNTING_AREA_COLOR)
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return [int(base[0]), int(base[1]), int(base[2])]

    try:
        color = [int(value[0]), int(value[1]), int(value[2])]
    except (TypeError, ValueError):
        return [int(base[0]), int(base[1]), int(base[2])]

    if not all(0 <= channel <= 255 for channel in color):
        return [int(base[0]), int(base[1]), int(base[2])]
    return color


def _as_points(value: Any) -> list[list[int]] | None:
    """
    Normalize polygon points; return None if invalid.

    Args:
        value: The points to normalize.

    Returns:
        The normalized points.
        None if the points are invalid.
    """
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None

    points: list[list[int]] = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            return None
        try:
            x, y = int(point[0]), int(point[1])
        except (TypeError, ValueError):
            return None
        if x < 0 or y < 0:
            return None
        points.append([x, y])
    return points


def _zone_from_mapping(zone: Mapping[str, Any], fallback_color: Sequence[int]) -> dict[str, Any] | None:
    """
    Build a normalized zone dict from a mapping.

    Args:
        zone: The zone to build from.
        fallback_color: The fallback color to use if the color is invalid.

    Returns:
        The normalized zone. None if the zone is invalid.
    """
    points = _as_points(zone.get('points') or zone.get('counting_area'))
    if points is None:
        return None
    return {
        'points': points,
        'color': _as_color(zone.get('color', zone.get('counting_area_color')), fallback_color),
    }


def normalize_counting_areas(
        source: Mapping[str, Any] | None = None,
        *,
        counting_areas: Any = None,
        counting_area: Any = None,
        counting_area_color: Any = None,
) -> list[dict[str, Any]]:
    """
    Normalize counting zones from config/API/kwargs.

    Prefers ``counting_areas``. Falls back to legacy ``counting_area`` + color.
    Each returned zone is ``{'points': [[x, y], ...], 'color': [B, G, R]}``.

    Args:
        source: The source to normalize.
        counting_areas: The counting areas to normalize.
        counting_area: The counting area to normalize.
        counting_area_color: The counting area color to normalize.

    Returns:
        The normalized counting areas. An empty list if the counting areas are invalid.
    """
    data = source or {}
    areas_raw = counting_areas if counting_areas is not None else data.get('counting_areas')
    legacy_area = counting_area if counting_area is not None else data.get('counting_area')
    legacy_color = (
        counting_area_color
        if counting_area_color is not None
        else data.get('counting_area_color', DEFAULT_COUNTING_AREA_COLOR)
    )
    fallback_color = _as_color(legacy_color)

    zones: list[dict[str, Any]] = []
    if isinstance(areas_raw, list) and areas_raw:
        for item in areas_raw:
            if isinstance(item, Mapping):
                zone = _zone_from_mapping(item, fallback_color)
            else:
                points = _as_points(item)
                zone = {'points': points, 'color': list(fallback_color)} if points is not None else None
            if zone is not None:
                zones.append(zone)

    if not zones:
        points = _as_points(legacy_area)
        if points is not None:
            zones.append({'points': points, 'color': list(fallback_color)})

    return zones


def areas_to_legacy_fields(areas: Sequence[Mapping[str, Any]]) -> tuple[list[list[int]], list[int]]:
    """
    Return legacy counting_area / counting_area_color from the first zone.

    Args:
        areas: The areas to return the legacy fields from.

    Returns:
        The legacy counting_area and counting_area_color.
    """
    if not areas:
        return [], list(DEFAULT_COUNTING_AREA_COLOR)

    first = areas[0]
    points = _as_points(first.get('points')) or []
    color = _as_color(first.get('color'), DEFAULT_COUNTING_AREA_COLOR)
    return points, color


def areas_for_config(areas: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """
    Build config keys for multi-zone storage with legacy aliases.

    Args:
        areas: The areas to build the config keys from.

    Returns:
        The config keys.
    """
    normalized = normalize_counting_areas({'counting_areas': list(areas)})
    legacy_area, legacy_color = areas_to_legacy_fields(normalized)
    return {
        'counting_areas': normalized,
        'counting_area': legacy_area,
        'counting_area_color': legacy_color,
    }


def areas_to_runtime(
        areas: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """
    Convert normalized areas to runtime tuples for ObjectCounter.

    Args:
        areas: The areas to convert to runtime tuples.

    Returns:
        The runtime tuples.
    """
    runtime: list[dict[str, Any]] = []
    for area in areas:
        points = _as_points(area.get('points'))
        if points is None:
            continue
        runtime.append({
            'points': [(int(x), int(y)) for x, y in points],
            'color': tuple(_as_color(area.get('color'), DEFAULT_COUNTING_AREA_COLOR)),
        })
    return runtime
