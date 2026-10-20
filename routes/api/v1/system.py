# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

import sys
import time

from flask import jsonify

from routes.api import api_v1_bp
from system.auth.api_auth import api_key_required
from system.utils.app_context import get_app_context
from system.utils.utils import get_system_info

_SERVER_START_TIME = time.time()


@api_v1_bp.route('/system/health', methods=['GET'])
@api_key_required(role='read')
def system_health():
    """
    Check system health, database connection, and active counter threads.
    """
    context = get_app_context()
    db_manager = context['db_manager']
    object_counters = context.get('object_counters', {})
    locations = context.get('locations', [])

    db_ok = False
    try:
        session = db_manager.create_session()
        session.execute(db_manager._text("SELECT 1"))
        session.close()
        db_ok = True
    except Exception:
        db_ok = False

    uptime = int(time.time() - _SERVER_START_TIME)

    return jsonify({
        'success': True,
        'data': {
            'status': 'healthy' if db_ok else 'degraded',
            'database': 'connected' if db_ok else 'disconnected',
            'uptime_seconds': uptime,
            'active_counters_count': len(object_counters),
            'total_counters_count': len(locations),
        }
    })


@api_v1_bp.route('/system/info', methods=['GET'])
@api_key_required(role='read')
def system_info():
    """
    Get detailed hardware, CUDA, OS, and PyTorch runtime information.
    """
    info = get_system_info()
    return jsonify({
        'success': True,
        'data': info,
    })
