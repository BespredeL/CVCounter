# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

from collections.abc import Mapping, Sequence

_DEFAULT_UNITS = ('B', 'KB', 'MB', 'GB', 'TB', 'PB')


def format_bytes(
        size: int | float,
        *,
        places: int | Mapping[str, int] = 2,
        units: Sequence[str] = _DEFAULT_UNITS,
) -> str:
    """
    Format a byte count as a human-readable size.

    ``places`` is the number of digits after the decimal point, or a map of
    unit name to digits. Zero digits prints an integer, which is how log and
    media sizes show plain bytes.

    Args:
        size: Byte count.
        places: Digits for every unit, or a per-unit map.
        units: Units to climb, stopping at the last one.

    Returns:
        str: Size and unit, for example ``1.50 KB``.
    """
    value = float(size)
    unit_list = tuple(units)
    for index, unit in enumerate(unit_list):
        if value < 1024 or index == len(unit_list) - 1:
            digits = places[unit] if isinstance(places, Mapping) else places
            if digits <= 0:
                return f'{int(value)} {unit}'
            return f'{value:.{int(digits)}f} {unit}'
        value /= 1024
    return f'{value:.2f} PB'
