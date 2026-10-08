# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 22.01.2026
# Updated: 29.07.2026
# Website: https://bespredel.name

from .counters import counters_bp
from .reports import reports_bp
from .settings import settings_bp
from .main import main_bp
from .datasets import datasets_bp

__all__ = ['counters_bp', 'reports_bp', 'settings_bp', 'main_bp', 'datasets_bp']
