# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Redaction helpers for values a response echoes back from configuration."""

from __future__ import annotations

import re

# Keeps scheme, user and host readable so the value stays useful in a listing,
# and replaces only the secret between the colon and the @.
_CREDENTIAL_RE = re.compile(r'://([^:]+):([^@]+)@')
_CREDENTIAL_MASK = r'://\1:••••••••@'


def mask_url(url: str | None) -> str:
    """
    Mask the password of an RTSP or HTTP source URL for API output.

    Args:
        url (str | None): Source URL, may be empty or missing.

    Returns:
        str: URL with its password replaced, or an empty string when there is no URL.
    """
    if not url:
        return ""
    return _CREDENTIAL_RE.sub(_CREDENTIAL_MASK, str(url))
