# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.07.2026
# Updated: 26.07.2026
# Website: https://bespredel.name

import re
from typing import Any, Optional

_URL_RE = re.compile(
    r'(?i)\b(?:rtsp|rtsps|http|https|ftp)://'
    r'(?:[^\s/@]+@)?'
    r'[^\s\'"<>]+'
)
_CREDENTIAL_RE = re.compile(
    r'(?i)\b(password|passwd|pwd|secret_key|hmac_secret|api[_-]?key)\s*[=:]\s*\S+'
)
_PATH_HINT_RE = re.compile(
    r'(?i)(?:[A-Za-z]:\\|/)(?:Users|home|var|opt|storage|config)[^\s\'"]{0,200}'
)


def sanitize_text(text: Optional[str], max_chars: int = 8000) -> str:
    """
    Strip credentials, stream URLs and path hints from free-form text.

    Args:
        text: Raw message or stack trace.
        max_chars: Maximum length after sanitization.

    Returns:
        Sanitized string (may be empty).
    """
    if not text:
        return ''
    cleaned = str(text)
    cleaned = _URL_RE.sub('[REDACTED_URL]', cleaned)
    cleaned = _CREDENTIAL_RE.sub(r'\1=[REDACTED]', cleaned)
    cleaned = _PATH_HINT_RE.sub('[REDACTED_PATH]', cleaned)
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars] + '...[truncated]'
    return cleaned


def sanitize_props(props: Optional[dict[str, Any]]) -> dict[str, Any]:
    """
    Return a shallow-copied props dict with string values sanitized.

    Args:
        props: Optional event properties.

    Returns:
        Safe props dict.
    """
    if not props:
        return {}
    safe: dict[str, Any] = {}
    for key, value in props.items():
        key_l = str(key).lower()
        if any(token in key_l for token in ('password', 'secret', 'token', 'video_path', 'uri', 'url')):
            continue
        if isinstance(value, str):
            safe[key] = sanitize_text(value, max_chars=500)
        elif isinstance(value, (int, float, bool)) or value is None:
            safe[key] = value
        else:
            safe[key] = sanitize_text(str(value), max_chars=200)
    return safe
