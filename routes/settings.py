# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 03.12.2025
# Updated: 28.07.2026
# Website: https://bespredel.name

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from system.auth import login_required, generate_password_hash
from system.__version__ import APP_VERSION
from system.utils.app_context import get_app_context, refresh_app_context
from system.utils.i18n import trans as translate
from system.utils.telemetry import get_telemetry

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings')
@login_required
def settings() -> str:
    """
    Display the application settings page.
    
    Returns:
        str: Rendered HTML template with settings interface
    
    Note:
        This route requires authentication
    """
    context = get_app_context()
    config = context['config']
    return render_template('settings.html', _config=config.read_config())


@settings_bp.route('/settings_save', methods=['POST'])
@login_required
def settings_save():
    """
    Save application settings.
    
    Returns:
        Response: Redirect to settings page with flash message
    
    Note:
        This route requires authentication
    """
    context = get_app_context()
    config = context['config']

    form_data = request.form.to_dict()

    # Retrieving users from a form and encrypting passwords
    for key, value in form_data.items():
        if key.startswith('users-'):
            if value == '':
                form_data[key] = config.get('users.' + key.replace('users-', ''))
            else:
                form_data[key] = generate_password_hash(value)

    # Saving updated form data to a configuration file
    config.save_from_request(form_data)
    refresh_app_context(context)

    # Re-apply telemetry settings after save
    get_telemetry().configure(config, runtime_context=context)
    get_telemetry().track('settings_saved')

    flash(translate('Settings saved'))
    return redirect(url_for('settings.settings'))


@settings_bp.route('/system_info')
@login_required
def system_info() -> str:
    """
    Display system information page.
    
    Returns:
        str: Rendered HTML template with system information
    
    Note:
        This route requires authentication
    """
    from system.utils.utils import get_system_info

    telemetry = get_telemetry()
    sys_info = get_system_info()
    return render_template(
        'system_info.html',
        sys_info=sys_info,
        app_version=APP_VERSION,
        telemetry_enabled=telemetry.enabled,
        telemetry_last_send=telemetry.get_last_send_status(),
    )


@settings_bp.route('/settings/telemetry/send', methods=['POST'])
@login_required
def telemetry_send():
    """Queue a manual telemetry diagnostic send."""
    ok, message = get_telemetry().request_manual_send()
    if ok:
        flash(translate('Telemetry send queued'))
    else:
        flash(translate(message) if message else translate('Telemetry send failed'), 'error')
    return redirect(url_for('settings.system_info'))


@settings_bp.route('/settings/telemetry/download')
@login_required
def telemetry_download():
    """Download a local diagnostics JSON report."""
    payload = get_telemetry().export_json_bytes()
    return Response(
        payload,
        mimetype='application/json',
        headers={
            'Content-Disposition': 'attachment; filename=cvcounter-diagnostics.json',
        },
    )
