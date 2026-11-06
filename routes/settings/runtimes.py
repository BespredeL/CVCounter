# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from flask import jsonify, request

from routes.settings import settings_bp
from system.auth import admin_required, login_required
from system.utils.i18n import trans as translate


def _apply_reason(result: dict) -> dict:
    """Replace a machine-readable reason with the user's language at the HTTP boundary."""
    if not result.get('ok') and result.get('reason'):
        params = result.get('reason_params') or {}
        result['error'] = translate(result['reason'], **params)
    return result


@settings_bp.route('/settings/api/runtimes/status', methods=['GET'])
@login_required
def api_runtimes_status():
    """
    Get current AI runtimes, installed packages, and GPU accelerator status.

    Returns:
        Response: JSON payload with runtime statuses
    """
    from system.utils.runtimes import get_runtime_status, runtime_manager

    status = get_runtime_status()
    install_job = runtime_manager.get_install_status()
    return jsonify({
        'ok': True,
        'runtimes': status,
        'install_job': install_job,
    })


@settings_bp.route('/settings/api/runtimes/install', methods=['POST'])
@admin_required
def api_runtimes_install():
    """
    Launch background installation of an AI runtime package bundle.

    Returns:
        Response: JSON payload with job initiation status

    Note:
        Installing packages rewrites the environment, so this requires admin privileges.
    """
    from system.utils.runtimes import runtime_manager

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    bundle = (data.get('bundle') or '').strip()

    if not bundle:
        return jsonify({
            'ok': False,
            'error': translate('Bundle name is required')
        }), 400

    result = _apply_reason(runtime_manager.start_install(bundle))
    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code


@settings_bp.route('/settings/api/runtimes/uninstall', methods=['POST'])
@admin_required
def api_runtimes_uninstall():
    """
    Launch background removal of an installed AI runtime package bundle.

    Packages still required by the application or by another installed bundle are kept.
    """
    from system.utils.runtimes import runtime_manager

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    bundle = (data.get('bundle') or '').strip()

    if not bundle:
        return jsonify({
            'ok': False,
            'error': translate('Bundle name is required')
        }), 400

    result = _apply_reason(runtime_manager.start_uninstall(bundle))
    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code


@settings_bp.route('/settings/api/runtimes/install/status', methods=['GET'])
@login_required
def api_runtimes_install_status():
    """
    Get current status and live console logs of the runtime package installer.

    Returns:
        Response: JSON payload with installer status and logs
    """
    from system.utils.runtimes import runtime_manager

    return jsonify({
        'ok': True,
        'job': runtime_manager.get_install_status()
    })


@settings_bp.route('/settings/api/runtimes/install/cancel', methods=['POST'])
@admin_required
def api_runtimes_install_cancel():
    """
    Abort the running package bundle installation or removal.

    Returns:
        Response: JSON payload with cancellation status
    """
    from system.utils.runtimes import runtime_manager

    result = runtime_manager.cancel_install()
    status_code = 200 if result.get('ok') else 409
    return jsonify(result), status_code
