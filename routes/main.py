# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

import os
import re
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from markupsafe import escape
from system.auth import (
    _safe_next_url,
    auth_enabled,
    get_authenticated_username,
    login_user,
    logout_user,
    verify_credentials,
)
from system.utils.app_context import get_app_context
from system.utils.counter_preview import preview_exists
from system.utils.i18n import trans as translate
from system.services.counter_readiness import build_setup_status_map
from system.utils.paths import resolve_project_path
from system.services.onboarding import (
    onboarding_payload,
    should_show_welcome,
)

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index() -> str:
    """
    Render the main index page.

    Returns:
        str: Rendered HTML template with list of available counters and their status
    """
    context = get_app_context()
    locations_dict = context['locations_dict']
    thread_manager = context['thread_manager']
    detections_cfg = (context.get('config') or {}).get('detections') or {}
    has_detections = bool(detections_cfg)
    config_mgr = context.get('config')
    def _weights_file_exists(wpath: str) -> bool:
        if not wpath:
            return False
        resolved = resolve_project_path(wpath) or wpath
        return os.path.isfile(resolved)

    has_valid_weights = any(
        isinstance(cfg, dict) and _weights_file_exists(str(cfg.get('weights_path') or '').strip())
        for cfg in detections_cfg.values()
    )
    setup_statuses = build_setup_status_map(config_mgr) if config_mgr else {}
    onboarding = onboarding_payload(config_mgr)

    return render_template(
        'index.html',
        object_counters=locations_dict,
        running_counters=thread_manager.threads,
        counter_previews={loc: preview_exists(loc) for loc in locations_dict},
        has_detections=has_detections,
        has_valid_weights=has_valid_weights,
        setup_statuses=setup_statuses,
        onboarding=onboarding,
        show_onboarding_welcome=should_show_welcome(config_mgr),
    )


@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Show login form or authenticate against config ``users``.
    
    Returns:
        str: Rendered HTML template for the login page
    """
    if not auth_enabled():
        flash(translate('Authentication is disabled (no users in config).'))
        return redirect(url_for('main.index'))

    next_url = _safe_next_url(request.values.get('next')) or url_for('main.index')
    if get_authenticated_username():
        return redirect(next_url)

    error = ''
    username = ''
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        if verify_credentials(username, password):
            login_user(username)
            flash(translate('Logged in successfully'))
            return redirect(next_url)
        error = translate('Invalid username or password')

    return render_template(
        'login.html',
        error=error,
        username=username,
        next_url=next_url,
    )


@main_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """
    Clear the session and return to the home page.
    
    Returns:
        str: Redirect to the home page
    """
    logout_user()
    flash(translate('You have been logged out.'))
    return redirect(url_for('main.index'))


@main_bp.route('/page/<string:name>')
def page(name: str = None) -> str:
    """
    Display a static page by name.

    Args:
        name (str): The name of the page to display

    Returns:
        str: Rendered HTML template for the requested page

    Raises:
        HTTPException: If the page is not found
    """
    page_name = str(escape(name))
    page_name = re.sub('[^A-Za-z0-9-_]+', '', page_name)

    if page_name == '':
        abort(404, translate('Page not found'))

    app = current_app
    path = os.path.join(app.root_path, 'templates', 'pages', page_name + '.html')
    if os.path.exists(path) is False or os.path.isfile(path) is False:
        abort(404, translate('Page not found'))

    return render_template('pages/' + page_name + '.html')
