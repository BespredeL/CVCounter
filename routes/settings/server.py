# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from flask import jsonify

from routes.settings import settings_bp
from system.auth import login_required
from system.utils.app_context import get_app_context
from system.utils.i18n import trans as translate


@settings_bp.route('/settings/api/restart', methods=['POST'])
@settings_bp.route('/api/server/restart', methods=['POST'])
@login_required
def api_server_restart():
    """
    Restart the application server process via web control.
    Requires authentication and server.allow_web_control to be enabled.

    Returns:
        Response: JSON status indicating restart was scheduled
    """
    from system.utils.server_control import is_web_control_allowed, schedule_server_restart

    context = get_app_context()
    if not is_web_control_allowed(context):
        return jsonify({
            'ok': False,
            'success': False,
            'error': translate('Server control via web interface is disabled in configuration')
        }), 403

    ok, message = schedule_server_restart(context=context, delay=0.8)
    if not ok:
        return jsonify({
            'ok': False,
            'success': False,
            'error': translate(message)
        }), 400

    return jsonify({
        'ok': True,
        'success': True,
        'message': translate('Server restart initiated. The page will reload shortly.'),
        'delay': 2
    })


@settings_bp.route('/settings/api/shutdown', methods=['POST'])
@settings_bp.route('/api/server/shutdown', methods=['POST'])
@login_required
def api_server_shutdown():
    """
    Shut down the application server process via web control.
    Requires authentication and server.allow_web_control to be enabled.

    Returns:
        Response: JSON status indicating shutdown was scheduled
    """
    from system.utils.server_control import is_web_control_allowed, schedule_server_shutdown

    context = get_app_context()
    if not is_web_control_allowed(context):
        return jsonify({
            'ok': False,
            'success': False,
            'error': translate('Server control via web interface is disabled in configuration')
        }), 403

    ok, message = schedule_server_shutdown(context=context, delay=0.8)
    if not ok:
        return jsonify({
            'ok': False,
            'success': False,
            'error': translate(message)
        }), 400

    return jsonify({
        'ok': True,
        'success': True,
        'message': translate('Server shutdown initiated. The application process will stop.'),
        'delay': 1
    })
