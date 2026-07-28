# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 28.07.2026
# Updated: 28.07.2026
# Website: https://bespredel.name

from __future__ import annotations
from typing import Any
from flask import current_app, g


def get_app_context() -> dict[str, Any]:
    """
    Return the application context dict from ``g`` or ``current_app.config``.
    
    Args:
        None

    Returns:
        dict: The application context dictionary
    """
    if not hasattr(g, 'app_context'):
        g.app_context = current_app.config.get('APP_CONTEXT')
    return g.app_context


def refresh_app_context(context: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Reload users/locations from config into the live APP_CONTEXT.

    Call after settings (or other config) saves so auth and location lists
    pick up changes without restarting the process.

    Args:
        context (dict[str, Any] | None): The application context dictionary

    Returns:
        dict: The application context dictionary
    """
    if context is None:
        context = get_app_context()

    config = context['config']
    detections = config.get('detections', {}) or {}
    context['users'] = config.get('users', {}) or {}
    context['locations'] = list(detections.keys())
    context['locations_dict'] = {
        key: (value.get('label', key) if isinstance(value, dict) else key)
        for key, value in detections.items()
    }
    return context
