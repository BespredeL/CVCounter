# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from flask import request


def is_ajax() -> bool:
    """
    Check if the request is an AJAX request.

    Args:
        None

    Returns:
        bool: True if the request is an AJAX request.
    """
    if str(request.headers.get('X-Requested-With', '')).lower() == 'xmlhttprequest':
        return True
    accept = request.headers.get('Accept', '')
    if 'application/json' in accept:
        return True
    return False
