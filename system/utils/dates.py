# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Recognize date and datetime values, including strings."""

from datetime import date, datetime
from typing import Any, Optional

_DATE_ONLY_FORMATS = (
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%Y/%m/%d",
    "%d/%m/%Y",
)

_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M:%S.%f",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
)

_MAX_DATE_STRING_LENGTH = 40


def _parse_date_string(value: str) -> Optional[datetime]:
    """
    Parse a date or datetime string.

    Args:
        value (str): Candidate string

    Returns:
        Optional[datetime]: Parsed value, or None when the string is not a date
    """
    text = value.strip()
    if not text or len(text) > _MAX_DATE_STRING_LENGTH:
        return None

    normalized = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    for fmt in (*_DATETIME_FORMATS, *_DATE_ONLY_FORMATS):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _is_date_only(value: Any) -> bool:
    """
    Return True when the value is a calendar date without a time.

    Args:
        value (Any): Value already known to be a date

    Returns:
        bool: True for a date-only value
    """
    if isinstance(value, datetime):
        return False
    if isinstance(value, date):
        return True
    if not isinstance(value, str):
        return False

    text = value.strip()
    if not text or "T" in text or ":" in text or text.endswith(("Z", "z")):
        return False
    for fmt in _DATE_ONLY_FORMATS:
        try:
            datetime.strptime(text, fmt)
            return True
        except ValueError:
            continue
    return False


def is_date(value: Any) -> bool:
    """
    Return True when value is a date, a datetime, or a string of either.

    Args:
        value (Any): Value to check. A string is parsed as a date or datetime.

    Returns:
        bool: True if the value represents a date or a datetime
    """
    if isinstance(value, (datetime, date)):
        return True
    if isinstance(value, str):
        return _parse_date_string(value) is not None
    return False


def format_date(value: Any, fmt: Optional[str] = None) -> str:
    """
    Format a date or datetime, including a string that parses as one.

    A date-only value uses ``%d.%m.%Y``. A datetime uses ``%d.%m.%Y %H:%M``.
    Pass ``fmt`` to override both.

    Args:
        value (Any): Date, datetime, or string
        fmt (Optional[str]): ``strftime`` pattern

    Returns:
        str: Formatted value, or the original text when it is not a date
    """
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day)
    elif isinstance(value, str):
        parsed = _parse_date_string(value)
    else:
        parsed = None

    if parsed is None:
        if value is None:
            return ""
        return value if isinstance(value, str) else str(value)

    if fmt:
        return parsed.strftime(fmt)
    if _is_date_only(value):
        return parsed.strftime("%d.%m.%Y")
    return parsed.strftime("%d.%m.%Y %H:%M")
