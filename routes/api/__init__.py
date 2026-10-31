# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Re-exports the /api/v1 blueprint, with the view modules imported so their routes attach."""

from __future__ import annotations

from routes.api.v1 import counters as _counters_routes
from routes.api.v1 import reports as _reports_routes
from routes.api.v1 import system as _system_routes
from routes.api.v1.blueprint import api_v1_bp

__all__ = ['api_v1_bp']
