# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 22.01.2026
# Updated: 22.01.2026
# Website: https://bespredel.name

"""
Authentication module for CVCounter application.
"""

from .auth import (
    get_auth,
    setup_auth,
    login_required,
    generate_password_hash,
    check_password_hash)

__all__ = [
    'get_auth',
    'setup_auth',
    'login_required',
    'generate_password_hash',
    'check_password_hash'
]
