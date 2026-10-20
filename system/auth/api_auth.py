# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, Optional, Tuple

from flask import current_app, g, jsonify, request

from system.utils.app_context import get_app_context

ROLE_HIERARCHY: Dict[str, int] = {
    'read': 1,
    'write': 2,
    'admin': 3,
}


def _get_api_config() -> Dict[str, Any]:
    """Retrieve API configuration dictionary from application context."""
    try:
        context = get_app_context()
        config = context.get('config')
        if config:
            return config.get('api', {})
    except Exception:
        pass
    if current_app:
        app_ctx = current_app.config.get('APP_CONTEXT', {})
        config = app_ctx.get('config')
        if config:
            return config.get('api', {})
    return {}


def get_api_key_from_request() -> Optional[str]:
    """
    Extract the API key from request headers.
    
    Checks:
    1. X-API-Key: <key>
    2. Authorization: Bearer <key>
    
    Returns:
        Optional[str]: Extracted API key, or None.
    """
    api_key = request.headers.get('X-API-Key')
    if api_key:
        return api_key.strip()

    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.lower().startswith('bearer '):
        parts = auth_header.split(None, 1)
        if len(parts) == 2:
            return parts[1].strip()

    return None


def mask_api_key(key: str) -> str:
    """
    Mask an API key for safe display in logs or UI.
    
    Args:
        key (str): The raw API key
        
    Returns:
        str: Masked string (e.g. 'cvc_adm_••••••••1a2b')
    """
    if not key or len(key) < 8:
        return "••••••••"
    prefix = key[:8]
    suffix = key[-4:]
    return f"{prefix}••••••••{suffix}"


def generate_api_key(name: str, role: str = 'read', prefix: str = 'cvc') -> Dict[str, Any]:
    """
    Generate a new structured API key object.
    
    Args:
        name (str): Human-readable name/description for the key
        role (str): Access role ('read', 'write', 'admin')
        prefix (str): Prefix for the token string
        
    Returns:
        dict: The key entry dictionary including unique ID and timestamp
    """
    role = role.lower() if role in ROLE_HIERARCHY else 'read'
    role_tag = {'read': 'ro', 'write': 'rw', 'admin': 'adm'}.get(role, 'ro')
    random_part = secrets.token_urlsafe(24).replace('-', '').replace('_', '')
    raw_key = f"{prefix}_{role_tag}_{random_part}"

    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    return {
        'id': f"key_{secrets.token_hex(6)}",
        'name': name.strip() or 'API Key',
        'key': raw_key,
        'role': role,
        'enabled': True,
        'created_at': now_iso,
    }


def validate_api_key(key: Optional[str], required_role: str = 'read') -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Validate provided API key against configured keys and required role.
    
    Args:
        key (Optional[str]): Provided API key
        required_role (str): Minimum role required ('read', 'write', 'admin')
        
    Returns:
        tuple[bool, Optional[dict], Optional[str]]: (is_valid, key_info_dict, error_message)
    """
    if not key:
        return False, None, "Missing API key. Provide via 'X-API-Key' or 'Authorization: Bearer <key>'"

    api_conf = _get_api_config()
    if not api_conf.get('enabled', True):
        return False, None, "REST API is currently disabled in configuration"

    configured_keys = api_conf.get('keys', [])
    if not isinstance(configured_keys, list) or not configured_keys:
        return False, None, "No API keys configured on server"

    required_level = ROLE_HIERARCHY.get(required_role.lower(), 1)
    matched_key: Optional[Dict[str, Any]] = None

    for entry in configured_keys:
        if not isinstance(entry, dict):
            continue
        candidate_key = entry.get('key', '')
        if candidate_key and hmac.compare_digest(str(key), str(candidate_key)):
            matched_key = entry
            break

    if not matched_key:
        return False, None, "Invalid API key"

    if not matched_key.get('enabled', True):
        return False, None, "API key has been disabled"

    key_role = matched_key.get('role', 'read').lower()
    key_level = ROLE_HIERARCHY.get(key_role, 1)

    if key_level < required_level:
        return False, matched_key, f"Forbidden: '{required_role}' permission required, but key has '{key_role}'"

    return True, matched_key, None


def api_key_required(role: str = 'read'):
    """
    Decorator to protect REST API endpoints with API key authentication.
    
    Args:
        role (str): Required minimum role ('read', 'write', 'admin'). Defaults to 'read'.
        
    Returns:
        Decorated view function returning JSON on failure.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = get_api_key_from_request()
            is_valid, key_info, error_msg = validate_api_key(key, required_role=role)
            if not is_valid:
                status_code = 403 if (key_info and "Forbidden" in (error_msg or "")) else 401
                error_code = "forbidden" if status_code == 403 else "unauthorized"
                return jsonify({
                    'success': False,
                    'error': {
                        'code': error_code,
                        'message': error_msg,
                    }
                }), status_code

            g.api_key = key_info
            return fn(*args, **kwargs)

        return wrapper
    return decorator
