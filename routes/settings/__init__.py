# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from flask import Blueprint

settings_bp = Blueprint('settings', __name__)

from . import api_keys, cameras, logs, models, pages, runtimes, server, telemetry  # noqa: E402, F401

__all__ = ['settings_bp']
