# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 03.12.2025
# Updated: 22.01.2026
# Website: https://bespredel.name

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask import current_app, g
from werkzeug.security import check_password_hash, generate_password_hash

from system.utils.utils import trans as translate

settings_bp = Blueprint('settings', __name__)


def get_app_context():
    """
    Get application context from g or current_app.
    """
    if not hasattr(g, 'app_context'):
        g.app_context = current_app.config.get('APP_CONTEXT')
    return g.app_context


def get_auth():
    """
    Get auth instance from app context.
    """
    context = get_app_context()
    return context['auth']


def setup_auth():
    """
    Setup authentication for settings blueprint.
    """
    auth = get_auth()
    context = get_app_context()
    users = context['users']

    @auth.verify_password
    def verify_password(username: str, password: str) -> str | None:
        """
        Verify user credentials for authentication.
        """
        if username in users and check_password_hash(users.get(username), password):
            return username
        return None

    return auth


@settings_bp.route('/settings')
def settings() -> str:
    """
    Display the application settings page.
    
    Returns:
        str: Rendered HTML template with settings interface
    
    Note:
        This route requires authentication
    """
    auth = setup_auth()

    @auth.login_required
    def _settings():
        context = get_app_context()
        config = context['config']
        return render_template('settings.html', _config=config.read_config())

    return _settings()


@settings_bp.route('/settings_save', methods=['POST'])
def settings_save():
    """
    Save application settings.
    
    Returns:
        Response: Redirect to settings page with flash message
    
    Note:
        This route requires authentication
    """
    auth = setup_auth()

    @auth.login_required
    def _settings_save():
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

        flash(translate('Settings saved'))
        return redirect(url_for('settings.settings'))

    return _settings_save()


@settings_bp.route('/system_info')
def system_info() -> str:
    """
    Display system information page.
    
    Returns:
        str: Rendered HTML template with system information
    
    Note:
        This route requires authentication
    """
    auth = setup_auth()

    @auth.login_required
    def _system_info():
        from system.utils.utils import get_system_info

        sys_info = get_system_info()
        return render_template('system_info.html', sys_info=sys_info)

    return _system_info()
