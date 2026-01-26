# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 22.01.2026
# Updated: 22.01.2026
# Website: https://bespredel.name

"""
Routes package for CVCounter application.
"""

from .counters import counters_bp
from .reports import reports_bp
from .settings import settings_bp
from .main import main_bp

__all__ = ['counters_bp', 'reports_bp', 'settings_bp', 'main_bp']
