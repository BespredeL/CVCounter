# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from flask import flash, redirect, render_template, request, url_for

from routes.settings import settings_bp
from system.auth import generate_password_hash, login_required
from system.__version__ import APP_VERSION
from system.utils.app_context import get_app_context, refresh_app_context
from system.utils.i18n import trans as translate
from system.utils.telemetry import get_telemetry


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
    return render_template(
        'settings.html',
        _config=config.read_config(),
        allow_web_control=config.get('server.allow_web_control', True)
    )


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
    active_tab = form_data.pop('_active_tab', None)

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
    if active_tab:
        return redirect(url_for('settings.settings', _anchor=f'pills-{active_tab}'))
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
    telemetry_status = telemetry.get_queue_status()
    context = get_app_context()
    config = context.get('config') if context else None
    allow_web_control = config.get('server.allow_web_control', True) if config else True
    return render_template(
        'system_info.html',
        sys_info=sys_info,
        app_version=APP_VERSION,
        telemetry_enabled=telemetry.enabled,
        telemetry_last_send=telemetry_status.get('last_send'),
        telemetry_status=telemetry_status,
        allow_web_control=allow_web_control,
    )
