# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from flask import Blueprint

settings_bp = Blueprint('settings', __name__)

from . import api_keys, cameras, logs, models, onboarding, pages, runtimes, server, telemetry

__all__ = ['settings_bp']
