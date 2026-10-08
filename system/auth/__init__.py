# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 22.01.2026
# Updated: 29.07.2026
# Website: https://bespredel.name

from system.utils.app_context import get_app_context, refresh_app_context

from .auth import (
    _safe_next_url,
    auth_enabled,
    check_password_hash,
    generate_password_hash,
    get_auth,
    get_authenticated_username,
    login_required,
    login_user,
    logout_user,
    setup_auth,
    verify_credentials,
)

__all__ = [
    'get_app_context',
    'refresh_app_context',
    'auth_enabled',
    'get_auth',
    'setup_auth',
    'login_required',
    'login_user',
    'logout_user',
    'verify_credentials',
    'generate_password_hash',
    'check_password_hash',
    'get_authenticated_username',
    '_safe_next_url',
]
